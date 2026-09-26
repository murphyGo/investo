"""E8 actual terminal metrics and null/zero/failure contracts."""

from __future__ import annotations

import re
from dataclasses import fields, replace
from hashlib import sha256

import pytest

from investo.models.event_narratives import EventGenerationPayload
from investo.models.event_quality import EventStageReceipt, EventTraceEntry
from investo.models.events import EventSelectionPlan
from investo.models.public_notification import PublicEventSummary
from investo.models.segments import US_EQUITY
from investo.publisher.event_quality import evaluate_event_quality, terminal_event_issue_codes
from investo.publisher.public_document import FinalizedPublicDocument, finalize_public_bundle
from tests.integration.test_event_finalization import _briefing, _context
from tests.unit.briefing.test_event_narrative import payload_for
from tests.unit.publisher.test_event_blocks import combined_payload


def _receipts(count: int) -> tuple[EventStageReceipt, ...]:
    return (
        EventStageReceipt(stage="collected", status="completed", count=count),
        EventStageReceipt(stage="classified", status="completed", count=count),
        EventStageReceipt(stage="selected", status="completed", count=count),
        EventStageReceipt(stage="prompted", status="completed", count=count),
        EventStageReceipt(stage="generated", status="completed", count=count),
    )


def _document(
    payload: EventGenerationPayload, markdown: str | None = None
) -> FinalizedPublicDocument:
    briefing = _briefing(payload)
    if markdown is not None:
        briefing = briefing.model_copy(update={"rendered_markdown": markdown})
    return finalize_public_bundle(
        {US_EQUITY: briefing}, context=_context({US_EQUITY: payload})
    ).documents[0]


def _tamper(document: FinalizedPublicDocument, **changes: object) -> FinalizedPublicDocument:
    """Deliberately corrupt a seal to test the independent read-only checker."""
    altered = object.__new__(FinalizedPublicDocument)
    for field in fields(document):
        object.__setattr__(
            altered, field.name, changes.get(field.name, getattr(document, field.name))
        )
    return altered


@pytest.mark.parametrize("count", [4, 5])
def test_terminal_four_or_five_events_are_distinct_from_three_notification_events(
    count: int,
) -> None:
    payload = combined_payload(
        "product_service", "public_statement", "earnings_result", "monetary_policy"
    )
    if count == 5:
        extra = payload_for(object_override="Product B")
        docs = (*payload.plan.evidence_documents, *extra.plan.evidence_documents)
        payload = EventGenerationPayload(
            plan=EventSelectionPlan(
                selected=(*payload.plan.selected, *extra.plan.selected),
                evidence_documents=docs,
                evidence_row_count=len(docs),
            ),
            narratives=(*payload.narratives, *extra.narratives),
        )
    document = _document(payload)
    before = document.briefing.rendered_markdown
    result = evaluate_event_quality(document, payload=payload, receipts=_receipts(count))
    assert result.state == "qualified"
    assert (
        result.selected_count
        == result.terminal_event_count
        == result.qualified_event_count
        == count
    )
    assert result.summary_event_count == 3
    assert result.details_limited_count == result.unsupported_count == result.omitted_count == 0
    assert result.selection_coverage == result.qualified_coverage == 1.0
    assert document.briefing.rendered_markdown == before


@pytest.mark.parametrize(
    "missing",
    [
        "marker_only",
        "url_only",
        "시점",
        "주체",
        "무슨 일이 있었나",
        "결정/실적/발표 내용",
        "의미",
        "시장 반응",
    ],
)
def test_incomplete_terminal_blocks_are_removed_not_qualified(missing: str) -> None:
    payload = payload_for()
    markdown = _briefing(payload).rendered_markdown
    if missing in {"marker_only", "url_only"}:
        body = (
            ""
            if missing == "marker_only"
            else "- 출처: [official](https://example.invalid/product_service)\n"
        )
        markdown = re.sub(
            r"(<!-- investo:block event:[0-9a-f]{24} -->\n).*?"
            r"(<!-- /investo:block event:[0-9a-f]{24} -->)",
            lambda match: match.group(1) + body + match.group(2),
            markdown,
            flags=re.DOTALL,
        )
    else:
        markdown = re.sub(rf"(?m)^- {missing}:.*\n", "", markdown)
    document = _document(payload, markdown)
    result = evaluate_event_quality(document, payload=payload, receipts=_receipts(1))
    assert (
        result.terminal_event_count
        == result.qualified_event_count
        == result.summary_event_count
        == 0
    )
    assert result.omitted_count == 1
    assert result.selection_coverage == result.qualified_coverage == 0.0
    assert result.state == "no_qualifying_event"
    assert "finalization_removed" in result.reasons
    assert result.issue_codes == ()


