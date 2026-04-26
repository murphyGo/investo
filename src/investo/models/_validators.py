"""Shared field validators for pydantic v2 models in this package.

Two intentional flavors of "reject blank string":

* :func:`reject_blank_strict` — strips whitespace and returns the
  stripped value. Use for short identifier-like fields where surrounding
  whitespace is meaningless (e.g. ``source_name``, ``title``).

* :func:`reject_blank_preserve` — rejects whitespace-only input but
  returns the original value unchanged. Use for markdown / free-form
  text where leading/trailing whitespace is part of the rendered output.

Plus :func:`ensure_tz_aware` for datetime fields where naive datetimes
would silently break cron-driven date math (KST/UTC drift).

All raise ``ValueError`` so pydantic surfaces them as
``ValidationError`` to callers.
"""

from __future__ import annotations

from datetime import datetime


def reject_blank_strict(value: str) -> str:
    """Strip whitespace and reject empty results."""

    stripped = value.strip()
    if not stripped:
        raise ValueError("must contain non-whitespace characters")
    return stripped


def reject_blank_preserve(value: str) -> str:
    """Reject whitespace-only strings without modifying the value."""

    if not value.strip():
        raise ValueError("must contain non-whitespace characters")
    return value


def ensure_tz_aware(value: datetime) -> datetime:
    """Reject naive datetimes (or custom tzinfo subclasses where
    ``utcoffset()`` returns ``None``).

    The double check (``tzinfo is None`` plus ``utcoffset() is None``)
    catches both standard naive datetimes and pathological tzinfo
    subclasses that exist but cannot resolve an offset.
    """

    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("datetime must be timezone-aware")
    return value
