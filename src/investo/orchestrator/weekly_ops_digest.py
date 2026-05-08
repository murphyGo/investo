"""u31 Step 4 — operator weekly digest.

Once a week (the operator wires the cron schedule via
``INVESTO_WEEKLY_OPS_DIGEST=1`` on a single workflow firing) the
boot path renders a multi-line digest covering the trailing 7 days of
the per-source coverage time series and posts it to the operator
chat. The intent is the operator's 5-minute weekly triage signal: how
many runs hit SUCCESS, which sources have started flaking, are we
burning unusual amounts of GHA minutes.

The digest is read-only — it only consumes the
``archive/_meta/coverage.jsonl`` written by
:mod:`source_health`. It does not require the pipeline to be running
on the same firing.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Final, TypedDict

from investo.orchestrator.source_health import resolve_coverage_path

DIGEST_OPT_IN_ENV: Final[str] = "INVESTO_WEEKLY_OPS_DIGEST"
_DIGEST_WINDOW_DAYS: Final[int] = 7


class _OutcomeEntry(TypedDict, total=False):
    source_name: str
    category: str
    status: str
    item_count: int


def build_weekly_digest_text(
    today: date,
    *,
    path: Path | None = None,
    minutes_used_estimate: float | None = None,
) -> str:
    """Render the operator weekly digest as a Markdown text block.

    Parameters
    ----------
    today:
        Anchor date — the digest reads ``today`` and the 6 prior
        calendar days from the coverage log.
    path:
        Override for the coverage log path; defaults to
        :func:`resolve_coverage_path`.
    minutes_used_estimate:
        Optional per-run GHA minute estimate. The operator can compute
        this from billing tooling and pass it in; we round to one
        decimal. Omit to skip the line entirely.
    """
    target_path = path if path is not None else resolve_coverage_path()
    by_date = _load_recent_lines(target_path, today=today, window_days=_DIGEST_WINDOW_DAYS)
    if not by_date:
        return _no_data_digest(today)

    runs_observed = len(by_date)
    runs_with_failures = sum(
        1
        for outcomes in by_date.values()
        if any(entry.get("status") == "failed" for entry in outcomes)
    )
    success_rate_pct = round(
        100 * (runs_observed - runs_with_failures) / runs_observed,
        1,
    )

    failure_counter: Counter[str] = Counter()
    for outcomes in by_date.values():
        for entry in outcomes:
            if entry.get("status") == "failed":
                name = entry.get("source_name")
                if isinstance(name, str):
                    failure_counter[name] += 1
    top_failed = failure_counter.most_common(5)

    lines = [
        f"📊 Investo 주간 운영 다이제스트 ({today.isoformat()} 기준 7일)",
        "",
        f"- 관측된 실행: {runs_observed}회 / 7일",
        f"- 실패 포함 실행: {runs_with_failures}회",
        f"- 성공률: {success_rate_pct}%",
    ]
    if top_failed:
        lines.append("- 실패 누적 상위 소스:")
        for name, count in top_failed:
            lines.append(f"  - {name} — {count}회")
    if minutes_used_estimate is not None:
        lines.append(f"- GHA 사용 추정: {minutes_used_estimate:.1f}분")
    return "\n".join(lines)


def _no_data_digest(today: date) -> str:
    return (
        f"📊 Investo 주간 운영 다이제스트 ({today.isoformat()} 기준 7일)\n\n"
        "- 관측된 실행 없음 (최근 7일 동안 coverage.jsonl 항목이 없습니다)."
    )


def _load_recent_lines(
    path: Path,
    *,
    today: date,
    window_days: int,
) -> dict[str, list[_OutcomeEntry]]:
    if not path.exists():
        return {}
    horizon = today - timedelta(days=window_days - 1)
    out: dict[str, list[_OutcomeEntry]] = {}
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
                out[td] = [_normalise_entry(entry) for entry in outcomes if isinstance(entry, dict)]
    except OSError:
        return {}
    return out


def _normalise_entry(raw: dict[str, object]) -> _OutcomeEntry:
    entry: _OutcomeEntry = {}
    name = raw.get("source_name")
    category = raw.get("category")
    status = raw.get("status")
    item_count = raw.get("item_count")
    if isinstance(name, str):
        entry["source_name"] = name
    if isinstance(category, str):
        entry["category"] = category
    if isinstance(status, str):
        entry["status"] = status
    if isinstance(item_count, int):
        entry["item_count"] = item_count
    return entry


def is_opt_in(raw: str | None = None) -> bool:
    """Return True iff the operator explicitly opted into the digest."""
    import os

    value = raw if raw is not None else os.environ.get(DIGEST_OPT_IN_ENV, "").strip()
    return value == "1"


def iter_failed_sources(
    by_date: Iterable[list[_OutcomeEntry]],
) -> Counter[str]:
    """Public helper for tests — count failures per source over the window."""
    out: Counter[str] = Counter()
    for outcomes in by_date:
        for entry in outcomes:
            if entry.get("status") == "failed":
                name = entry.get("source_name")
                if isinstance(name, str):
                    out[name] += 1
    return out


__all__ = [
    "DIGEST_OPT_IN_ENV",
    "build_weekly_digest_text",
    "is_opt_in",
    "iter_failed_sources",
]
