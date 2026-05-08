"""u31 Step 5 — process-wide retry budget for HTTP retry sites.

A single cron run can stack retries across many independent surfaces
(source adapters, the Telegram dispatcher, ``git push``). Each surface
already caps its own retries — but without a *global* budget, a
particularly bad upstream day can cause the run to spend all 12
minutes of GHA wall-clock retrying transient errors that would never
have recovered.

This module exposes a process-singleton counter:

* :func:`allow_retry` — call before each potential retry. Returns
  True if the budget still has slack, False if exhausted. The
  caller treats False as "stop retrying, return the last failure".
* :func:`reset_budget` — reset the counter (test seam; production
  resets implicitly on each subprocess startup).
* :func:`remaining` — diagnostic accessor for tests and operator
  surfaces.

Default budget (:data:`DEFAULT_RETRY_BUDGET`) is sized for a healthy
run: ~10 source adapters x 2 retries + 3 Telegram retries + 2 git
push retries ~ 25 retries. We round up to 30 to leave operating slack.
The operator can override with the env var :data:`RETRY_BUDGET_ENV` —
useful when a known-flaky upstream warrants a higher ceiling
temporarily, or when an operator wants to drive the run through
faster on a manual re-trigger.

Thread-safety: cron runs are single-process / single-event-loop, so
the global counter is intentionally not synchronized. Tests that race
multiple call sites should explicitly call :func:`reset_budget` per
test.
"""

from __future__ import annotations

import logging
import os
from typing import Final

_logger = logging.getLogger(__name__)

DEFAULT_RETRY_BUDGET: Final[int] = 30
RETRY_BUDGET_ENV: Final[str] = "INVESTO_RETRY_BUDGET"


def _resolve_budget() -> int:
    raw = os.environ.get(RETRY_BUDGET_ENV, "").strip()
    if not raw:
        return DEFAULT_RETRY_BUDGET
    try:
        parsed = int(raw)
    except ValueError:
        _logger.warning(
            "[retry_budget] invalid %s=%r; falling back to default %d",
            RETRY_BUDGET_ENV,
            raw,
            DEFAULT_RETRY_BUDGET,
        )
        return DEFAULT_RETRY_BUDGET
    if parsed < 0:
        _logger.warning(
            "[retry_budget] negative %s=%d; falling back to default %d",
            RETRY_BUDGET_ENV,
            parsed,
            DEFAULT_RETRY_BUDGET,
        )
        return DEFAULT_RETRY_BUDGET
    return parsed


_budget_used: int = 0


def reset_budget() -> None:
    """Reset the process-wide retry counter."""
    global _budget_used
    _budget_used = 0


def remaining() -> int:
    """Return the number of retries still allowed in this run."""
    return max(0, _resolve_budget() - _budget_used)


def allow_retry() -> bool:
    """Charge one retry against the budget. Returns True if allowed."""
    global _budget_used
    if _budget_used >= _resolve_budget():
        _logger.warning(
            "[retry_budget] exhausted (%d / %d) — declining further retries",
            _budget_used,
            _resolve_budget(),
        )
        return False
    _budget_used += 1
    return True


__all__ = [
    "DEFAULT_RETRY_BUDGET",
    "RETRY_BUDGET_ENV",
    "allow_retry",
    "remaining",
    "reset_budget",
]
