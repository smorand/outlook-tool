"""Tests for device-code authentication, caching and refresh."""

from __future__ import annotations

import stat
import time
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from auth import Authenticator, DeviceCodePrompt, LoginRequiredError, TokenSet

if TYPE_CHECKING:
    from config import Settings

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
DEVICECODE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"


def _make(settings: Settings, client: httpx.AsyncClient) -> Authenticator:
    return Authenticator(settings, client)


async def test_store_and_load_cache_roundtrip(settings: Settings) -> None:
    """Stored tokens are readable and the cache file is owner-only (0600)."""
    async with httpx.AsyncClient() as client:
        auth = _make(settings, client)
        token = TokenSet(access_token="abc", refresh_token="ref", expires_at=time.time() + 3600)
        auth._store(token)
        assert settings.token_cache_path.exists()
        mode = stat.S_IMODE(settings.token_cache_path.stat().st_mode)
        assert mode == 0o600
        loaded = auth._load_cache()
        assert loaded is not None
        assert loaded.access_token == "abc"


async def test_get_access_token_uses_valid_cache(settings: Settings) -> None:
    """A valid cached token is returned without any network call."""
    async with httpx.AsyncClient() as client:
        auth = _make(settings, client)
        auth._store(TokenSet(access_token="cached", expires_at=time.time() + 3600))
        assert await auth.get_access_token() == "cached"


async def test_get_access_token_requires_login_when_empty(settings: Settings) -> None:
    """With no cache, get_access_token raises LoginRequiredError."""
    async with httpx.AsyncClient() as client:
        auth = _make(settings, client)
        with pytest.raises(LoginRequiredError):
            await auth.get_access_token()


@respx.mock
async def test_refresh_when_expired(settings: Settings) -> None:
    """An expired token with a refresh token is silently refreshed."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fresh", "expires_in": 3600, "scope": "s"})
    )
    async with httpx.AsyncClient() as client:
        auth = _make(settings, client)
        auth._store(TokenSet(access_token="old", refresh_token="ref", expires_at=time.time() - 10))
        token = await auth.get_access_token()
        assert token == "fresh"
        # Refresh response omitted a new refresh token: the old one is preserved.
        reloaded = auth._load_cache()
        assert reloaded is not None
        assert reloaded.refresh_token == "ref"


@respx.mock
async def test_refresh_failure_raises_login_required(settings: Settings) -> None:
    """A failed refresh surfaces as LoginRequiredError."""
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    async with httpx.AsyncClient() as client:
        auth = _make(settings, client)
        auth._store(TokenSet(access_token="old", refresh_token="ref", expires_at=time.time() - 10))
        with pytest.raises(LoginRequiredError):
            await auth.get_access_token()


@respx.mock
async def test_login_device_code_flow(settings: Settings) -> None:
    """The device-code flow prompts the user then caches the issued token."""
    respx.post(DEVICECODE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "device_code": "DEV",
                "user_code": "ABCD",
                "verification_uri": "https://microsoft.com/devicelogin",
                "expires_in": 900,
                "interval": 0,
            },
        )
    )
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "issued", "refresh_token": "r", "expires_in": 3600, "scope": "s"}
        )
    )
    prompts: list[DeviceCodePrompt] = []

    async with httpx.AsyncClient() as client:
        auth = _make(settings, client)

        def on_prompt(prompt: DeviceCodePrompt) -> None:
            prompts.append(prompt)

        token = await auth.login(on_prompt)

    assert token.access_token == "issued"
    assert prompts and prompts[0].user_code == "ABCD"
    assert settings.token_cache_path.exists()
