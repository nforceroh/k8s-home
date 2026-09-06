#!/usr/bin/env python3
"""Request missing Lidarr albums from DroppedNeedle by MusicBrainz ID.

The script is read-only by default. Pass --submit to create DroppedNeedle
requests. Credentials are read from environment variables unless supplied as
CLI options.

DroppedNeedle uses username/password login (POST /api/v1/auth/login) which
returns a bearer token in an AuthResponse. This script logs in once per run
(when --submit is passed) and uses the returned token for subsequent
request calls.

NOTE: The login path and request-body field names below (`/api/v1/auth/login`,
`username`/`password`) are inferred from the Swagger schema and are the most
common FastAPI convention, but weren't directly confirmed from the docs page.
If login fails with a 404 or a 422 naming different fields, check the actual
path/schema in the DroppedNeedle docs and adjust LOGIN_PATH / the payload in
`login()` accordingly.
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


class ValidationApiError(ApiError):
    """Raised when the API returns a 422 with field-level validation detail."""

    def __init__(self, message: str, detail: Any):
        super().__init__(message)
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
                raise ApiError(f"{method} {url} returned HTTP {error.code}: {raw_body}") from error
            time.sleep(2**attempt)
        except (URLError, TimeoutError) as error:
            if attempt == retries or method != "GET":
                raise ApiError(f"{method} {url} failed: {error}") from error
            time.sleep(2**attempt)
        except json.JSONDecodeError as error:
            raise ApiError(f"{method} {url} returned invalid JSON") from error

    raise ApiError(f"{method} {url} failed")


def lidarr_get(
    base_url: str, api_key: str, path: str, *, timeout: int
) -> Any:
    query = urlencode({"apikey": api_key})
    return request_json("GET", f"{base_url.rstrip('/')}{path}?{query}", timeout=timeout)


def get_lidarr_albums(base_url: str, api_key: str, timeout: int) -> list[Album]:
    artists = lidarr_get(base_url, api_key, "/api/v1/artist", timeout=timeout)
    albums = lidarr_get(base_url, api_key, "/api/v1/album", timeout=timeout)
    if not isinstance(artists, list) or not isinstance(albums, list):
        raise ApiError("Lidarr returned an unexpected artist or album response")

    artist_names = {item.get("id"): item.get("artistName", "") for item in artists}
    artist_mbids = {item.get("id"): item.get("foreignArtistId", "") for item in artists}
    result: list[Album] = []
    for item in albums:
        album_mbid = item.get("foreignAlbumId")
        if not album_mbid:
            continue
        artist_id = item.get("artistId")
        result.append(
            Album(
                title=item.get("title", "Unknown album"),
                artist_name=artist_names.get(artist_id, "Unknown artist"),
                album_mbid=album_mbid,
                artist_mbid=artist_mbids.get(artist_id, ""),
                has_file=bool(item.get("hasFile")),
                monitored=bool(item.get("monitored")),
            )
        )
    return sorted({album.album_mbid: album for album in result}.values(), key=lambda album: (album.artist_name.casefold(), album.title.casefold()))


def login(base_url: str, username: str, password: str, timeout: int) -> str:
    """Log in to DroppedNeedle and return the bearer token."""
    payload = {"username": username, "password": password}
    response = request_json(
        "POST",
        f"{base_url.rstrip('/')}{LOGIN_PATH}",
        payload=payload,
        timeout=timeout,
        retries=0,
    )
    if not isinstance(response, dict) or "token" not in response:
        raise ApiError(f"Login succeeded but response had no 'token' field: {response!r}")
    return response["token"]


def request_album(base_url: str, token: str, album: Album, timeout: int) -> Any:
    payload = {
        "musicbrainz_id": album.album_mbid,
        "artist_mbid": album.artist_mbid,
        "artist_name": album.artist_name,
        "album_title": album.title,
        "request_kind": "album",
    }
    return request_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v1/requests/new",
        headers={"Authorization": f"Bearer {token}"},
        payload=payload,
        timeout=timeout,
        retries=0,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lidarr-url", default=os.getenv("LIDARR_URL", DEFAULT_LIDARR_URL))
    parser.add_argument("--lidarr-api-key", default=os.getenv("LIDARR_API_KEY"))
    parser.add_argument("--droppedneedle-url", default=os.getenv("DROPPEDNEEDLE_URL", DEFAULT_DROPPEDNEEDLE_URL))
    parser.add_argument("--droppedneedle-username", default=os.getenv("DROPPEDNEEDLE_USERNAME"))
    parser.add_argument("--droppedneedle-password", default=os.getenv("DROPPEDNEEDLE_PASSWORD"))
    parser.add_argument("--include-downloaded", action="store_true", help="Include albums Lidarr already has files for")
    parser.add_argument("--unmonitored", action="store_true", help="Include albums that are not monitored in Lidarr")
    parser.add_argument("--submit", action="store_true", help="Submit requests; without this flag the script only previews them")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.lidarr_api_key:
        print("LIDARR_API_KEY or --lidarr-api-key is required", file=sys.stderr)
        return 2
    if args.submit and not (args.droppedneedle_username and args.droppedneedle_password):
        print(
            "DROPPEDNEEDLE_USERNAME/DROPPEDNEEDLE_PASSWORD "
            "(or --droppedneedle-username/--droppedneedle-password) are required with --submit",
            file=sys.stderr,
        )
        return 2

    try:
        albums = get_lidarr_albums(args.lidarr_url, args.lidarr_api_key, args.timeout)
    except ApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    selected = [
        album
        for album in albums
        if (args.include_downloaded or not album.has_file)
        and (args.unmonitored or album.monitored)
    ]
    print(f"Found {len(albums)} Lidarr albums; selected {len(selected)} for DroppedNeedle")
    for album in selected:
        print(f"- {album.artist_name} - {album.title} [{album.album_mbid}]")

    if not args.submit:
        print("Dry run: no DroppedNeedle requests submitted. Re-run with --submit to submit these albums.")
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
    for album in selected:
        try:
            response = request_album(args.droppedneedle_url, token, album, args.timeout)
            print(f"submitted: {album.artist_name} - {album.title}: {json.dumps(response, sort_keys=True)}")
            submitted += 1
        except ApiError as error:
            failures += 1
            print(f"failed: {album.artist_name} - {album.title}: {error}", file=sys.stderr)
        time.sleep(SUBMIT_DELAY_SECONDS)

    print(f"Done: {submitted} submitted, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())