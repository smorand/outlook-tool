"""OAuth2 device-code authentication with token caching and refresh.

Uses a public first-party client ID (no secret). The refresh token is cached on
disk with 0600 permissions so subsequent runs are non-interactive until the
refresh token is revoked or expires.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from tracing import trace_span

if TYPE_CHECKING:
    from pathlib import Path

    import httpx

    from config import Settings

logger = logging.getLogger(__name__)

# Seconds of remaining lifetime below which a token is treated as expired.
_EXPIRY_SKEW_SECONDS = 120
_DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


class AuthError(Exception):
    """Base authentication error."""


class LoginRequiredError(AuthError):
    """No usable cached token and refresh failed: an interactive login is needed."""


class DeviceCodePrompt(BaseModel):
    """Details shown to the user to complete the device-code login."""

    verification_uri: str
    user_code: str
    expires_in: int


class TokenSet(BaseModel):
    """A cached set of OAuth2 tokens."""

    access_token: str
    refresh_token: str | None = None
    expires_at: float
    scope: str = ""
    token_type: str = "Bearer"

    @property
    def is_valid(self) -> bool:
        """True if the access token is present and not near expiry."""
        return bool(self.access_token) and (self.expires_at - time.time()) > _EXPIRY_SKEW_SECONDS


PromptCallback = Callable[[DeviceCodePrompt], Awaitable[None]] | Callable[[DeviceCodePrompt], None]


class Authenticator:
    """Obtains and refreshes Graph access tokens via the device-code flow."""

    __slots__ = ("_client", "_settings", "_token")

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client
        self._token: TokenSet | None = None

    async def get_access_token(self) -> str:
        """Return a valid access token, refreshing silently when possible.

        Raises:
            LoginRequiredError: when no cached token can be used or refreshed.
        """
        token = self._token or self._load_cache()
        if token and token.is_valid:
            self._token = token
            return token.access_token
        if token and token.refresh_token:
            refreshed = await self._refresh(token.refresh_token)
            self._store(refreshed)
            return refreshed.access_token
        raise LoginRequiredError("no valid cached token; run the 'login' command first")

    async def login(self, on_prompt: PromptCallback) -> TokenSet:
        """Run the interactive device-code flow and cache the resulting tokens."""
        with trace_span("auth.login"):
            prompt, device_code, interval, deadline = await self._start_device_code()
            result = on_prompt(prompt)
            if result is not None:
                await result  # support async prompt callbacks
            token = await self._poll_for_token(device_code, interval, deadline)
            self._store(token)
            logger.info("login succeeded; token cached at %s", self._settings.token_cache_path)
            return token

    def has_cached_token(self) -> bool:
        """True if a token cache file exists on disk."""
        return self._settings.token_cache_path.exists()

    async def _start_device_code(self) -> tuple[DeviceCodePrompt, str, int, float]:
        response = await self._client.post(
            f"{self._settings.authority}/devicecode",
            data={"client_id": self._settings.client_id, "scope": self._settings.scopes},
        )
        payload = response.json()
        if "device_code" not in payload:
            raise AuthError(f"device-code request refused: {payload.get('error_description', payload)}")
        prompt = DeviceCodePrompt(
            verification_uri=payload.get("verification_uri") or payload.get("verification_url", ""),
            user_code=payload["user_code"],
            expires_in=int(payload.get("expires_in", 900)),
        )
        interval = int(payload.get("interval", 5))
        deadline = time.time() + prompt.expires_in
        return prompt, payload["device_code"], interval, deadline

    async def _poll_for_token(self, device_code: str, interval: int, deadline: float) -> TokenSet:
        while time.time() < deadline:
            await asyncio.sleep(interval)
            response = await self._client.post(
                f"{self._settings.authority}/token",
                data={
                    "grant_type": _DEVICE_CODE_GRANT,
                    "client_id": self._settings.client_id,
                    "device_code": device_code,
                },
            )
            payload = response.json()
            error = payload.get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval += 5
                continue
            if "access_token" in payload:
                return self._token_from_payload(payload)
            raise AuthError(f"login failed: {payload.get('error_description', error)}")
        raise AuthError("device-code login timed out before completion")

    async def _refresh(self, refresh_token: str) -> TokenSet:
        with trace_span("auth.refresh") as span:
            response = await self._client.post(
                f"{self._settings.authority}/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._settings.client_id,
                    "refresh_token": refresh_token,
                    "scope": self._settings.scopes,
                },
            )
            payload = response.json()
            if "access_token" not in payload:
                span.set_attribute("auth.refresh.ok", False)
                raise LoginRequiredError(f"token refresh failed: {payload.get('error_description', payload)}")
            span.set_attribute("auth.refresh.ok", True)
            token = self._token_from_payload(payload)
            # Refresh responses may omit a new refresh token: keep the old one.
            if token.refresh_token is None:
                token = token.model_copy(update={"refresh_token": refresh_token})
            return token

    @staticmethod
    def _token_from_payload(payload: dict[str, object]) -> TokenSet:
        expires_in = float(payload.get("expires_in", 3600))  # type: ignore[arg-type]
        return TokenSet(
            access_token=str(payload["access_token"]),
            refresh_token=payload.get("refresh_token"),  # type: ignore[arg-type]
            expires_at=time.time() + expires_in,
            scope=str(payload.get("scope", "")),
            token_type=str(payload.get("token_type", "Bearer")),
        )

    def _load_cache(self) -> TokenSet | None:
        path = self._settings.token_cache_path
        if not path.exists():
            return None
        try:
            return TokenSet.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            logger.warning("ignoring unreadable token cache %s: %s", path, exc)
            return None

    def _store(self, token: TokenSet) -> None:
        self._token = token
        path: Path = self._settings.token_cache_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically with owner-only permissions (contains a refresh token).
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(token.model_dump_json(), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(path)
