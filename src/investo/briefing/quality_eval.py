"""u32 Step 4 — daily quality evaluation harness.

The quality dashboard is the public-site answer to the persona-3
question "is the bot trustworthy?". It computes three KPIs over the
trailing 7 days and surfaces them on ``site_docs/quality.md``:

* **Source liveness rate** — fraction of runs in the window where every
  registered source returned ``ok`` or ``zero`` (no ``failed``). Low
  values mean adapters are flaking.
* **Figures presence rate** — fraction of *non-data-limited* archived
  briefings whose body carries at least one flaggable numeric token
  (price, percentage, or unit-bearing figure). Low values mean Stage 2
  is producing prose without anchoring it to numbers.
* **Fallback ratio** — fraction of archived briefings where the body
  is the explicit data-limited boilerplate (``데이터 부족 안내`` /
  ``실시간 안내``). High values mean upstream data quality is the
  bottleneck.

Pure helpers — the publisher decides where to write the page.
``compute_quality_kpis`` accepts explicit ``coverage_path`` and
``archive_root`` so tests stay deterministic.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from investo.briefing.numeric_self_check import extract_flaggable_numbers

# Marker the data-limited body emits in the boilerplate text. Updating
# the boilerplate copy without updating this marker silently invalidates
# the fallback-ratio KPI — keep them aligned.
_DATA_LIMITED_MARKERS: Final[tuple[str, ...]] = (
    "[데이터부족]",
    "데이터 부족 안내",
    "실시간 안내",
)

# u55 — marker the numeric_verify gate inserts at the top of a briefing
# whose core-fact verification produced ``downgrade`` actions. Presence
# means the briefing went out but at least one core fact was either
# unverified or in conflict — counts AGAINST ``figures_verified``.
_VERIFY_DOWNGRADE_MARKER: Final[str] = "⚠️ 확인 필요: 수치 검증 실패"


@dataclass(frozen=True, slots=True)
class QualityKPIs:
    """Summary of the trailing-window quality KPIs.

    Each ``*_rate`` property returns ``None`` when the denominator is
    zero so the renderer can surface ``n/a`` (u54 AC-4) rather than
    a misleading ``0.0%``. ``runs_observed`` and ``briefings_observed``
    are non-negative integers used in the rendered denominators.

    u54 — new counter fields:

    * ``failed_sources`` — sum of failed-source counts across the
      window (one count per run; not deduped across runs because each
      run is its own observation).
    * ``zero_item_sources`` — sum of zero-item-source counts (same
      shape).
    * ``core_missing_segments`` — count of (run, segment) pairs where
      every core source registered for that segment was bad
      (failed / zero); raises the "core data missing" signal even when
      a segment still published.
    * ``segments_limited_or_worse`` — count of (run, segment) pairs at
      severity ≥ ``limited``; complements ``runs_with_failed_source``
      by surfacing per-segment severity rather than per-run.
    """

    today: date
    window_days: int
    runs_observed: int
    runs_with_failed_source: int
    briefings_observed: int
    briefings_data_limited: int
    briefings_with_figures: int
    failed_sources: int = 0
    zero_item_sources: int = 0
    core_missing_segments: int = 0
    segments_limited_or_worse: int = 0
    # u55 — distinct precision-first KPI sibling to ``figures_presence``.
    # Numerator = briefings whose Stage 2 body had ≥1 *typed* core market
    # fact verified within tolerance against a source-emitted Decimal.
    # Denominator = same as ``figures_presence`` (non-data-limited
    # briefings observed). ``None`` = no observations.
    briefings_with_verified_figures: int = 0

    @property
    def source_liveness_rate(self) -> float | None:
        """u54 — Returns ``None`` when no runs were observed.

        Renderers translate ``None`` to ``n/a`` rather than ``0.0%``,
        which would falsely imply "we observed zero liveness" instead
        of "we have no observations".
        """
        if self.runs_observed == 0:
            return None
        return (self.runs_observed - self.runs_with_failed_source) / self.runs_observed

    @property
    def figures_presence_rate(self) -> float | None:
        non_limited = self.briefings_observed - self.briefings_data_limited
        if non_limited <= 0:
            return None
        return self.briefings_with_figures / non_limited

    @property
    def figures_verified_rate(self) -> float | None:
        """u55 — fraction of non-limited briefings carrying ≥1 verified core fact.

        ``None`` when the denominator is zero (rendered as ``n/a``).
        Sibling to :meth:`figures_presence_rate`; both columns coexist on
        the quality page.
        """
        non_limited = self.briefings_observed - self.briefings_data_limited
        if non_limited <= 0:
            return None
        return self.briefings_with_verified_figures / non_limited

    @property
    def fallback_ratio(self) -> float | None:
        if self.briefings_observed == 0:
            return None
        return self.briefings_data_limited / self.briefings_observed


@dataclass(frozen=True, slots=True)
class QualityHistoryRow:
    """One slot in the rolling quality-history window.

    ``has_data=False`` preserves missing-day gaps so visual renderers do
    not turn absent publishes into synthetic zero-valued KPI points.

    u54 — ``worst_severity`` carries the worst per-segment severity
    observed on that day, ``None`` for legacy rows that pre-date the
    field.
    """

    day: date
    source_liveness: float | None = None
    figures_presence: float | None = None
    fallback_ratio: float | None = None
    published_segments: int | None = None
    total_items: int | None = None
    total_failed_sources: int | None = None
    worst_severity: str | None = None
    # u55 — append-only sibling KPI column. Legacy JSONL rows leave this
    # as ``None`` (backward-compat); rows written from u55 onward carry
    # the verified-fraction. Surfaced by the sparkline as a distinct
    # series so a downward trend on ``figures_presence`` vs upward on
    # ``figures_verified`` (or vice versa) reads as a meaningful signal.
    figures_verified: float | None = None
    # u59 — optional macro coverage diagnostics. Legacy rows leave
    # these unset; new quality-history rows can expose macro actual
    # availability without changing the public KPI meanings.
    macro_actual_missing_segments: int | None = None
    required_macro_omitted: int | None = None
    current_run_zero_item_sources: int = 0
    current_run_core_missing_segments: int = 0
    current_run_segments_limited_or_worse: int = 0
    current_run_data_limited_briefings: int = 0
    current_run_briefings_observed: int = 0

    @property
    def has_data(self) -> bool:
        return (
            self.source_liveness is not None
            and self.figures_presence is not None
            and self.fallback_ratio is not None
        )


def compute_quality_kpis(
    today: date,
    *,
    coverage_path: Path,
    archive_root: Path,
    window_days: int = 7,
) -> QualityKPIs:
    """Compute the trailing-window KPIs over the inputs.

    Both inputs may be missing — a freshly-deployed runtime has no
    ``coverage.jsonl`` and no archive yet. In that case the returned
    KPIs report ``None`` rates (rendered as ``n/a``) with zero
    counters (u54 AC-4).
    """
    runs = _load_recent_runs(coverage_path, today=today, window_days=window_days)
    runs_with_failed = sum(
        1
        for outcomes in runs.values()
        if any(entry.get("status") == "failed" for entry in outcomes)
    )
    failed_sources = sum(
        sum(1 for entry in outcomes if entry.get("status") == "failed")
        for outcomes in runs.values()
    )
    zero_item_sources = sum(
        sum(1 for entry in outcomes if entry.get("status") == "zero") for outcomes in runs.values()
    )
    archive_files = list(_iter_archive_files(archive_root, today=today, window_days=window_days))
    briefings_observed = len(archive_files)
    briefings_data_limited = sum(1 for path in archive_files if _is_data_limited(path))
    briefings_with_figures = sum(
        1 for path in archive_files if not _is_data_limited(path) and _carries_numeric_figure(path)
    )
    # u55 — count briefings that carry at least one figure AND do *not*
    # carry the u55 numeric_verify downgrade callout. The callout
    # marker is only inserted when the gate flagged unverified /
    # conflict actions, so its absence is the signal that every core
    # fact in the body verified against a source-emitted Decimal.
    briefings_with_verified = sum(
        1
        for path in archive_files
        if not _is_data_limited(path)
        and _carries_numeric_figure(path)
        and not _has_verify_downgrade(path)
    )
    return QualityKPIs(
        today=today,
        window_days=window_days,
        runs_observed=len(runs),
        runs_with_failed_source=runs_with_failed,
        briefings_observed=briefings_observed,
        briefings_data_limited=briefings_data_limited,
        briefings_with_figures=briefings_with_figures,
        failed_sources=failed_sources,
        zero_item_sources=zero_item_sources,
        briefings_with_verified_figures=briefings_with_verified,
        # ``core_missing_segments`` / ``segments_limited_or_worse``
        # require per-segment severity which the legacy
        # ``coverage.jsonl`` schema does not record. The orchestrator
        # writes the augmented severity field starting in u54 (see
        # ``source_health.append_daily_coverage``); back-fill is
        # impossible for historic days, so we count only what the file
        # exposes today.
        core_missing_segments=_count_core_missing_segments(runs),
        segments_limited_or_worse=_count_segments_limited_or_worse(runs),
    )


def _count_core_missing_segments(runs: dict[str, list[dict[str, object]]]) -> int:
    """u54 — read per-segment severity stamps written by source_health.

    The augmented ``coverage.jsonl`` schema carries a ``severities``
    dict mapping ``MarketSegment`` → severity string. Lines without
    the field (legacy rows) contribute 0. The "core missing" signal
    is severity ``in {"limited", "failed"}``.
    """
    total = 0
    for outcomes in runs.values():
        # ``outcomes`` is the raw list of per-source dicts. The
        # severities live on a sibling key reified by the loader.
        # We piggyback on the ``__severities__`` synthetic key the
        # loader injects so both inputs flow through the same code
        # path.
        severities = _extract_severities(outcomes)
        for sev in severities.values():
            if sev in ("limited", "failed"):
                total += 1
    return total


def _count_segments_limited_or_worse(runs: dict[str, list[dict[str, object]]]) -> int:
    """u54 — every (run, segment) pair at severity ≥ ``limited``.

    Mirrors :func:`_count_core_missing_segments` today; kept as a
    separate KPI so a future weighting (e.g. failed-counts-2x) can
    diverge without breaking the existing counter.
    """
    return _count_core_missing_segments(runs)


def _extract_severities(outcomes: list[dict[str, object]]) -> dict[str, str]:
    """Pull the synthetic ``__severities__`` slot injected by the loader.

    Returns ``{}`` when the slot is absent (legacy rows) — those rows
    cannot contribute to the per-segment severity KPIs.
    """
    for entry in outcomes:
        if entry.get("__synthetic__") == "severities":
            payload = entry.get("payload")
            if isinstance(payload, dict):
                return {str(k): str(v) for k, v in payload.items() if isinstance(v, str)}
    return {}


def compute_quality_history(
    days: int = 30,
    *,
    history_path: Path,
    today: date | None = None,
) -> list[QualityHistoryRow]:
    """Read the rolling quality-history JSONL with missing-day gaps preserved."""
    if days <= 0 or not history_path.exists():
        return []
    parsed_rows = _load_quality_history_rows(history_path)
    if not parsed_rows:
        return []
    end_day = today if today is not None else max(parsed_rows)
    start_day = end_day - timedelta(days=days - 1)
    rows: list[QualityHistoryRow] = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        rows.append(parsed_rows.get(day, QualityHistoryRow(day=day)))
    return rows


def render_quality_page(kpis: QualityKPIs) -> str:
    """Render the public-site ``site_docs/quality.md`` body."""
    if kpis.briefings_observed == 0 and kpis.runs_observed == 0:
        return _no_data_page(kpis)
    lines: list[str] = []
    lines.append("# 데이터 품질")
    lines.append("")
    lines.append(
        f"_지난 {kpis.window_days}일 ({kpis.today.isoformat()} 기준) "
        f"자동 측정한 데이터 품질 지표입니다._"
    )
    lines.append("")
    lines.append("| 지표 | 값 | 분모 |")
    lines.append("|------|------|------|")
    lines.append(
        f"| 소스 라이브니스 | {_format_pct(kpis.source_liveness_rate)} | {kpis.runs_observed} 회 |"
    )
    lines.append(
        "| 수치 인용 비율 | "
        f"{_format_pct(kpis.figures_presence_rate)} | "
        f"{max(kpis.briefings_observed - kpis.briefings_data_limited, 0)} 건 |"
    )
    # u55 — distinct precision KPI: typed core-fact verification.
    lines.append(
        "| 수치 검증 비율 | "
        f"{_format_pct(kpis.figures_verified_rate)} | "
        f"{max(kpis.briefings_observed - kpis.briefings_data_limited, 0)} 건 |"
    )
    lines.append(
        f"| 데이터 부족 폴백 | {_format_pct(kpis.fallback_ratio)} | {kpis.briefings_observed} 건 |"
    )
    # u54 — Additional reader-facing counters for source-status truth.
    lines.append(f"| 실패한 소스 누적 | {kpis.failed_sources} 회 | {kpis.runs_observed} 회 |")
    lines.append(f"| 0건 반환 소스 누적 | {kpis.zero_item_sources} 회 | {kpis.runs_observed} 회 |")
    lines.append(
        f"| 핵심 소스 결손 세그먼트 | {kpis.core_missing_segments} 건 | {kpis.runs_observed} 회 |"
    )
    lines.append(
        f"| 제한/실패 세그먼트 | {kpis.segments_limited_or_worse} 건 | {kpis.runs_observed} 회 |"
    )
    lines.append("")
    lines.append(
        "> 이 지표는 매 게시 직후 자동 갱신됩니다. ``n/a`` 는 측정 가능한 "
        "표본이 없다는 뜻이며 0% 가 아닙니다. 표본 크기를 함께 확인하세요."
    )
    lines.append("")
    return "\n".join(lines)


def _format_pct(value: float | None) -> str:
    """u54 — Render ``None`` as ``n/a`` rather than ``0.0%`` (AC-4).

    Renderers must surface "we have no observations" explicitly so the
    reader does not confuse undefined with worst-case zero liveness.
    """
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _no_data_page(kpis: QualityKPIs) -> str:
    return (
        "# 데이터 품질\n\n"
        f"_지난 {kpis.window_days}일 동안 측정 가능한 게시가 없습니다 "
        f"({kpis.today.isoformat()} 기준)._\n"
    )


def _load_recent_runs(
    path: Path, *, today: date, window_days: int
) -> dict[str, list[dict[str, object]]]:
    if not path.exists():
        return {}
    horizon = today - timedelta(days=window_days - 1)
    out: dict[str, list[dict[str, object]]] = {}
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
                try:
                    parsed_date = date.fromisoformat(td)
                except ValueError:
                    continue
                if parsed_date < horizon or parsed_date > today:
                    continue
                entries: list[dict[str, object]] = [
                    item for item in outcomes if isinstance(item, dict)
                ]
                # u54 — fold the optional ``severities`` map into the
                # outcome list as a synthetic entry so downstream
                # KPI counters can read it through one code path
                # without changing the function signature. Legacy
                # lines (no severities field) get an empty payload —
                # they contribute 0 to severity-based KPIs.
                severities = parsed.get("severities")
                if isinstance(severities, dict):
                    entries.append({"__synthetic__": "severities", "payload": severities})
                out[td] = entries
    except OSError:
        return {}
    return out


def _iter_archive_files(archive_root: Path, *, today: date, window_days: int) -> Iterable[Path]:
    """Yield archive markdown files written within the window."""
    if not archive_root.exists():
        return
    horizon = today - timedelta(days=window_days - 1)
    for md_path in archive_root.rglob("*.md"):
        try:
            iso = md_path.stem
            parsed_date = date.fromisoformat(iso)
        except ValueError:
            continue
        if parsed_date < horizon or parsed_date > today:
            continue
        if "_meta" in md_path.parts or "weekly" in md_path.parts:
            continue
        if md_path.name == "index.md":
            continue
        yield md_path


def _is_data_limited(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(marker in text for marker in _DATA_LIMITED_MARKERS)


def _carries_numeric_figure(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(extract_flaggable_numbers(text))


def _has_verify_downgrade(path: Path) -> bool:
    """u55 — ``True`` iff the briefing carries the verify-downgrade callout."""
    try:
        return _VERIFY_DOWNGRADE_MARKER in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _load_quality_history_rows(path: Path) -> dict[date, QualityHistoryRow]:
    rows: dict[date, QualityHistoryRow] = {}
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
                row = _parse_quality_history_row(parsed)
                if row is not None:
                    rows[row.day] = row
    except OSError:
        return {}
    return rows


def _parse_quality_history_row(payload: dict[str, object]) -> QualityHistoryRow | None:
    raw_day = payload.get("date")
    if not isinstance(raw_day, str):
        return None
    try:
        parsed_day = date.fromisoformat(raw_day)
    except ValueError:
        return None
    source_liveness = _optional_rate(payload.get("source_liveness"))
    figures_presence = _optional_rate(payload.get("figures_presence"))
    fallback_ratio = _optional_rate(payload.get("fallback_ratio"))
    if source_liveness is None or figures_presence is None or fallback_ratio is None:
        return None
    raw_severity = payload.get("worst_severity")
    worst_severity = raw_severity if isinstance(raw_severity, str) else None
    return QualityHistoryRow(
        day=parsed_day,
        source_liveness=source_liveness,
        figures_presence=figures_presence,
        fallback_ratio=fallback_ratio,
        published_segments=_optional_int(payload.get("published_segments")),
        total_items=_optional_int(payload.get("total_items")),
        total_failed_sources=_optional_int(payload.get("total_failed_sources")),
        worst_severity=worst_severity,
        figures_verified=_optional_rate(payload.get("figures_verified")),
        macro_actual_missing_segments=_optional_int(payload.get("macro_actual_missing_segments")),
        required_macro_omitted=_optional_int(payload.get("required_macro_omitted")),
        current_run_zero_item_sources=_optional_int(payload.get("current_run_zero_item_sources"))
        or 0,
        current_run_core_missing_segments=_optional_int(
            payload.get("current_run_core_missing_segments")
        )
        or 0,
        current_run_segments_limited_or_worse=_optional_int(
            payload.get("current_run_segments_limited_or_worse")
        )
        or 0,
        current_run_data_limited_briefings=_optional_int(
            payload.get("current_run_data_limited_briefings")
        )
        or 0,
        current_run_briefings_observed=_optional_int(payload.get("current_run_briefings_observed"))
        or 0,
    )


def _optional_rate(value: object) -> float | None:
    if not isinstance(value, int | float):
        return None
    parsed = float(value)
    if parsed < 0.0 or parsed > 1.0:
        return None
    return parsed


def _optional_int(value: object) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if value < 0:
        return None
    return value


__all__ = [
    "QualityHistoryRow",
    "QualityKPIs",
    "compute_quality_history",
    "compute_quality_kpis",
    "render_quality_page",
]
