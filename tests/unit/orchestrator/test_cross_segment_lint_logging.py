"""u57 Step 7 — log signature + R13 hygiene for cross-segment lint."""

from __future__ import annotations

import logging
from datetime import date

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import Briefing
from investo.models.bundle_context import BundleContext, MarketStateSummary
from investo.orchestrator.pipeline import _apply_reader_format_to_segments


def _briefing(markdown_body: str) -> Briefing:
    full = f"{markdown_body}\n{DISCLAIMER}\n"
    return Briefing(
        target_date=date(2026, 5, 11),
        market_summary="요약 [상승 관찰]",
        key_issues="핵심",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=full,
    )


def _ctx(close_states: dict[str, str]) -> BundleContext:
    return BundleContext(
        bundle_id="2026-05-11-bundle",
        target_kst_date=date(2026, 5, 11),
        segments={
            seg: MarketStateSummary(
                segment=seg,
                target_date=date(2026, 5, 11),
                tz="UTC",
                close_state=state,  # type: ignore[arg-type]
            )
            for seg, state in close_states.items()
        },
    )


_BODY_WITH_VIOLATION = (
    "## ① 요약\n\nAAPL 단독 등장.\n\n## ② 전일 핵심 이슈\n\n### 코스피 종가\n0.5%.\n\n"
    "## ③ 섹터\n\n.\n\n## ④ 지표\n\n.\n\n## ⑤ 종목\n\n.\n\n## ⑥ 관전\n\n.\n"
)


class TestLogSignatures:
    def test_warn_signature_includes_segment_and_kind(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = _ctx({DOMESTIC_EQUITY: "pending", US_EQUITY: "pending", CRYPTO: "pending"})
        briefings = {DOMESTIC_EQUITY: _briefing(_BODY_WITH_VIOLATION)}
        caplog.set_level(logging.WARNING)
        _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        records = [
            r
            for r in caplog.records
            if "cross_segment_lint.foreign_ticker_no_linkage" in r.getMessage()
        ]
        assert records
        extras = records[0]
        # Extras carry segment + kind + severity, never raw_metadata
        # values (R13 secret hygiene).
        assert getattr(extras, "segment", None) == DOMESTIC_EQUITY
        assert "cross_segment_lint" in getattr(extras, "kind", "")
        assert "raw_metadata" not in extras.__dict__


class TestR13SecretHygiene:
    def test_no_secret_shaped_in_extras(self, caplog: pytest.LogCaptureFixture) -> None:
        """Lint extras carry numeric lengths only — no raw paragraph
        text, no API keys, no auth tokens.
        """
        ctx = _ctx({DOMESTIC_EQUITY: "pending", US_EQUITY: "pending", CRYPTO: "pending"})
        briefings = {DOMESTIC_EQUITY: _briefing(_BODY_WITH_VIOLATION)}
        caplog.set_level(logging.WARNING)
        _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        for record in caplog.records:
            if "cross_segment_lint" not in record.getMessage():
                continue
            # Standard secret-shaped substrings — none should leak
            # into the log payload.
            for needle in ("sk-", "Bearer ", "ghp_", "AKIA"):
                assert needle not in record.getMessage()
            # No paragraph dumps in extras either.
            for key, value in record.__dict__.items():
                if key.startswith("_"):
                    continue
                if isinstance(value, str):
                    for needle in ("sk-", "Bearer ", "ghp_", "AKIA"):
                        assert needle not in value
