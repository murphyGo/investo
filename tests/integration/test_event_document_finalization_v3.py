"""Exercise native Stage 1/2, the actual sole finalizer, writer and sidecar reader."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from investo.briefing._core.orchestration import GenerationPolicy
from investo.briefing.generation_contract import GenerationInput, NativeEventGenerationResult
from investo.briefing.watchlist import WatchlistConfig
from investo.models.event_config import EventGenerationPolicy
from investo.models.event_context import ContextClassificationResult
from investo.models.event_document import EventDigest, EventEditionContent
from investo.orchestrator.event_preview import preview_event_briefing
from investo.publisher.event_archive_reader import (
    event_edition_sidecar_path,
    read_published_event_edition,
)
from investo.publisher.public_document import (
    PublicDocumentFinalizationError,
    finalize_public_bundle,
)
from investo.publisher.writer import write_finalized_document
from tests._helpers.event_context_v3 import NOW
from tests._helpers.event_document_v3 import TARGET, native_case, native_context
from tests.integration.test_event_generation import _ReplayRunner


def test_native_actual_finalizer_is_deterministic_without_legacy_bridge() -> None:
    item, draft = native_case()
    bundles = [
        finalize_public_bundle({draft.segment: draft}, context=native_context((item, draft)))
        for _ in range(2)
    ]
    first, second = (bundle.documents[0] for bundle in bundles)
    assert first.rendered_markdown == second.rendered_markdown
    assert first.markdown_sha256 == second.markdown_sha256
    assert first.edition_view == second.edition_view
    with pytest.raises(TypeError, match="no legacy"):
        _ = first.briefing
    assert "## ①" not in first.rendered_markdown and "## ⑦" not in first.rendered_markdown
    assert "1200" in first.rendered_markdown and "FY2026" in first.rendered_markdown
    assert first.canonical_event_receipts[0].cumulative_fact_hashes == draft.articles[0].fact_ids
    assert first.notification_summary.conclusion == draft.articles[0].headline
    assert first.edition_view is not None
    assert "The service expands access" not in first.edition_view.edition.model_dump_json()


@pytest.mark.parametrize("text", ["문장 끝 미완성", "완전한 문장입니다. " * 20])
def test_invalid_presentation_digest_preserves_valid_article(text: str) -> None:
    item, draft = native_case()
    article = draft.articles[0]
    digest = EventDigest(
        event_id=article.event_id,
        fact_ids=article.fact_ids,
        text=text.strip(),
        source_refs=article.source_refs,
    )
    draft = draft.model_copy(update={"digests": (digest,)})
    sealed = finalize_public_bundle(
        {draft.segment: draft}, context=native_context((item, draft))
    ).documents[0]
    assert sealed.surviving_event_ids == (article.event_id,)
    assert sealed.edition_view is not None and sealed.edition_view.edition.digests == ()
    assert sealed.notification_summary.conclusion == article.headline
    assert sealed.warnings == ("event.digest_omitted",)


@pytest.mark.parametrize(
    "text", ["Acme 매출은 9999 USD입니다." + "가" * 160, "반드시 매수하세요." + "가" * 160]
)
def test_original_digest_hard_claim_cannot_hide_behind_presentation_omission(text: str) -> None:
    item, draft = native_case()
    article = draft.articles[0]
    draft = draft.model_copy(
        update={
            "digests": (
                EventDigest(
                    event_id=article.event_id,
                    fact_ids=article.fact_ids,
                    text=text,
                    source_refs=article.source_refs,
                ),
            )
        }
    )
    with pytest.raises(PublicDocumentFinalizationError):
        finalize_public_bundle({draft.segment: draft}, context=native_context((item, draft)))


def test_native_trust_block_retains_valid_market_sibling() -> None:
    good = native_case("us-equity")
    item, bad = native_case("crypto")
    bad = bad.model_copy(
        update={
            "articles": (
                bad.articles[0].model_copy(update={"what_changed": "Acme Widget 9999 USD입니다."}),
            )
        }
    )
    bundle = finalize_public_bundle(
        {"us-equity": good[1], "crypto": bad}, context=native_context(good, (item, bad))
    )
    assert tuple(d.segment for d in bundle.documents) == ("us-equity",)
    assert [o.state for o in bundle.segment_outcomes] == ["finalized", "trust_blocked"]


def test_native_writer_and_reader_bind_both_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path)
    item, draft = native_case()
    sealed = finalize_public_bundle(
        {draft.segment: draft}, context=native_context((item, draft))
    ).documents[0]
    path = write_finalized_document(sealed)
    assert sha256(path.read_bytes()).hexdigest() == sealed.markdown_sha256
    read = read_published_event_edition(draft.segment, TARGET)
    assert read.status == "available" and read.edition is not None
    assert read.edition.projection_sha256 == read.edition.canonical_projection_hash
    path.write_text(path.read_text() + "tampered")
    assert read_published_event_edition(draft.segment, TARGET).status == "hash_mismatch"
    event_edition_sidecar_path(draft.segment, TARGET).unlink()
    assert read_published_event_edition(draft.segment, TARGET).status == "missing"


async def test_native_preview_runs_exactly_two_existing_provider_stages_without_io() -> None:
    item, draft = native_case()
    classification = ContextClassificationResult(
        schema_version=3, events=(draft.editorial_plan.events[0].source_event,)
    )
    runner = _ReplayRunner(
        [
            classification.model_dump_json(),
            EventEditionContent(articles=draft.articles).model_dump_json(),
        ]
    )
    request = GenerationInput(
        target_date=TARGET,
        segment=draft.segment,
        items=(item,),
        runner=runner,
        watchlist_config=WatchlistConfig(),
        event_observed_at=NOW,
        event_generation_policy=EventGenerationPolicy(mode="preview", document_schema=3),
        generation_policy=GenerationPolicy(timeout_s=3, max_attempts=1, total_budget_s=30),
    )
    result = await preview_event_briefing(request)
    assert isinstance(result.generation, NativeEventGenerationResult)
    assert len(runner.prompts) == 2
    assert len(result.finalized.documents) == 1
    assert result.finalized.documents[0].surviving_event_ids == (draft.articles[0].event_id,)
    with pytest.raises(TypeError, match="no legacy"):
        _ = result.generation.briefing


async def test_native_empty_preview_preserves_quiet_without_provider_calls() -> None:
    runner = _ReplayRunner([])
    request = GenerationInput(
        target_date=TARGET,
        segment="us-equity",
        items=(),
        runner=runner,
        watchlist_config=WatchlistConfig(),
        event_observed_at=NOW,
        event_generation_policy=EventGenerationPolicy(mode="preview", document_schema=3),
    )
    result = await preview_event_briefing(request)
    assert runner.prompts == []
    assert result.finalized.documents[0].edition_view is not None
    assert result.finalized.documents[0].edition_view.edition.availability.status == "quiet"
    limited = await preview_event_briefing(replace(request, data_limited=True))
    assert (
        limited.finalized.documents[0].edition_view.edition.availability.status == "source_limited"
    )
