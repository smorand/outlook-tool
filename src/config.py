"""Application settings using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Public, multi-tenant first-party client ID (Microsoft Office). No secret needed.
# Chosen because locked-down tenants rarely block the genuine Office client, unlike
# Azure CLI. Delegated device-code flow yields a token pre-consented for a broad
# Graph scope bundle (Mail.ReadWrite, Mail.Send, Calendars.ReadWrite, ...).
DEFAULT_OFFICE_CLIENT_ID = "d3590ed6-52b3-4102-aeff-aad2292ab01c"

# Scopes we explicitly request. The Office client grants the full bundle regardless,
# but we ask only for what this tool uses.
DEFAULT_SCOPES = (
    "https://graph.microsoft.com/Mail.ReadWrite "
    "https://graph.microsoft.com/Mail.Send "
    "https://graph.microsoft.com/Calendars.ReadWrite "
    "offline_access openid profile"
)


def _default_token_cache_path() -> Path:
    return Path.home() / ".cache" / "outlook-mail" / "token.json"


class Settings(BaseSettings):
    """Configuration loaded from environment variables (prefix OUTLOOK_MAIL_).

    A .env file is loaded automatically if present.
    """

    model_config = SettingsConfigDict(
        env_prefix="OUTLOOK_MAIL_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str = "outlook-mail"

    # OAuth2 device-code flow (public client, no secret).
    client_id: str = DEFAULT_OFFICE_CLIENT_ID
    authority: str = "https://login.microsoftonline.com/common/oauth2/v2.0"
    scopes: str = DEFAULT_SCOPES

    # Microsoft Graph.
    graph_base: str = "https://graph.microsoft.com/v1.0"
    request_timeout: float = 60.0

    # Token cache (contains a refresh token: written with 0600 permissions).
    token_cache_path: Path = Field(default_factory=_default_token_cache_path)

    # Attachment handling. Graph caps single-request sendMail near 4 MB; above the
    # inline threshold we switch to a draft plus an upload session.
    attachment_inline_limit: int = 3_000_000
    # Upload-session chunk size MUST be a multiple of 320 KiB (327680 bytes).
    upload_chunk_size: int = 3_276_800

    @property
    def log_dir(self) -> Path:
        """Directory for log files (app + OpenTelemetry), alongside the token cache."""
        return self.token_cache_path.parent
