"""Shared fixtures for u2 briefing tests."""

from __future__ import annotations

import pytest

from investo.briefing._core import orchestration


@pytest.fixture(autouse=True)
def zero_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip FD R3 backoff sleeps in unit tests.

    u83 — the retry-loop constant moved from ``briefing.pipeline`` to
    ``briefing._core.orchestration`` in the pipeline decomposition;
    patch the symbol at its new home (mechanical import-path update).
    """
    monkeypatch.setattr(orchestration, "_BACKOFF_SCHEDULE", (0.0, 0.0, 0.0))
