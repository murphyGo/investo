"""Reader output has exact table placement, source privacy and old-hash compatibility."""

import json
from hashlib import sha256

from investo.models.event_article import NarrativeBlock
from investo.publisher.event_archive_reader import published_edition_bytes
from investo.publisher.event_edition import project_event_edition, render_event_edition
from investo.publisher.public_document import finalize_public_bundle
from tests._helpers.event_article_v2 import article_case
from tests._helpers.event_document_v3 import native_case, native_context


def test_table_block_renders_at_selected_position_once():
    _, draft, _, _ = article_case()
    article = draft.articles[0]
    first, last = article.narrative.blocks
    narrative = article.narrative.model_copy(
        update={
            "blocks": (first, NarrativeBlock(kind="fact_table", fact_ids=article.fact_ids), last)
        }
    )
    draft = draft.model_copy(
        update={"articles": (article.model_copy(update={"narrative": narrative}),)}
    )
    markdown = render_event_edition(draft)
    header = "| 주체 | 항목 | 값 | 단위 | 기간 | 구분 |"
    assert (
        markdown.index(narrative.sentences[0].text)
        < markdown.index(header)
        < markdown.index(narrative.sentences[1].text)
    )
    assert markdown.count(header) == 1
    assert markdown.count(f"<!-- investo:fact {article.fact_ids[0]} -->") == 1
    validation = render_event_edition(draft, for_validation=True)
    assert header not in validation and "1200" in validation


def test_public_projection_never_serializes_private_packet_or_review():
    _, draft, _, _ = article_case()
    view = project_event_edition(draft, render_event_edition(draft))
    payload = published_edition_bytes(view.edition).decode()
    assert "service access." not in payload
    assert "packet_hash" not in payload and "article_readiness" not in payload
    assert view.edition.events[0].support.meaning == "source_reported"
    assert view.edition.events[0].narrative == draft.articles[0].narrative


def test_legacy_hash_shape_has_no_new_default_fields():
    _, draft = native_case()
    edition = project_event_edition(draft, render_event_edition(draft)).edition
    payload = json.loads(published_edition_bytes(edition))
    assert "content_contract_version" not in payload
    assert "content_contract_version" not in payload["events"][0]
    assert "narrative" not in payload["events"][0]
    claimed = payload.pop("projection_sha256")
    assert (
        claimed
        == sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
    )


def test_malformed_article_plan_blocks_only_its_market():
    broken_item, broken, _, _ = article_case("crypto")
    good_item, good = native_case("us-equity")
    plan = broken.editorial_plan.events[0]
    broken = broken.model_copy(
        update={
            "editorial_plan": broken.editorial_plan.model_copy(
                update={
                    "events": (
                        plan.model_copy(
                            update={
                                "source_event": plan.source_event.model_copy(
                                    update={"item_ids": (96,)}
                                )
                            }
                        ),
                    )
                }
            )
        }
    )
    bundle = finalize_public_bundle(
        {"crypto": broken, "us-equity": good},
        context=native_context((broken_item, broken), (good_item, good)),
    )
    assert tuple(d.segment for d in bundle.documents) == ("us-equity",)
    assert any(
        o.segment == "crypto" and o.state == "trust_blocked" for o in bundle.segment_outcomes
    )


def test_reviewed_prose_can_be_scored_by_existing_human_acceptance_contract():
    # Synthetic protocol fixture. This is not an actual human/corpus acceptance.
    from investo.models.event_article import ARTICLE_POLICY_HASH
    from investo.models.event_quality import (
        EventSemanticAnnotation,
        EventSemanticReview,
        SemanticEventScore,
    )
    from investo.publisher.event_quality import measure_event_quality_v3
    from tests._helpers.event_context_v3 import NOW

    item, draft, _, _ = article_case()
    sealed = finalize_public_bundle(
        {draft.segment: draft}, context=native_context((item, draft))
    ).documents[0]
    event_id = draft.articles[0].event_id
    annotation = EventSemanticAnnotation(
        content_contract_version=2,
        article_policy_hash=ARTICLE_POLICY_HASH,
        case_id="synthetic-protocol",
        segment=draft.segment,
        origin="synthetic_oracle",
        reviewed_code_sha="1" * 40,
        remote_data_baseline_sha="2" * 40,
        target_date=draft.target_date,
        source_availability="normal",
        news_rich=True,
        expected_event_ids=(event_id,),
        expected_detailed_event_ids=(event_id,),
        must_include=(event_id,),
        required_fact_ids=draft.articles[0].fact_ids,
        expected_outcome="normal",
    )
    review = EventSemanticReview(
        content_contract_version=2,
        detailed_event_ids=(event_id,),
        projection_sha256=sealed.edition_view.edition.projection_sha256,
        case_id=annotation.case_id,
        annotation_sha256=annotation.annotation_sha256,
        markdown_sha256=sealed.markdown_sha256,
        reviewer_id="synthetic-human-shape",
        reviewer_kind="human",
        reviewed_at=NOW,
        result="pass",
        scores=(SemanticEventScore(event_id=event_id, what=1, when=1, why=1, react=1, source=1),),
    )
    measured = measure_event_quality_v3(
        sealed,
        annotation=annotation,
        candidate_event_ids=(event_id,),
        selected_event_ids=(event_id,),
        human_review=review,
    )
    assert measured.human_five_of_five.numerator == measured.human_five_of_five.denominator == 1
    assert measured.automated_result == "pass"


def test_multiple_tables_cannot_repeat_same_fact_row():
    import pytest

    from investo.models.event_article import ArticleNarrative

    _, draft, _, _ = article_case()
    narrative = draft.articles[0].narrative
    table = NarrativeBlock(kind="fact_table", fact_ids=draft.articles[0].fact_ids)
    with pytest.raises(ValueError, match="duplicate_fact_table_row"):
        ArticleNarrative.model_validate(
            {**narrative.model_dump(), "blocks": (*narrative.blocks, table, table)}
        )


def test_news_rich_all_brief_edition_fails_automatic_content_acceptance():
    from investo.models.event_article import ARTICLE_POLICY_HASH
    from investo.models.event_quality import EventSemanticAnnotation
    from investo.publisher.event_quality import measure_event_quality_v3

    item, draft, _, _ = article_case(impact="context")
    sealed = finalize_public_bundle(
        {draft.segment: draft}, context=native_context((item, draft))
    ).documents[0]
    event_id = draft.articles[0].event_id
    assert sealed.edition_view.edition.events[0].article_kind == "brief"
    annotation = EventSemanticAnnotation(
        content_contract_version=2,
        article_policy_hash=ARTICLE_POLICY_HASH,
        case_id="synthetic-all-brief",
        segment=draft.segment,
        origin="synthetic_oracle",
        reviewed_code_sha="1" * 40,
        remote_data_baseline_sha="2" * 40,
        target_date=draft.target_date,
        source_availability="normal",
        news_rich=True,
        expected_event_ids=(event_id,),
        expected_detailed_event_ids=(event_id,),
        must_include=(event_id,),
        required_fact_ids=draft.articles[0].fact_ids,
        expected_outcome="normal",
    )
    measured = measure_event_quality_v3(
        sealed,
        annotation=annotation,
        candidate_event_ids=(event_id,),
        selected_event_ids=(event_id,),
    )
    assert measured.detailed_article_count == 0 and measured.automated_result == "fail"
