"""Authentication helpers for DroppedNeedle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import DroppedNeedleClient


@dataclass(frozen=True)
class AuthResponse:
    """The token and user data returned by the login endpoint."""

    token: str
    user: dict[str, Any] | None = None


class DroppedNeedleAuth:
    """Authenticate a client with username/password credentials."""

    def __init__(self, client: DroppedNeedleClient):
        self.client = client

    def login(self, username: str, password: str) -> AuthResponse:
        response = self.client.call(
            "/api/v1/auth/login",
            "POST",
            json_body={"username": username, "password": password},
        )
        if not isinstance(response, dict) or not isinstance(response.get("token"), str):
            raise ValueError(f"Login response did not contain a token: {response!r}")
        auth = AuthResponse(response["token"], response.get("user"))
        self.client.token = auth.token
        return auth

    def logout(self) -> Any:
        return self.client.call("/api/v1/auth/logout", "POST", require_auth=True)

    def me(self) -> Any:
        return self.client.call("/api/v1/auth/me", require_auth=True)

    def login_from_environment(self) -> AuthResponse:
        import os

        username = os.environ.get("DROPPEDNEEDLE_USERNAME")
        password = os.environ.get("DROPPEDNEEDLE_PASSWORD")
        if not username or not password:
            raise ValueError("DROPPEDNEEDLE_USERNAME and DROPPEDNEEDLE_PASSWORD are required")
        return self.login(username, password)
