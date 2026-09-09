#!/usr/bin/env python3
"""Discard DroppedNeedle "held" downloads whose file tags don't match the expected track.

DroppedNeedle holds a downloaded track for review when the audio matched the
expected track by duration, but its AcoustID recording-identity check
disagreed -- usually because the file's own tags say it's a *different*
song/artist than what was requested (shown in the UI as "COULDN'T VERIFY").
This script finds held items where the evidence (the file's own tags) doesn't
match the expected track/artist, and discards them.

Read-only by default. Pass --sync to actually discard matching items.

Credentials are read from environment variables unless supplied as CLI
options:
  DROPPEDNEEDLE_URL, DROPPEDNEEDLE_USERNAME, DROPPEDNEEDLE_PASSWORD
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass

from droppedneedle import ApiError, DownloadsApi, DroppedNeedleAuth, DroppedNeedleClient


DEFAULT_DROPPEDNEEDLE_URL = "https://droppedneedle.k3s.nf.lab"
DEFAULT_TIMEOUT = 30
ACTION_DELAY_SECONDS = 0.3


@dataclass(frozen=True)
class HeldItem:
    id: int
    artist_name: str | None
    track_title: str | None
    album_title: str | None
    evidence_artist: str | None
    evidence_title: str | None
    reason: str
    reason_detail: str | None
    source_task_id: str | None

    @property
    def is_tag_mismatch(self) -> bool:
        """True if the file's own tags (evidence) disagree with what was expected."""

        def norm(value: str | None) -> str:
            return (value or "").strip().casefold()

        title_mismatch = bool(self.evidence_title) and norm(self.evidence_title) != norm(self.track_title)
        artist_mismatch = bool(self.evidence_artist) and norm(self.evidence_artist) != norm(self.artist_name)
        return title_mismatch or artist_mismatch

    def describe_mismatch(self) -> str:
        parts = []
        if self.evidence_title and self.evidence_title.strip().casefold() != (self.track_title or "").strip().casefold():
            parts.append(f"title: expected '{self.track_title}', tags say '{self.evidence_title}'")
        if self.evidence_artist and self.evidence_artist.strip().casefold() != (self.artist_name or "").strip().casefold():
            parts.append(f"artist: expected '{self.artist_name}', tags say '{self.evidence_artist}'")
        return "; ".join(parts) if parts else "(no evidence fields to compare)"


def get_held_items(base_url: str, token: str, timeout: int) -> list[HeldItem]:
    response = DownloadsApi(DroppedNeedleClient(base_url, token=token, timeout=timeout)).held()
    if not isinstance(response, dict) or "items" not in response:
        raise ApiError(f"Unexpected held-items response shape: {response!r}")

    items: list[HeldItem] = []
    for raw in response["items"]:
        items.append(
            HeldItem(
                id=raw["id"],
                artist_name=raw.get("artist_name"),
                track_title=raw.get("track_title"),
                album_title=raw.get("album_title"),
                evidence_artist=raw.get("evidence_artist"),
                evidence_title=raw.get("evidence_title"),
                reason=raw.get("reason", ""),
                reason_detail=raw.get("reason_detail"),
                source_task_id=raw.get("source_task_id"),
            )
        )
    return items


def discard_held(base_url: str, token: str, held_id: int, timeout: int) -> Any:
    return DownloadsApi(DroppedNeedleClient(base_url, token=token, timeout=timeout)).discard_held(held_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droppedneedle-url", default=os.getenv("DROPPEDNEEDLE_URL", DEFAULT_DROPPEDNEEDLE_URL))
    parser.add_argument("--droppedneedle-username", default=os.getenv("DROPPEDNEEDLE_USERNAME"))
    parser.add_argument("--droppedneedle-password", default=os.getenv("DROPPEDNEEDLE_PASSWORD"))
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Actually discard matching held items. Without this flag the script only previews what it would discard.",
    )
    parser.add_argument(
        "--all-held",
        action="store_true",
        help="Discard ALL held items, not just ones where the tags mismatch (use with care).",
    )
    parser.add_argument("--artist", default=None, help="Restrict to held items whose expected artist_name contains this (case-insensitive substring).")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of items processed, for testing on a small batch first.")
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

    try:
        client = DroppedNeedleClient(args.droppedneedle_url, timeout=args.timeout)
        token = DroppedNeedleAuth(client).login(args.droppedneedle_username, args.droppedneedle_password).token
    except ApiError as error:
        print(f"login failed: {error}", file=sys.stderr)
        return 1

    try:
        items = get_held_items(args.droppedneedle_url, token, args.timeout)
    except ApiError as error:
        print(f"error fetching held items: {error}", file=sys.stderr)
        return 1

    if args.artist:
        needle = args.artist.casefold()
        items = [item for item in items if needle in (item.artist_name or "").casefold()]

    candidates = items if args.all_held else [item for item in items if item.is_tag_mismatch]

    if args.limit is not None:
        candidates = candidates[: args.limit]

    print(f"Found {len(items)} held items total; {len(candidates)} candidates for discard "
          f"({'all held items' if args.all_held else 'tag-mismatch only'})")

    for item in candidates:
        detail = item.describe_mismatch() if not args.all_held else (item.reason_detail or item.reason)
        print(f"- [{item.id}] {item.artist_name} - {item.track_title} ({item.album_title}): {detail}")

    if not args.sync:
        print("Dry run: nothing discarded. Re-run with --sync to actually discard these.")
        return 0

    discarded = 0
    failures = 0
    for item in candidates:
        try:
            discard_held(args.droppedneedle_url, token, item.id, args.timeout)
            print(f"discarded: [{item.id}] {item.artist_name} - {item.track_title}")
            discarded += 1
        except ApiError as error:
            failures += 1
            print(f"failed to discard [{item.id}] {item.artist_name} - {item.track_title}: {error}", file=sys.stderr)
        time.sleep(ACTION_DELAY_SECONDS)

    print(f"Done: {discarded} discarded, {failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())