def test_source_locator_loss_is_terminal_but_never_qualified() -> None:
    payload = payload_for()
    markdown = re.sub(r"(?m)^- 출처:.*\n", "", _briefing(payload).rendered_markdown)
    result = evaluate_event_quality(
        _document(payload, markdown), payload=payload, receipts=_receipts(1)
    )
    assert (
        result.terminal_event_count
        == result.details_limited_count
        == result.summary_event_count
        == 1
    )
    assert result.qualified_event_count == 0
    assert result.selection_coverage == 1.0
    assert result.qualified_coverage == 0.0
    assert result.state == "detail_limited"


@pytest.mark.parametrize("concealment", ["comment", "fence", "duplicate"])
def test_hidden_or_duplicate_canonical_tldr_cannot_mask_removed_event_reexposure(
    concealment: str,
) -> None:
    payload = combined_payload("product_service", "public_statement")
    markdown = re.sub(
        r"(?m)^- 결정/실적/발표 내용:.*\n", "", _briefing(payload).rendered_markdown, count=1
    )
    document = _document(payload, markdown)
    markdown = document.briefing.rendered_markdown
    match = re.search(r"(?ms)^## 한눈에 보기[^\n]*\n.*?(?=^## |\Z)", markdown)
    assert match is not None
    canonical = match.group(0)
    forged = canonical.replace(
        payload.narratives[1].what_happened, payload.narratives[0].what_happened
    )
    assert forged != canonical
    prefix = {
        "comment": "<!--\n" + canonical + "-->\n",
        "fence": "```markdown\n" + canonical + "```\n",
        "duplicate": canonical,
    }[concealment]
    markdown = markdown[: match.start()] + prefix + forged + markdown[match.end() :]
    altered = _tamper(
        document,
        briefing=document.briefing.model_copy(update={"rendered_markdown": markdown}),
        markdown_sha256=sha256(markdown.encode()).hexdigest(),
    )
    result = evaluate_event_quality(altered, payload=payload, receipts=_receipts(2))
    assert result.state == "hard_trust_blocked"
    assert "event.summary_reexposure" in result.issue_codes
    assert result.terminal_event_count is result.qualified_coverage is None


@pytest.mark.parametrize("duplicate", ["tldr", "conclusion"])
def test_duplicate_visible_summary_container_is_rejected_even_with_canonical_content(
    duplicate: str,
) -> None:
    payload = payload_for()
    document = _document(payload)
    markdown = document.briefing.rendered_markdown
    pattern = (
        r"(?ms)^## 한눈에 보기[^\n]*\n.*?(?=^## |\Z)"
        if duplicate == "tldr"
        else r"(?m)^> \*\*오늘의 결론\*\*:.*\n"
    )
    match = re.search(pattern, markdown)
    assert match is not None
    markdown = markdown[: match.end()] + match.group(0) + markdown[match.end() :]
    altered = _tamper(
        document,
        briefing=document.briefing.model_copy(update={"rendered_markdown": markdown}),
        markdown_sha256=sha256(markdown.encode()).hexdigest(),
    )
    result = evaluate_event_quality(altered, payload=payload, receipts=_receipts(1))
    assert result.state == "hard_trust_blocked"
    assert "event.summary_reexposure" in result.issue_codes


@pytest.mark.parametrize("limited", [False, True])
def test_completed_zero_has_zero_counts_and_null_denominators(limited: bool) -> None:
    payload = EventGenerationPayload(
        plan=EventSelectionPlan(), narratives=(), collection_limited=limited
    )
    result = evaluate_event_quality(_document(payload), payload=payload, receipts=_receipts(0))
    assert result.collected_candidate_count == result.selected_count == result.prompted_count == 0
    assert (
        result.terminal_event_count
        == result.qualified_event_count
        == result.summary_event_count
        == 0
    )
    assert result.selection_coverage is None and result.qualified_coverage is None
    assert result.state == ("source_limited" if limited else "no_qualifying_event")


