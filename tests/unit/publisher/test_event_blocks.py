"""Synthetic event terminal ownership and content contracts."""

from __future__ import annotations

import re

import pytest

from investo._internal.event_rendering import event_summary_lines, render_event_blocks
from investo.models.event_narratives import EventGenerationPayload
from investo.models.events import EventKind, EventSelectionPlan
from investo.models.public_notification import PublicEventSummary
from investo.publisher.event_blocks import (
    event_hard_issue_codes,
    reconcile_event_blocks,
    reconcile_event_summaries,
    terminal_events,
)
from tests.unit.briefing.test_event_narrative import payload_for

TERMINAL_TAMPERING_CASES = (
    (
        "meaning",
        "- 의미: 수요가 늘어나는 경우 기업 활동에 영향을 줄 수 있습니다.",
        "- 의미: Another의 매출이 999% 늘어날 수 있습니다.",
    ),
    (
        "reaction",
        "- 시장 반응: 시장 반응은 확인하지 못했습니다.",
        "- 시장 반응: Another의 주가가 999% 상승했습니다.",
    ),
    ("headline", "### Acme 제품 출시", "### Another 제품 출시"),
    (
        "foreign_host_ellipsis",
        "https://example.invalid/product_service",
        "https://untrusted.invalid/.../forged",
    ),
    (
        "source_label",
        "[official](https://example.invalid/product_service)",
        "[Reuters](https://example.invalid/product_service)",
    ),
)


def combined_payload(*kinds: EventKind) -> EventGenerationPayload:
    inputs = tuple(payload_for(kind) for kind in kinds)
    documents = tuple(doc for payload in inputs for doc in payload.plan.evidence_documents)
    return EventGenerationPayload(
        plan=EventSelectionPlan(
            selected=tuple(event for payload in inputs for event in payload.plan.selected),
            evidence_documents=documents,
            evidence_row_count=len(documents),
        ),
        narratives=tuple(narrative for payload in inputs for narrative in payload.narratives),
    )


def event_markdown(payload: EventGenerationPayload) -> str:
    return "## ② 전일 핵심 이슈\n\n" + render_event_blocks(payload) + "\n\n## ③ 섹터/수급 동향\n"


@pytest.mark.parametrize(
    "kind", ["monetary_policy", "earnings_result", "product_service", "public_statement"]
)
def test_complete_terminal_event_preserves_literal_facts_and_summary(kind: EventKind) -> None:
    payload = payload_for(kind)
    markdown = event_markdown(payload)
    assert event_hard_issue_codes(markdown, payload) == ()
    (event,) = terminal_events(markdown, payload)
    assert event.coverage == "supported"
    assert event.first_sentence == payload.narratives[0].what_happened
    assert event.notification_summary().fact_summary == event.what_happened
    assert all(fact.value_text in markdown for fact in payload.plan.selected[0].change_facts)


@pytest.mark.parametrize(
    "label", ["시점", "주체", "무슨 일이 있었나", "결정/실적/발표 내용", "의미", "시장 반응"]
)
def test_missing_terminal_slot_cannot_survive_on_marker_or_url(label: str) -> None:
    payload = payload_for()
    markdown = re.sub(rf"(?m)^- {label}:.*\n", "", event_markdown(payload))
    assert event_hard_issue_codes(markdown, payload) == ()
    assert terminal_events(markdown, payload) == ()
    repaired, survivors = reconcile_event_blocks(
        markdown, payload, surviving_event_ids=(payload.narratives[0].event_id,)
    )
    assert survivors == ()
    assert "investo:block event:" not in repaired
    assert payload.narratives[0].what_happened not in repaired


def test_removed_source_locator_downgrades_without_fabricating_source() -> None:
    payload = payload_for()
    markdown = re.sub(r"(?m)^- 출처:.*\n", "", event_markdown(payload))
    assert event_hard_issue_codes(markdown, payload) == ()
    assert terminal_events(markdown, payload)[0].coverage == "detail_limited"


