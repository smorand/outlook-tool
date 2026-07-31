"""Application version.

Resolved from installed package metadata, with a build-time override fallback.
The build step may overwrite this file with a literal ``__version__`` string.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

try:
    __version__: str = _package_version("outlook-tool")
except PackageNotFoundError:  # pragma: no cover - only when running from a non-installed tree
    __version__ = "dev"