def test_failed_collection_and_unclassified_are_unknown_despite_later_candidate_zero() -> None:
    receipts = (
        EventStageReceipt(stage="collected", status="failed"),
        EventStageReceipt(stage="candidate", status="completed", count=0),
        EventStageReceipt(stage="classified", status="failed"),
        EventStageReceipt(stage="selected", status="not_run"),
    )
    result = evaluate_event_quality(None, payload=None, receipts=receipts)
    assert result.collected_candidate_count is None and result.selected_count is None
    assert result.prompted_count is None and result.terminal_event_count is None
    assert result.summary_event_count is None and result.unsupported_count is None
    assert result.selection_coverage is None and result.qualified_coverage is None
    assert result.state == "classification_unavailable"
    assert {
        "classification_unavailable",
        "finalization_unavailable",
        "source_limited",
        "source_unavailable",
    } <= set(result.reasons)


def test_missing_finalizer_keeps_observed_selection_but_no_terminal_zeros() -> None:
    result = evaluate_event_quality(None, payload=payload_for(), receipts=_receipts(1))
    assert result.state == "finalization_unavailable"
    assert result.selected_count == result.prompted_count == 1
    assert result.terminal_event_count is None and result.qualified_event_count is None
    assert result.omitted_count is None and result.summary_event_count is None


def test_missing_classification_receipt_is_not_inferred_from_payload_or_document() -> None:
    payload = payload_for()
    result = evaluate_event_quality(
        _document(payload), payload=payload, receipts=(_receipts(1)[0],)
    )
    assert result.state == "classification_unavailable"
    assert result.selected_count is None and result.prompted_count is None
    assert result.terminal_event_count == 1
    assert result.selection_coverage is None


def test_existing_hard_finding_cannot_be_cleared_by_valid_terminal_content() -> None:
    payload = payload_for()
    result = evaluate_event_quality(
        _document(payload),
        payload=payload,
        receipts=_receipts(1),
        hard_issue_codes=(
            "numeric.anchor_assertion",
            "private unsupported diagnostic must not escape",
        ),
    )
    assert result.state == "hard_trust_blocked"
    assert result.terminal_event_count is None and result.qualified_event_count is None
    assert result.selection_coverage is None and result.qualified_coverage is None
    assert "private unsupported" not in result.model_dump_json()


@pytest.mark.parametrize("surface", ["dto", "conclusion", "tldr"])
def test_removed_event_summary_reexposure_is_a_hard_quality_finding(surface: str) -> None:
    payload = combined_payload("product_service", "public_statement")
    markdown = re.sub(
        r"(?m)^- 결정/실적/발표 내용:.*\n", "", _briefing(payload).rendered_markdown, count=1
    )
    document = _document(payload, markdown)
    removed = payload.narratives[0]
    if surface == "dto":
        summary = replace(
            document.notification_summary,
            events=(
                PublicEventSummary(
                    removed.event_id, removed.headline, removed.what_happened, "supported"
                ),
            ),
        )
        document = _tamper(document, notification_summary=summary)
    else:
        final_markdown = document.briefing.rendered_markdown
        prefix = "> **오늘의 결론**: " if surface == "conclusion" else "- "
        actual = payload.narratives[1].what_happened
        changed = final_markdown.replace(prefix + actual, prefix + removed.what_happened, 1)
        assert changed != final_markdown
        document = _tamper(
            document,
            briefing=document.briefing.model_copy(update={"rendered_markdown": changed}),
            markdown_sha256=sha256(changed.encode()).hexdigest(),
        )
    result = evaluate_event_quality(document, payload=payload, receipts=_receipts(2))
    assert result.state == "hard_trust_blocked"
    assert "event.summary_reexposure" in result.issue_codes
    assert result.terminal_event_count is None and result.qualified_event_count is None


def test_source_tamper_deduplicates_multiple_findings_on_one_event() -> None:
    payload = payload_for()
    document = _document(payload)
    markdown = document.briefing.rendered_markdown.replace(
        "https://example.invalid/product_service", "https://untrusted.invalid/forged"
    ).replace("주체: Acme", "주체: Another")
    damaged = _tamper(
        document,
        briefing=document.briefing.model_copy(update={"rendered_markdown": markdown}),
        markdown_sha256=sha256(markdown.encode()).hexdigest(),
    )
    result = evaluate_event_quality(damaged, payload=payload, receipts=_receipts(1))
    assert {"event.entity_unsupported", "event.evidence_invalid"} <= set(result.issue_codes)
    assert result.unsupported_count == 1
    assert result.state == "hard_trust_blocked" and result.qualified_coverage is None


