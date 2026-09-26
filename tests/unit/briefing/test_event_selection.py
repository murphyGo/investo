"""Protected rows, byte accounting, and deterministic editorial selection."""

import json
from datetime import timedelta

from investo.briefing.event_evidence import build_event_candidates, make_evidence_document
from investo.briefing.event_selection import event_score, select_events
from investo.models.events import EventFactDraft, EvidenceRef
from tests.unit.briefing.test_event_evidence import NOW, document, draft, item, ref


def test_two_news_survive_fourteen_price_rows() -> None:
    doc = document()
    news = build_event_candidates(
        [draft(doc), draft(doc, "B")], [item(doc)], [doc], observed_at=NOW
    )
    # Parent reserves this plan first, before allocating the existing 14-price
    # grouped set; shared evidence for two events consumes exactly one row.
    plan = select_events(
        news,
        [doc],
        segment="us-equity",
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
        total_row_budget=48,
        section_row_budget=14,
    )
    assert len(plan.selected) == 2
    assert plan.evidence_row_count == 1
    assert 14 - plan.evidence_row_count == 13
    assert [row["event_id"] for row in json.loads(plan.protected_block)["events"]] == [
        event.event_id for event in plan.selected
    ]


def test_crypto_five_two_row_events_fit_only_four() -> None:
    docs, items, drafts = [], [], []
    for i in range(5):
        primary = make_evidence_document(
            source_name=f"news-{i}",
            title=f"Firm{i} launches Asset{i}",
            summary="Details announced.",
            url=f"https://example.invalid/{i}",
            published_at=NOW - timedelta(hours=1),
            received_at=NOW,
            event_time=NOW.date(),
            event_time_basis="source_date",
        )
        extra = make_evidence_document(
            source_name=f"official-{i}",
            title=f"Asset{i} available",
            summary=f"Asset{i} is live.",
            url=f"https://example.invalid/{i}-extra",
            published_at=NOW - timedelta(hours=1),
            received_at=NOW,
            event_time=NOW.date(),
            event_time_basis="source_date",
        )
        docs.extend([primary, extra])
        items.extend([item(primary), item(extra)])
        actor = ref(primary, f"Firm{i}")
        drafts.append(
            draft(document()).model_copy(
                update={
                    "item_ids": (2 * i + 1, 2 * i + 2),
                    "actor_refs": (actor,),
                    "action_refs": (ref(primary, "launches"),),
                    "object_refs": (ref(primary, f"Asset{i}"),),
                    "relation_refs": (actor,),
                    "impact_refs": (actor,),
                    "facts": (
                        EventFactDraft(
                            predicate="launch", evidence_ref=ref(extra, extra.summary, "summary")
                        ),
                    ),
                }
            )
        )
    candidates = build_event_candidates(drafts, items, docs, observed_at=NOW)
    plan = select_events(
        candidates, docs, segment="crypto", window_start=NOW - timedelta(days=1), window_end=NOW
    )
    assert len(plan.selected) == 4
    assert plan.evidence_row_count == 8
    assert plan.protected_byte_count == len(plan.protected_block.encode("utf-8")) <= 8192
    assert [r.reason for r in plan.excluded] == ["budget_deferred"]
    reversed_plan = select_events(
        list(reversed(candidates)),
        list(reversed(docs)),
        segment="crypto",
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
    )
    assert plan == reversed_plan


def test_repeat_background_conflict_and_unknown_are_not_inflated() -> None:
    doc = document()
    candidate = build_event_candidates([draft(doc)], [item(doc)], [doc], observed_at=NOW)[0]
    assert event_score(candidate) == 70
    for change in (
        {"novelty": "repeat"},
        {"timing": "background"},
        {"evidence_state": "conflicting"},
        {"relation": "unrelated"},
    ):
        plan = select_events(
            [candidate.model_copy(update=change)],
            [doc],
            segment="us-equity",
            window_start=NOW - timedelta(days=1),
            window_end=NOW,
        )
        assert not plan.selected
    unknown = build_event_candidates(
        [draft(doc)], [item(doc)], [doc], observed_at=NOW, baseline_available=False
    )[0]
    assert event_score(unknown) == 40
    assert not select_events(
        [unknown], [doc], segment="crypto", window_start=NOW - timedelta(days=1), window_end=NOW
    ).selected


def test_unknown_timing_is_only_selected_with_limited_evidence() -> None:
    doc = document()
    candidate = build_event_candidates(
        [draft(doc).model_copy(update={"timing": "unknown"})],
        [item(doc)],
        [doc],
        observed_at=NOW,
    )[0]
    assert candidate.effective_date is not None
    assert candidate.evidence_state == "detail_limited"
    assert candidate.selection_reason == "detail_limited"
    assert event_score(candidate) == 60
    plan = select_events(
        [candidate],
        [doc],
        segment="us-equity",
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
    )
    assert plan.selected == (candidate,)
    assert json.loads(plan.protected_block)["events"][0]["evidence_state"] == "detail_limited"


def test_required_fact_rows_cannot_be_dropped_to_satisfy_budget() -> None:
    doc = document()
    candidate = build_event_candidates([draft(doc)], [item(doc)], [doc], observed_at=NOW)[0]
    plan = select_events(
        [candidate],
        [doc],
        segment="us-equity",
        total_row_budget=0,
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
    )
    assert not plan.selected
    assert plan.protected_block == ""
    assert plan.excluded[0].reason == "budget_deferred"


def test_byte_overflow_is_deferred_before_selected_not_truncated() -> None:
    doc = document(detail="가" * 1200)
    candidate = build_event_candidates([draft(doc)], [item(doc)], [doc], observed_at=NOW)[0]
    extra = tuple(
        EvidenceRef(
            document_id=doc.document_id,
            revision_id=doc.revision_id,
            field="detail_excerpt",
            start=i,
            end=i + 240,
        )
        for i in range(12)
    )
    candidate = candidate.model_copy(update={"evidence_refs": (*candidate.evidence_refs, *extra)})
    plan = select_events(
        [candidate],
        [doc],
        segment="us-equity",
        window_start=NOW - timedelta(days=1),
        window_end=NOW,
    )
    assert not plan.selected
    assert plan.protected_byte_count == 0
    assert plan.excluded[0].reason == "budget_deferred"
