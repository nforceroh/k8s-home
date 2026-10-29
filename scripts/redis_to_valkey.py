#!/usr/bin/env python3
"""Copy Redis keys to Valkey using native commands rather than RDB serialization."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

from redis import Redis
from redis.exceptions import RedisError, ResponseError


BATCH_SIZE = 128
ITEMS_PER_COMMAND = 500
SUPPORTED_TYPES = {"string", "hash", "list", "set", "zset"}


class MigrationError(Exception):
    """Raised when a safe logical migration cannot proceed."""


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace")
    return str(value)


def _batches(items: Iterable[Any], size: int) -> Iterator[list[Any]]:
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _active_databases(client: Redis) -> set[int]:
    databases: set[int] = set()
    for name in client.info(section="keyspace"):
        match = re.fullmatch(r"db(\d+)", _text(name))
        if match:
            databases.add(int(match.group(1)))
    return databases


def _hash_field_expirations(
    client: Redis, key: bytes, fields: Sequence[bytes]
) -> dict[bytes, int]:
    expirations: dict[bytes, int] = {}
    for field_batch in _batches(fields, ITEMS_PER_COMMAND):
        result = client.execute_command(
            "HPEXPIRETIME",
            key,
            "FIELDS",
            len(field_batch),
            *field_batch,
        )
        for field, expires_at in zip(field_batch, result, strict=True):
            timestamp = int(expires_at)
            if timestamp > 0:
                expirations[field] = timestamp
    return expirations


def _inspect_hash_expirations(client: Redis, key: bytes, batch_size: int) -> int:
    expiring_fields = 0
    fields = (
        field for field, _ in client.hscan_iter(key, count=batch_size)
    )
    for field_batch in _batches(fields, ITEMS_PER_COMMAND):
        expirations = _hash_field_expirations(client, key, field_batch)
        expiring_fields += len(expirations)
    return expiring_fields


def _inspect_database(client: Redis, batch_size: int) -> tuple[Counter[str], int]:
    counts: Counter[str] = Counter()
    expiring_hash_fields = 0
    for key_batch in _batches(client.scan_iter(count=batch_size), batch_size):
        pipeline = client.pipeline(transaction=False)
        for key in key_batch:
            pipeline.type(key)
        types = pipeline.execute()
        for key, raw_type in zip(key_batch, types, strict=True):
            key_type = _text(raw_type)
            if key_type == "none":
                continue
            counts[key_type] += 1
            if key_type == "hash":
                expiring_hash_fields += _inspect_hash_expirations(
                    client, key, batch_size
                )
    return counts, expiring_hash_fields


def _assert_no_server_level_data(client: Redis) -> None:
    try:
        modules = client.execute_command("MODULE", "LIST")
        functions = client.execute_command("FUNCTION", "LIST")
    except ResponseError as error:
        raise MigrationError(
            "Cannot inspect Redis modules/functions; refusing to copy keys only."
        ) from error
    if modules:
        raise MigrationError(
            "Redis modules are loaded; module data is not supported by this copier."
        )
    if functions:
        raise MigrationError(
            "Redis function libraries are loaded; they are not copied by this tool."
        )


def _assert_hash_expiry_support(client: Redis) -> None:
    try:
        client.execute_command(
            "HPEXPIRETIME",
            b"__migration_probe__",
            "FIELDS",
            1,
            b"__migration_probe__",
        )
    except ResponseError as error:
        raise MigrationError(
            "Both servers must support HPEXPIRETIME/HPEXPIREAT to preserve "
            "hash-field expirations."
        ) from error


def _new_client(url: str, database: int | None = None) -> Redis:
    options: dict[str, Any] = {
        "decode_responses": False,
        "socket_connect_timeout": 5,
        "socket_timeout": 60,
    }
    if database is not None:
        options["db"] = database
    return Redis.from_url(url, **options)


def _server_role(client: Redis) -> str:
    return _text(client.info(section="replication").get("role", ""))


def _require_source_and_target(source: Redis, target: Redis) -> None:
    source_id = source.info(section="server").get("run_id")
    target_id = target.info(section="server").get("run_id")
    if source_id and source_id == target_id:
        raise MigrationError("Source and target resolve to the same Redis server.")
    if _server_role(source) not in {"master", "primary"}:
        raise MigrationError("The source must be a writable Redis primary.")
    if _server_role(target) not in {"master", "primary"}:
        raise MigrationError(
            "Valkey is still a replica. Remove replicaof from GitOps and wait for "
            "Argo CD to sync before running the migration."
        )
    _assert_no_server_level_data(source)
    _assert_hash_expiry_support(source)
    _assert_hash_expiry_support(target)


def _parse_databases(value: str) -> list[int]:
    try:
        databases = [int(item.strip()) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "databases must be comma-separated non-negative integers"
        ) from error
    if not databases or any(database < 0 for database in databases):
        raise argparse.ArgumentTypeError(
            "databases must be comma-separated non-negative integers"
        )
    if len(set(databases)) != len(databases):
        raise argparse.ArgumentTypeError("database numbers must be unique")
    return sorted(databases)


def _inspect_all(
    source_url: str,
    target_url: str,
    databases: Sequence[int],
    batch_size: int,
    flush_target: bool,
) -> tuple[dict[int, Counter[str]], dict[int, int]]:
    counts_by_database: dict[int, Counter[str]] = {}
    expiring_fields_by_database: dict[int, int] = {}
    unsupported: Counter[str] = Counter()

    for database in databases:
        source = _new_client(source_url, database)
        target = _new_client(target_url, database)
        try:
            source.ping()
            target.ping()
            if not flush_target and next(target.scan_iter(count=1), None) is not None:
                raise MigrationError(
                    f"Valkey database {database} is not empty. Refusing to "
                    "overwrite it; use --flush-target only if clearing it is intended."
                )
            counts, expiring_fields = _inspect_database(source, batch_size)
            counts_by_database[database] = counts
            expiring_fields_by_database[database] = expiring_fields
            unsupported.update(
                {
                    key_type: count
                    for key_type, count in counts.items()
                    if key_type not in SUPPORTED_TYPES
                }
            )
        finally:
            source.close()
            target.close()

    if unsupported:
        summary = ", ".join(
            f"{key_type}={count}" for key_type, count in sorted(unsupported.items())
        )
        raise MigrationError(
            f"Unsupported Redis key types found ({summary}); no target data was changed."
        )
    return counts_by_database, expiring_fields_by_database


def _queue_hash(
    pipeline: Any,
    key: bytes,
    values: dict[bytes, bytes],
    expirations: dict[bytes, int],
) -> None:
    items = list(values.items())
    for item_batch in _batches(items, ITEMS_PER_COMMAND):
        pipeline.hset(key, mapping=dict(item_batch))

    fields_by_expiration: dict[int, list[bytes]] = defaultdict(list)
    for field, expires_at in expirations.items():
        fields_by_expiration[expires_at].append(field)
    for expires_at, fields in fields_by_expiration.items():
        for field_batch in _batches(fields, ITEMS_PER_COMMAND):
            pipeline.execute_command(
                "HPEXPIREAT",
                key,
                expires_at,
                "FIELDS",
                len(field_batch),
                *field_batch,
            )


def _queue_value(
    pipeline: Any,
    key: bytes,
    key_type: str,
    value: Any,
    expirations: dict[bytes, int],
) -> None:
    if key_type == "string":
        pipeline.set(key, value)
    elif key_type == "hash":
        _queue_hash(pipeline, key, value, expirations)
    elif key_type == "list":
        for item_batch in _batches(value, ITEMS_PER_COMMAND):
            pipeline.rpush(key, *item_batch)
    elif key_type == "set":
        for item_batch in _batches(value, ITEMS_PER_COMMAND):
            pipeline.sadd(key, *item_batch)
    elif key_type == "zset":
        for item_batch in _batches(value, ITEMS_PER_COMMAND):
            pipeline.zadd(key, mapping=dict(item_batch))


def _copy_database(
    source: Redis, target: Redis, batch_size: int
) -> Counter[str]:
    copied: Counter[str] = Counter()
    for key_batch in _batches(source.scan_iter(count=batch_size), batch_size):
        type_pipeline = source.pipeline(transaction=False)
        for key in key_batch:
            type_pipeline.type(key)
        raw_types = type_pipeline.execute()
        entries = [
            (key, _text(raw_type))
            for key, raw_type in zip(key_batch, raw_types, strict=True)
            if _text(raw_type) != "none"
        ]
        if not entries:
            continue
        if any(key_type not in SUPPORTED_TYPES for _, key_type in entries):
            raise MigrationError(
                "The source changed after preflight and contains an unsupported type."
            )

        read_pipeline = source.pipeline(transaction=False)
        result_indexes: list[tuple[int, int]] = []
        for key, key_type in entries:
            if key_type == "string":
                read_pipeline.get(key)
            elif key_type == "hash":
                read_pipeline.hgetall(key)
            elif key_type == "list":
                read_pipeline.lrange(key, 0, -1)
            elif key_type == "set":
                read_pipeline.smembers(key)
            else:
                read_pipeline.zrange(key, 0, -1, withscores=True)
            value_index = len(result_indexes) * 2
            read_pipeline.pttl(key)
            result_indexes.append((value_index, value_index + 1))

        read_started = time.monotonic()
        results = read_pipeline.execute()
        values_and_ttls = [
            (results[value_index], int(results[ttl_index]))
            for value_index, ttl_index in result_indexes
        ]

        hash_expirations: dict[bytes, dict[bytes, int]] = {}
        expiry_pipeline = source.pipeline(transaction=False)
        expiry_keys: list[tuple[bytes, list[bytes], int]] = []
        for (key, key_type), (value, _) in zip(
            entries, values_and_ttls, strict=True
        ):
            if key_type == "hash" and value:
                fields = list(value)
                for field_batch in _batches(fields, ITEMS_PER_COMMAND):
                    expiry_pipeline.execute_command(
                        "HPEXPIRETIME",
                        key,
                        "FIELDS",
                        len(field_batch),
                        *field_batch,
                    )
                    expiry_keys.append((key, field_batch, len(expiry_keys)))
        if expiry_keys:
            expiry_results = expiry_pipeline.execute()
            for key, fields, result_index in expiry_keys:
                field_expirations = hash_expirations.setdefault(key, {})
                for field, expires_at in zip(
                    fields, expiry_results[result_index], strict=True
                ):
                    timestamp = int(expires_at)
                    if timestamp > 0:
                        field_expirations[field] = timestamp

        elapsed_ms = int((time.monotonic() - read_started) * 1000)
        write_pipeline = target.pipeline(transaction=False)
        scheduled: list[tuple[str, int]] = []
        for (key, key_type), (value, ttl_ms) in zip(
            entries, values_and_ttls, strict=True
        ):
            remaining_ttl = ttl_ms - elapsed_ms if ttl_ms >= 0 else ttl_ms
            if ttl_ms == -2 or (ttl_ms >= 0 and remaining_ttl <= 0):
                continue
            if value is None or value == {} or value == [] or value == set():
                continue
            write_pipeline.delete(key)
            _queue_value(
                write_pipeline,
                key,
                key_type,
                value,
                hash_expirations.get(key, {}),
            )
            if remaining_ttl >= 0:
                write_pipeline.pexpire(key, remaining_ttl)
            scheduled.append((key_type, key))
        if scheduled:
            write_pipeline.execute()
            copied.update(key_type for key_type, _ in scheduled)
    return copied


def _format_counts(counts: Counter[str]) -> str:
    if not counts:
        return "empty"
    return ", ".join(
        f"{key_type}={count}" for key_type, count in sorted(counts.items())
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy Redis keys to Valkey using typed commands. The default is a "
            "read-only dry run."
        )
    )
    parser.add_argument(
        "--databases",
        type=_parse_databases,
        help="comma-separated database numbers (default: active DBs on either server)",
    )
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform the copy; without this flag, only inspect the databases",
    )
    parser.add_argument(
        "--source-writes-paused",
        action="store_true",
        help="confirm applications are no longer writing to Redis",
    )
    parser.add_argument(
        "--flush-target",
        action="store_true",
        help="flush selected Valkey databases before copying (destructive)",
    )
    args = parser.parse_args(argv)

    source_url = os.environ.get("REDIS_SOURCE_URL")
    target_url = os.environ.get("VALKEY_TARGET_URL")
    if not source_url or not target_url:
        parser.error("set REDIS_SOURCE_URL and VALKEY_TARGET_URL")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.flush_target and not args.execute:
        parser.error("--flush-target requires --execute")
    if args.execute and not args.source_writes_paused:
        parser.error("--execute requires --source-writes-paused")

    source = _new_client(source_url)
    target = _new_client(target_url)
    try:
        source.ping()
        target.ping()
        _require_source_and_target(source, target)
        databases = args.databases
        if databases is None:
            databases = sorted(
                _active_databases(source) | _active_databases(target)
            )
        if not databases:
            print("No active databases or keys found.")
            return 0

        counts_by_database, expiring_fields_by_database = _inspect_all(
            source_url,
            target_url,
            databases,
            args.batch_size,
            args.flush_target,
        )
        for database in databases:
            print(
                f"DB {database}: {_format_counts(counts_by_database[database])}; "
                f"expiring hash fields="
                f"{expiring_fields_by_database[database]}"
            )
        if not args.execute:
            print("Dry run only; no data was changed.")
            if args.flush_target:
                print("The selected target databases would be flushed.")
            return 0

        for database in databases:
            source_db = _new_client(source_url, database)
            target_db = _new_client(target_url, database)
            try:
                if args.flush_target:
                    target_db.flushdb()
                copied = _copy_database(source_db, target_db, args.batch_size)
                print(f"DB {database} copied: {_format_counts(copied)}")
            finally:
                source_db.close()
                target_db.close()
        print("Copy finished. Verify the destination before switching applications.")
        return 0
    except (MigrationError, RedisError, OSError, ValueError) as error:
        print(f"Migration stopped: {error}", file=sys.stderr)
        return 1
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    raise SystemExit(main())
