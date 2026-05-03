"""Shared fixtures for u2 briefing tests."""

from __future__ import annotations

import pytest

from investo.briefing import pipeline


@pytest.fixture(autouse=True)
def zero_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip FD R3 backoff sleeps in unit tests."""
    monkeypatch.setattr(pipeline, "_BACKOFF_SCHEDULE", (0.0, 0.0, 0.0))
