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
_DATA_LIMITED_MARKER: Final[str] = "데이터 부족 안내"


@dataclass(frozen=True, slots=True)
class QualityKPIs:
    """Summary of the trailing-window quality KPIs.

    Each ``*_rate`` is in ``[0.0, 1.0]``; ``runs_observed`` and
    ``briefings_observed`` are non-negative integers used in the
    rendered denominators.
    """

    today: date
    window_days: int
    runs_observed: int
    runs_with_failed_source: int
    briefings_observed: int
    briefings_data_limited: int
    briefings_with_figures: int

    @property
    def source_liveness_rate(self) -> float:
        if self.runs_observed == 0:
            return 0.0
        return (self.runs_observed - self.runs_with_failed_source) / self.runs_observed

    @property
    def figures_presence_rate(self) -> float:
        non_limited = self.briefings_observed - self.briefings_data_limited
        if non_limited <= 0:
            return 0.0
        return self.briefings_with_figures / non_limited

    @property
    def fallback_ratio(self) -> float:
        if self.briefings_observed == 0:
            return 0.0
        return self.briefings_data_limited / self.briefings_observed


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
    KPIs report ``0.0`` rates with zero counters.
    """
    runs = _load_recent_runs(coverage_path, today=today, window_days=window_days)
    runs_with_failed = sum(
        1
        for outcomes in runs.values()
        if any(entry.get("status") == "failed" for entry in outcomes)
    )
    archive_files = list(_iter_archive_files(archive_root, today=today, window_days=window_days))
    briefings_observed = len(archive_files)
    briefings_data_limited = sum(1 for path in archive_files if _is_data_limited(path))
    briefings_with_figures = sum(
        1 for path in archive_files if not _is_data_limited(path) and _carries_numeric_figure(path)
    )
    return QualityKPIs(
        today=today,
        window_days=window_days,
        runs_observed=len(runs),
        runs_with_failed_source=runs_with_failed,
        briefings_observed=briefings_observed,
        briefings_data_limited=briefings_data_limited,
        briefings_with_figures=briefings_with_figures,
    )


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
    lines.append(
        f"| 데이터 부족 폴백 | {_format_pct(kpis.fallback_ratio)} | {kpis.briefings_observed} 건 |"
    )
    lines.append("")
    lines.append(
        "> 이 지표는 매 게시 직후 자동 갱신됩니다. 0% / 100% 같은 극단값은 "
        "관측 데이터가 부족한 초기 운영 상황일 수 있으니 표본 크기를 함께 확인하세요."
    )
    lines.append("")
    return "\n".join(lines)


def _format_pct(value: float) -> str:
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
                out[td] = [item for item in outcomes if isinstance(item, dict)]
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
        return _DATA_LIMITED_MARKER in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _carries_numeric_figure(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(extract_flaggable_numbers(text))


__all__ = [
    "QualityKPIs",
    "compute_quality_kpis",
    "render_quality_page",
]
