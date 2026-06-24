"""Shared time-state contract for market-session phrasing."""

from __future__ import annotations

from typing import Literal

TimeState = Literal[
    "pre-market",
    "open",
    "intraday",
    "close",
    "post-close",
    "scheduled",
]

__all__ = ["TimeState"]