def test_changed_terminal_bytes_invalidate_the_seal_without_false_success_metrics() -> None:
    payload = payload_for()
    document = _document(payload)
    damaged = _tamper(
        document,
        briefing=document.briefing.model_copy(
            update={"rendered_markdown": document.briefing.rendered_markdown + "\n"}
        ),
    )
    result = evaluate_event_quality(damaged, payload=payload, receipts=_receipts(1))
    assert "event.seal_mismatch" in result.issue_codes
    assert result.state == "hard_trust_blocked" and result.selection_coverage is None


def test_trace_source_limit_preserves_all_reasons_but_not_private_hashes_in_public_json() -> None:
    payload = payload_for()
    receipts = list(_receipts(1))
    receipts[0] = EventStageReceipt(
        stage="collected",
        status="completed",
        count=1,
        trace=(
            EventTraceEntry(
                hash_id="a" * 64,
                stage="collected",
                reason="source_unavailable",
                source_name="official",
            ),
        ),
    )
    result = evaluate_event_quality(_document(payload), payload=payload, receipts=receipts)
    assert result.state == "source_limited" and result.qualified_event_count == 1
    assert "source_unavailable" in result.reasons
    assert "receipts" not in result.model_dump()
    assert "a" * 64 not in result.model_dump_json()


def test_stage_count_mismatch_cannot_report_successful_coverage() -> None:
    payload = payload_for()
    result = evaluate_event_quality(_document(payload), payload=payload, receipts=_receipts(0))
    assert result.state == "hard_trust_blocked"
    assert result.issue_codes == ("event.stage_receipt_invalid",)
    assert result.selected_count is None and result.terminal_event_count is None


def test_terminal_seam_is_read_only_and_detects_declared_phantom_survivor() -> None:
    payload = payload_for()
    document = _document(payload)
    before = document.briefing.rendered_markdown
    assert terminal_event_issue_codes(
        before,
        payload=payload,
        notification_summary=document.notification_summary,
        surviving_event_ids=(),
    ) == ("event.terminal_mismatch",)
    assert document.briefing.rendered_markdown == before


def test_terminal_receipts_replace_claims_with_actual_survivors_and_summary_trace() -> None:
    payload = combined_payload("product_service", "public_statement", "earnings_result")
    markdown = re.sub(
        r"(?m)^- 결정/실적/발표 내용:.*\n", "", _briefing(payload).rendered_markdown, count=1
    )
    markdown = re.sub(r"(?m)^- 출처:.*\n", "", markdown)
    document = _document(payload, markdown)
    receipts = (
        *_receipts(3),
        EventStageReceipt(stage="finalized", status="completed", count=3),
        EventStageReceipt(stage="summary", status="completed", count=3),
        EventStageReceipt(stage="structure_checked", status="completed", count=0),
    )
    result = evaluate_event_quality(document, payload=payload, receipts=receipts)
    by_stage = {receipt.stage: receipt for receipt in result.receipts}
    assert len(by_stage) == len(result.receipts)
    assert by_stage["finalized"].status == "completed"
    assert by_stage["finalized"].count == 2
    assert tuple(entry.hash_id for entry in by_stage["finalized"].trace) == tuple(
        event.event_id for event in payload.plan.selected
    )
    assert tuple(entry.reason for entry in by_stage["finalized"].trace) == (
        "finalization_removed",
        "detail_limited",
        "detail_limited",
    )
    assert by_stage["summary"].count == 2
    assert tuple(entry.hash_id for entry in by_stage["summary"].trace) == tuple(
        event.event_id for event in document.notification_summary.events
    )
    assert by_stage["structure_checked"].status == "completed"
    assert by_stage["structure_checked"].count == 0
    assert evaluate_event_quality(document, payload=payload, receipts=result.receipts) == result


@pytest.mark.parametrize("failure", ["hard", "seal"])
def test_terminal_failure_receipts_keep_only_actually_completed_structure_count(
    failure: str,
) -> None:
    payload = payload_for()
    document = _document(payload)
    if failure == "seal":
        document = _tamper(document, markdown_sha256="0" * 64)
    result = evaluate_event_quality(
        document,
        payload=payload,
        receipts=_receipts(1),
        hard_issue_codes=("numeric.anchor_assertion",) if failure == "hard" else (),
    )
    by_stage = {receipt.stage: receipt for receipt in result.receipts}
    for stage in ("finalized", "summary"):
        assert by_stage[stage].status == "failed" and by_stage[stage].count is None
    assert by_stage["finalized"].trace[0].reason == "hard_trust_blocked"
    assert by_stage["summary"].trace == ()
    assert by_stage["structure_checked"].status == "completed"
    assert by_stage["structure_checked"].count == result.unsupported_count == 0


