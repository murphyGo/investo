"""Actual generator/finalizer path with synthetic CLI responses and no I/O."""

import subprocess

import pytest

from investo.briefing.errors import BriefingGenerationError
from investo.briefing.generation_contract import GenerationInput
from investo.briefing.watchlist import WatchlistConfig
from investo.models.event_article import ArticleCompositionBatch, ArticleReviewBatch
from investo.models.event_config import EventExecutionConfig
from investo.models.event_context import ContextClassificationResult
from investo.orchestrator.event_preview import preview_event_briefing
from tests._helpers.event_article_v2 import article_case
from tests._helpers.event_context_v3 import NOW


def responses(composition, review, event):
    return [
        ContextClassificationResult(schema_version=3, events=(event,)).model_dump_json(),
        ArticleCompositionBatch(articles=(composition,)).model_dump_json(),
        ArticleReviewBatch(articles=(review,)).model_dump_json(),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("market", ["domestic-equity", "us-equity", "crypto"])
async def test_three_call_article_is_korean_prose_and_sealed(market, tmp_path, monkeypatch):
    item, draft, composition, review = article_case(market)
    outputs = responses(composition, review, draft.editorial_plan.events[0].source_event)
    calls = []

    def runner(args, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(args, 0, outputs[len(calls) - 1], "")

    monkeypatch.chdir(tmp_path)
    before = tuple(tmp_path.rglob("*"))
    result = await preview_event_briefing(
        GenerationInput(
            target_date=draft.target_date,
            segment=market,
            items=(item,),
            runner=runner,
            watchlist_config=WatchlistConfig(),
            event_observed_at=NOW,
            event_generation_policy=EventExecutionConfig(
                mode="preview", document_schema=3, profile="article_v2"
            ),
        )
    )
    assert len(calls) == 3
    assert [c["timeout"] for c in calls] == [600, 900, 600]
    assert len(result.finalized.documents) == 1
    sealed = result.finalized.documents[0]
    assert composition.narrative.sentences[1].text in sealed.rendered_markdown
    assert sealed.edition_view.edition.content_contract_version == 2
    assert "### 배경" not in sealed.rendered_markdown
    assert tuple(tmp_path.rglob("*")) == before


@pytest.mark.asyncio
async def test_missing_explanation_repairs_batch_once():
    item, draft, composition, review = article_case()
    generic = composition.narrative.sentences[1].model_copy(
        update={"text": "Acme는 Widget에 관해 설명했습니다."}
    )
    initial = composition.model_copy(
        update={
            "narrative": composition.narrative.model_copy(
                update={
                    "blocks": (
                        composition.narrative.blocks[0],
                        composition.narrative.blocks[1].model_copy(
                            update={"sentences": (generic,)}
                        ),
                    )
                }
            )
        }
    )
    incomplete = review.model_copy(
        update={
            "draft_hash": initial.draft_hash,
            "questions": tuple(
                q.model_copy(update={"verdict": "missing"}) if q.question_id == "why" else q
                for q in review.questions
            ),
        }
    )
    outputs = responses(initial, incomplete, draft.editorial_plan.events[0].source_event)
    outputs += [
        ArticleCompositionBatch(articles=(composition,)).model_dump_json(),
        ArticleReviewBatch(articles=(review,)).model_dump_json(),
    ]
    calls = []

    def runner(args, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(args, 0, outputs[len(calls) - 1], "")

    result = await preview_event_briefing(
        GenerationInput(
            target_date=draft.target_date,
            segment=draft.segment,
            items=(item,),
            runner=runner,
            watchlist_config=WatchlistConfig(),
            event_observed_at=NOW,
            event_generation_policy=EventExecutionConfig(
                mode="preview", document_schema=3, profile="article_v2"
            ),
        )
    )
    assert len(calls) == 5 and result.finalized.documents


@pytest.mark.asyncio
async def test_semantic_causality_failure_cannot_publish_or_retry():
    item, draft, composition, review = article_case()
    failed = review.model_copy(
        update={
            "claims": (
                review.claims[0].model_copy(
                    update={"verdict": "contradicted", "reason": "causality"}
                ),
                *review.claims[1:],
            )
        }
    )
    outputs = responses(composition, failed, draft.editorial_plan.events[0].source_event)
    calls = []

    def runner(args, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(args, 0, outputs[len(calls) - 1], "")

    with pytest.raises(BriefingGenerationError, match="post_validation"):
        await preview_event_briefing(
            GenerationInput(
                target_date=draft.target_date,
                segment=draft.segment,
                items=(item,),
                runner=runner,
                watchlist_config=WatchlistConfig(),
                event_observed_at=NOW,
                event_generation_policy=EventExecutionConfig(
                    mode="preview", document_schema=3, profile="article_v2"
                ),
            )
        )
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_packet_overflow_defers_whole_event_and_preserves_selected_facts(monkeypatch):
    import json

    import investo.briefing.event_article as article_api

    cases = (article_case(), article_case(actor="OtherCo"))
    originals = {composition.event_id: (composition, review) for _, _, composition, review in cases}
    events = tuple(
        case[1].editorial_plan.events[0].source_event.model_copy(update={"item_ids": (index,)})
        for index, case in enumerate(cases, 1)
    )
    original_packet_payload = article_api.packet_payload

    def bounded(packets, documents):
        if len(packets) > 1:
            raise ValueError("context.budget_exhausted")
        return original_packet_payload(packets, documents)

    monkeypatch.setattr(article_api, "packet_payload", bounded)
    calls = []
    selected = []

    def runner(args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            output = ContextClassificationResult(schema_version=3, events=events).model_dump_json()
        elif len(calls) == 2:
            evidence = json.loads(
                kwargs["input"].split("<source-data>\n", 1)[1].split("\n</source-data>", 1)[0]
            )
            selected[:] = [packet["event_id"] for packet in evidence["packets"]]
            output = ArticleCompositionBatch(
                articles=tuple(originals[event_id][0] for event_id in selected)
            ).model_dump_json()
        else:
            output = ArticleReviewBatch(
                articles=tuple(originals[event_id][1] for event_id in selected)
            ).model_dump_json()
        return subprocess.CompletedProcess(args, 0, output, "")

    request = GenerationInput(
        target_date=cases[0][1].target_date,
        segment="us-equity",
        items=tuple(c[0] for c in cases),
        runner=runner,
        watchlist_config=WatchlistConfig(),
        event_observed_at=NOW,
        event_generation_policy=EventExecutionConfig(
            mode="preview", document_schema=3, profile="article_v2"
        ),
    )
    result = await preview_event_briefing(request)
    generated = result.generation.document
    assert (
        len(generated.articles)
        == len(result.finalized.documents[0].edition_view.edition.events)
        == 1
    )
    assert any(reason == "budget_deferred" for _, reason in generated.editorial_plan.exclusions)
    assert set(generated.articles[0].fact_ids) == set(
        generated.editorial_plan.events[0].required_fact_ids
    )
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_observed_macro_cannot_displace_supported_news_article():
    from investo.briefing.event_context import prepare_context_documents
    from investo.models import NormalizedItem
    from investo.models.event_context import ContextEventDraft, ContextFactDraft
    from tests._helpers.event_context_v3 import metadata_ref, ref

    item, draft, composition, review = article_case()
    macro = NormalizedItem(
        source_name="bls-macro-actuals",
        category="macro",
        title="Series observation",
        summary="Series actual 2400 USD FY2026; prior 2300.",
        published_at=NOW,
        raw_metadata={
            "macro_event_key": "series:2026",
            "macro_event_status": "actual",
            "macro_priority": "P1",
            "observed_at": NOW.isoformat(),
        },
    )
    doc = prepare_context_documents((macro,), received_at=NOW, article_passages=True)[0]
    source = ContextEventDraft(
        item_ids=(2,),
        event_kind="macro_release",
        actor_refs=(ref(doc, "Series"),),
        action_refs=(ref(doc, "actual"),),
        timing="occurred",
        relation="direct",
        impact="systemic",
        facts=(
            ContextFactDraft(
                predicate="result",
                status="actual",
                value_kind="numeric",
                subject_refs=(ref(doc, "Series"),),
                metric_refs=(ref(doc, "Series"),),
                value_refs=(ref(doc, "2400"),),
                unit_refs=(ref(doc, "USD"),),
                period_refs=(ref(doc, "FY2026"),),
                status_refs=(metadata_ref(doc, "macro_event_status"),),
            ),
        ),
    )
    outputs = [
        ContextClassificationResult(
            schema_version=3, events=(draft.editorial_plan.events[0].source_event, source)
        ).model_dump_json(),
        ArticleCompositionBatch(articles=(composition,)).model_dump_json(),
        ArticleReviewBatch(articles=(review,)).model_dump_json(),
    ]
    calls = []

    def runner(args, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(args, 0, outputs[len(calls) - 1], "")

    result = await preview_event_briefing(
        GenerationInput(
            target_date=draft.target_date,
            segment="us-equity",
            items=(macro, item),
            runner=runner,
            watchlist_config=WatchlistConfig(),
            event_observed_at=NOW,
            event_generation_policy=EventExecutionConfig(
                mode="preview", document_schema=3, profile="article_v2"
            ),
        )
    )
    assert len(result.generation.document.articles) == 1
    assert result.generation.document.articles[0].event_id == composition.event_id
    assert len(result.generation.document.reference_panels) == 1
    assert result.finalized.documents


@pytest.mark.asyncio
async def test_whole_classification_prompt_fits_32k_with_schema_and_span_hints():
    import json

    from investo.briefing.event_document import generate_event_document
    from investo.models import NormalizedItem

    items = tuple(
        NormalizedItem(
            source_name=f"official-{index % 4}",
            category="news",
            title="Acme announced Widget",
            summary="Acme announced Widget. " * 40,
            published_at=NOW,
            url=f"https://example.com/notices/{index}",
        )
        for index in range(96)
    )
    calls = []

    def runner(args, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(args, 0, '{"schema_version":3,"events":[]}', "")

    await generate_event_document(
        GenerationInput(
            target_date=NOW.date(),
            segment="us-equity",
            items=items,
            runner=runner,
            watchlist_config=WatchlistConfig(),
            event_observed_at=NOW,
            event_generation_policy=EventExecutionConfig(
                mode="preview", document_schema=3, profile="article_v2"
            ),
        )
    )
    assert len(calls) == 1
    prompt = calls[0]["input"]
    assert len(prompt.encode()) <= 32 * 1024
    context = prompt.split("Transmitted context:\n")[1].split("\nRequired actual item IDs:")[0]
    assert len(context.encode()) <= 24 * 1024
    rows = json.loads(context)["documents"]
    assert 0 < len(rows) < 96
    assert any(row["assertion_hints"] for row in rows)
