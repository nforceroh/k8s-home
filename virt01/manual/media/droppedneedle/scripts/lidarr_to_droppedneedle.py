#!/usr/bin/env python3
"""Sync Lidarr artists/albums to DroppedNeedle by MusicBrainz ID.

The script is read-only by default. Pass --sync to actually create
DroppedNeedle requests. Credentials are read from environment variables
unless supplied as CLI options.

DroppedNeedle uses username/password login (POST /api/v1/auth/login) which
returns a bearer token in an AuthResponse. This script logs in once per run
(when --sync is passed) and uses the returned token for subsequent
request calls.

Artist sync: DroppedNeedle appears to require that an artist already has at
least one album requested before an artist-level "sync whole discography"
request will be accepted. So with --sync-artists, the script:
  1. Submits any missing/selected albums for the artist as usual.
  2. If none of that artist's albums were selected/submitted (e.g. the whole
     discography is already downloaded), it submits ONE fallback album
     request for that artist (any album, regardless of file/monitor status)
     purely to satisfy the "at least one album" prerequisite.
  3. Then submits the artist-level request (request_kind="artist").
Artists with zero albums at all in Lidarr are skipped, since there's nothing
to submit to unlock the artist request.

NOTE: The login path/fields (`/api/v1/auth/login`, `username`/`password`),
and the artist-request payload shape (request_kind="artist") are inferred
from the Swagger schema and DroppedNeedle's observed behavior, not from
confirmed docs. If either 422s, check the printed validation detail for the
actual expected field names and adjust `login()` / `request_artist()`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from droppedneedle import AlbumsApi, ApiError as DroppedNeedleApiError, AuthResponse, DroppedNeedleAuth, DroppedNeedleClient, RequestsApi


DEFAULT_LIDARR_URL = "https://lidarr.k3s.nf.lab"
DEFAULT_DROPPEDNEEDLE_URL = "https://droppedneedle.k3s.nf.lab"
DEFAULT_TIMEOUT = 30
LOGIN_PATH = "/api/v1/auth/login"
SUBMIT_DELAY_SECONDS = 0.5


@dataclass(frozen=True)
class Album:
    title: str
    artist_name: str
    album_mbid: str
    artist_mbid: str
    has_file: bool
    monitored: bool


class ApiError(RuntimeError):
    """Raised when an API request cannot be completed successfully."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ValidationApiError(ApiError):
    """Raised when the API returns a 422 with field-level validation detail."""

    def __init__(self, message: str, detail: Any):
        super().__init__(message, status_code=422)
        self.detail = detail


def _format_validation_detail(detail: Any) -> str:
    if not isinstance(detail, dict):
        return str(detail)
    errors = detail.get("detail")
    if not isinstance(errors, list):
        return str(detail)
    lines = []
    for err in errors:
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        msg = err.get("msg", "invalid value")
        lines.append(f"  {loc}: {msg}")
    return "\n".join(lines) if lines else str(detail)


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"

    for attempt in range(retries + 1):
        request = Request(url, data=body, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw)
        except HTTPError as error:
            raw_body = error.read().decode("utf-8", errors="replace")
            if error.code == 422:
                try:
                    parsed_detail = json.loads(raw_body)
                except json.JSONDecodeError:
                    parsed_detail = raw_body
                raise ValidationApiError(
                    f"{method} {url} failed validation (422):\n"
                    f"{_format_validation_detail(parsed_detail)}",
                    parsed_detail,
                ) from error
            if attempt == retries or method != "GET":
                raise ApiError(f"{method} {url} returned HTTP {error.code}: {raw_body}", status_code=error.code) from error
            time.sleep(2**attempt)
        except (URLError, TimeoutError) as error:
            if attempt == retries or method != "GET":
                raise ApiError(f"{method} {url} failed: {error}") from error
            time.sleep(2**attempt)
        except json.JSONDecodeError as error:
            raise ApiError(f"{method} {url} returned invalid JSON") from error

    raise ApiError(f"{method} {url} failed")


def lidarr_get(base_url: str, api_key: str, path: str, *, timeout: int) -> Any:
    query = urlencode({"apikey": api_key})
    return request_json("GET", f"{base_url.rstrip('/')}{path}?{query}", timeout=timeout)


