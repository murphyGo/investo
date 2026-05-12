"""u54 — Per-segment severity-alert debouncing (AC-7).

A flaky core source can flap ``limited`` ↔ ``normal`` across daily
runs. Without debouncing, every flap would page the operator on
Telegram. This module owns the *decision*: "should we alert this run
given the trailing severity history?".

Policy (frozen):

* **Debounce threshold** ``REQUIRED_CONSECUTIVE_BAD = 2``. The most
  recent run plus the immediately-preceding run must *both* be at
  severity ≥ ``limited`` for the gate to open. A recovery (any
  ``normal`` / ``partial``) resets the counter.
* **Severity threshold** ``BAD_SEVERITIES = {"limited", "failed"}``.
* **First-run safety**: missing trailing history (no
  ``coverage.jsonl`` line for ``today - 1``) → no alert.

Pure helper. The orchestrator reads
:func:`investo.briefing.quality_history.recent_segment_severities`,
hands the result here, and dispatches via the existing
``OperatorAlerter`` only when this function returns ``True``.

Pipeline failure alerts (FR-007 hard failures) are independent —
this gate is consulted only for *severity-derived* alerts.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

REQUIRED_CONSECUTIVE_BAD: Final[int] = 2
BAD_SEVERITIES: Final[frozenset[str]] = frozenset({"limited", "failed"})


def should_alert_severity(severities: Sequence[str]) -> bool:
    """Return True only when *every* trailing severity is "bad".

    ``severities`` is the chronological tuple emitted by
    :func:`investo.briefing.quality_history.recent_segment_severities`.
    A tuple shorter than :data:`REQUIRED_CONSECUTIVE_BAD` represents
    insufficient history → no alert (first-run safety).
    """
    if len(severities) < REQUIRED_CONSECUTIVE_BAD:
        return False
    trailing = severities[-REQUIRED_CONSECUTIVE_BAD:]
    return all(sev in BAD_SEVERITIES for sev in trailing)


__all__ = [
    "BAD_SEVERITIES",
    "REQUIRED_CONSECUTIVE_BAD",
    "should_alert_severity",
]
