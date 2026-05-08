"""u31 Step 3 — per-source health time series + N-day FAILED auto-detection.

Each pipeline run appends one JSON line to ``archive/_meta/coverage.jsonl``
summarising the day's per-adapter outcomes. The file is append-only so
the operator (or future tooling) can plot per-source success rate
without needing a database.

The companion :func:`detect_consecutive_failed` helper walks the
trailing N days of the same file and returns the sources that have
been ``failed`` for every one of those days. The orchestrator uses
this to surface a "source X has failed for N consecutive days" alert
to the operator chat — a soft signal that the adapter likely needs
manual attention even though the pipeline as a whole may still
succeed (other sources covered the segment).

Determinism:

* ``append_daily_coverage`` takes ``target_date`` and the outcome
  tuple — no clock read on its own.
* ``detect_consecutive_failed`` takes a ``today`` parameter for the
  same reason.

Storage path resolution mirrors :mod:`boot_alert_dedup` — the env var
:data:`COVERAGE_PATH_ENV` overrides the default; pure helpers accept
an explicit ``path`` so tests stay deterministic.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from investo.models.coverage import SourceOutcome

_logger = logging.getLogger(__name__)

COVERAGE_PATH_ENV: Final[str] = "INVESTO_COVERAGE_LOG_PATH"
_DEFAULT_COVERAGE_PATH: Final[Path] = Path("archive/_meta/coverage.jsonl")
# Default consecutive-failure threshold. The orchestrator passes this
# explicitly; tests pin different values.
DEFAULT_CONSECUTIVE_THRESHOLD: Final[int] = 3


def resolve_coverage_path() -> Path:
    raw = os.environ.get(COVERAGE_PATH_ENV, "").strip()
    return Path(raw) if raw else _DEFAULT_COVERAGE_PATH


def append_daily_coverage(
    target_date: date,
    source_outcomes: Sequence[SourceOutcome],
    *,
    path: Path | None = None,
) -> None:
    """Append one JSON line summarising today's per-source outcomes.

    Idempotent across runs: if the file already carries a line for the
    same ``target_date``, the new line still appends. Operators
    interpret duplicates as multiple runs for the same date (manual
    re-trigger / partial cron retry); the latest line wins for any
    consumer that walks back-to-front.
    """
    target_path = path if path is not None else resolve_coverage_path()
    line = {
        "target_date": target_date.isoformat(),
        "outcomes": [
            {
                "source_name": outcome.source_name,
                "category": outcome.category,
                "status": outcome.status,
                "item_count": outcome.item_count,
            }
            for outcome in source_outcomes
        ],
    }
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError as exc:
        _logger.warning("[source_health] could not append coverage line: %s", exc)


def detect_consecutive_failed(
    *,
    today: date,
    threshold: int = DEFAULT_CONSECUTIVE_THRESHOLD,
    path: Path | None = None,
) -> tuple[str, ...]:
    """Return source names that ``failed`` on every one of the last ``threshold`` days.

    "Last ``threshold`` days" includes ``today`` and walks backward by
    one calendar day at a time. A source must have a ``failed`` line
    for *every* day in the window — gaps (no line) and ``ok`` / ``zero``
    days both reset the counter. Returns a deterministic alphabetical
    tuple of source names.
    """
    if threshold <= 0:
        return ()
    target_path = path if path is not None else resolve_coverage_path()
    if not target_path.exists():
        return ()
    by_date = _load_coverage_by_date(target_path)
    candidate_sources: set[str] = set()
    for offset in range(threshold):
        day = today - timedelta(days=offset)
        outcomes = by_date.get(day.isoformat())
        if outcomes is None:
            return ()
        failed_today: set[str] = set()
        for entry in outcomes:
            if not isinstance(entry, dict):
                continue
            if entry.get("status") != "failed":
                continue
            name = entry.get("source_name")
            if isinstance(name, str):
                failed_today.add(name)
        if offset == 0:
            candidate_sources = failed_today
        else:
            candidate_sources &= failed_today
        if not candidate_sources:
            return ()
    return tuple(sorted(candidate_sources))


def _load_coverage_by_date(path: Path) -> dict[str, list[dict[str, object]]]:
    """Return the latest line per ``target_date``, parsed.

    Later lines overwrite earlier ones for the same date — so a manual
    re-trigger that completes after an earlier failure of the same date
    is treated as the source of truth for that day.
    """
    by_date: dict[str, list[dict[str, object]]] = {}
    try:
        with path.open("r", encoding="utf-8") as fp:
            for raw_line in fp:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(parsed, dict):
                    continue
                td = parsed.get("target_date")
                outcomes = parsed.get("outcomes")
                if not isinstance(td, str) or not isinstance(outcomes, list):
                    continue
                by_date[td] = [item for item in outcomes if isinstance(item, dict)]
    except OSError as exc:
        _logger.warning("[source_health] could not read coverage log: %s", exc)
    return by_date


__all__ = [
    "COVERAGE_PATH_ENV",
    "DEFAULT_CONSECUTIVE_THRESHOLD",
    "append_daily_coverage",
    "detect_consecutive_failed",
    "resolve_coverage_path",
]
