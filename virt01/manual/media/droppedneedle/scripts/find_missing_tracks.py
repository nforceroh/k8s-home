#!/usr/bin/env python3
"""Report tracks expected on linked releases but missing from the local library."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any

from droppedneedle import AlbumsApi, ApiError, DroppedNeedleAuth, DroppedNeedleClient, LibraryApi


DEFAULT_DROPPEDNEEDLE_URL = "https://droppedneedle.k3s.nf.lab"
DEFAULT_TIMEOUT = 30
PAGE_SIZE = 100


@dataclass(frozen=True)
class Album:
    id: str
    title: str
    artist_name: str
    release_id: str | None
    release_group_id: str | None
    track_count: int


@dataclass(frozen=True)
class LocalTrack:
    recording_id: str | None
    disc_number: int
    track_number: int
    title: str
    file_size_bytes: int
    format: str


@dataclass(frozen=True)
class ExpectedTrack:
    position: int
    disc_number: int
    title: str
    recording_id: str | None
    release_track_id: str | None


def _as_int(value: Any, field: str, raw: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(f"Unexpected {field} in response: {raw!r}")
    return value


def get_library_albums(api: LibraryApi) -> list[Album]:
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
                    release_id=raw.get("musicbrainz_release_id"),
                    release_group_id=raw.get("musicbrainz_release_group_id"),
                    track_count=_as_int(raw.get("track_count", 0), "track_count", raw),
                )
            )
        total = response.get("total")
        if not response["items"] or not isinstance(total, int) or len(albums) >= total:
            return albums
        page += 1


def get_local_tracks(api: LibraryApi) -> dict[str, list[LocalTrack]]:
    tracks_by_album: dict[str, list[LocalTrack]] = {}
    offset = 0
    while True:
        response = api.tracks(limit=PAGE_SIZE, offset=offset)
        if not isinstance(response, dict) or not isinstance(response.get("items"), list):
            raise ApiError(f"Unexpected library track response shape: {response!r}")
        for raw in response["items"]:
            if not isinstance(raw, dict) or not raw.get("album_id"):
                raise ApiError(f"Unexpected library track item: {raw!r}")
            file_size = _as_int(raw.get("file_size_bytes"), "file_size_bytes", raw)
            tracks_by_album.setdefault(str(raw["album_id"]), []).append(
                LocalTrack(
                    recording_id=raw.get("musicbrainz_recording_id"),
                    disc_number=_as_int(raw.get("disc_number", 1), "disc_number", raw),
                    track_number=_as_int(raw.get("track_number", 0), "track_number", raw),
                    title=str(raw.get("title") or "Unknown track"),
                    file_size_bytes=file_size,
                    format=str(raw.get("format") or ""),
                )
            )
        if not response["items"] or len(response["items"]) < PAGE_SIZE:
            return tracks_by_album
        offset += PAGE_SIZE


def get_expected_tracks(api: AlbumsApi, release_id: str) -> list[ExpectedTrack] | None:
    try:
        response = api.get(release_id)
    except ApiError as error:
        if error.status_code == 404:
            return None
        raise
    if not isinstance(response, dict) or not isinstance(response.get("tracks"), list):
        raise ApiError(f"Unexpected release response shape for {release_id}: {response!r}")
    tracks: list[ExpectedTrack] = []
    for raw in response["tracks"]:
        if not isinstance(raw, dict):
            raise ApiError(f"Unexpected release track: {raw!r}")
        tracks.append(
            ExpectedTrack(
                position=_as_int(raw.get("position"), "position", raw),
                disc_number=_as_int(raw.get("disc_number", 1), "disc_number", raw),
                title=str(raw.get("title") or "Unknown track"),
                recording_id=raw.get("recording_id"),
                release_track_id=raw.get("release_track_id"),
            )
        )
    return tracks


def find_missing(expected: list[ExpectedTrack], local: list[LocalTrack]) -> list[ExpectedTrack]:
    present = [track for track in local if track.file_size_bytes > 0]
    recording_ids = {track.recording_id for track in present if track.recording_id}
    positions = {(track.disc_number, track.track_number) for track in present}
    missing: list[ExpectedTrack] = []
    for track in expected:
        if track.recording_id:
            found = track.recording_id in recording_ids
        else:
            found = (track.disc_number, track.position) in positions
        if not found:
            missing.append(track)
    return missing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artist", help="Restrict to albums whose artist contains this text (case-insensitive).")
    parser.add_argument("--title", help="Restrict to albums whose title contains this text (case-insensitive).")
    parser.add_argument("--album-id", action="append", default=[], help="Internal library ID or MusicBrainz ID; repeatable.")
    parser.add_argument("--limit", type=int, help="Inspect at most this many matching albums.")
    parser.add_argument("--details", action="store_true", help="List each missing track instead of only album summaries.")
    parser.add_argument("--droppedneedle-url", default=os.getenv("DROPPEDNEEDLE_URL", DEFAULT_DROPPEDNEEDLE_URL))
    parser.add_argument("--droppedneedle-username", default=os.getenv("DROPPEDNEEDLE_USERNAME"))
    parser.add_argument("--droppedneedle-password", default=os.getenv("DROPPEDNEEDLE_PASSWORD"))
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        print("--limit must be greater than zero", file=sys.stderr)
        return 2
    if not (args.droppedneedle_username and args.droppedneedle_password):
        print("DROPPEDNEEDLE_USERNAME/DROPPEDNEEDLE_PASSWORD (or credential options) are required", file=sys.stderr)
        return 2

    try:
        client = DroppedNeedleClient(args.droppedneedle_url, timeout=args.timeout)
        token = DroppedNeedleAuth(client).login(args.droppedneedle_username, args.droppedneedle_password).token
        library_api = LibraryApi(DroppedNeedleClient(args.droppedneedle_url, token=token, timeout=args.timeout))
        albums_api = AlbumsApi(DroppedNeedleClient(args.droppedneedle_url, token=token, timeout=args.timeout))
        albums = get_library_albums(library_api)
        local_tracks = get_local_tracks(library_api)
    except ApiError as error:
        print(f"error loading local library: {error}", file=sys.stderr)
        return 1

    requested_ids = set(args.album_id)
    artist_needle = args.artist.casefold() if args.artist else None
    title_needle = args.title.casefold() if args.title else None
    candidates = [
        album for album in albums
        if (not requested_ids or album.id in requested_ids or album.release_id in requested_ids or album.release_group_id in requested_ids)
        and (not artist_needle or artist_needle in album.artist_name.casefold())
        and (not title_needle or title_needle in album.title.casefold())
    ]
    if args.limit is not None:
        candidates = candidates[: args.limit]

    reports = 0
    try:
        for album in candidates:
            if not album.release_id:
                print(f"- [{album.id}] {album.artist_name} - {album.title}: no linked MusicBrainz release; skipped")
                continue
            expected = get_expected_tracks(albums_api, album.release_id)
            if expected is None:
                print(f"- [{album.id}] {album.artist_name} - {album.title}: linked release not found; skipped")
                continue
            missing = find_missing(expected, local_tracks.get(album.id, []))
            if not missing:
                continue
            reports += 1
            present_count = len(expected) - len(missing)
            completion = (present_count / len(expected) * 100) if expected else 0
            if args.details:
                print(f"[{album.id}] {album.artist_name} - {album.title}")
                print(f"  release={album.release_id} expected={len(expected)} present={present_count} missing={len(missing)}")
                for track in missing:
                    identity = f", recording={track.recording_id}" if track.recording_id else ""
                    print(f"  - disc {track.disc_number}, track {track.position}: {track.title}{identity}")
            else:
                print(
                    f"[{album.id}] {album.artist_name} - {album.title}: "
                    f"{present_count}/{len(expected)} tracks ({completion:.0f}% complete), "
                    f"{len(missing)} missing"
                )
    except ApiError as error:
        print(f"error inspecting linked release: {error}", file=sys.stderr)
        return 1

    print(f"Report complete: {reports} album(s) with missing tracks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())