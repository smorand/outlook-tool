"""Tests for logging configuration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from logging_config import level_for_verbosity, setup_logging

if TYPE_CHECKING:
    from pathlib import Path


def test_level_for_verbosity_mapping() -> None:
    """Verbosity count maps to ERROR/INFO/DEBUG."""
    assert level_for_verbosity(0) == "ERROR"
    assert level_for_verbosity(1) == "INFO"
    assert level_for_verbosity(2) == "DEBUG"
    assert level_for_verbosity(5) == "DEBUG"


def test_setup_logging_default_is_error(tmp_path: Path) -> None:
    """Without -v the console/root level is ERROR (quiet)."""
    setup_logging(app_name="probe0", log_dir=tmp_path)
    assert logging.getLogger().getEffectiveLevel() == logging.ERROR


def test_setup_logging_writes_file_at_info(tmp_path: Path) -> None:
    """With -v (INFO) the file handler records emitted messages."""
    setup_logging(app_name="probe", verbosity=1, log_dir=tmp_path)
    logging.getLogger("probe.test").info("hello-file")
    log_file = tmp_path / "probe.log"
    assert log_file.exists()
    assert "hello-file" in log_file.read_text(encoding="utf-8")


def test_setup_logging_vv_sets_debug(tmp_path: Path) -> None:
    """Two -v flags lower the effective level to DEBUG."""
    setup_logging(app_name="probe2", verbosity=2, log_dir=tmp_path)
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG


def test_setup_logging_mutes_http_loggers(tmp_path: Path) -> None:
    """httpx/httpcore loggers are muted to avoid leaking upload-session URLs."""
    setup_logging(app_name="probe3", verbosity=2, log_dir=tmp_path)
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
