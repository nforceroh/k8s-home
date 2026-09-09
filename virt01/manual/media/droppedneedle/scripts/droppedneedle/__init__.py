"""Python client modules for the DroppedNeedle API."""

from .auth import AuthResponse, DroppedNeedleAuth
from .client import ApiError, DroppedNeedleClient
from .resources import (
    AlbumsApi,
    ArtistsApi,
    DownloadsApi,
    DroppedNeedleApi,
    LibraryApi,
    RequestsApi,
    SearchApi,
)

__all__ = [
    "AlbumsApi",
    "ApiError",
    "ArtistsApi",
    "AuthResponse",
    "DownloadsApi",
    "DroppedNeedleApi",
    "DroppedNeedleAuth",
    "DroppedNeedleClient",
    "LibraryApi",
    "RequestsApi",
    "SearchApi",
]
