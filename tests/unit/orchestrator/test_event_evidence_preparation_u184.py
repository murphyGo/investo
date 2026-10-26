"""A source's qualification, failure and HTTP quota survive the shared seam."""

from dataclasses import replace

import httpx
import pytest
from pydantic import ValidationError

from investo.models.coverage import SourceOutcome
from investo.models.enrichment import EnrichmentPolicy, EnrichmentQualification, SourceQualification
from investo.models.event_evidence import make_event_context_document, make_evidence_document
from investo.models.event_passages import passage_spans
from investo.orchestrator.event_evidence import prepare_event_evidence
from tests.unit.models.test_enrichment import qualification_record
from tests.unit.sources.test_event_evidence import NOW, body, source_item


def preview_policy(qualification: EnrichmentQualification) -> EnrichmentPolicy:
    return EnrichmentPolicy(
        mode="preview",
        article_passages=True,
        max_excerpt_chars=6000,
        preview_sources=("cftc-policy-rss",),
        qualification_sha256=qualification.policy_hash,
    )


def expanded_qualification() -> EnrichmentQualification:
    return EnrichmentQualification(
        sources=(
            SourceQualification.model_validate(
                {
                    **qualification_record("cftc-policy-rss").model_dump(),
                    "max_excerpt_chars": 6000,
                    "private_retention_basis": "Synthetic test qualification",
                }
            ),
        )
    )


def test_expanded_retention_cannot_be_inherited_from_old_qualification() -> None:
    with pytest.raises(ValidationError, match="retention"):
        SourceQualification.model_validate(
            {
                **qualification_record("cftc-policy-rss").model_dump(),
                "max_excerpt_chars": 6000,
            }
        )


def test_complete_late_passage_and_original_offsets() -> None:
    text = "X" * 1300 + "\nThe new rule applies only after formal approval.\nNo current change."
    spans = passage_spans(text)
    assert spans[0][0] == 1301
    evidence = make_evidence_document(
        source_name="official",
        title="Announcement",
        detail_excerpt=text,
        published_at=NOW,
        received_at=NOW,
    )
    legacy = make_event_context_document(evidence)
    article = make_event_context_document(evidence, article_passages=True)
    assert "formal approval" not in " ".join(c.text for c in legacy.chunks)
    chunk = next(c for c in article.chunks if "formal approval" in c.text)
    field, start, end = chunk.source_locator.split(":")
    assert getattr(evidence, field)[int(start) : int(end)] == chunk.text


@pytest.mark.asyncio
async def test_preview_requires_capability_and_exact_qualification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("investo.models.enrichment.EVENT_ENRICHMENT_PREVIEW_READY", False)
    qualification = expanded_qualification()
    kwargs = dict(
        policy=preview_policy(qualification), qualification=qualification, received_at=NOW
    )
    with pytest.raises(ValueError, match="qualification"):
        await prepare_event_evidence((source_item(),), (), **kwargs)
    monkeypatch.setattr("investo.models.enrichment.EVENT_ENRICHMENT_PREVIEW_READY", True)
    with pytest.raises(ValueError, match="hash mismatch"):
        await prepare_event_evidence(
            (source_item(),),
            (),
            **{**kwargs, "policy": replace(kwargs["policy"], qualification_sha256="0" * 64)},
        )


@pytest.mark.asyncio
async def test_failed_source_no_http_and_expanded_qualified_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("investo.models.enrichment.EVENT_ENRICHMENT_PREVIEW_READY", True)
    qualification = expanded_qualification()
    calls = []
    paragraphs = "".join(f"<p>Paragraph {i}: " + "background " * 55 + ".</p>" for i in range(5))

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, text=body(text=paragraphs), headers={"content-type": "text/html"}
        )

    original = source_item()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        failed = await prepare_event_evidence(
            (original,),
            (
                SourceOutcome(
                    original.source_name,
                    "news",
                    "failed",
                    failure_reason="test failure",
                    transient=False,
                ),
            ),
            policy=preview_policy(qualification),
            qualification=qualification,
            received_at=NOW,
            client=client,
        )
        assert not calls and failed.items == (original,)
        result = await prepare_event_evidence(
            (original,),
            (),
            policy=preview_policy(qualification),
            qualification=qualification,
            received_at=NOW,
            client=client,
        )
    assert result.request_count == len(calls) == 1
    assert result.items[0].summary == original.summary
    assert result.items[0].event_evidence is not None
    assert 1200 < len(result.items[0].event_evidence.detail_excerpt) <= 6000


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["off", "shadow"])
async def test_passive_preparation_does_not_open_http(mode: str) -> None:
    item = source_item()
    result = await prepare_event_evidence(
        (item,),
        (),
        policy=EnrichmentPolicy(mode=mode),
        qualification=EnrichmentQualification(),
        received_at=NOW,
    )
    assert result.items == (item,) and result.request_count == 0


def test_complete_paragraph_separators_are_not_missing_content() -> None:
    evidence = make_evidence_document(
        source_name="official",
        title="Two paragraphs",
        detail_excerpt="First paragraph.\nSecond paragraph.",
        published_at=NOW,
        received_at=NOW,
    )
    document = make_event_context_document(evidence, article_passages=True)
    assert not document.evidence_budget_limited
    assert len([c for c in document.chunks if c.role == "background"]) == 2


def test_legacy_distinct_role_chunks_cannot_exceed_four() -> None:
    evidence = make_evidence_document(
        source_name="official", title="abcdefghij", published_at=NOW, received_at=NOW
    )
    with pytest.raises(ValueError, match="budget"):
        make_event_context_document(
            evidence,
            role_chunks=tuple(("fact", evidence.title[i], f"title:{i}:{i + 1}") for i in range(5)),
        )


@pytest.mark.asyncio
async def test_source_extraction_omission_survives_context_conversion(monkeypatch) -> None:
    monkeypatch.setattr("investo.models.enrichment.EVENT_ENRICHMENT_PREVIEW_READY", True)
    qualification = expanded_qualification()
    content = "".join(f"<p>Complete paragraph number {i}.</p>" for i in range(7))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text=body(text=content), headers={"content-type": "text/html"}
            )
        )
    ) as client:
        result = await prepare_event_evidence(
            (source_item(),),
            (),
            policy=preview_policy(qualification),
            qualification=qualification,
            received_at=NOW,
            client=client,
        )
    evidence = result.items[0].event_evidence
    assert evidence is not None and evidence.evidence_budget_limited
    assert "number 6" not in evidence.detail_excerpt
    assert make_event_context_document(evidence, article_passages=True).evidence_budget_limited
