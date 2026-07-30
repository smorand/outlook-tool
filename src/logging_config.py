"""Logging configuration: quiet console by default, verbosity via -v/-vv.

Verbosity mapping (count of -v flags):
    0  -> ERROR (default, quiet)
    1  -> INFO
    2+ -> DEBUG

A file handler always writes <app_name>.log into the given log_dir (the app passes
its cache dir), so a trace is available on disk regardless of console verbosity.
"""

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

LOG_FORMAT = "%(module)s.%(funcName)s: %(message)s"
FILE_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s %(module)s.%(funcName)s: %(message)s"


def level_for_verbosity(verbosity: int) -> str:
    """Map a -v count to a logging level name."""
    if verbosity <= 0:
        return "ERROR"
    if verbosity == 1:
        return "INFO"
    return "DEBUG"


def setup_logging(
    app_name: str = "app",
    *,
    verbosity: int = 0,
    log_dir: Path | None = None,
) -> None:
    """Configure console + file logging.

    Args:
        app_name: Used for the log file name (<app_name>.log).
        verbosity: Count of -v flags. 0=ERROR (quiet), 1=INFO, 2+=DEBUG.
        log_dir: Directory for the log file (created if missing). Defaults to cwd.
    """
    effective_level = level_for_verbosity(verbosity)

    target_dir = log_dir or Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / f"{app_name}.log"

    console = Console(stderr=True)
    console_handler = RichHandler(
        console=console,
        show_time=True,
        omit_repeated_times=False,  # repeat the timestamp on every line, never leave it blank
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        log_time_format="[ %Y-%m-%d %H:%M:%S ]",
    )
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(FILE_LOG_FORMAT))
    file_handler.setLevel(effective_level)

    logging.basicConfig(
        level=effective_level,
        handlers=[console_handler, file_handler],
        force=True,
    )
