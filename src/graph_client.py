"""Thin async Microsoft Graph client with bearer-token injection."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tracing import trace_span

if TYPE_CHECKING:
    import httpx

    from auth import Authenticator
    from config import Settings

logger = logging.getLogger(__name__)

# HTTP status at or above which a Graph response is treated as an error.
_HTTP_ERROR_THRESHOLD = 400


class GraphError(Exception):
    """A Microsoft Graph API call returned an error status."""

    __slots__ = ("detail", "status_code")

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Graph API error {status_code}: {detail}")


class GraphClient:
    """Issues authenticated requests against Microsoft Graph.

    The access token is fetched from the Authenticator before each call, so token
    refresh happens transparently.
    """

    __slots__ = ("_auth", "_client", "_settings")

    def __init__(self, settings: Settings, authenticator: Authenticator, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._auth = authenticator
        self._client = client

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        absolute: bool = False,
        authenticated: bool = True,
    ) -> httpx.Response:
        """Perform a Graph request and raise on error status.

        Args:
            method: HTTP verb.
            path: Path relative to the Graph base, or an absolute URL if absolute=True.
            json: Optional JSON body.
            headers: Extra headers.
            content: Raw body bytes (used for upload-session chunks).
            absolute: Treat path as a full URL (upload-session URLs are absolute).
            authenticated: Attach the bearer token. Upload-session chunk PUTs use a
                pre-authenticated URL and MUST NOT carry an Authorization header.
        """
        url = path if absolute else f"{self._settings.graph_base}{path}"
        request_headers: dict[str, str] = {}
        if authenticated:
            token = await self._auth.get_access_token()
            request_headers["Authorization"] = f"Bearer {token}"
        if headers:
            request_headers.update(headers)
        with trace_span(
            "api.graph",
            attributes={"http.method": method, "graph.path": path if not absolute else "<upload>"},
        ) as span:
            response = await self._client.request(
                method,
                url,
                json=json,
                content=content,
                headers=request_headers,
                timeout=self._settings.request_timeout,
            )
            span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= _HTTP_ERROR_THRESHOLD:
                detail = self._error_detail(response)
                span.set_attribute("graph.error", detail)
                raise GraphError(response.status_code, detail)
            return response

    async def get(self, path: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        """GET a Graph resource."""
        return await self.request("GET", path, headers=headers)

    async def post(self, path: str, *, json: Any = None, headers: dict[str, str] | None = None) -> httpx.Response:
        """POST to a Graph resource."""
        return await self.request("POST", path, json=json, headers=headers)

    async def patch(self, path: str, *, json: Any = None) -> httpx.Response:
        """PATCH a Graph resource."""
        return await self.request("PATCH", path, json=json)

    async def delete(self, path: str) -> httpx.Response:
        """DELETE a Graph resource."""
        return await self.request("DELETE", path)

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:500]
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            return str(error.get("message", error))
        return str(payload)[:500]
