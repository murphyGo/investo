"""Append-only forecast log derived from published briefing conclusions."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Final

from investo.briefing.action_tag import (
    ACTION_TAGS,
    DEFAULT_ACTION_TAG,
    LEGACY_TAG_ALIASES,
    ActionTag,
)
from investo.briefing.extract import extract_conclusion
from investo.briefing.segments import MarketSegment
from investo.models import Briefing

FORECAST_LOG_PATH_ENV: Final[str] = "INVESTO_FORECAST_LOG_PATH"
DEFAULT_FORECAST_LOG_PATH: Final[Path] = Path("archive/_meta/forecast_log.jsonl")
_logger = logging.getLogger(__name__)
# u56 — accept both legacy stance tags and the new observation set.
_TAG_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?:관망|변동성↑|강세|약세|혼조"
    r"|상승 관찰|하락 관찰|혼재|변동성 확대"
    r"|데이터부족)\]$"
)
_TICKER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Z0-9.])[A-Z][A-Z0-9.]{1,9}(?![A-Z0-9.])|(?<!\d)\d{6}(?!\d)"
)


class ForecastLogError(RuntimeError):
    """Raised when forecast log persistence fails."""


def resolve_forecast_log_path() -> Path:
    raw = os.environ.get(FORECAST_LOG_PATH_ENV, "").strip()
    return Path(raw) if raw else DEFAULT_FORECAST_LOG_PATH


def append_forecast_entries(
    target_date: date,
    *,
    segment_briefings: Mapping[MarketSegment, Briefing],
    published_at: datetime,
    briefing_urls: Mapping[MarketSegment, str],
    log_path: Path | None = None,
) -> Path:
    """Replace the target date's forecast rows with rows from this publish."""
    target = log_path if log_path is not None else resolve_forecast_log_path()
    iso_date = target_date.isoformat()
    existing = [row for row in _load_rows(target) if row.get("target_date") != iso_date]
    for segment in sorted(segment_briefings):
        briefing = segment_briefings[segment]
        conclusion = extract_conclusion(briefing.rendered_markdown) or briefing.market_summary
        tag = _extract_action_tag(conclusion)
        existing.append(
            {
                "target_date": iso_date,
                "segment": segment,
                "action_tag": tag,
                "tickers": _extract_tickers(conclusion),
                "published_at": published_at.isoformat(),
                "briefing_url": briefing_urls.get(segment, ""),
            }
        )
    existing.sort(key=lambda row: (str(row.get("target_date", "")), str(row.get("segment", ""))))
    _write_rows_atomic(target, existing)
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
                    _logger.warning("[forecast_log] skipping corrupt JSONL line %d", line_no)
                    continue
                if isinstance(parsed, dict) and isinstance(parsed.get("target_date"), str):
                    rows.append(parsed)
    except OSError as exc:
        raise ForecastLogError(f"could not read forecast log: {exc}") from exc
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
        raise ForecastLogError(f"could not write forecast log: {exc}") from exc


def _extract_action_tag(conclusion: str) -> ActionTag:
    # u56 — accept either the legacy stance tag set or the new
    # observation set. Legacy tags are normalised via the alias map so
    # historical archive conclusions still aggregate cleanly.
    match = _TAG_RE.search(conclusion.strip())
    if match is None:
        return DEFAULT_ACTION_TAG
    tag = match.group(0)
    if tag in ACTION_TAGS:
        return tag
    aliased = LEGACY_TAG_ALIASES.get(tag)
    if aliased is not None:
        return aliased
    return DEFAULT_ACTION_TAG


def _extract_tickers(text: str) -> list[str]:
    return sorted(set(match.group(0) for match in _TICKER_RE.finditer(text)))


__all__ = [
    "DEFAULT_FORECAST_LOG_PATH",
    "FORECAST_LOG_PATH_ENV",
    "ForecastLogError",
    "append_forecast_entries",
    "resolve_forecast_log_path",
]
