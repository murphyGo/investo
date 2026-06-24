"""Append-only quality KPI history for the public quality dashboard."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final

_logger = logging.getLogger(__name__)

QUALITY_HISTORY_PATH_ENV: Final[str] = "INVESTO_QUALITY_HISTORY_PATH"
DEFAULT_QUALITY_HISTORY_PATH: Final[Path] = Path("archive/_meta/quality_history.jsonl")


class QualityHistoryError(RuntimeError):
    """Raised when the quality history file cannot be updated atomically."""


@dataclass(frozen=True, slots=True)
class QualitySnapshot:
    """One daily quality snapshot persisted to ``quality_history.jsonl``.

    u54 — optional ``worst_severity`` field carries the worst per-segment
    severity observed during the run. ``append_quality_snapshot`` reads
    it during same-day re-publish to enforce keep-worst-wins so an
    operator re-run after a transient fix cannot upgrade an earlier
    ``limited`` row to ``normal`` silently.
    """

    source_liveness: float
    figures_presence: float
    fallback_ratio: float
    published_segments: int
    total_items: int
    total_failed_sources: int
    worst_severity: str | None = None
    # u55 — append-only sibling KPI; ``None`` skips persisting the
    # column (legacy back-compat). Existing JSONL rows without this
    # field are read with ``figures_verified=None``.
    figures_verified: float | None = None
    # u59 — append-only macro coverage diagnostics. Defaults keep
    # legacy call sites backward-compatible while making new rows
    # queryable by operators and future quality dashboards.
    macro_actual_missing_segments: int = 0
    required_macro_omitted: int = 0
    # u96 — current publish snapshot fields. These are floors for the
    # public dashboard so same-run segment evidence cannot be understated
    # by stale trailing-window inputs.
    current_run_zero_item_sources: int = 0
    current_run_core_missing_segments: int = 0
    current_run_segments_limited_or_worse: int = 0
    current_run_data_limited_briefings: int = 0
    current_run_briefings_observed: int = 0
    # u109 — bounded domestic exact-anchor quarantine diagnostics.
    domestic_anchor_withheld_count: int = 0
    domestic_anchor_withheld_reasons: tuple[str, ...] = ()


_SEVERITY_RANK: Final[dict[str, int]] = {
    "normal": 0,
    "partial": 1,
    "limited": 2,
    "failed": 3,
}


def resolve_quality_history_path() -> Path:
    """Return the configured quality-history JSONL path."""
    raw = os.environ.get(QUALITY_HISTORY_PATH_ENV, "").strip()
    return Path(raw) if raw else DEFAULT_QUALITY_HISTORY_PATH


def append_quality_snapshot(
    target_date: date,
    *,
    snapshot: QualitySnapshot,
    history_path: Path | None = None,
    keep_worst: bool = True,
) -> Path:
    """Upsert one daily quality snapshot using temp-file + rename.

    Same-day re-publish replaces that day's line instead of appending a
    duplicate, so consumers can treat the file as one row per KST date.
    Corrupt historical JSONL lines are skipped with a warning.

    u54 — ``keep_worst=True`` (default) enforces worst-wins for the
    severity column: an incoming ``snapshot.worst_severity`` that is
    *better* than the existing same-day row is dropped (the existing
    severity is preserved). This prevents an operator re-run from
    silently improving the historical record after a transient fix.
    Set ``keep_worst=False`` to bypass (e.g. integration tests that
    explicitly want last-write semantics).
    """
    target = history_path if history_path is not None else resolve_quality_history_path()
    rows = _load_rows(target)
    row: dict[str, object] = {
        "date": target_date.isoformat(),
        "source_liveness": _clamp_rate(snapshot.source_liveness),
        "figures_presence": _clamp_rate(snapshot.figures_presence),
        "fallback_ratio": _clamp_rate(snapshot.fallback_ratio),
        "published_segments": max(snapshot.published_segments, 0),
        "total_items": max(snapshot.total_items, 0),
        "total_failed_sources": max(snapshot.total_failed_sources, 0),
        "macro_actual_missing_segments": max(snapshot.macro_actual_missing_segments, 0),
        "required_macro_omitted": max(snapshot.required_macro_omitted, 0),
        "current_run_zero_item_sources": max(snapshot.current_run_zero_item_sources, 0),
        "current_run_core_missing_segments": max(
            snapshot.current_run_core_missing_segments,
            0,
        ),
        "current_run_segments_limited_or_worse": max(
            snapshot.current_run_segments_limited_or_worse,
            0,
        ),
        "current_run_data_limited_briefings": max(
            snapshot.current_run_data_limited_briefings,
            0,
        ),
        "current_run_briefings_observed": max(snapshot.current_run_briefings_observed, 0),
        "domestic_anchor_withheld_count": max(snapshot.domestic_anchor_withheld_count, 0),
        "domestic_anchor_withheld_reasons": list(snapshot.domestic_anchor_withheld_reasons),
    }
    if snapshot.worst_severity is not None:
        row["worst_severity"] = snapshot.worst_severity
    if snapshot.figures_verified is not None:
        row["figures_verified"] = _clamp_rate(snapshot.figures_verified)
    upserted: list[dict[str, object]] = []
    replaced = False
    for existing in rows:
        if existing.get("date") == row["date"]:
            if not replaced:
                if keep_worst:
                    row = _merge_keep_worst(existing=existing, incoming=row)
                upserted.append(row)
                replaced = True
            continue
        upserted.append(existing)
    if not replaced:
        upserted.append(row)
    upserted.sort(key=lambda item: str(item.get("date", "")))
    _write_rows_atomic(target, upserted)
    return target


def _merge_keep_worst(
    *,
    existing: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    """u54 — Preserve the worst severity across a same-day re-publish.

    Compares ``existing.worst_severity`` vs ``incoming.worst_severity``
    using :data:`_SEVERITY_RANK`. If the existing row carries a worse
    severity, that field is copied into the incoming row before the
    upsert; otherwise the incoming row wins. A debug log is emitted
    when a dropped upgrade is detected so operators have visibility
    into the silent merge.
    """
    existing_sev = existing.get("worst_severity")
    incoming_sev = incoming.get("worst_severity")
    if not isinstance(existing_sev, str) or not isinstance(incoming_sev, str):
        return incoming
    existing_rank = _SEVERITY_RANK.get(existing_sev, -1)
    incoming_rank = _SEVERITY_RANK.get(incoming_sev, -1)
    if existing_rank > incoming_rank:
        _logger.info(
            "[quality_history] keep_worst: existing=%s incoming=%s -> keeping %s",
            existing_sev,
            incoming_sev,
            existing_sev,
        )
        merged = dict(incoming)
        merged["worst_severity"] = existing_sev
        return merged
    return incoming


def _load_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for line_no, raw_line in enumerate(fp, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    _logger.warning(
                        "[quality_history] skipping corrupt JSONL line %d in %s",
                        line_no,
                        path,
                    )
                    continue
                if isinstance(parsed, dict) and isinstance(parsed.get("date"), str):
                    rows.append(parsed)
    except OSError as exc:
        raise QualityHistoryError(f"could not read quality history: {exc}") from exc
    return rows


def _write_rows_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        tmp.replace(path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise QualityHistoryError(f"could not write quality history: {exc}") from exc


def _clamp_rate(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return round(value, 6)


def recent_segment_severities(
    segment: str,
    *,
    today: date,
    coverage_path: Path,
    lookback_runs: int = 2,
) -> tuple[str, ...]:
    """u54 — Read trailing per-segment severities from ``coverage.jsonl``.

    The :class:`investo.notifier.operator_alerter.OperatorAlerter`
    severity gate uses this helper to debounce single-run spikes
    (AC-7): only when the segment is at severity ≥ ``limited`` for
    ``lookback_runs`` consecutive runs does an alert fire. Returns
    severities in *chronological* order (oldest first). Missing rows
    (no line for that calendar day, or no severities map on the line)
    are omitted — the caller treats a short tuple as "not enough
    history yet" and skips the alert.

    Pure read; the helper does not write to ``coverage.jsonl`` and is
    safe to call before / after / during pipeline stages.
    """
    if lookback_runs <= 0 or not coverage_path.exists():
        return ()
    rows = _load_severities_by_date(coverage_path)
    out: list[str] = []
    for offset in range(lookback_runs):
        day = (today - timedelta(days=lookback_runs - 1 - offset)).isoformat()
        severities = rows.get(day)
        if severities is None:
            return ()
        severity = severities.get(segment)
        if severity is None:
            return ()
        out.append(severity)
    return tuple(out)


def _load_severities_by_date(path: Path) -> dict[str, dict[str, str]]:
    by_date: dict[str, dict[str, str]] = {}
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
                severities = parsed.get("severities")
                if not isinstance(td, str) or not isinstance(severities, dict):
                    continue
                cleaned = {str(k): str(v) for k, v in severities.items() if isinstance(v, str)}
                by_date[td] = cleaned
    except OSError:
        return {}
    return by_date


__all__ = [
    "DEFAULT_QUALITY_HISTORY_PATH",
    "QUALITY_HISTORY_PATH_ENV",
    "QualityHistoryError",
    "QualitySnapshot",
    "append_quality_snapshot",
    "recent_segment_severities",
    "resolve_quality_history_path",
]
