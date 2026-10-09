"""Truthful display labels for an explicitly observed live price."""

from collections.abc import Mapping
from datetime import UTC, datetime


def price_snapshot_label(metadata: Mapping[str, object]) -> str | None:
    if metadata.get("price_time_basis") != "live_snapshot":
        return None
    raw = metadata.get("price_as_of", "")
    try:
        if not isinstance(raw, str):
            raise ValueError("price as-of must be text")
        as_of = datetime.fromisoformat(raw)
        if as_of.utcoffset() is None:
            raise ValueError("price as-of must be aware")
    except (ValueError, OverflowError):
        return "조회 시점 가격 · 시각 미확인"
    return f"조회 시점 가격 · {as_of.astimezone(UTC):%Y-%m-%d %H:%M} UTC"
