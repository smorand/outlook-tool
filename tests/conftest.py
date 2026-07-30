"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from config import Settings

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings with an isolated token cache and tiny attachment thresholds."""
    return Settings(
        token_cache_path=tmp_path / "token.json",
        attachment_inline_limit=10,
        upload_chunk_size=4,
    )


class StubAuth:
    """Minimal authenticator stub returning a fixed token, no network."""

    async def get_access_token(self) -> str:
        """Return a canned bearer token."""
        return "test-token"


@pytest.fixture
def stub_auth() -> StubAuth:
    """Provide a stub authenticator for service tests."""
    return StubAuth()
