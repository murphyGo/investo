"""u52 — archive parser shape pins.

Six DoD-mandated shapes:

* C2(a) normal 1-day walk-back.
* C2(b) 3-day walk-back skipping weekend.
* C2(c) Sat/Sun cursor skipped silently.
* C2(d) missing file silently skipped.
* C2(e) §⑥ heading present but body empty → no items extracted.
* C2(f) malformed numbered list lines (no ``**bold**``) → skipped.

Plus C3 (substring match → resolved) and C4 (future expected_date →
carried_over).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from investo.briefing.carryover_parser import (
    DEFAULT_LOOKBACK_DAYS,
    ENV_LOOKBACK_DAYS,
    MAX_LOOKBACK_DAYS,
    load_carryover,
    resolve_lookback_days,
)
from investo.models import NormalizedItem


def _write_archive(
    archive_root: Path,
    segment: str,
    day: date,
    body: str,
) -> Path:
    path = archive_root / segment / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


_HEADER_LINES = (
    "# 2026-05-07 미국 증시 시황\n"
    "\n"
    "**기준 시각**: 2026-05-07 NY · [2026-05-07T04:00Z, 2026-05-08T04:00Z)\n"
    "\n"
    "> **오늘의 결론**: 어제 미국 증시는 보합. [관망]\n"
    "> **핵심 동인**: 거시 지표 부재.\n"
    "> **주의할 점**: FOMC 의사록 대기.\n"
    "\n"
)


def _briefing_md(items_block: str, lookahead_block: str = "") -> str:
    return (
        _HEADER_LINES
        + "## ① 요약\n\n오늘의 요약 본문.\n\n"
        + "## ② 전일 핵심 이슈\n\n전일 본문.\n\n"
        + "## ③ 섹터/수급 동향\n\n섹터 본문.\n\n"
        + "## ④ 지표·이벤트\n\n지표 본문.\n\n"
        + "## ⑤ 주요 종목\n\n종목 본문.\n\n"
        + "## ⑥ 오늘의 관전 포인트\n\n"
        + items_block
        + ("\n" + lookahead_block if lookahead_block else "")
        + "\n"
    )


def test_parser_normal_one_day_walkback(tmp_path: Path) -> None:
    """C2(a) — yesterday's §⑥ numbered items become unresolved carryover."""
    yesterday = date(2026, 5, 7)
    today = date(2026, 5, 8)
    _write_archive(
        tmp_path,
        "us-equity",
        yesterday,
        _briefing_md(
            "1. **ARM 어닝**: 분기 실적 발표 예고.\n2. **FOMC 의사록**: 다음 주 공개 예정.\n"
        ),
    )

    result = load_carryover(tmp_path, "us-equity", today, lookback=1)
    assert result.lookback_days == 1
    assert len(result.prior_unresolved) == 2
    topics = {item.ticker_or_topic for item in result.prior_unresolved}
    assert topics == {"ARM 어닝", "FOMC 의사록"}
    # event_type classifier sanity
    types = {item.event_type for item in result.prior_unresolved}
    assert "earnings" in types
    assert "fed" in types


def test_parser_three_day_walkback_skips_weekend(tmp_path: Path) -> None:
    """C2(b) + C2(c) — 3-day walk-back hops over the weekend silently."""
    # Today = Monday 2026-05-11. Walking back 3 trading days hits
    # Fri 05-08, Thu 05-07, Wed 05-06 (skipping Sat/Sun).
    today = date(2026, 5, 11)
    for day in (date(2026, 5, 8), date(2026, 5, 7), date(2026, 5, 6)):
        _write_archive(
            tmp_path,
            "us-equity",
            day,
            _briefing_md(f"1. **EVENT-{day.isoformat()}**: 본문.\n"),
        )

    result = load_carryover(tmp_path, "us-equity", today, lookback=3)
    assert result.lookback_days == 3
    assert len(result.prior_unresolved) == 3
    originated = {item.originated_date for item in result.prior_unresolved}
    assert originated == {date(2026, 5, 8), date(2026, 5, 7), date(2026, 5, 6)}


def test_parser_missing_file_silent_skip(tmp_path: Path) -> None:
    """C2(d) — a yesterday with no archive file yields empty carryover."""
    today = date(2026, 5, 8)
    result = load_carryover(tmp_path, "us-equity", today, lookback=3)
    assert result.is_empty
    assert result.lookback_days == 0


def test_parser_empty_section_six(tmp_path: Path) -> None:
    """C2(e) — §⑥ present but no numbered items → empty bundle."""
    yesterday = date(2026, 5, 7)
    today = date(2026, 5, 8)
    _write_archive(
        tmp_path,
        "us-equity",
        yesterday,
        _briefing_md("**금일 핵심 확인 사항**\n\n관전 포인트가 없습니다.\n"),
    )
    result = load_carryover(tmp_path, "us-equity", today, lookback=1)
    # lookback_days reflects the day was loaded; just no items extracted.
    assert result.lookback_days == 1
    assert result.is_empty