@pytest.mark.parametrize("case,old,new", TERMINAL_TAMPERING_CASES)
def test_replaced_terminal_claims_preserve_hard_findings(case: str, old: str, new: str) -> None:
    payload = payload_for()
    original = event_markdown(payload)
    assert old in original
    codes = set(event_hard_issue_codes(original.replace(old, new), payload))
    if case in {"foreign_host_ellipsis", "source_label"}:
        assert "event.evidence_invalid" in codes
    else:
        assert codes & {
            "event.fact_unsupported",
            "event.entity_unsupported",
            "event.evidence_invalid",
        }


def test_canonical_source_url_prefix_truncation_remains_presentation_limited() -> None:
    payload = payload_for()
    markdown = event_markdown(payload).replace(
        "https://example.invalid/product_service", "https://example.invalid/prod..."
    )
    assert event_hard_issue_codes(markdown, payload) == ()
    assert terminal_events(markdown, payload)[0].coverage == "detail_limited"


@pytest.mark.parametrize(
    "old,new,code",
    [
        ("주체: Acme", "주체: Another", "event.entity_unsupported"),
        (
            "[실제] Product A가 정식 출시됐습니다.",
            "[실제] Product A가 999개 출시됐습니다.",
            "event.fact_unsupported",
        ),
        (
            "https://example.invalid/product_service",
            "https://untrusted.invalid/forged",
            "event.evidence_invalid",
        ),
    ],
)
def test_tampered_terminal_factual_slots_are_hard_findings(old: str, new: str, code: str) -> None:
    payload = payload_for()
    assert code in event_hard_issue_codes(event_markdown(payload).replace(old, new), payload)


def test_terminal_summary_content_matches_shared_b6_policy_without_reading_generated_fields() -> (
    None
):
    payload = combined_payload("product_service", "public_statement")
    markdown = event_markdown(payload)
    values = event_summary_lines(payload)
    assembled = reconcile_event_summaries(
        "## ① 요약\n\n" + markdown, payload, terminal_events(markdown, payload)
    )
    assert f"> **오늘의 결론**: {values[0]}" in assembled
    assert f"> **핵심 동인**: {values[1]}" in assembled
    assert f"> **주의할 점**: {values[2]}" in assembled
    assert assembled.split("## 한눈에 보기", 1)[1].split("## ①", 1)[0].count("\n- ") == 3


def test_public_event_summary_rejects_incomplete_or_oversized_sentence() -> None:
    with pytest.raises(ValueError, match="complete sentences"):
        PublicEventSummary("a" * 24, "발표", "발표 관련 미완성", "supported")
    with pytest.raises(ValueError, match="bounds"):
        PublicEventSummary("a" * 24, "발표", "가" * 180 + ".", "supported")


@pytest.mark.parametrize("summary_before_hero", [False, True])
def test_summary_content_preserves_current_and_proposed_u154_preamble_blocks(
    summary_before_hero: bool,
) -> None:
    payload = payload_for()
    title = "# 2026-09-21 미국 증시 시황\n\n"
    hero = (
        "<!-- investo:block hero:fixture -->\n"
        "![합성 도표](fixture.svg)\n<!-- /investo:block -->\n\n"
    )
    callouts = (
        "> **오늘의 결론**: 기존 결론입니다.\n"
        "> **핵심 동인**: 기존 동인입니다.\n"
        "> **주의할 점**: 추가 확인이 필요합니다.\n\n"
    )
    tldr = (
        "## 한눈에 보기\n\n- 이전 첫째 문장입니다.\n"
        "- 이전 둘째 문장입니다.\n- 이전 셋째 문장입니다.\n\n"
    )
    preamble = tldr + callouts + hero if summary_before_hero else callouts + hero + tldr
    markdown = (
        title + preamble + "## ① 요약\n\n추가 자료를 확인합니다.\n\n" + event_markdown(payload)
    )
    first = reconcile_event_summaries(markdown, payload, terminal_events(markdown, payload))
    second = reconcile_event_summaries(first, payload, terminal_events(first, payload))
    assert first == second
    assert first.startswith(title) and hero in first
    assert first.count("> **오늘의 결론**:") == 1
    assert first.count("> **핵심 동인**:") == 1
    assert first.count("> **주의할 점**:") == 1
    assert (first.index("## 한눈에 보기") < first.index(hero)) is summary_before_hero
    assert payload.narratives[0].what_happened in first
    assert "이전 첫째" not in first
