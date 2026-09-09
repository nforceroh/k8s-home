"""Convenience resource classes built on :class:`DroppedNeedleClient`."""

from __future__ import annotations

from typing import Any

from .client import DroppedNeedleClient


class _Resource:
    def __init__(self, client: DroppedNeedleClient):
        self.client = client


class SearchApi(_Resource):
    def search(self, query: str, **options: Any) -> Any:
        return self.client.call("/api/v1/search", params={"q": query, **options})

    def suggest(self, query: str, limit: int = 5) -> Any:
        return self.client.call("/api/v1/search/suggest", params={"q": query, "limit": limit})

    def bucket(self, bucket: str, query: str, **options: Any) -> Any:
        return self.client.call(
            "/api/v1/search/{bucket}",
            path_params={"bucket": bucket},
            params={"q": query, **options},
        )


class AlbumsApi(_Resource):
    def get(self, musicbrainz_id: str) -> Any:
        return self.client.call("/api/v1/albums/{album_id}", path_params={"album_id": musicbrainz_id})

    def tracks(self, musicbrainz_id: str) -> Any:
        return self.client.call("/api/v1/albums/{album_id}/tracks", path_params={"album_id": musicbrainz_id})

    def refresh(self, musicbrainz_id: str) -> Any:
        return self.client.call("/api/v1/albums/{album_id}/refresh", "POST", path_params={"album_id": musicbrainz_id}, require_auth=True)


class ArtistsApi(_Resource):
    def get(self, musicbrainz_id: str) -> Any:
        return self.client.call("/api/v1/artists/{artist_id}", path_params={"artist_id": musicbrainz_id})

    def albums(self, musicbrainz_id: str) -> Any:
        return self.client.call("/api/v1/artists/{artist_id}/releases", path_params={"artist_id": musicbrainz_id})

    def follow(self, musicbrainz_id: str, **body: Any) -> Any:
        return self.client.call("/api/v1/artists/{artist_id}/follow", "POST", path_params={"artist_id": musicbrainz_id}, json_body=body, require_auth=True)


class RequestsApi(_Resource):
    def create(self, musicbrainz_id: str, *, artist_mbid: str, artist_name: str, request_kind: str = "album", album_title: str | None = None) -> Any:
        body = {
            "musicbrainz_id": musicbrainz_id,
            "artist_mbid": artist_mbid,
            "artist_name": artist_name,
            "request_kind": request_kind,
        }
        if album_title is not None:
            body["album_title"] = album_title
        return self.client.call("/api/v1/requests/new", "POST", json_body=body, require_auth=True)

    def batch(self, body: dict[str, Any]) -> Any:
        return self.client.call("/api/v1/requests/batch", "POST", json_body=body, require_auth=True)

    def active(self, **params: Any) -> Any:
        return self.client.call("/api/v1/requests/active", params=params, require_auth=True)

    def history(self, **params: Any) -> Any:
        return self.client.call("/api/v1/requests/history", params=params, require_auth=True)

    def wanted(self, **params: Any) -> Any:
        return self.client.call("/api/v1/requests/wanted", params=params, require_auth=True)


class DownloadsApi(_Resource):
    def list(self, **params: Any) -> Any:
        return self.client.call("/api/v1/downloads", params=params, require_auth=True)

    def cancel(self, task_id: str) -> Any:
        return self.client.call(
            "/api/v1/downloads/{task_id}/cancel",
            "POST",
            path_params={"task_id": task_id},
            require_auth=True,
        )

    def stop_all_retries(self) -> Any:
        return self.client.call("/api/v1/downloads/stop-all-retries", "POST", require_auth=True)

    def held(self, release_group_mbid: str | None = None) -> Any:
        return self.client.call("/api/v1/downloads/held", params={"release_group_mbid": release_group_mbid}, require_auth=True)

    def discard_held(self, held_id: int) -> Any:
        return self.client.call("/api/v1/downloads/held/{held_id}/discard", "POST", path_params={"held_id": held_id}, require_auth=True)

    def import_held(self, held_id: int) -> Any:
        return self.client.call("/api/v1/downloads/held/{held_id}/import", "POST", path_params={"held_id": held_id}, require_auth=True)

    def reverify_held(self, held_id: int) -> Any:
        return self.client.call("/api/v1/downloads/held/{held_id}/reverify", "POST", path_params={"held_id": held_id}, require_auth=True)


class LibraryApi(_Resource):
    def stats(self) -> Any:
        return self.client.call("/api/v1/library/stats", require_auth=True)

    def albums(self, **params: Any) -> Any:
        return self.client.call("/api/v1/library/albums", params=params, require_auth=True)

    def remove_album(self, album_id: str, *, delete_files: bool = False, stop_wanted: bool = False) -> Any:
        return self.client.call(
            "/api/v1/library/album/{album_id}",
            "DELETE",
            path_params={"album_id": album_id},
            params={"delete_files": delete_files, "stop_wanted": stop_wanted},
            require_auth=True,
        )

    def artists(self, **params: Any) -> Any:
        return self.client.call("/api/v1/library/artists", params=params, require_auth=True)

    def tracks(self, **params: Any) -> Any:
        return self.client.call("/api/v1/library/tracks", params=params, require_auth=True)


class DroppedNeedleApi:
    """Grouped facade exposing the main DroppedNeedle API resources."""

    def __init__(self, client: DroppedNeedleClient):
        self.client = client
        self.search = SearchApi(client)
        self.albums = AlbumsApi(client)
        self.artists = ArtistsApi(client)
        self.requests = RequestsApi(client)
        self.downloads = DownloadsApi(client)
        self.library = LibraryApi(client)
