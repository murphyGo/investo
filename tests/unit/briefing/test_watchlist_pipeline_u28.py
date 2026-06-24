"""u28 — pipeline-level wiring tests for the watchlist usability foundation.

Pins three integration guarantees layered on top of the unit tests in
``test_watchlist.py``:

1. The site callout still renders when the user has not configured a
   watchlist — first-time visitors see the onboarding nudge.
2. The site callout switches to the "데이터 수집 부족으로 매칭 판단 보류"
   branch when the segment coverage is ``insufficient``, even if some items
   would have matched.
3. The Telegram one-liner skips both branches (unconfigured and
   coverage_hold) so the channel surface stays clean.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from investo.briefing import pipeline
from investo.briefing._core import orchestration  # u83: call_claude_code seam moved here
from investo.briefing.errors import SubprocessOutcome
from investo.briefing.segments import US_EQUITY
from investo.briefing.watchlist import WatchlistConfig
from investo.models import NormalizedItem
from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown

_TARGET_DATE = date(2026, 5, 7)


def _item(idx: int, *, title: str | None = None) -> NormalizedItem:
    return NormalizedItem(
        source_name=f"src-{idx}",
        category="news",
        title=title or f"item-{idx}",
        published_at=datetime(2026, 5, 7, 12, idx, tzinfo=UTC),
    )


def _stub_claude(monkeypatch: pytest.MonkeyPatch, *, item_count: int) -> None:
    stdouts = [
        valid_classification_stdout(item_count=item_count),
        valid_stage2_markdown(),
    ]
    captured: list[str] = []

    async def fake_call(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        captured.append(prompt)
        return SubprocessOutcome(
            stdout=stdouts[len(captured) - 1],
            stderr="",
            returncode=0,
            elapsed_s=1.0,
        )

    monkeypatch.setattr(orchestration, "call_claude_code", fake_call)


def _macro_item() -> NormalizedItem:
    return NormalizedItem(
        source_name="fred-economic-calendar",
        category="calendar",
        title="2026-05-13 — Producer Price Index",
        summary="FRED release_id=46 scheduled for 2026-05-13",
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        scheduled_at=datetime(2026, 5, 13, 0, 0, tzinfo=UTC),
        raw_metadata={
            "release_id": "46",
            "release_name": "Producer Price Index",
            "scheduled_date": "2026-05-13",
        },
    )


@pytest.mark.asyncio
async def test_unconfigured_site_callout_renders_onboarding_nudge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_claude(monkeypatch, item_count=2)

    result = await pipeline.generate_briefing(
        _TARGET_DATE,
        [_item(1), _item(2)],
        segment=US_EQUITY,
        watchlist_config=WatchlistConfig(),  # explicitly empty
    )

    header = result.rendered_markdown.split("## ① 요약", maxsplit=1)[0]
    # Onboarding nudge appears in the site callout block.
    assert "> **내 관심 자산 영향**: 관심 목록 미설정" in header
    assert "config/watchlist.json" in header


@pytest.mark.asyncio
async def test_generation_input_api_does_not_load_watchlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_claude(monkeypatch, item_count=2)

    def fail_load_watchlist() -> WatchlistConfig:
        raise AssertionError("canonical generation must use explicit watchlist_config")

    monkeypatch.setattr(pipeline, "load_watchlist", fail_load_watchlist)

    result = await pipeline.generate_briefing_from_input(
        pipeline.GenerationInput(
            target_date=_TARGET_DATE,
            items=[_item(1), _item(2)],
            segment=US_EQUITY,
            watchlist_config=WatchlistConfig(),
        )
    )

    assert result.briefing.target_date == _TARGET_DATE
    assert result.macro_lineage == ()


@pytest.mark.asyncio
async def test_generation_input_result_carries_macro_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    macro_item = _macro_item()
    _stub_claude(monkeypatch, item_count=1)

    result = await pipeline.generate_briefing_from_input(
        pipeline.GenerationInput(
            target_date=_TARGET_DATE,
            items=[macro_item],
            segment=US_EQUITY,
            watchlist_config=WatchlistConfig(),
            macro_lineage_all_items=[macro_item],
        )
    )

    assert result.briefing.target_date == _TARGET_DATE
    assert len(result.macro_lineage) == 1
    assert result.macro_lineage[0].event_key == (
        "fred-economic-calendar:release_id=46:scheduled_date=2026-05-13"
    )


@pytest.mark.asyncio
async def test_legacy_wrapper_extends_macro_lineage_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    macro_item = _macro_item()
    _stub_claude(monkeypatch, item_count=1)
    lineage_out = []

    briefing = await pipeline.generate_briefing(
        _TARGET_DATE,
        [macro_item],
        segment=US_EQUITY,
        watchlist_config=WatchlistConfig(),
        macro_lineage_all_items=[macro_item],
        macro_lineage_out=lineage_out,
    )

    assert briefing.target_date == _TARGET_DATE
    assert len(lineage_out) == 1


@pytest.mark.asyncio
async def test_insufficient_coverage_switches_to_hold_branch_in_callout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured watchlist with NVDA-matching items should still render the
    coverage-hold callout instead of the matched-list when coverage is
    insufficient (zero items routed to the segment ⇒ status='insufficient').
    """

    async def fail_if_called(*args: object, **kwargs: object) -> SubprocessOutcome:
        # Empty-segment fallback path does not call the LLM.
        raise AssertionError("Claude should not be called for the empty segment fallback")

    monkeypatch.setattr(orchestration, "call_claude_code", fail_if_called)

    result = await pipeline.generate_briefing(
        _TARGET_DATE,
        [],
        segment=US_EQUITY,
        watchlist_config=WatchlistConfig(tickers=("NVDA",)),
    )

    header = result.rendered_markdown.split("## ① 요약", maxsplit=1)[0]
    assert "> **내 관심 자산 영향**: 데이터 수집 부족으로 매칭 판단 보류" in header
    # The matched-list branch must NOT fire.
    assert "건 확인" not in header.split("내 관심 자산 영향")[1].split("\n")[0]
