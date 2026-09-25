"""SIRO persistent digital companion core."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("siro-core")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0+uninstalled"

__all__ = ["__version__"]
