"""u97 — evidence-weighted story hierarchy tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from investo.briefing._assembly.markdown_render import (
    _grouped_stage2_rendered_items,
    _render_grouped_sections,
)
from investo.briefing._core.classification import ClassificationResult
from investo.briefing._core.section_planning import (
    SectionPlan,
    build_section_plan,
    story_identity,
)
from investo.briefing.prompts import STAGE2_SYSTEM
from investo.models import NormalizedItem

TARGET = date(2026, 6, 9)


def _item(
    title: str,
    *,
    source_name: str = "test-source",
    category: str = "news",
    days_old: int = 0,
    raw_metadata: dict[str, str | int | float] | None = None,
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category=category,  # type: ignore[arg-type]
        title=title,
        summary=f"{title} summary",
        url=f"https://example.com/{title.replace(' ', '-').casefold()}",
        published_at=datetime(2026, 6, 9, 12, tzinfo=UTC) - timedelta(days=days_old),
        raw_metadata=raw_metadata or {},
    )


def test_story_metadata_marks_required_macro_actual_as_core() -> None:
    macro = _item(
        "Producer Price Index actual",
        source_name="fred-macro",
        category="macro",
        raw_metadata={
            "series_id": "PPIFID",
            "release_date": "2026-06-09",
            "macro_event_status": "actual",
        },
    )
    plan = build_section_plan(
        [macro],
        ClassificationResult(assignments={1: 4}, unassigned=[]),
        target_date=TARGET,
    )

    metadata = plan.story_metadata[story_identity(macro)]
    assert metadata.tier == "core"
    assert "required_macro_actual" in metadata.reasons
    assert metadata.score >= 410
    assert plan.required_macro_items == (macro,)


def test_story_metadata_classifies_supporting_context_and_watchlist_only() -> None:
    supporting = _item("Semiconductor sector flow", category="news")
    context = _item("Background policy calendar", source_name="general-news")
    watchlist = _item(
        "AAPL supplier headline",
        raw_metadata={"watchlist_match": "AAPL", "story_tier": "watchlist_only"},
    )
    plan = build_section_plan(
        [supporting, context, watchlist],
        ClassificationResult(assignments={1: 3, 2: 3, 3: 3}, unassigned=[]),
        target_date=TARGET,
    )

    assert plan.story_metadata[story_identity(supporting)].tier == "supporting"
    assert plan.story_metadata[story_identity(context)].tier == "context"
    assert plan.story_metadata[story_identity(watchlist)].tier == "watchlist_only"


def test_general_market_word_does_not_promote_news_to_core() -> None:
    item = _item(
        "Company enters market competition",
        source_name="general-news",
        category="news",
    )
    plan = build_section_plan(
        [item],
        ClassificationResult(assignments={1: 2}, unassigned=[]),
        target_date=TARGET,
    )

    metadata = plan.story_metadata[story_identity(item)]
    assert metadata.tier != "core"
    assert "segment_native_market_state" not in metadata.reasons


def test_core_evidence_wins_section_cap_over_lower_tiers() -> None:
    low_tier_items = tuple(_item(f"context-{idx}", days_old=idx + 1) for idx in range(20))
    core = _item("S&P 500 close anchor", source_name="yfinance-history", category="price")
    items = [*low_tier_items, core]
    plan = build_section_plan(
        items,
        ClassificationResult(
            assignments={idx: 2 for idx in range(1, len(items) + 1)},
            unassigned=[],
        ),
        target_date=TARGET,
    )

    rendered = _grouped_stage2_rendered_items(plan)
    assert core in rendered
    assert low_tier_items[13] not in rendered
    assert rendered[0] == core


def test_grouped_stage2_prompt_serializes_tier_labels() -> None:
    core = _item("BTC market anchor", source_name="coingecko-global-market", category="price")
    watchlist = _item(
        "SOL watchlist-only note",
        raw_metadata={"watchlist_match": "SOL", "story_tier": "watchlist_only"},
    )
    plan = build_section_plan(
        [watchlist, core],
        ClassificationResult(assignments={1: 2, 2: 2}, unassigned=[]),
        target_date=TARGET,
    )

    rendered = _render_grouped_sections(plan.items_by_section, story_metadata=plan.story_metadata)

    assert rendered.index("[tier=core") < rendered.index("[tier=watchlist_only")
    assert "score=" in rendered
    assert "[coingecko-global-market] BTC market anchor" in rendered


def test_default_section_plan_stays_backward_compatible() -> None:
    item = _item("legacy")
    plan = SectionPlan(
        target_date=TARGET,
        items_by_section={2: (item,), 3: (), 4: (), 5: ()},
        unassigned=(),
    )

    assert _grouped_stage2_rendered_items(plan) == (item,)
    assert "[tier=" not in _render_grouped_sections(plan.items_by_section)


def test_stage2_prompt_bans_mechanical_tier_label_leakage() -> None:
    assert "watchlist_only" in STAGE2_SYSTEM
    assert "copy" in STAGE2_SYSTEM
    assert "tier labels" in STAGE2_SYSTEM