@pytest.mark.parametrize("prior_failure", [False, True])
def test_unavailable_document_receipts_do_not_invent_completed_zero(prior_failure: bool) -> None:
    receipts = _receipts(1)
    if prior_failure:
        receipts += (EventStageReceipt(stage="finalized", status="failed"),)
    result = evaluate_event_quality(None, payload=payload_for(), receipts=receipts)
    by_stage = {receipt.stage: receipt for receipt in result.receipts}
    assert by_stage["finalized"].status == ("failed" if prior_failure else "not_run")
    assert by_stage["finalized"].count is None
    assert by_stage["summary"].status == by_stage["structure_checked"].status == "not_run"
    assert by_stage["summary"].count is by_stage["structure_checked"].count is None


@pytest.mark.parametrize("stage", ["classified", "prompted", "generated"])
def test_known_stage_zero_cannot_support_a_one_event_payload(stage: str) -> None:
    payload = payload_for()
    receipts = tuple(
        receipt.model_copy(update={"count": 0}) if receipt.stage == stage else receipt
        for receipt in _receipts(1)
    )
    result = evaluate_event_quality(_document(payload), payload=payload, receipts=receipts)
    assert result.state == "hard_trust_blocked"
    assert "event.stage_receipt_invalid" in result.issue_codes
    assert result.terminal_event_count is result.qualified_coverage is None


def test_more_classified_candidates_than_selected_events_are_valid() -> None:
    payload = combined_payload(
        "product_service", "public_statement", "earnings_result", "monetary_policy"
    )
    extra = payload_for(object_override="Product B")
    docs = (*payload.plan.evidence_documents, *extra.plan.evidence_documents)
    payload = EventGenerationPayload(
        plan=EventSelectionPlan(
            selected=(*payload.plan.selected, *extra.plan.selected),
            evidence_documents=docs,
            evidence_row_count=len(docs),
        ),
        narratives=(*payload.narratives, *extra.narratives),
    )
    receipts = tuple(
        receipt.model_copy(update={"count": 12}) if receipt.stage == "classified" else receipt
        for receipt in _receipts(5)
    )
    result = evaluate_event_quality(_document(payload), payload=payload, receipts=receipts)
    assert result.state == "qualified" and result.issue_codes == ()
    assert result.selected_count == result.terminal_event_count == 5
    assert result.qualified_coverage == 1.0


@pytest.mark.parametrize("stage", ["classified", "prompted", "generated"])
def test_missing_stage_observation_does_not_invent_zero_or_stage_mismatch(stage: str) -> None:
    payload = payload_for()
    receipts = tuple(receipt for receipt in _receipts(1) if receipt.stage != stage)
    result = evaluate_event_quality(_document(payload), payload=payload, receipts=receipts)
    assert result.issue_codes == ()
    assert all(receipt.stage != stage for receipt in result.receipts)
    if stage == "prompted":
        assert result.prompted_count is None


def test_incoming_hard_trace_stays_blocked_when_remeasured_against_valid_document() -> None:
    payload = payload_for()
    document = _document(payload)
    first = evaluate_event_quality(
        document,
        payload=payload,
        receipts=_receipts(1),
        hard_issue_codes=("numeric.anchor_assertion",),
    )
    second = evaluate_event_quality(document, payload=payload, receipts=first.receipts)
    assert second.state == "hard_trust_blocked"
    assert second.terminal_event_count is second.qualified_event_count is None
    assert second.selection_coverage is second.qualified_coverage is None
    assert second.receipts == first.receipts


@pytest.mark.parametrize("has_document", [False, True])
def test_prior_observed_unsupported_count_is_sticky_even_without_a_trace(
    has_document: bool,
) -> None:
    payload = payload_for()
    receipts = (
        *_receipts(1),
        EventStageReceipt(stage="structure_checked", status="completed", count=1),
    )
    result = evaluate_event_quality(
        _document(payload) if has_document else None,
        payload=payload,
        receipts=receipts,
    )
    assert result.state == "hard_trust_blocked"
    assert "hard_trust_blocked" in result.reasons
    assert result.terminal_event_count is result.qualified_coverage is None
    assert result.unsupported_count == (0 if has_document else 1)
