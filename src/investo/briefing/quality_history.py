"""Append-only quality KPI history for the public quality dashboard."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

_logger = logging.getLogger(__name__)

QUALITY_HISTORY_PATH_ENV: Final[str] = "INVESTO_QUALITY_HISTORY_PATH"
DEFAULT_QUALITY_HISTORY_PATH: Final[Path] = Path("archive/_meta/quality_history.jsonl")


class QualityHistoryError(RuntimeError):
    """Raised when the quality history file cannot be updated atomically."""


@dataclass(frozen=True, slots=True)
class QualitySnapshot:
    """One daily quality snapshot persisted to ``quality_history.jsonl``."""

    source_liveness: float
    figures_presence: float
    fallback_ratio: float
    published_segments: int
    total_items: int
    total_failed_sources: int


def resolve_quality_history_path() -> Path:
    """Return the configured quality-history JSONL path."""
    raw = os.environ.get(QUALITY_HISTORY_PATH_ENV, "").strip()
    return Path(raw) if raw else DEFAULT_QUALITY_HISTORY_PATH


def append_quality_snapshot(
    target_date: date,
    *,
    snapshot: QualitySnapshot,
    history_path: Path | None = None,
) -> Path:
    """Upsert one daily quality snapshot using temp-file + rename.

    Same-day re-publish replaces that day's line instead of appending a
    duplicate, so consumers can treat the file as one row per KST date.
    Corrupt historical JSONL lines are skipped with a warning.
    """
    target = history_path if history_path is not None else resolve_quality_history_path()
    rows = _load_rows(target)
    row = {
        "date": target_date.isoformat(),
        "source_liveness": _clamp_rate(snapshot.source_liveness),
        "figures_presence": _clamp_rate(snapshot.figures_presence),
        "fallback_ratio": _clamp_rate(snapshot.fallback_ratio),
        "published_segments": max(snapshot.published_segments, 0),
        "total_items": max(snapshot.total_items, 0),
        "total_failed_sources": max(snapshot.total_failed_sources, 0),
    }
    upserted: list[dict[str, object]] = []
    replaced = False
    for existing in rows:
        if existing.get("date") == row["date"]:
            if not replaced:
                upserted.append(row)
                replaced = True
            continue
        upserted.append(existing)
    if not replaced:
        upserted.append(row)
    upserted.sort(key=lambda item: str(item.get("date", "")))
    _write_rows_atomic(target, upserted)
    return target


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


__all__ = [
    "DEFAULT_QUALITY_HISTORY_PATH",
    "QUALITY_HISTORY_PATH_ENV",
    "QualityHistoryError",
    "QualitySnapshot",
    "append_quality_snapshot",
    "resolve_quality_history_path",
]
