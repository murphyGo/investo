"""Real evidence, synthetic checks and operational acceptance stay independent."""

import pytest
from pydantic import ValidationError

from investo.models.event_quality import (
    EventCutoverAcceptance,
    EventSemanticAnnotation,
    EventSemanticReview,
    SemanticEventScore,
    SemanticRate,
    semantic_records_hash,
)
from investo.publisher.event_quality import measure_event_quality_v3
from investo.publisher.public_document import finalize_public_bundle
from tests._helpers.event_context_v3 import NOW
from tests._helpers.event_document_v3 import TARGET, native_case, native_context


def semantic_case():
    item, draft = native_case()
    sealed = finalize_public_bundle(
        {draft.segment: draft}, context=native_context((item, draft))
    ).documents[0]
    event_id = draft.articles[0].event_id
    annotation = EventSemanticAnnotation(
        case_id="real-0",
        segment=draft.segment,
        origin="real_human_annotation",
        reviewed_code_sha="a" * 40,
        remote_data_baseline_sha="b" * 40,
        target_date=TARGET,
        source_availability="normal",
        news_rich=True,
        expected_event_ids=(event_id,),
        must_include=(event_id,),
        required_fact_ids=draft.articles[0].fact_ids,
        expected_support=(sealed.edition_view.edition.events[0].support,),
        expected_outcome="normal",
    )
    return sealed, annotation, event_id


def test_native_ids_and_rates_are_hash_bound_without_awarding_human_score():
    sealed, annotation, event_id = semantic_case()
    result = measure_event_quality_v3(
        sealed,
        annotation=annotation,
        candidate_event_ids=(event_id,),
        selected_event_ids=(event_id,),
    )
    assert result.automated_result == "pass"
    assert result.required_fact_preservation.ratio == 1
    assert result.human_five_of_five.ratio is None
    assert result.external_event_capture.ratio is None
    assert result.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        EventSemanticAnnotation.model_validate(
            {**annotation.model_dump(), "expected_event_ids": ("c" * 64,)}
        )


def test_unobserved_selection_cannot_pass_and_unknown_stays_null():
    sealed, annotation, _ = semantic_case()
    result = measure_event_quality_v3(
        sealed, annotation=annotation, candidate_event_ids=None, selected_event_ids=None
    )
    assert result.automated_result != "pass"
    assert result.must_include_selection.ratio is None
    with pytest.raises(ValidationError):
        SemanticRate(numerator=1, denominator=None)


def test_candidate_and_human_score_cannot_borrow_another_event():
    sealed, annotation, event_id = semantic_case()
    with pytest.raises(ValueError, match="selection_identity"):
        measure_event_quality_v3(
            sealed, annotation=annotation, candidate_event_ids=(), selected_event_ids=(event_id,)
        )
    review = EventSemanticReview(
        case_id=annotation.case_id,
        annotation_sha256=annotation.annotation_sha256,
        markdown_sha256=sealed.markdown_sha256,
        reviewer_id="human-reviewer",
        reviewer_kind="human",
        reviewed_at=NOW,
        scores=(SemanticEventScore(event_id="f" * 24, what=1, when=1, why=1, react=1, source=1),),
        result="pass",
    )
    with pytest.raises(ValueError, match="review_identity"):
        measure_event_quality_v3(
            sealed,
            annotation=annotation,
            candidate_event_ids=(event_id,),
            selected_event_ids=(event_id,),
            human_review=review,
        )


def test_ai_or_partial_scores_do_not_become_human_pass():
    sealed, annotation, event_id = semantic_case()
    kwargs = dict(
        case_id=annotation.case_id,
        annotation_sha256=annotation.annotation_sha256,
        markdown_sha256=sealed.markdown_sha256,
        reviewer_id="reviewer",
        reviewed_at=NOW,
        scores=(SemanticEventScore(event_id=event_id, what=1, when=1, why=1, react=1, source=1),),
        result="pass",
    )
    with pytest.raises(ValidationError):
        EventSemanticReview(reviewer_kind="ai", **kwargs)
    with pytest.raises(ValidationError):
        EventSemanticReview(
            reviewer_kind="human",
            **{**kwargs, "scores": (kwargs["scores"][0].model_copy(update={"why": 0}),)},
        )


@pytest.mark.parametrize("status", ["ready", "active_observing", "accepted", "cleanup_complete"])
def test_operational_states_require_real_corpus_source_and_cursor_gates(status):
    empty = semantic_records_hash(())
    kwargs = dict(
        status=status,
        reviewed_code_sha="a" * 40,
        policy_sha256="b" * 64,
        annotation_sha256=empty,
        review_sha256=empty,
        market_allowlist=("us-equity",),
    )
    with pytest.raises(ValidationError, match="acceptance_pending"):
        EventCutoverAcceptance(**kwargs)
    blocked = EventCutoverAcceptance(**{**kwargs, "status": "blocked"})
    assert not blocked.human_market_ready("us-equity")
    with pytest.raises(ValidationError, match="evidence_hash_invalid"):
        EventCutoverAcceptance(**{**kwargs, "status": "blocked", "annotation_sha256": "f" * 64})


def test_unavailable_terminal_meaning_cannot_receive_human_five_of_five():
    sealed, annotation, event_id = semantic_case()
    review = EventSemanticReview(
        case_id=annotation.case_id,
        annotation_sha256=annotation.annotation_sha256,
        markdown_sha256=sealed.markdown_sha256,
        reviewer_id="human",
        reviewer_kind="human",
        reviewed_at=NOW,
        scores=(SemanticEventScore(event_id=event_id, what=1, when=1, why=1, react=1, source=1),),
        result="pass",
    )
    with pytest.raises(ValueError, match="support_score_invalid"):
        measure_event_quality_v3(
            sealed,
            annotation=annotation,
            candidate_event_ids=(event_id,),
            selected_event_ids=(event_id,),
            human_review=review,
        )
