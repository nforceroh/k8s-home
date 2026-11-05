from __future__ import annotations

import io
import unittest
from collections import Counter
from contextlib import redirect_stdout
from typing import Any
from unittest.mock import patch

from redis_to_valkey import (
    MigrationError,
    _assert_no_server_level_data,
    _copy_database,
    _inspect_database,
    _inspect_all,
)


class FakePipeline:
    def __init__(self, client: FakeRedis) -> None:
        self.client = client
        self.commands: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        def queue(*args: Any, **kwargs: Any) -> FakePipeline:
            self.commands.append((name, args, kwargs))
            return self

        return queue

    def execute(self) -> list[Any]:
        results = [
            getattr(self.client, name)(*args, **kwargs)
            for name, args, kwargs in self.commands
        ]
        self.commands.clear()
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[bytes, tuple[str, Any]] = {}
        self.ttls: dict[bytes, int] = {}
        self.field_expirations: dict[bytes, dict[bytes, int]] = {}
        self.modules: list[dict[str, str]] = []
        self.functions: list[dict[str, str]] = []

    def pipeline(self, transaction: bool = False) -> FakePipeline:
        del transaction
        return FakePipeline(self)

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def dbsize(self) -> int:
        return len(self.data)

    def scan_iter(self, count: int = 10) -> Any:
        del count
        yield from self.data

    def type(self, key: bytes) -> bytes:
        return self.data.get(key, ("none", None))[0].encode()

    def pttl(self, key: bytes) -> int:
        return self.ttls.get(key, -2 if key not in self.data else -1)

    def get(self, key: bytes) -> bytes | None:
        return self.data.get(key, ("string", None))[1]

    def hgetall(self, key: bytes) -> dict[bytes, bytes]:
        return self.data.get(key, ("hash", {}))[1]

    def hscan_iter(self, key: bytes, count: int = 10) -> Any:
        del count
        yield from self.hgetall(key).items()

    def lrange(self, key: bytes, start: int, end: int) -> list[bytes]:
        items = self.data.get(key, ("list", []))[1]
        return items[start:] if end == -1 else items[start : end + 1]

    def smembers(self, key: bytes) -> set[bytes]:
        return self.data.get(key, ("set", set()))[1]

    def zrange(
        self, key: bytes, start: int, end: int, withscores: bool = False
    ) -> list[Any]:
        del start, end, withscores
        return self.data.get(key, ("zset", []))[1]

    def execute_command(self, command: str, *args: Any) -> Any:
        if command == "MODULE" and args == ("LIST",):
            return self.modules
        if command == "FUNCTION" and args == ("LIST",):
            return self.functions
        if command == "HPEXPIRETIME":
            key, _, count, *fields = args
            return [
                self.field_expirations.get(key, {}).get(field, -1)
                for field in fields[:count]
            ]
        if command == "HPEXPIREAT":
            key, expires_at, _, count, *fields = args
            expirations = self.field_expirations.setdefault(key, {})
            for field in fields[:count]:
                expirations[field] = expires_at
            return [1] * count
        raise AssertionError(f"Unexpected command: {command}")

    def delete(self, key: bytes) -> int:
        self.data.pop(key, None)
        self.ttls.pop(key, None)
        return 1

    def set(self, key: bytes, value: bytes) -> bool:
        self.data[key] = ("string", value)
        return True

    def hset(self, key: bytes, mapping: dict[bytes, bytes]) -> int:
        fields = self.data.setdefault(key, ("hash", {}))[1]
        fields.update(mapping)
        return len(mapping)

    def rpush(self, key: bytes, *values: bytes) -> int:
        items = self.data.setdefault(key, ("list", []))[1]
        items.extend(values)
        return len(items)

    def sadd(self, key: bytes, *values: bytes) -> int:
        members = self.data.setdefault(key, ("set", set()))[1]
        before = len(members)
        members.update(values)
        return len(members) - before

    def zadd(self, key: bytes, mapping: dict[bytes, float]) -> int:
        members = self.data.setdefault(key, ("zset", []))[1]
        members.extend(mapping.items())
        return len(mapping)

    def pexpire(self, key: bytes, milliseconds: int) -> bool:
        self.ttls[key] = milliseconds
        return True


class RedisToValkeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = FakeRedis()
        self.target = FakeRedis()
        self.source.data = {
            b"string": ("string", b"value"),
            b"hash": ("hash", {b"plain": b"value", b"expires": b"soon"}),
            b"list": ("list", [b"first", b"second"]),
            b"set": ("set", {b"one", b"two"}),
            b"zset": ("zset", [(b"member", 2.5)]),
        }
        self.source.ttls = {b"string": 60_000, b"hash": 120_000}
        self.source.field_expirations = {
            b"hash": {b"expires": 1_900_000_000_000}
        }

    def test_preflight_counts_types_and_hash_field_expirations(self) -> None:
        counts, expiring_fields = _inspect_database(self.source, batch_size=2)

        self.assertEqual(
            counts,
            Counter(
                {"string": 1, "hash": 1, "list": 1, "set": 1, "zset": 1}
            ),
        )
        self.assertEqual(expiring_fields, 1)

    def test_loaded_modules_do_not_block_server_level_preflight(self) -> None:
        self.source.modules = [{"name": "search"}]

        _assert_no_server_level_data(self.source)

    def test_function_libraries_block_server_level_preflight(self) -> None:
        self.source.functions = [{"library_name": "migration_functions"}]

        with self.assertRaises(MigrationError):
            _assert_no_server_level_data(self.source)

    def test_module_key_types_in_selected_database_are_rejected(self) -> None:
        self.source.data[b"module-key"] = ("ReJSON-RL", b"")

        with patch(
            "redis_to_valkey._new_client",
            side_effect=[self.source, self.target],
        ):
            with self.assertRaisesRegex(
                MigrationError, r"Unsupported Redis key types found \(ReJSON-RL=1\)"
            ):
                _inspect_all(
                    "source",
                    "target",
                    databases=[7],
                    batch_size=2,
                    flush_target=False,
                )

    def test_preflight_reports_progress(self) -> None:
        output = io.StringIO()
        with patch(
            "redis_to_valkey._new_client",
            side_effect=[self.source, self.target],
        ):
            with redirect_stdout(output):
                _inspect_all(
                    "source",
                    "target",
                    databases=[7],
                    batch_size=2,
                    flush_target=False,
                )

        self.assertIn("DB 7 preflight starting", output.getvalue())
        self.assertIn("DB 7 preflight complete", output.getvalue())

    def test_copy_preserves_values_and_expirations(self) -> None:
        progress_reports: list[tuple[int, bool]] = []
        copied = _copy_database(
            self.source,
            self.target,
            batch_size=2,
            progress_callback=lambda scanned, finished: progress_reports.append(
                (scanned, finished)
            ),
        )

        self.assertEqual(
            copied,
            Counter(
                {"string": 1, "hash": 1, "list": 1, "set": 1, "zset": 1}
            ),
        )
        self.assertEqual(
            progress_reports,
            [(2, False), (4, False), (5, False), (5, True)],
        )
        self.assertEqual(self.target.data, self.source.data)
        self.assertGreater(self.target.ttls[b"string"], 0)
        self.assertLessEqual(self.target.ttls[b"string"], 60_000)
        self.assertEqual(
            self.target.field_expirations,
            self.source.field_expirations,
        )


if __name__ == "__main__":
    unittest.main()
