"""u162 event and numeric cards through the real public-document finalizer.

The only phase hooks simulate editorial changes after assembly. Source
validation, numeric resolution, repair, terminal gates and sealing stay real.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from investo._internal.disclaimer import DISCLAIMER
from investo._internal.event_rendering import validate_event_payload
from investo.briefing.event_evidence import build_event_candidates, make_evidence_document
from investo.briefing.event_selection import select_events
from investo.models.briefing import Briefing
from investo.models.event_narratives import (
    EventGenerationPayload,
    EventMeaning,
    EventNarrative,
    EventReaction,
)
from investo.models.events import EventCandidateDraft, EventFactDraft, EventKind, EventSelectionPlan
from investo.models.items import NormalizedItem
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import DOMESTIC_EQUITY, US_EQUITY
from investo.publisher import public_document as public_document_module
from investo.publisher.public_document import (
    FinalizedPublicDocument,
    PublicDocumentContext,
    PublicDocumentDraft,
    PublicDocumentLayout,
    PublicDocumentSupplement,
    _render_supplement_block,
    finalize_public_bundle,
)
from investo.publisher.watchpoint_matrix import DATA_LIMITED_NOTE
from tests.integration.test_event_finalization import _briefing as event_briefing
from tests.integration.test_event_finalization import _context as event_context
from tests.unit.briefing.test_event_evidence import NOW, item, ref
from tests.unit.briefing.test_event_narrative import payload_for
from tests.unit.publisher.test_event_blocks import combined_payload

_WATCH_MARKER = re.compile(r"<!-- investo:watch event:([0-9a-f]{24}) -->")
_NUMERIC_ASSETS = (
    ("^GSPC", "S&P 500", "5600"),
    ("^IXIC", "나스닥 종합", "18000"),
    ("^DJI", "다우존스", "42000"),
    ("AAPL", "애플", "220"),
    ("MSFT", "마이크로소프트", "430"),
    ("NVDA", "엔비디아", "130"),
)


def _watchpoints(markdown: str) -> str:
    return (
        markdown.split("## ⑥ 오늘의 관전 포인트", 1)[1]
        .split("## ⑦ 면책조항", 1)[0]
        .split("<details>", 1)[0]
    )


def _watchpoint_ids(markdown: str) -> tuple[str, ...]:
    return tuple(_WATCH_MARKER.findall(_watchpoints(markdown)))


def _numeric_rows(count: int = 6) -> str:
    return "\n".join(
        f"- {label} 가격; 출처: Yahoo; 현재: 확인 중; "
        "상방: 직전 고가 상회 여부; 하방: 직전 저가 이탈 여부; "
        "관심 영향: 가격 변동 흐름을 확인합니다."
        for _, label, _ in _NUMERIC_ASSETS[:count]
    )


def _anchors() -> tuple[MarketAnchor, ...]:
    return tuple(
        MarketAnchor(
            ticker=ticker,
            close=Decimal(value),
            pct=Decimal("1.25"),
            pct_from_52w_high=Decimal("-10"),
            pct_from_52w_low=Decimal("20"),
            is_ath=False,
        )
        for ticker, _, value in _NUMERIC_ASSETS
    )


def _briefing(payload: EventGenerationPayload, numeric_rows: str = "") -> Briefing:
    briefing = event_briefing(payload)
    watch = numeric_rows or "- 후속 발표; 출처: official; 현재: 발표 상태를 확인합니다."
    return briefing.model_copy(
        update={
            "today_watch": watch,
            "rendered_markdown": briefing.rendered_markdown.replace(
                "## ⑥ 오늘의 관전 포인트\n\n후속 발표를 확인합니다.",
                "## ⑥ 오늘의 관전 포인트\n\n" + watch,
            ),
        }
    )


def _context(payload: EventGenerationPayload, *, numeric: bool = False) -> PublicDocumentContext:
    positioning = NormalizedItem(
        source_name="cftc-cot-positioning",
        category="macro",
        title="합성 지수선물 포지셔닝",
        published_at=NOW,
        raw_metadata={
            "contract_group": "equity_index",
            "contract_label": "E-mini S&P 500",
            "net_contracts": "-2400",
            "net_pct_open_interest": "-4.2",
            "as_of_date": "2026-09-15",
            "release_date": "2026-09-18",
        },
    )
    return replace(
        event_context({US_EQUITY: payload}),
        anchors_by_segment={US_EQUITY: _anchors()} if numeric else {},
        items_by_segment={US_EQUITY: (positioning,)} if numeric else {},
    )


def _finalize(
    payload: EventGenerationPayload, *, numeric_rows: str = "", numeric: bool = False
) -> FinalizedPublicDocument:
    return finalize_public_bundle(
        {US_EQUITY: _briefing(payload, numeric_rows)}, context=_context(payload, numeric=numeric)
    ).documents[0]


def _source_event(
    kind: EventKind,
    *,
    scheduled_next: bool = False,
    source_unknown: bool = False,
) -> EventGenerationPayload:
    """Build synthetic source-addressed negotiation/regulation/service evidence."""
    actor, action, obj, predicate, fact_text, what = {
        "geopolitical": (
            "양국 대표단",
            "협상 재개",
            "",
            "agreement",
            "양국 대표단이 협상을 재개했습니다.",
            "양국 대표단이 협상을 재개했습니다.",
        ),
        "regulation": (
            "의회",
            "법안 의결",
            "",
            "status_change",
            "의회가 소비자 보호 법안을 의결했습니다.",
            "의회가 소비자 보호 법안을 의결했습니다.",
        ),
        "product_service": (
            "Acme",
            "서비스 출시",
            "Cloud Service",
            "launch",
            "Cloud Service가 정식 서비스를 시작했습니다.",
            "Acme는 Cloud Service를 정식 출시했습니다.",
        ),
    }[kind]
    future = "후속 공식 설명회는 다음 주에 열릴 예정입니다."
    doc = make_evidence_document(
        source_name="unknown" if source_unknown else "official",
        title=f"{actor} {action} {obj}".strip(),
        summary=fact_text + (" " + future if scheduled_next else ""),
        url=None if source_unknown else f"https://example.invalid/watch-{kind}",
        published_at=NOW - timedelta(hours=1),
        received_at=NOW,
        event_time=NOW.date(),
        event_time_basis="source_date",
        source_tier="unknown" if source_unknown else "official",
    )
    facts = [
        EventFactDraft.model_validate(
            {"predicate": predicate, "evidence_ref": ref(doc, fact_text, "summary")}
        )
    ]
    if scheduled_next:
        facts.append(
            EventFactDraft(
                predicate="status_change",
                evidence_ref=ref(doc, future, "summary"),
                status="scheduled",
            )
        )
    proposed = EventCandidateDraft(
        item_ids=(1,),
        event_kind=kind,
        actor_refs=(ref(doc, actor),),
        action_refs=(ref(doc, action),),
        object_refs=(ref(doc, obj),) if obj else (),
        relation_refs=(ref(doc, fact_text, "summary"),),
        impact_refs=(ref(doc, fact_text, "summary"),),
        facts=tuple(facts),
        timing="announced",
        relation="direct",
        impact="sector",
    )
    candidates = build_event_candidates([proposed], [item(doc)], [doc], observed_at=NOW)
    plan = select_events(
        candidates,
        [doc],
        segment=US_EQUITY,
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
    )
    (event,) = plan.selected
    narrative = EventNarrative(
        event_id=event.event_id,
        headline=f"{actor} {action}",
        what_happened=what,
        fact_ids=tuple(fact.fact_id for fact in event.change_facts),
        source_refs=event.evidence_refs,
        meaning=EventMeaning(
            text="후속 결정이 이어지는 경우 관련 산업에 영향을 줄 수 있습니다.",
            mode="conditional",
            evidence_refs=(ref(doc, fact_text, "summary"),),
        ),
        reaction=EventReaction(text=None, status="unavailable"),
    )
    payload = EventGenerationPayload(plan=plan, narratives=(narrative,))
    validate_event_payload(payload)
    return payload


def _edit_after_projection(
    monkeypatch: pytest.MonkeyPatch,
    edit: Callable[[str], str],
    *,
    only_domestic: bool = False,
) -> None:
    original = public_document_module._project_assembled_draft

    def project(draft: PublicDocumentDraft, context: PublicDocumentContext) -> PublicDocumentDraft:
        projected = original(draft, context)
        if only_domestic and projected.segment != DOMESTIC_EQUITY:
            return projected
        changed = edit(projected.layout.markdown)
        return public_document_module._draft_with_layout(
            projected,
            PublicDocumentLayout.reindex(changed, expectation=projected.layout.expectation),
        )

    monkeypatch.setattr(public_document_module, "_project_assembled_draft", project)


def _edit_domestic_after_repair(
    monkeypatch: pytest.MonkeyPatch, edit: Callable[[str], str]
) -> None:
    original = public_document_module._repair_projected_draft

    def repair(draft: PublicDocumentDraft, context: PublicDocumentContext) -> PublicDocumentDraft:
        repaired = original(draft, context)
        if draft.segment != DOMESTIC_EQUITY:
            return repaired
        return public_document_module._draft_with_layout(
            repaired,
            PublicDocumentLayout.reindex(
                edit(repaired.layout.markdown), expectation=repaired.layout.expectation
            ),
        )

    monkeypatch.setattr(public_document_module, "_repair_projected_draft", repair)


@pytest.mark.parametrize("kind", ["product_service", "geopolitical", "regulation"])
def test_source_backed_qualitative_current_survives_actual_finalizer(kind: EventKind) -> None:
    payload = _source_event(kind)
    document = _finalize(payload)
    body = _watchpoints(document.briefing.rendered_markdown)
    (event,) = payload.plan.selected
    assert _watchpoint_ids(document.briefing.rendered_markdown) == (event.event_id,)
    assert f"- 현재 상태: [실제] {event.change_facts[0].value_text}" in body
    assert "- 기준 시점:" in body and "2026-09-21" in body
    assert f"https://example.invalid/watch-{kind}" in body
    assert payload.narratives[0].meaning.text in body
    assert "- 다음 확인:" in body
    assert "상방" not in body and "하방" not in body
    assert DATA_LIMITED_NOTE not in body
    assert document.watchpoint_companion.event_rendered == 1
    assert document.watchpoint_companion.numeric_rendered == 0
    assert document.notification_summary.events[0].event_id == event.event_id


def test_same_event_schedule_is_next_check_and_never_the_current_state() -> None:
    payload = _source_event("product_service", scheduled_next=True)
    document = _finalize(payload)
    body = _watchpoints(document.briefing.rendered_markdown)
    actual, scheduled = payload.plan.selected[0].change_facts
    current = next(line for line in body.splitlines() if line.startswith("- 현재 상태:"))
    assert actual.value_text in current
    assert scheduled.value_text not in current
    assert f"- 다음 확인: [예정] {scheduled.value_text}" in body


def test_mixed_composition_keeps_one_event_and_one_verified_numeric_card() -> None:
    payload = combined_payload("product_service", "public_statement", "earnings_result")
    document = _finalize(payload, numeric_rows=_numeric_rows(), numeric=True)
    body = _watchpoints(document.briefing.rendered_markdown)
    assert body.count("#### 관찰 신호:") == 2
    assert _watchpoint_ids(document.briefing.rendered_markdown) == (
        payload.plan.selected[0].event_id,
    )
    assert body.count("- 현재:") == 1
    assert "5,600.00" in body
    assert document.watchpoint_companion.event_attempted == 3
    assert document.watchpoint_companion.numeric_attempted == 6
    assert document.watchpoint_companion.event_rendered == 1
    assert document.watchpoint_companion.numeric_rendered == 1
    assert DATA_LIMITED_NOTE not in body


def test_event_only_composition_uses_two_surviving_events() -> None:
    payload = combined_payload("product_service", "public_statement", "earnings_result")
    document = _finalize(payload)
    assert _watchpoint_ids(document.briefing.rendered_markdown) == tuple(
        event.event_id for event in payload.plan.selected[:2]
    )
    assert _watchpoints(document.briefing.rendered_markdown).count("#### 관찰 신호:") == 2
    assert document.watchpoint_companion.event_rendered == 2
    assert document.watchpoint_companion.numeric_rendered == 0


@pytest.mark.parametrize(
    "numeric_rows,expected_count",
    [(_numeric_rows(), 6), ("", 2)],
    ids=["legacy-six", "fallback-two"],
)
def test_empty_or_off_event_path_preserves_legacy_numeric_bytes(
    numeric_rows: str, expected_count: int
) -> None:
    payload = EventGenerationPayload(plan=EventSelectionPlan(), narratives=())
    context = _context(payload, numeric=True)
    source = _briefing(payload, numeric_rows)
    active = finalize_public_bundle({US_EQUITY: source}, context=context).documents[0]
    off = finalize_public_bundle(
        {US_EQUITY: source}, context=replace(context, event_payloads_by_segment={})
    ).documents[0]
    active_body = _watchpoints(active.briefing.rendered_markdown)
    assert active_body == _watchpoints(off.briefing.rendered_markdown)
    assert active_body.count("#### 관찰 신호:") == expected_count
    assert _watchpoint_ids(active.briefing.rendered_markdown) == ()


@pytest.mark.parametrize("delete_all", [False, True])
def test_post_assembly_event_deletion_reconciles_cards_summaries_and_repeated_bytes(
    monkeypatch: pytest.MonkeyPatch, delete_all: bool
) -> None:
    payload = combined_payload("product_service", "public_statement", "earnings_result")
    removed = payload.plan.selected if delete_all else payload.plan.selected[:1]

    def delete_events(markdown: str) -> str:
        for event in removed:
            markdown = re.sub(
                rf"<!-- investo:block event:{event.event_id} -->.*?"
                rf"<!-- /investo:block event:{event.event_id} -->",
                "",
                markdown,
                flags=re.DOTALL,
            )
        return markdown

    _edit_after_projection(monkeypatch, delete_events)
    context = _context(payload, numeric=True)
    document = finalize_public_bundle(
        {US_EQUITY: _briefing(payload, _numeric_rows())}, context=context
    ).documents[0]
    markdown = document.briefing.rendered_markdown
    for event in removed:
        assert event.event_id not in markdown
        assert event.event_id not in document.surviving_event_ids
    assert tuple(event.event_id for event in document.notification_summary.events) == (
        () if delete_all else tuple(event.event_id for event in payload.plan.selected[1:])
    )
    assert _watchpoint_ids(markdown) == (() if delete_all else (payload.plan.selected[1].event_id,))
    assert _watchpoints(markdown).count("#### 관찰 신호:") == (6 if delete_all else 2)
    repeated = finalize_public_bundle({US_EQUITY: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == markdown
    assert repeated.markdown_sha256 == document.markdown_sha256
    assert repeated.notification_summary == document.notification_summary
    assert repeated.watchpoint_companion == document.watchpoint_companion


@pytest.mark.parametrize("reason", ["source_unknown", "meaning_unavailable", "source_deleted"])
def test_unusable_event_inputs_do_not_invent_a_qualitative_card(reason: str) -> None:
    payload = _source_event("product_service", source_unknown=reason == "source_unknown")
    if reason == "meaning_unavailable":
        payload = payload.model_copy(
            update={
                "narratives": (
                    payload.narratives[0].model_copy(
                        update={"meaning": EventMeaning(text=None, mode="unavailable")}
                    ),
                )
            }
        )
    source = _briefing(payload)
    if reason == "source_deleted":
        source = source.model_copy(
            update={
                "rendered_markdown": re.sub(
                    r"(?m)^- 출처:.*\n", "", source.rendered_markdown, count=1
                )
            }
        )
    document = finalize_public_bundle({US_EQUITY: source}, context=_context(payload)).documents[0]
    assert document.surviving_event_ids == (payload.plan.selected[0].event_id,)
    assert _watchpoint_ids(document.briefing.rendered_markdown) == ()
    assert _watchpoints(document.briefing.rendered_markdown).strip() == DATA_LIMITED_NOTE
    assert document.watchpoint_companion.event_rendered == 0
    assert document.watchpoint_companion.event_limitation_reasons
    if reason == "source_deleted":
        assert document.watchpoint_companion.event_limitation_reasons == ("source_locator_missing",)


def test_detail_limited_event_with_intact_fact_and_locator_keeps_qualitative_card() -> None:
    payload = payload_for()
    event = payload.plan.selected[0].model_copy(update={"evidence_state": "detail_limited"})
    payload = payload.model_copy(
        update={"plan": payload.plan.model_copy(update={"selected": (event,)})}
    )
    document = _finalize(payload)
    assert document.surviving_event_ids == (event.event_id,)
    assert document.notification_summary.events[0].coverage == "detail_limited"
    assert _watchpoint_ids(document.briefing.rendered_markdown) == (event.event_id,)
    assert event.change_facts[0].value_text in _watchpoints(document.briefing.rendered_markdown)
    assert document.watchpoint_companion.event_rendered == 1
    assert "finalization_removed" not in document.watchpoint_companion.event_limitation_reasons


@pytest.mark.parametrize("tag", ["div hidden", 'script type="text/plain"', "pre"])
def test_hidden_or_literal_event_card_cannot_seal_after_real_repair(
    monkeypatch: pytest.MonkeyPatch, tag: str
) -> None:
    payload = payload_for()
    event_id = payload.plan.selected[0].event_id
    card = re.compile(
        rf"<!-- investo:watch event:{event_id} -->.*?<!-- /investo:watch event:{event_id} -->",
        re.DOTALL,
    )

    def hide_card(markdown: str) -> str:
        changed, count = card.subn(
            lambda match: f"<{tag}>\n\n{match.group(0)}\n\n</{tag.split()[0]}>",
            markdown,
        )
        assert count == 1
        return changed

    _edit_domestic_after_repair(monkeypatch, hide_card)
    bundle = finalize_public_bundle(
        {DOMESTIC_EQUITY: _briefing(payload), US_EQUITY: _briefing(payload)},
        context=event_context({DOMESTIC_EQUITY: payload, US_EQUITY: payload}),
    )
    assert tuple(document.segment for document in bundle.documents) == (US_EQUITY,)
    blocked, sibling = bundle.segment_outcomes
    assert blocked.state == "trust_blocked"
    assert "event.evidence_invalid" in blocked.issue_codes
    assert sibling.state == "finalized"
    assert _watchpoint_ids(bundle.documents[0].briefing.rendered_markdown) == (event_id,)


def test_source_locator_removed_after_real_repair_cannot_leave_authoritative_event_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = payload_for()
    event_id = payload.plan.selected[0].event_id
    event_block = re.compile(
        rf"<!-- investo:block event:{event_id} -->.*?<!-- /investo:block event:{event_id} -->",
        re.DOTALL,
    )

    def remove_event_source(markdown: str) -> str:
        changed, count = event_block.subn(
            lambda match: re.sub(r"(?m)^- 출처:.*\n", "", match.group(0), count=1),
            markdown,
        )
        assert count == 1
        assert _watchpoint_ids(changed) == (event_id,)
        assert "[official](https://example.invalid/product_service)" in _watchpoints(changed)
        return changed

    _edit_domestic_after_repair(monkeypatch, remove_event_source)
    bundle = finalize_public_bundle(
        {DOMESTIC_EQUITY: _briefing(payload), US_EQUITY: _briefing(payload)},
        context=event_context({DOMESTIC_EQUITY: payload, US_EQUITY: payload}),
    )
    assert tuple(document.segment for document in bundle.documents) == (US_EQUITY,)
    assert bundle.segment_outcomes[0].state == "trust_blocked"
    assert "event.watchpoint_mismatch" in bundle.segment_outcomes[0].issue_codes
    assert _watchpoint_ids(bundle.documents[0].briefing.rendered_markdown) == (event_id,)


def test_unresolved_numeric_prose_cannot_be_reclassified_as_an_event() -> None:
    payload = payload_for()
    unresolved = (
        "- ETH 해시레이트; 출처: Etherscan; 현재: 999; "
        "상방: 상승 추세 확인; 하방: 하락 추세 확인; 관심 영향: 검증 자료를 확인합니다."
    )
    document = _finalize(payload, numeric_rows=unresolved)
    body = _watchpoints(document.briefing.rendered_markdown)
    assert _watchpoint_ids(document.briefing.rendered_markdown) == (
        payload.plan.selected[0].event_id,
    )
    assert "해시레이트" not in body and "999" not in body
    assert document.watchpoint_companion.event_rendered == 1
    assert document.watchpoint_companion.numeric_rendered == 0


@pytest.mark.parametrize(
    "injected,issue_code",
    [
        ("### 코스피 9.99% 상승\n", "numeric.anchor_assertion"),
        ("반드시 상승합니다.\n", "compliance.language"),
    ],
)
def test_hard_findings_in_event_card_are_not_hidden_by_recomposition_and_sibling_survives(
    monkeypatch: pytest.MonkeyPatch, injected: str, issue_code: str
) -> None:
    payload = payload_for()
    marker = f"<!-- investo:watch event:{payload.plan.selected[0].event_id} -->"

    def inject(markdown: str) -> str:
        assert marker in markdown
        return markdown.replace(marker, marker + "\n" + injected, 1)

    _edit_after_projection(monkeypatch, inject, only_domestic=True)
    context = event_context({DOMESTIC_EQUITY: payload, US_EQUITY: payload})
    bundle = finalize_public_bundle(
        {DOMESTIC_EQUITY: _briefing(payload), US_EQUITY: _briefing(payload)}, context=context
    )
    assert tuple(document.segment for document in bundle.documents) == (US_EQUITY,)
    blocked, surviving = bundle.segment_outcomes
    assert blocked.state == "trust_blocked"
    assert issue_code in blocked.issue_codes
    assert surviving.state == "finalized"
    assert _watchpoint_ids(bundle.documents[0].briefing.rendered_markdown) == (
        payload.plan.selected[0].event_id,
    )


def test_mixed_cap_cannot_hide_raw_domestic_watchpoint_numeric_claim() -> None:
    payload = payload_for()
    domestic = _briefing(payload, _numeric_rows() + "\n\n### 코스닥 9.99% 상승\n")
    context = replace(
        event_context({DOMESTIC_EQUITY: payload, US_EQUITY: payload}),
        anchors_by_segment={
            DOMESTIC_EQUITY: (
                MarketAnchor(
                    ticker="^KOSPI", close=Decimal("2650"), pct=Decimal("1.25"), is_ath=False
                ),
            )
        },
    )
    bundle = finalize_public_bundle(
        {DOMESTIC_EQUITY: domestic, US_EQUITY: _briefing(payload)}, context=context
    )
    assert tuple(document.segment for document in bundle.documents) == (US_EQUITY,)
    assert bundle.segment_outcomes[0].state == "trust_blocked"
    assert "numeric.anchor_assertion" in bundle.segment_outcomes[0].issue_codes


@pytest.mark.parametrize("numeric", [False, True])
def test_event_composition_preserves_supplement_disclaimer_and_second_finalization_bytes(
    numeric: bool,
) -> None:
    payload = combined_payload("product_service", "public_statement")
    supplement = PublicDocumentSupplement(
        supplement_id="us-equity.visual.event-watch",
        kind="visual",
        markdown="![공식 발표 관찰 자료](event-watch.svg)",
        stable_order=1,
    )
    fragment = _render_supplement_block(supplement)
    source = _briefing(payload, _numeric_rows() if numeric else "")
    source = source.model_copy(
        update={
            "rendered_markdown": source.rendered_markdown.replace(
                DISCLAIMER, fragment + "\n\n" + DISCLAIMER
            )
        }
    )
    context = replace(
        _context(payload, numeric=numeric), supplements_by_segment={US_EQUITY: (supplement,)}
    )
    document = finalize_public_bundle({US_EQUITY: source}, context=context).documents[0]
    assert document.briefing.rendered_markdown.count(fragment) == 1
    assert document.briefing.rendered_markdown.count(DISCLAIMER) == 1
    assert len(_watchpoint_ids(document.briefing.rendered_markdown)) == (1 if numeric else 2)
    repeated = finalize_public_bundle({US_EQUITY: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == document.briefing.rendered_markdown
    assert repeated.markdown_sha256 == document.markdown_sha256
    assert repeated.notification_summary == document.notification_summary
    assert repeated.watchpoint_companion == document.watchpoint_companion
