"""New visual text and source links remain within existing terminal trust ownership."""

from datetime import date
from decimal import Decimal

from investo._internal.numeric_verify import find_body_value
from investo.models.segments import DOMESTIC_EQUITY, US_EQUITY
from investo.publisher.anchor_assertion_gate import scan_anchor_assertions
from investo.publisher.public_document import _repair_projected_draft
from investo.visuals.cards import (
    MarketSnapshotCardInput,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
)
from investo.visuals.html_cards import render_card_html
from tests.unit.publisher.test_public_document_containment_u144 import (
    _canonical_markdown,
    _projected_draft,
)


def test_html_numeric_assertion_is_not_hidden_from_existing_anchor_gate() -> None:
    html = '<section class="investo-data-card"><p>코스피는 2,700.00으로 마감했습니다.</p></section>'
    findings = scan_anchor_assertions(html, segment=DOMESTIC_EQUITY, available_symbols=())
    assert findings


def test_bad_source_link_removes_entire_html_and_svg_supplement() -> None:
    card = WatchlistRelevanceCardInput(
        target_date=date(2026, 7, 21),
        segment=DOMESTIC_EQUITY,
        configured=True,
        total_matches=1,
        rows=(
            WatchlistRelevanceRow(
                term="자산",
                kind="직접 관련",
                source_name="출처",
                title="근거 기사",
                url="https://example.invalid/path/...",
            ),
        ),
    )
    body = render_card_html(card) + "\n\n![원본 SVG](valid.svg)"
    markdown = _canonical_markdown(
        watchpoint_body="- 확인할 조건", supplements=(("visual", "html-card", body),)
    )
    projected, context = _projected_draft(markdown, supplement_ids=("html-card",))
    region = next(r for r in projected.layout.regions if r.region_id == "visual:html-card")
    assert region.projection_policy == "reader_visible"
    repaired = _repair_projected_draft(projected, context)
    assert "근거 기사" not in repaired.layout.markdown
    assert "valid.svg" not in repaired.layout.markdown
    assert any(
        o.region_id == "visual:html-card" and o.disposition == "omitted"
        for o in repaired.block_outcomes
    )


def test_entity_escaping_does_not_hide_ampersand_financial_alias_or_change_offsets() -> None:
    card = MarketSnapshotCardInput(
        target_date=date(2026, 7, 21),
        segment=US_EQUITY,
        coverage_status="partial",
        conclusion="S&P 500은 6,100.00으로 마감했습니다.",
        main_driver="S&P 500은 10% 급락했습니다.",
        caution="조건 확인.",
    )
    html = render_card_html(card)
    assert "S&amp;P" in html
    assert find_body_value(html, "spx_close") == Decimal("6100.00")
    findings = scan_anchor_assertions(html, segment=US_EQUITY, available_symbols=())
    assert findings
    assert all(html[f.start : f.end].strip() == f.sentence for f in findings)
    assert not scan_anchor_assertions(html, segment=US_EQUITY, available_symbols=("^GSPC",))
