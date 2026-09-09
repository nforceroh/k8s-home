"""Transport and OpenAPI-driven endpoint access for DroppedNeedle."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 30
DEFAULT_API_PREFIX = "/api/v1"
_PATH_PARAMETER = re.compile(r"{([^}]+)}")


class ApiError(RuntimeError):
    """Raised when DroppedNeedle cannot complete an API request."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class DroppedNeedleClient:
    """Low-level client with an optional bearer token and OpenAPI validation."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        openapi_path: str | Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.openapi_path = Path(openapi_path) if openapi_path else None
        self._spec: dict[str, Any] | None = None

    @property
    def spec(self) -> dict[str, Any]:
        """Load the repository's OpenAPI document lazily when requested."""
        if self._spec is None:
            path = self.openapi_path or Path(__file__).with_name("dn_openapi.json")
            if not path.exists():
                path = path.parent.parent / "dn_openapi.json"
            try:
                self._spec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ApiError(f"Unable to load OpenAPI document {path}: {error}") from error
        return self._spec

    def endpoint(self, path: str, method: str) -> dict[str, Any]:
        """Return an endpoint definition, raising a useful error for typos."""
        normalized = path if path.startswith("/") else f"/{path}"
        try:
            return self.spec["paths"][normalized][method.lower()]
        except KeyError as error:
            raise ApiError(f"Endpoint is not declared in OpenAPI: {method.upper()} {normalized}") from error

    def request(
        self,
        method: str,
        path: str,
        *,
        path_params: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        require_auth: bool = False,
        timeout: int | None = None,
    ) -> Any:
        """Call a declared endpoint and decode JSON responses when possible."""
        normalized = path if path.startswith("/") else f"/{path}"
        values = dict(path_params or {})
        missing = [name for name in _PATH_PARAMETER.findall(normalized) if name not in values]
        if missing:
            raise ValueError(f"Missing path parameter(s) for {normalized}: {', '.join(missing)}")
        for name, value in values.items():
            normalized = normalized.replace(f"{{{name}}}", str(value))

        request_url = f"{self.base_url}{normalized}"
        if params:
            query = [(key, value) for key, value in params.items() if value is not None]
            if query:
                request_url = f"{request_url}?{urlencode(query, doseq=True)}"

        body = None if json_body is None else json.dumps(json_body).encode("utf-8")
        request_headers = {"Accept": "application/json", **(headers or {})}
        if self.token:
            request_headers.setdefault("Authorization", f"Bearer {self.token}")
        elif require_auth:
            raise ApiError("This endpoint requires authentication; call login() first")
        if body is not None:
            request_headers["Content-Type"] = "application/json"

        request = Request(request_url, data=body, headers=request_headers, method=method.upper())
        try:
            with urlopen(request, timeout=timeout or self.timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "json" in content_type or raw[:1] in (b"{", b"[", b'"'):
                    return json.loads(raw)
                return raw
        except HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                detail: Any = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                detail = raw
            message = f"{method.upper()} {request_url} returned HTTP {error.code}"
            if detail is not None:
                message += f": {detail}"
            raise ApiError(message, status_code=error.code, detail=detail) from error
        except URLError as error:
            raise ApiError(f"{method.upper()} {request_url} failed: {error}") from error

    def call(self, path: str, method: str = "GET", **kwargs: Any) -> Any:
        """Call any endpoint declared in ``dn_openapi.json``."""
        self.endpoint(path, method)
        return self.request(method, path, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Expose operationIds as callable methods when the spec defines them."""
        for path, operations in self.spec.get("paths", {}).items():
            for method, operation in operations.items():
                if operation.get("operationId") == name:
                    return lambda **kwargs: self.call(path, method, **kwargs)
        raise AttributeError(name)
