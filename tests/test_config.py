"""Tests for the config module."""

import pytest

from config import DEFAULT_OFFICE_CLIENT_ID, Settings


def test_default_settings() -> None:
    """Default settings expose the public Office client and Graph base."""
    settings = Settings()
    assert settings.app_name == "outlook-mail"
    assert settings.client_id == DEFAULT_OFFICE_CLIENT_ID
    assert settings.graph_base.startswith("https://graph.microsoft.com")
    assert "Mail.Send" in settings.scopes
    assert settings.token_cache_path.name == "token.json"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings can be overridden via OUTLOOK_MAIL_-prefixed env vars."""
    monkeypatch.setenv("OUTLOOK_MAIL_CLIENT_ID", "custom-id")
    monkeypatch.setenv("OUTLOOK_MAIL_APP_NAME", "test_app")
    settings = Settings()
    assert settings.client_id == "custom-id"
    assert settings.app_name == "test_app"