def get_lidarr_data(base_url: str, api_key: str, timeout: int) -> tuple[list[dict[str, Any]], list[Album]]:
    """Fetch all Lidarr artists and albums.

    Returns (artists, albums) where artists is every artist that has a
    MusicBrainz artist ID (deduped by mbid), and albums is every album that
    has a MusicBrainz album ID (deduped by mbid) -- unfiltered by
    monitored/has_file status. Filtering for "what to actually request"
    happens later in main().
    """
    raw_artists = lidarr_get(base_url, api_key, "/api/v1/artist", timeout=timeout)
    raw_albums = lidarr_get(base_url, api_key, "/api/v1/album", timeout=timeout)
    if not isinstance(raw_artists, list) or not isinstance(raw_albums, list):
        raise ApiError("Lidarr returned an unexpected artist or album response")

    total_raw_artists = len(raw_artists)
    artists_without_mbid = [item.get("artistName", "Unknown") for item in raw_artists if not item.get("foreignArtistId")]
    print(
        f"note: Lidarr returned {total_raw_artists} artists total; "
        f"{len(artists_without_mbid)} have no MusicBrainz artist ID and will be skipped",
        file=sys.stderr,
    )
    if artists_without_mbid:
        print(
            f"note: skipped (no MBID): {', '.join(artists_without_mbid[:15])}"
            f"{', ...' if len(artists_without_mbid) > 15 else ''}",
            file=sys.stderr,
        )

    artist_names = {item.get("id"): item.get("artistName", "") for item in raw_artists}
    artist_mbids = {item.get("id"): item.get("foreignArtistId", "") for item in raw_artists}

    artists_by_mbid: dict[str, dict[str, Any]] = {}
    for item in raw_artists:
        mbid = item.get("foreignArtistId")
        if not mbid:
            continue
        artists_by_mbid.setdefault(
            mbid,
            {
                "name": item.get("artistName", "Unknown artist"),
                "mbid": mbid,
                "monitored": bool(item.get("monitored")),
            },
        )
    artists = sorted(artists_by_mbid.values(), key=lambda a: a["name"].casefold())

    albums_by_mbid: dict[str, Album] = {}
    for item in raw_albums:
        album_mbid = item.get("foreignAlbumId")
        if not album_mbid:
            continue
        artist_id = item.get("artistId")
        albums_by_mbid.setdefault(
            album_mbid,
            Album(
                title=item.get("title", "Unknown album"),
                artist_name=artist_names.get(artist_id, "Unknown artist"),
                album_mbid=album_mbid,
                artist_mbid=artist_mbids.get(artist_id, ""),
                has_file=bool(item.get("hasFile")),
                monitored=bool(item.get("monitored")),
            ),
        )
    albums = sorted(albums_by_mbid.values(), key=lambda album: (album.artist_name.casefold(), album.title.casefold()))
    return artists, albums


def group_albums_by_artist(albums: list[Album]) -> dict[str, list[Album]]:
    """Group albums by artist_mbid, preserving first-seen order."""
    groups: dict[str, list[Album]] = {}
    for album in albums:
        groups.setdefault(album.artist_mbid, []).append(album)
    return groups


def get_album_status(base_url: str, token: str, album_mbid: str, timeout: int) -> dict[str, Any] | None:
    """Look up an album by MusicBrainz ID and return its DroppedNeedle status.

    Confirmed endpoint: GET /api/v1/albums/{musicbrainz_id} -- returns album
    metadata plus `in_library` and `requested` booleans. Returns None if the
    album isn't known to DroppedNeedle at all (404), which the caller should
    treat as "not requested yet, safe to submit".
    """
    try:
        response = AlbumsApi(DroppedNeedleClient(base_url, token=token, timeout=timeout)).get(album_mbid)
    except DroppedNeedleApiError as error:
        if error.status_code == 404:
            return None
        raise ApiError(str(error), status_code=error.status_code) from error
    return response if isinstance(response, dict) else None


def login(base_url: str, username: str, password: str, timeout: int) -> str:
    """Log in to DroppedNeedle and return the bearer token."""
    client = DroppedNeedleClient(base_url, timeout=timeout)
    try:
        return DroppedNeedleAuth(client).login(username, password).token
    except DroppedNeedleApiError as error:
        raise ApiError(str(error), status_code=error.status_code) from error


def request_album(base_url: str, token: str, album: Album, timeout: int) -> Any:
    try:
        return RequestsApi(DroppedNeedleClient(base_url, token=token, timeout=timeout)).create(
            album.album_mbid,
            artist_mbid=album.artist_mbid,
            artist_name=album.artist_name,
            album_title=album.title,
        )
    except DroppedNeedleApiError as error:
        raise ApiError(str(error), status_code=error.status_code) from error


