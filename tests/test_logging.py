"""Tests for logging configuration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from logging_config import setup_logging

if TYPE_CHECKING:
    from pathlib import Path


def test_setup_logging_writes_file(tmp_path: Path) -> None:
    """setup_logging creates <app_name>.log and records emitted messages."""
    setup_logging(app_name="probe", log_dir=tmp_path)
    logging.getLogger("probe.test").info("hello-file")
    log_file = tmp_path / "probe.log"
    assert log_file.exists()
    assert "hello-file" in log_file.read_text(encoding="utf-8")


def test_setup_logging_verbose_sets_debug(tmp_path: Path) -> None:
    """The verbose flag lowers the effective level to DEBUG."""
    setup_logging(app_name="probe2", verbose=True, log_dir=tmp_path)
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
