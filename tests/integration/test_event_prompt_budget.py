"""Exact evidence rows survive the price-heavy Stage 2 boundary."""

from datetime import timedelta

from investo.briefing._core.classification import EventClassificationResult
from investo.briefing._core.section_planning import build_section_plan
from investo.briefing.event_evidence import prepare_evidence_documents
from investo.briefing.event_prompt import prepare_event_selection, render_event_prompt_evidence
from investo.models import NormalizedItem
from tests.unit.briefing.test_event_evidence import NOW, document, draft, item


def test_fourteen_prices_do_not_displace_two_eligible_events() -> None:
    news = [item(document(path=path)) for path in ("one", "two")]
    prices = [
        NormalizedItem(
            source_name="price", category="price", title=f"PRICE_{i:02}", published_at=NOW
        )
        for i in range(14)
    ]
    items = [*prices, *news]
    docs = prepare_evidence_documents(items, received_at=NOW)
    classification = EventClassificationResult(
        schema_version=2,
        assignments={i: 2 for i in range(1, 17)},
        unassigned=[15, 16],
        events=(draft(docs[14], "A", 15), draft(docs[15], "B", 16)),
    )
    events = prepare_event_selection(
        classification,
        items,
        docs,
        observed_at=NOW,
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
        segment="us-equity",
    )
    result = render_event_prompt_evidence(
        build_section_plan(items, classification, NOW.date()),
        events,
        items,
        docs,
        segment="us-equity",
    )
    assert len(events.selected) == 2
    assert events.evidence_row_count == 2
    assert result.section_two_row_count == result.row_count == 14
    assert "Product A" in events.protected_block and "Product B" in events.protected_block
    assert result.grouped_sections.count("PRICE_") == 12
    assert "Product" not in result.grouped_sections + result.unassigned
    assert len(events.protected_block.encode()) <= 8192