def test_parser_malformed_list_skipped(tmp_path: Path) -> None:
    """C2(f) — a numbered line without ``**bold**`` is ignored."""
    yesterday = date(2026, 5, 7)
    today = date(2026, 5, 8)
    _write_archive(
        tmp_path,
        "us-equity",
        yesterday,
        _briefing_md("1. 토픽 없이 본문만 있음 (bold prefix 누락).\n2. **OK 토픽**: 정상 본문.\n"),
    )
    result = load_carryover(tmp_path, "us-equity", today, lookback=1)
    assert len(result.prior_unresolved) == 1
    assert result.prior_unresolved[0].ticker_or_topic == "OK 토픽"


def test_parser_resolves_status_when_candidate_matches(tmp_path: Path) -> None:
    """C3 — today's candidates carry ARM → carryover ARM flips to resolved."""
    yesterday = date(2026, 5, 7)
    today = date(2026, 5, 8)
    _write_archive(
        tmp_path,
        "us-equity",
        yesterday,
        _briefing_md(
            "1. **ARM 어닝**: 분기 실적 발표 예고.\n2. **TSLA 컨퍼런스콜**: 가이던스 갱신 여부.\n"
        ),
    )
    candidates = [
        NormalizedItem(
            source_name="yahoo-finance-news",
            category="news",
            title="ARM Holdings reports Q4 earnings beat",
            published_at=datetime(2026, 5, 8, 12, 0, tzinfo=UTC),
        ),
    ]
    result = load_carryover(
        tmp_path,
        "us-equity",
        today,
        candidates=candidates,
        lookback=1,
    )
    resolved_topics = {item.ticker_or_topic for item in result.prior_resolved}
    unresolved_topics = {item.ticker_or_topic for item in result.prior_unresolved}
    assert "ARM 어닝" in resolved_topics
    assert "TSLA 컨퍼런스콜" in unresolved_topics


def test_parser_future_expected_date_marks_carried_over(tmp_path: Path) -> None:
    """C4 — lookahead-table row whose expected_date > today → carried_over."""
    yesterday = date(2026, 5, 7)
    today = date(2026, 5, 8)
    lookahead = (
        "**이번 주·이번 달 주요 일정**\n"
        "\n"
        "| 날짜 | 이벤트 |\n"
        "|------|--------|\n"
        "| 2026-05-20 | [FOMC 의사록](https://example.com) 공개 |\n"
        "| 2026-05-07 | 지나간 이벤트 — 미확인 |\n"
    )
    _write_archive(
        tmp_path,
        "us-equity",
        yesterday,
        _briefing_md("", lookahead_block=lookahead),
    )
    result = load_carryover(tmp_path, "us-equity", today, lookback=1)
    statuses = {item.expected_date: item.status for item in result.prior_unresolved}
    # Future date → carried_over.
    assert statuses[date(2026, 5, 20)] == "carried_over"
    # Past date with no candidate match → unresolved.
    assert statuses[date(2026, 5, 7)] == "unresolved"


def test_parser_isolates_segment(tmp_path: Path) -> None:
    """A domestic-equity archive does not bleed into a us-equity walk-back."""
    yesterday = date(2026, 5, 7)
    today = date(2026, 5, 8)
    _write_archive(
        tmp_path,
        "domestic-equity",
        yesterday,
        _briefing_md("1. **KOSPI 200**: 변동성 확대.\n"),
    )
    result = load_carryover(tmp_path, "us-equity", today, lookback=1)
    assert result.is_empty


def test_parser_skips_malformed_archive_without_conclusion(tmp_path: Path) -> None:
    """An archive missing the conclusion + watermark anchors is ignored.

    Defensive — DEBT-060 chokepoint requires us to gate on the
    canonical anchors so a corrupted file cannot inject phantom
    events.
    """
    yesterday = date(2026, 5, 7)
    today = date(2026, 5, 8)
    _write_archive(
        tmp_path,
        "us-equity",
        yesterday,
        "## ⑥ 오늘의 관전 포인트\n\n1. **NOISE**: 본문.\n",
    )
    result = load_carryover(tmp_path, "us-equity", today, lookback=1)
    assert result.is_empty


def test_resolve_lookback_days_clamps_env(monkeypatch: object) -> None:
    """Out-of-range env override falls back to the default with a WARNING."""
    # Negative
    assert resolve_lookback_days({ENV_LOOKBACK_DAYS: "-1"}) == DEFAULT_LOOKBACK_DAYS
    # Above max
    assert (
        resolve_lookback_days({ENV_LOOKBACK_DAYS: str(MAX_LOOKBACK_DAYS + 1)})
        == DEFAULT_LOOKBACK_DAYS
    )
    # Non-numeric
    assert resolve_lookback_days({ENV_LOOKBACK_DAYS: "abc"}) == DEFAULT_LOOKBACK_DAYS
    # Blank
    assert resolve_lookback_days({ENV_LOOKBACK_DAYS: ""}) == DEFAULT_LOOKBACK_DAYS
    # Valid in-range value passes through
    assert resolve_lookback_days({ENV_LOOKBACK_DAYS: "5"}) == 5
