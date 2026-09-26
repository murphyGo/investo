"""Real u144 finalizer with event source slots, containment and sealed DTOs."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from importlib import import_module

import pytest

from investo._internal.data_limited_segment import build_data_limited_briefing
from investo._internal.disclaimer import DISCLAIMER
from investo._internal.event_rendering import render_event_blocks
from investo.models.briefing import Briefing
from investo.models.event_narratives import EventGenerationPayload
from investo.models.events import EventKind, EventSelectionPlan
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import DOMESTIC_EQUITY, US_EQUITY, MarketSegment, SegmentCoverage
from investo.publisher.public_document import PublicDocumentContext, finalize_public_bundle
from tests._helpers.briefings import build_briefing
from tests.unit.briefing.test_event_narrative import payload_for
from tests.unit.publisher.test_event_blocks import TERMINAL_TAMPERING_CASES, combined_payload

_DATE = date(2026, 9, 21)


def _briefing(payload: EventGenerationPayload) -> Briefing:
    markdown = (
        "> **오늘의 결론**: 기존 요약 문장입니다.\n"
        "> **핵심 동인**: 기존 동인 문장입니다.\n"
        "> **주의할 점**: 추가 발표를 확인합니다.\n\n"
        "## ① 요약\n\n수집된 발표를 확인했습니다.\n\n"
        "## ② 전일 핵심 이슈\n\n" + render_event_blocks(payload) + "\n\n"
        "## ③ 섹터/수급 동향\n\n수급 자료를 확인했습니다.\n\n"
        "## ④ 지표·이벤트\n\n일정을 추가로 확인해야 합니다.\n\n"
        "## ⑤ 주요 종목\n\n추가 종목 자료는 확인하지 못했습니다.\n\n"
        "## ⑥ 오늘의 관전 포인트\n\n후속 발표를 확인합니다.\n\n"
        "<details><summary>수집/품질 진단</summary>\n수집 정상\n</details>\n\n" + DISCLAIMER + "\n"
    )
    return build_briefing(target_date=_DATE).model_copy(
        update={
            "market_summary": "GENERATED_ONLY_SENTINEL",
            "key_issues": "GENERATED_ONLY_SENTINEL",
            "rendered_markdown": markdown,
        }
    )


def _context(payloads: dict[MarketSegment, EventGenerationPayload]) -> PublicDocumentContext:
    return PublicDocumentContext(
        target_date=_DATE,
        expected_segments=tuple(
            segment for segment in (DOMESTIC_EQUITY, US_EQUITY) if segment in payloads
        ),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="normal",
                item_count=1,
                source_count=1,
                categories=("news",),
                missing_categories=(),
            )
            for segment in payloads
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_DATE),
        entity_observed_at_utc=datetime(2026, 9, 22, tzinfo=UTC),
        event_payloads_by_segment=payloads,
    )


@pytest.mark.parametrize(
    "kind", ["monetary_policy", "earnings_result", "product_service", "public_statement"]
)
def test_real_finalizer_event_slots_seal_and_repeat_bytes(kind: EventKind) -> None:
    payload = payload_for(kind)
    context = _context({US_EQUITY: payload})
    document = finalize_public_bundle({US_EQUITY: _briefing(payload)}, context=context).documents[0]
    assert document.surviving_event_ids == (payload.narratives[0].event_id,)
    assert (
        tuple(item.event_id for item in document.event_identity_receipts)
        == document.surviving_event_ids
    )
    assert document.event_identity_receipts[0].published_at == context.entity_observed_at_utc
    assert document.notification_summary.conclusion == payload.narratives[0].what_happened
    assert document.notification_summary.events[0].coverage == "supported"
    assert "GENERATED_ONLY_SENTINEL" not in repr(document.notification_summary)
    repeated = finalize_public_bundle({US_EQUITY: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == document.briefing.rendered_markdown
    assert repeated.notification_summary == document.notification_summary


def test_four_terminal_events_have_three_ordered_notification_events() -> None:
    payload = combined_payload(
        "product_service", "public_statement", "earnings_result", "monetary_policy"
    )
    document = finalize_public_bundle(
        {US_EQUITY: _briefing(payload)}, context=_context({US_EQUITY: payload})
    ).documents[0]
    assert len(document.surviving_event_ids) == 4
    assert (
        tuple(event.event_id for event in document.notification_summary.events)
        == document.surviving_event_ids[:3]
    )


def test_removed_first_event_reconciles_every_summary_and_does_not_return() -> None:
    payload = combined_payload("product_service", "public_statement")
    source = _briefing(payload)
    markdown = re.sub(r"(?m)^- 결정/실적/발표 내용:.*\n", "", source.rendered_markdown, count=1)
    source = source.model_copy(update={"rendered_markdown": markdown})
    context = _context({US_EQUITY: payload})
    document = finalize_public_bundle({US_EQUITY: source}, context=context).documents[0]
    assert document.surviving_event_ids == (payload.narratives[1].event_id,)
    assert document.notification_summary.conclusion == payload.narratives[1].what_happened
    assert payload.narratives[0].event_id not in document.briefing.rendered_markdown
    assert payload.narratives[0].what_happened not in document.briefing.rendered_markdown
    repeated = finalize_public_bundle({US_EQUITY: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == document.briefing.rendered_markdown


def test_real_section_containment_removes_all_event_dependents_and_repeats() -> None:
    payload = payload_for()
    source = _briefing(payload)
    source = source.model_copy(
        update={
            "rendered_markdown": source.rendered_markdown.replace(
                "## ③ 섹터/수급 동향",
                "> **그래서 의미는?** 수급 변화가 특정 지역의...\n\n## ③ 섹터/수급 동향",
            )
        }
    )
    context = _context({US_EQUITY: payload})
    document = finalize_public_bundle({US_EQUITY: source}, context=context).documents[0]
    assert any(
        "meaning.truncated_surface" in outcome.issue_codes for outcome in document.block_outcomes
    )
    assert document.surviving_event_ids == ()
    assert document.event_identity_receipts == ()
    assert document.notification_summary.events == ()
    assert (
        document.notification_summary.conclusion == "검증을 통과한 사건 설명을 제공하지 못했습니다."
    )
    assert payload.narratives[0].what_happened not in document.briefing.rendered_markdown
    repeated = finalize_public_bundle({US_EQUITY: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == document.briefing.rendered_markdown


def test_hard_invalid_event_is_not_hidden_by_containment_and_sibling_survives() -> None:
    payload = payload_for()
    invalid = payload.model_copy(
        update={"narratives": (payload.narratives[0].model_copy(update={"fact_ids": ()}),)}
    )
    source = _briefing(payload)
    context = _context({DOMESTIC_EQUITY: invalid, US_EQUITY: payload})
    bundle = finalize_public_bundle({DOMESTIC_EQUITY: source, US_EQUITY: source}, context=context)
    assert tuple(document.segment for document in bundle.documents) == (US_EQUITY,)
    assert "event.fact_unsupported" in bundle.segment_outcomes[0].issue_codes


@pytest.mark.parametrize("case,old,new", TERMINAL_TAMPERING_CASES)
def test_terminal_tampering_cannot_be_hidden_by_repair_and_valid_sibling_survives(
    case: str, old: str, new: str
) -> None:
    payload = payload_for()
    original = _briefing(payload)
    assert old in original.rendered_markdown
    altered = original.rendered_markdown.replace(old, new).replace(
        "## ③ 섹터/수급 동향",
        "> **그래서 의미는?** 수급 변화가 특정 지역의...\n\n## ③ 섹터/수급 동향",
    )
    bad = original.model_copy(update={"rendered_markdown": altered})
    bundle = finalize_public_bundle(
        {DOMESTIC_EQUITY: bad, US_EQUITY: original},
        context=_context({DOMESTIC_EQUITY: payload, US_EQUITY: payload}),
    )
    assert tuple(document.segment for document in bundle.documents) == (US_EQUITY,)
    blocked = bundle.segment_outcomes[0]
    assert blocked.state == "trust_blocked"
    if case in {"foreign_host_ellipsis", "source_label"}:
        assert "event.evidence_invalid" in blocked.issue_codes
    else:
        assert set(blocked.issue_codes) & {
            "event.fact_unsupported",
            "event.entity_unsupported",
            "event.evidence_invalid",
        }
    assert bundle.documents[0].notification_summary.events[0].coverage == "supported"


@pytest.mark.parametrize("actor", ["AT&T", "Acme_Labs"])
def test_terminal_plain_dto_decodes_renderer_escapes_and_repeats_bytes(actor: str) -> None:
    payload = payload_for(actor_override=actor)
    context = _context({US_EQUITY: payload})
    document = finalize_public_bundle({US_EQUITY: _briefing(payload)}, context=context).documents[0]
    narrative = payload.narratives[0]
    summary = document.notification_summary
    assert summary.conclusion == narrative.what_happened
    assert summary.events[0].headline == narrative.headline
    assert summary.events[0].fact_summary == narrative.what_happened
    assert actor in summary.conclusion
    assert "&amp;" not in repr(summary)
    assert "\\" not in repr(summary)
    repeated = finalize_public_bundle({US_EQUITY: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == document.briefing.rendered_markdown
    assert repeated.notification_summary == summary


class _VisibleHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.headings: list[tuple[str, str]] = []
        self.hrefs: list[str] = []
        self._heading: str | None = None
        self._heading_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2"}:
            self._heading = tag
            self._heading_text = []
        if tag == "a":
            self.hrefs.extend(value for name, value in attrs if name == "href" and value)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading:
            self.headings.append((tag, "".join(self._heading_text)))
            self._heading = None

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._heading is not None:
            self._heading_text.append(data)


def test_sealed_markdown_html_keeps_existing_order_sources_and_hides_event_markers() -> None:
    payload = payload_for()
    document = finalize_public_bundle(
        {US_EQUITY: _briefing(payload)}, context=_context({US_EQUITY: payload})
    ).documents[0]
    markdown_renderer = import_module("markdown")
    rendered = markdown_renderer.markdown(
        document.briefing.rendered_markdown, extensions=["tables", "fenced_code", "admonition"]
    )
    parsed = _VisibleHtml()
    parsed.feed(rendered)
    visible = " ".join(parsed.text)
    assert [text for tag, text in parsed.headings if tag == "h1"] == ["2026-09-21 미국 증시 시황"]
    numbered = [
        text for tag, text in parsed.headings if tag == "h2" and text.startswith(tuple("①②③④⑤⑥⑦"))
    ]
    assert numbered == [
        "① 요약",
        "② 전일 핵심 이슈",
        "③ 섹터/수급 동향",
        "④ 지표·이벤트",
        "⑤ 주요 종목",
        "⑥ 오늘의 관전 포인트",
        "⑦ 면책조항",
    ]
    assert visible.index("2026-09-21 미국 증시 시황") < visible.index("오늘의 결론")
    assert visible.index("오늘의 결론") < visible.index("② 전일 핵심 이슈")
    assert payload.narratives[0].what_happened in visible
    assert "official" in visible
    assert "https://example.invalid/product_service" in parsed.hrefs
    assert "매매 권유나 투자 자문이 아닙니다." in visible
    assert "investo:block" not in visible
    assert "investo:events" not in visible
    assert payload.narratives[0].event_id not in visible


@pytest.mark.parametrize("limited", [False, True])
def test_empty_selection_distinguishes_collection_limit_and_repeats(limited: bool) -> None:
    payload = EventGenerationPayload(
        plan=EventSelectionPlan(), narratives=(), collection_limited=limited
    )
    context = _context({US_EQUITY: payload})
    document = finalize_public_bundle({US_EQUITY: _briefing(payload)}, context=context).documents[0]
    assert document.notification_summary.conclusion == (
        "뉴스 수집이 제한되어 중요 사건을 판단하기 어렵습니다."
        if limited
        else "수집된 근거에서 주요 사건을 선정하지 못했습니다."
    )
    repeated = finalize_public_bundle({US_EQUITY: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == document.briefing.rendered_markdown


def test_existing_minimal_fallback_stays_empty_when_sealed_briefing_is_reused() -> None:
    payload = payload_for()
    context = _context({DOMESTIC_EQUITY: payload})
    source = build_data_limited_briefing(_DATE, DOMESTIC_EQUITY)
    baseline_context = replace(context, event_payloads_by_segment={})
    baseline = finalize_public_bundle(
        {DOMESTIC_EQUITY: source}, context=baseline_context
    ).documents[0]
    repeated = finalize_public_bundle(
        {DOMESTIC_EQUITY: baseline.briefing}, context=context
    ).documents[0]
    assert repeated.briefing.rendered_markdown == baseline.briefing.rendered_markdown
    assert repeated.notification_summary.events == ()
    assert repeated.surviving_event_ids == ()


def test_empty_event_context_preserves_legacy_finalizer_bytes() -> None:
    payload = payload_for()
    context = replace(_context({US_EQUITY: payload}), event_payloads_by_segment={})
    source = _briefing(payload)
    first = finalize_public_bundle({US_EQUITY: source}, context=context).documents[0]
    again = finalize_public_bundle({US_EQUITY: source}, context=replace(context)).documents[0]
    assert first.briefing.rendered_markdown == again.briefing.rendered_markdown
    assert first.notification_summary.events == ()
    assert first.surviving_event_ids == ()
