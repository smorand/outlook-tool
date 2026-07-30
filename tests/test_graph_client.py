"""Tests for the Graph client wrapper."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from graph_client import GraphClient, GraphError

if TYPE_CHECKING:
    from config import Settings
    from tests.conftest import StubAuth


@respx.mock
async def test_get_attaches_bearer_token(settings: Settings, stub_auth: StubAuth) -> None:
    """GET issues the request with the bearer token from the authenticator."""
    respx.get("https://graph.microsoft.com/v1.0/me").mock(return_value=httpx.Response(200, json={"id": "1"}))
    async with httpx.AsyncClient() as client:
        graph = GraphClient(settings, stub_auth, client)
        response = await graph.get("/me")
    assert response.json()["id"] == "1"
    assert respx.calls.last.request.headers["Authorization"] == "Bearer test-token"


@respx.mock
async def test_error_status_raises_graph_error(settings: Settings, stub_auth: StubAuth) -> None:
    """A 4xx/5xx response is turned into a GraphError with message detail."""
    respx.get("https://graph.microsoft.com/v1.0/me").mock(
        return_value=httpx.Response(404, json={"error": {"code": "x", "message": "not found"}})
    )
    async with httpx.AsyncClient() as client:
        graph = GraphClient(settings, stub_auth, client)
        with pytest.raises(GraphError) as exc_info:
            await graph.get("/me")
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail
