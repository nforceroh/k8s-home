#!/usr/bin/env python3
"""Cancel DroppedNeedle downloads and optionally discard held files.

The command is read-only by default. Pass ``--sync`` to cancel selected
downloads, stop scheduled retries, and/or discard held review files.

When no scope is supplied, all three scopes are previewed: active downloads,
scheduled retries, and held files. Completed and cancelled history is never
cleared by this command.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

from droppedneedle import ApiError, DownloadsApi, DroppedNeedleAuth, DroppedNeedleClient


DEFAULT_DROPPEDNEEDLE_URL = "https://droppedneedle.k3s.nf.lab"
DEFAULT_TIMEOUT = 30
ACTION_DELAY_SECONDS = 0.3
TERMINAL_STATUSES = {"completed", "cancelled"}


@dataclass(frozen=True)
class DownloadTask:
    id: str
    artist_name: str
    album_title: str
    track_title: str | None
    status: str

    @classmethod
    def from_response(cls, raw: dict[str, Any]) -> "DownloadTask":
        return cls(
            id=str(raw["id"]),
            artist_name=raw.get("artist_name", "Unknown artist"),
            album_title=raw.get("album_title", "Unknown album"),
            track_title=raw.get("track_title"),
            status=str(raw.get("status", "unknown")),
        )

    def describe(self) -> str:
        title = self.track_title or self.album_title
        return f"[{self.id}] {self.artist_name} - {title} ({self.status})"


@dataclass(frozen=True)
class HeldItem:
    id: int
    artist_name: str | None
    album_title: str | None
    track_title: str | None

    @classmethod
    def from_response(cls, raw: dict[str, Any]) -> "HeldItem":
        return cls(
            id=int(raw["id"]),
            artist_name=raw.get("artist_name"),
            album_title=raw.get("album_title"),
            track_title=raw.get("track_title"),
        )

    def describe(self) -> str:
        title = self.track_title or self.album_title or "Unknown item"
        return f"[{self.id}] {self.artist_name or 'Unknown artist'} - {title}"


def get_download_tasks(base_url: str, token: str, timeout: int) -> list[DownloadTask]:
    api = DownloadsApi(DroppedNeedleClient(base_url, token=token, timeout=timeout))
    page = 1
    tasks: list[DownloadTask] = []
    while True:
        response = api.list(page=page, page_size=100)
        if not isinstance(response, dict) or not isinstance(response.get("items"), list):
            raise ApiError(f"Unexpected downloads response shape: {response!r}")
        raw_items = response["items"]
        tasks.extend(DownloadTask.from_response(item) for item in raw_items)
        if len(raw_items) < 100:
            return tasks
        page += 1


def get_held_items(base_url: str, token: str, timeout: int) -> list[HeldItem]:
    response = DownloadsApi(DroppedNeedleClient(base_url, token=token, timeout=timeout)).held()
    if not isinstance(response, dict) or not isinstance(response.get("items"), list):
        raise ApiError(f"Unexpected held-items response shape: {response!r}")
    return [HeldItem.from_response(item) for item in response["items"]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droppedneedle-url", default=os.getenv("DROPPEDNEEDLE_URL", DEFAULT_DROPPEDNEEDLE_URL))
    parser.add_argument("--droppedneedle-username", default=os.getenv("DROPPEDNEEDLE_USERNAME"))
    parser.add_argument("--droppedneedle-password", default=os.getenv("DROPPEDNEEDLE_PASSWORD"))
    parser.add_argument("--active", action="store_true", help="Cancel non-terminal download tasks.")
    parser.add_argument("--retries", action="store_true", help="Stop scheduled auto-retries.")
    parser.add_argument("--held", action="store_true", help="Discard all held review files.")
    parser.add_argument("--sync", action="store_true", help="Apply the selected destructive actions.")
    parser.add_argument("--limit", type=int, default=None, help="Limit active and held items for a controlled test.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not (args.droppedneedle_username and args.droppedneedle_password):
        print(
            "DROPPEDNEEDLE_USERNAME/DROPPEDNEEDLE_PASSWORD "
            "(or --droppedneedle-username/--droppedneedle-password) are required",
            file=sys.stderr,
        )
        return 2

    scopes = {"active": args.active, "retries": args.retries, "held": args.held}
    if not any(scopes.values()):
        scopes = {scope: True for scope in scopes}

    try:
        client = DroppedNeedleClient(args.droppedneedle_url, timeout=args.timeout)
        token = DroppedNeedleAuth(client).login(args.droppedneedle_username, args.droppedneedle_password).token
    except ApiError as error:
        print(f"login failed: {error}", file=sys.stderr)
        return 1

    api = DownloadsApi(DroppedNeedleClient(args.droppedneedle_url, token=token, timeout=args.timeout))
    tasks: list[DownloadTask] = []
    held_items: list[HeldItem] = []
    try:
        if scopes["active"]:
            tasks = [
                task
                for task in get_download_tasks(args.droppedneedle_url, token, args.timeout)
                if task.status.casefold() not in TERMINAL_STATUSES
            ]
        if scopes["held"]:
            held_items = get_held_items(args.droppedneedle_url, token, args.timeout)
    except ApiError as error:
        print(f"error discovering downloads: {error}", file=sys.stderr)
        return 1

    if args.limit is not None:
        tasks = tasks[: args.limit]
        held_items = held_items[: args.limit]

    if scopes["active"]:
        print(f"Active downloads: {len(tasks)}")
        for task in tasks:
            print(f"- cancel {task.describe()}")
    if scopes["retries"]:
        print("Scheduled retries: stop all retries for the authenticated user")
    if scopes["held"]:
        print(f"Held files: {len(held_items)}")
        for item in held_items:
            print(f"- discard {item.describe()}")

    if not args.sync:
        print("Dry run: nothing changed. Re-run with --sync to apply these actions.")
        return 0

    failures = 0
    cancelled = 0
    discarded = 0
    if scopes["active"]:
        for task in tasks:
            try:
                api.cancel(task.id)
                print(f"cancelled: {task.describe()}")
                cancelled += 1
            except ApiError as error:
                failures += 1
                print(f"failed to cancel {task.describe()}: {error}", file=sys.stderr)
            time.sleep(ACTION_DELAY_SECONDS)

    if scopes["retries"]:
        try:
            response = api.stop_all_retries()
            stopped = response.get("stopped", "?") if isinstance(response, dict) else response
            print(f"stopped scheduled retries: {stopped}")
        except ApiError as error:
            failures += 1
            print(f"failed to stop scheduled retries: {error}", file=sys.stderr)

    if scopes["held"]:
        for item in held_items:
            try:
                api.discard_held(item.id)
                print(f"discarded: {item.describe()}")
                discarded += 1
            except ApiError as error:
                failures += 1
                print(f"failed to discard {item.describe()}: {error}", file=sys.stderr)
            time.sleep(ACTION_DELAY_SECONDS)

    print(f"Done: {cancelled} downloads cancelled, {discarded} held files discarded, {failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())