def request_artist(base_url: str, token: str, artist_name: str, artist_mbid: str, timeout: int) -> Any:
    """Submit an artist-level sync request.

    NOTE: Mirrors the album request shape with request_kind="artist" -- not
    directly confirmed against DroppedNeedle's docs. Only call this after an
    album request has succeeded at least once for the same artist.
    """
    try:
        return RequestsApi(DroppedNeedleClient(base_url, token=token, timeout=timeout)).create(
            artist_mbid,
            artist_mbid=artist_mbid,
            artist_name=artist_name,
            request_kind="artist",
        )
    except DroppedNeedleApiError as error:
        raise ApiError(str(error), status_code=error.status_code) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lidarr-url", default=os.getenv("LIDARR_URL", DEFAULT_LIDARR_URL))
    parser.add_argument("--lidarr-api-key", default=os.getenv("LIDARR_API_KEY"))
    parser.add_argument("--droppedneedle-url", default=os.getenv("DROPPEDNEEDLE_URL", DEFAULT_DROPPEDNEEDLE_URL))
    parser.add_argument("--droppedneedle-username", default=os.getenv("DROPPEDNEEDLE_USERNAME"))
    parser.add_argument("--droppedneedle-password", default=os.getenv("DROPPEDNEEDLE_PASSWORD"))
    parser.add_argument("--missing-only", action="store_true", help="Only select albums Lidarr doesn't have a file for (default: select all albums regardless of file status)")
    parser.add_argument("--monitored-only", action="store_true", help="Only select albums that are monitored in Lidarr (default: select all albums regardless of monitored status)")
    parser.add_argument(
        "--sync",
        "--submit",
        dest="sync",
        action="store_true",
        help="Actually submit requests to DroppedNeedle. Without this flag the script only previews what it would do.",
    )
    parser.add_argument(
        "--sync-artists",
        action="store_true",
        help=(
            "After submitting an artist's albums, also submit an artist-level sync "
            "request covering ALL Lidarr artists (monitored or not). If an artist had "
            "no album selected/submitted, one fallback album is submitted first to "
            "satisfy DroppedNeedle's apparent requirement of at least one existing album."
        ),
    )
    parser.add_argument(
        "--artist",
        default=None,
        help="Restrict everything to a single artist: case-insensitive substring match on name, or exact MusicBrainz artist ID. Lists that artist's albums.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of artists processed (in sorted-by-name order), for testing on a small batch before running the full library.",
    )
    parser.add_argument("--list-artists", action="store_true", help="Print only artist names (one per line) and exit -- no album details, no login required")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Submit album requests even if DroppedNeedle's library already has that album (default: check first and skip existing albums)",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.lidarr_api_key:
        print("LIDARR_API_KEY or --lidarr-api-key is required", file=sys.stderr)
        return 2
    if args.sync and not (args.droppedneedle_username and args.droppedneedle_password):
        print(
            "DROPPEDNEEDLE_USERNAME/DROPPEDNEEDLE_PASSWORD "
            "(or --droppedneedle-username/--droppedneedle-password) are required with --sync",
            file=sys.stderr,
        )
        return 2

    try:
        artists, albums = get_lidarr_data(args.lidarr_url, args.lidarr_api_key, args.timeout)
    except ApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.artist:
        needle = args.artist.casefold()
        artists = [a for a in artists if needle in a["name"].casefold() or needle == a["mbid"].casefold()]
        if not artists:
            print(f"No Lidarr artist matched '{args.artist}'", file=sys.stderr)
            return 1

    if args.limit is not None:
        artists = artists[: args.limit]

    if args.list_artists:
        for artist in artists:
            print(artist["name"])
        return 0

    if args.artist or args.limit is not None:
        in_scope_mbids = {a["mbid"] for a in artists}
        albums = [album for album in albums if album.artist_mbid in in_scope_mbids]

    all_albums_by_artist = group_albums_by_artist(albums)

    selected = [
        album
        for album in albums
        if (not args.missing_only or not album.has_file)
        and (not args.monitored_only or album.monitored)
    ]
    selected_by_artist = group_albums_by_artist(selected)
    selected_mbids = {album.album_mbid for album in selected}

    scope_note = f" (limited to first {args.limit} artists)" if args.limit is not None else ""
    missing_count = sum(1 for a in albums if not a.has_file)
    monitored_count = sum(1 for a in albums if a.monitored)
    print(
        f"note: of {len(albums)} albums -- {missing_count} are missing (no file), "
        f"{monitored_count} are monitored, {len(selected)} match your current filters "
        f"(missing-only={'yes' if args.missing_only else 'no, all statuses included'}, "
        f"monitored-only={'yes' if args.monitored_only else 'no, all statuses included'}).",
        file=sys.stderr,
    )
    print(f"Found {len(albums)} Lidarr albums across {len(artists)} artists{scope_note}; selected {len(selected)} albums to request")

    if args.artist:
        for artist in artists:
            artist_albums = sorted(all_albums_by_artist.get(artist["mbid"], []), key=lambda a: a.title.casefold())
            print(f"\n{artist['name']} [{artist['mbid']}] (monitored={artist['monitored']}, {len(artist_albums)} albums in Lidarr)")
            for album in artist_albums:
                status = "has file" if album.has_file else "MISSING"
                mon = "monitored" if album.monitored else "unmonitored"
                marker = " -> would request" if album.album_mbid in selected_mbids else ""
                print(f"  - {album.title} [{album.album_mbid}] ({status}, {mon}){marker}")
    else:
        for album in selected:
            print(f"- {album.artist_name} - {album.title} [{album.album_mbid}]")

    if not args.sync:
        print("Dry run: no DroppedNeedle requests submitted. Re-run with --sync to submit these.")
        return 0

    try:
        token = login(
            args.droppedneedle_url,
            args.droppedneedle_username,
            args.droppedneedle_password,
            args.timeout,
        )
    except ApiError as error:
        print(f"login failed: {error}", file=sys.stderr)
        return 1

    submitted = 0
    failures = 0
    skipped_existing = 0
    artists_synced = 0
    artist_failures = 0

    for artist in artists:
        artist_mbid = artist["mbid"]
        artist_name = artist["name"]
        artist_selected = selected_by_artist.get(artist_mbid, [])
        artist_all = all_albums_by_artist.get(artist_mbid, [])

        artist_album_submitted = False
        for album in artist_selected:
            if not args.force:
                try:
                    status = get_album_status(args.droppedneedle_url, token, album.album_mbid, args.timeout)
                except ApiError as error:
                    print(f"warning: could not check status for {album.artist_name} - {album.title}: {error}", file=sys.stderr)
                    status = None
                if status and (status.get("in_library") or status.get("requested")):
                    reason = "in library" if status.get("in_library") else "already requested"
                    print(f"skipped ({reason}): {album.artist_name} - {album.title}")
                    skipped_existing += 1
                    artist_album_submitted = True
                    continue
            try:
                response = request_album(args.droppedneedle_url, token, album, args.timeout)
                print(f"submitted: {album.artist_name} - {album.title}: {json.dumps(response, sort_keys=True)}")
                submitted += 1
                artist_album_submitted = True
            except ApiError as error:
                failures += 1
                print(f"failed: {album.artist_name} - {album.title}: {error}", file=sys.stderr)
            time.sleep(SUBMIT_DELAY_SECONDS)

        if not args.sync_artists:
            continue

        if not artist_mbid:
            print(f"skipped artist sync for {artist_name}: no artist MBID available", file=sys.stderr)
            artist_failures += 1
            continue

        if not artist_album_submitted:
            # No album satisfied the prerequisite yet (either --missing-only/--monitored-only
            # excluded everything, or all candidates failed). Try any remaining album in
            # Lidarr for this artist, checking status first so we don't double-submit.
            for fallback in sorted(artist_all, key=lambda a: a.title.casefold()):
                if not args.force:
                    try:
                        status = get_album_status(args.droppedneedle_url, token, fallback.album_mbid, args.timeout)
                    except ApiError as error:
                        print(f"warning: could not check status for {artist_name} - {fallback.title}: {error}", file=sys.stderr)
                        status = None
                    if status and (status.get("in_library") or status.get("requested")):
                        artist_album_submitted = True
                        break
                try:
                    response = request_album(args.droppedneedle_url, token, fallback, args.timeout)
                    print(
                        f"submitted (fallback, to unlock artist sync): {artist_name} - {fallback.title}: "
                        f"{json.dumps(response, sort_keys=True)}"
                    )
                    submitted += 1
                    artist_album_submitted = True
                except ApiError as error:
                    print(f"failed to submit fallback album {fallback.title} for {artist_name}: {error}", file=sys.stderr)
                    time.sleep(SUBMIT_DELAY_SECONDS)
                    continue
                time.sleep(SUBMIT_DELAY_SECONDS)
                break

            if not artist_album_submitted:
                print(f"skipped artist sync for {artist_name}: no eligible albums to submit for this artist", file=sys.stderr)
                artist_failures += 1
                continue

        try:
            response = request_artist(args.droppedneedle_url, token, artist_name, artist_mbid, args.timeout)
            print(f"synced artist: {artist_name}: {json.dumps(response, sort_keys=True)}")
            artists_synced += 1
        except ApiError as error:
            artist_failures += 1
            print(f"failed to sync artist {artist_name}: {error}", file=sys.stderr)
        time.sleep(SUBMIT_DELAY_SECONDS)

    summary = f"Done: {submitted} albums submitted, {failures} album failures, {skipped_existing} already in DroppedNeedle (skipped)"
    if args.sync_artists:
        summary += f"; {artists_synced} artists synced, {artist_failures} artist failures"
    print(summary)
    return 1 if (failures or artist_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())