#!/usr/bin/env python3
"""Remove albums from DroppedNeedle's local library.

The script is read-only by default. Pass --sync to remove matching albums.
Selectors may be DroppedNeedle internal library IDs or MusicBrainz release
group/release IDs. Deletion is only possible for albums currently in the
local library.
Credentials are read from environment variables unless supplied as options.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

from droppedneedle import ApiError, DroppedNeedleAuth, DroppedNeedleClient, LibraryApi


DEFAULT_DROPPEDNEEDLE_URL = "https://droppedneedle.k3s.nf.lab"
DEFAULT_TIMEOUT = 30
ACTION_DELAY_SECONDS = 0.3
PAGE_SIZE = 100


@dataclass(frozen=True)
class Album:
    id: str
    title: str
    artist_name: str
    musicbrainz_id: str | None
    release_id: str | None
    track_count: int
    format: str | None


def get_library_albums(base_url: str, token: str, timeout: int) -> list[Album]:
    api = LibraryApi(DroppedNeedleClient(base_url, token=token, timeout=timeout))
    albums: list[Album] = []
    page = 1

    while True:
        response = api.albums(page=page, page_size=PAGE_SIZE)
        if not isinstance(response, dict) or not isinstance(response.get("items"), list):
            raise ApiError(f"Unexpected library album response shape: {response!r}")

        for raw in response["items"]:
            if not isinstance(raw, dict) or not raw.get("id"):
                raise ApiError(f"Unexpected library album item: {raw!r}")
            albums.append(
                Album(
                    id=str(raw["id"]),
                    title=str(raw.get("title") or "Unknown album"),
                    artist_name=str(raw.get("artist_name") or "Unknown artist"),
                    musicbrainz_id=raw.get("musicbrainz_release_group_id"),
                    release_id=raw.get("musicbrainz_release_id"),
                    track_count=int(raw.get("track_count") or 0),
                    format=raw.get("format"),
                )
            )

        total = response.get("total")
        if not response["items"] or not isinstance(total, int) or len(albums) >= total:
            return albums
        page += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--album-id",
        action="append",
        default=[],
        help="Internal library ID or MusicBrainz release/release-group ID; repeat for multiple IDs.",
    )
    parser.add_argument("--artist", help="Restrict to albums whose artist contains this text (case-insensitive).")
    parser.add_argument("--title", help="Restrict to albums whose title contains this text (case-insensitive).")
    parser.add_argument("--limit", type=int, help="Process at most this many matching albums.")
    parser.add_argument(
        "--delete-files",
        action="store_true",
        help="Also delete the album's files. Without this flag, only the library entry is removed.",
    )
    parser.add_argument(
        "--stop-wanted",
        action="store_true",
        help="Stop future wanted-list retries for the removed albums.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Actually remove matching albums. Without this flag the script only previews them.",
    )
    parser.add_argument("--droppedneedle-url", default=os.getenv("DROPPEDNEEDLE_URL", DEFAULT_DROPPEDNEEDLE_URL))
    parser.add_argument("--droppedneedle-username", default=os.getenv("DROPPEDNEEDLE_USERNAME"))
    parser.add_argument("--droppedneedle-password", default=os.getenv("DROPPEDNEEDLE_PASSWORD"))
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.album_id and not args.artist and not args.title:
        print("provide at least one --album-id, --artist, or --title selector", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit < 1:
        print("--limit must be greater than zero", file=sys.stderr)
        return 2
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
        albums = get_library_albums(args.droppedneedle_url, token, args.timeout)
    except ApiError as error:
        print(f"error loading library albums: {error}", file=sys.stderr)
        return 1

    requested_ids = set(args.album_id)
    artist_needle = args.artist.casefold() if args.artist else None
    title_needle = args.title.casefold() if args.title else None
    candidates = [
        album
        for album in albums
        if (
            not requested_ids
            or album.id in requested_ids
            or album.musicbrainz_id in requested_ids
            or album.release_id in requested_ids
        )
        and (not artist_needle or artist_needle in album.artist_name.casefold())
        and (not title_needle or title_needle in album.title.casefold())
    ]
    if args.limit is not None:
        candidates = candidates[: args.limit]

    print(f"Found {len(albums)} library albums; {len(candidates)} candidates for removal")
    for album in candidates:
        mbids = ", ".join(
            value
            for value in (album.musicbrainz_id, album.release_id)
            if value
        )
        mbid = f", MBID {mbids}" if mbids else ""
        print(f"- [{album.id}] {album.artist_name} - {album.title} ({album.track_count} tracks{mbid})")

    if not candidates:
        if requested_ids:
            library_mbids = {
                value
                for album in albums
                for value in (album.musicbrainz_id, album.release_id)
                if value
            }
            not_in_library = sorted(requested_ids - {album.id for album in albums} - library_mbids)
            if not_in_library:
                print(
                    "These selectors do not identify albums currently in the local library: "
                    + ", ".join(not_in_library)
                )
        print("No matching albums found.")
        return 0
    if not args.sync:
        print("Dry run: nothing removed. Re-run with --sync to remove these albums.")
        return 0

    api = LibraryApi(DroppedNeedleClient(args.droppedneedle_url, token=token, timeout=args.timeout))
    removed = 0
    failures = 0
    for album in candidates:
        try:
            response = api.remove_album(
                album.id,
                delete_files=args.delete_files,
                stop_wanted=args.stop_wanted,
            )
            if isinstance(response, dict) and response.get("success") is False:
                raise ApiError(f"API reported unsuccessful removal: {response!r}")
            print(f"removed: [{album.id}] {album.artist_name} - {album.title}")
            removed += 1
        except ApiError as error:
            failures += 1
            print(f"failed to remove [{album.id}] {album.artist_name} - {album.title}: {error}", file=sys.stderr)
        time.sleep(ACTION_DELAY_SECONDS)

    print(f"Done: {removed} removed, {failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
