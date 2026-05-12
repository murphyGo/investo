"""Unit tests for u57 Step 1 — time-state regex catalogue."""

from __future__ import annotations

import pytest

from investo.briefing.time_state import (
    TIME_STATE_PATTERNS,
    TIME_STATE_PRIORITY,
    detect_time_state,
)


class TestDetectTimeStatePositive:
    """Each TimeState has at least one positive sample."""

    def test_pre_market_korean(self) -> None:
        assert detect_time_state("뉴욕증시 개장 전 약세") == "pre-market"

    def test_pre_market_compact(self) -> None:
        assert detect_time_state("프리마켓 0.3% 하락") == "pre-market"

    def test_open_with_percent(self) -> None:
        assert detect_time_state("코스피 0.5% 상승 출발") == "open"

    def test_open_bare(self) -> None:
        assert detect_time_state("나스닥 상승 출발") == "open"

    def test_open_hyphenated_percent(self) -> None:
        assert detect_time_state("S&P 500 2.5% 하락 출발") == "open"

    def test_close_simple(self) -> None:
        assert detect_time_state("코스피 마감") == "close"

    def test_close_spaced(self) -> None:
        assert detect_time_state("뉴욕증시 장 마감") == "close"

    def test_close_jongga(self) -> None:
        assert detect_time_state("종가 기준 SPX +0.4%") == "close"

    def test_post_close(self) -> None:
        assert detect_time_state("시간 외 거래 NVDA -1.2%") == "post-close"

    def test_post_close_after_market(self) -> None:
        assert detect_time_state("애프터마켓 AAPL 실적 발표") == "post-close"

    def test_scheduled(self) -> None:
        assert detect_time_state("FOMC 5월 13일 발표 예정") == "scheduled"

    def test_scheduled_jeonmang(self) -> None:
        assert detect_time_state("내일 코스피 전망") == "scheduled"


class TestDetectTimeStateNegative:
    """Empty / whitespace / unmatched → None."""

    def test_empty_string(self) -> None:
        assert detect_time_state("") is None

    def test_whitespace_only(self) -> None:
        assert detect_time_state("   ") is None

    def test_no_time_marker(self) -> None:
        assert detect_time_state("애플 신제품 발표") is None


class TestPriorityResolution:
    """When multiple patterns match, the latest factual state wins."""

    def test_open_then_close_resolves_to_close(self) -> None:
        # ``상승 출발 후 하락 마감`` matches BOTH open and close — close
        # wins because it describes the final state.
        assert detect_time_state("상승 출발 후 하락 마감") == "close"

    def test_pre_market_then_open_resolves_to_open(self) -> None:
        assert detect_time_state("개장 전 상승 출발") == "open"

    def test_scheduled_alone(self) -> None:
        # ``발표 예정`` alone → scheduled (lowest priority but only one
        # match).
        assert detect_time_state("FOMC 발표 예정") == "scheduled"


class TestPriorityConstants:
    """Pin the priority ordering — regressions break the conflict resolver."""

    def test_close_higher_than_open(self) -> None:
        assert TIME_STATE_PRIORITY["close"] > TIME_STATE_PRIORITY["open"]

    def test_post_close_higher_than_close_excluded(self) -> None:
        # ``post-close`` (시간 외) is factually after ``close``; the
        # priority maps reflect that.
        assert TIME_STATE_PRIORITY["post-close"] < TIME_STATE_PRIORITY["close"]

    def test_all_states_present(self) -> None:
        assert set(TIME_STATE_PRIORITY) >= set(TIME_STATE_PATTERNS)


class TestIdempotence:
    """NFR-003 — same input → same output."""

    @pytest.mark.parametrize(
        "title",
        [
            "코스피 0.5% 상승 출발",
            "상승 출발 후 하락 마감",
            "FOMC 발표 예정",
            "",
        ],
    )
    def test_repeat_call_same_result(self, title: str) -> None:
        first = detect_time_state(title)
        second = detect_time_state(title)
        assert first == second
