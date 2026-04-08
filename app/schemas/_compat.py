"""Python 3.10 compatibility: StrEnum fallback."""

try:
    from enum import StrEnum  # Python 3.11+
except ImportError:
    from strenum import StrEnum  # noqa: F401

__all__ = ["StrEnum"]
