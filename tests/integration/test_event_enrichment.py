"""Synthetic feed evidence traverses actual collection, generation and sealing.

Only HTTP transport, recorded LLM responses and unrelated archive/visual sidecars
are isolated. Routing, evidence validation, numeric gates and the finalizer remain
the production implementations. No source article or provider response is stored.
"""

from __future__ import annotations

import json
import socket
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Never, cast
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import HttpUrl

from investo.briefing.event_evidence import build_event_candidates, prepare_evidence_documents
from investo.briefing.generation_contract import GenerationInput, GenerationResult
from investo.briefing.pipeline import generate_briefing_from_input
from investo.briefing.segments import segment_items
from investo.briefing.watchlist import WatchlistConfig
from investo.models import Briefing, MarketSegment, NormalizedItem, SourceOutcome
from investo.models.enrichment import EnrichmentPolicy, EnrichmentQualification, SourceQualification
from investo.models.event_config import EventExecutionConfig, EventMode
from investo.models.events import EventCandidate, EventCandidateDraft, EventFactDraft, EvidenceRef
from investo.orchestrator import pipeline
from investo.orchestrator.event_receipts import EventReceiptBaseline
from investo.orchestrator.stages import PipelineContext
from investo.publisher.public_document import (
    FinalizedPublicBundle,
    PublicDocumentContext,
    finalize_public_bundle,
)
from investo.sources import aggregator
from investo.sources.cnbc_top_news import CnbcTopNewsAdapter
from investo.sources.fed_speech_rss import FedSpeechRssAdapter
from investo.sources.korea_policy_rss import KoreaPolicyRssAdapter
from investo.sources.protocol import SourceAdapter
from tests._helpers.briefing_pipeline import valid_stage2_markdown

_TARGET = date(2026, 9, 21)
_OBSERVED = datetime(2026, 9, 22, 6, tzinfo=UTC)
_FACT = "매출 123.45억 달러를 기록했습니다."
_FIRST_SENTENCE = "Acme는 분기 매출 123.45억 달러를 발표했습니다."
_UNSELECTED = "선정하지 않은 독립 배경 문장입니다."
_DESCRIPTION = "합성 자료의 사업 배경을 설명합니다. " * 18 + _UNSELECTED + " " + _FACT
_OVER_CAP = "EXCERPT_AFTER_1200_MUST_NOT_ESCAPE"
_KOREA_FACT = "국내한정별도근거는 금융교육 안내를 확인했습니다."
_FAILED_FACT = "FAILED_SOURCE_EVIDENCE_MUST_NOT_ESCAPE"
_KOREA_FEED = "https://www.fsc.go.kr/synthetic-feed.xml"
_PUBLICATION = "Mon, 21 Sep 2026 12:00:00 GMT"
_FED_BODY_URL = "https://www.federalreserve.gov/newsevents/speech/synthetic20260921a.htm"
_FED_FEED_DETAIL = (
    "이것은 합성 연설의 원래 피드 설명입니다. 원문에서 추가 설명을 확인할 수 있습니다."
)


def _rss(*, title: str, description: str, url: str) -> bytes:
    return (
        "<rss><channel><item>"
        f"<title>{title}</title><link>{url}</link><pubDate>{_PUBLICATION}</pubDate>"
        f"<description><![CDATA[<p>{description}</p>]]></description>"
        f"<guid>{url}</guid></item></channel></rss>"
    ).encode()


def _cnbc_xml() -> bytes:
    return _rss(
        title="Acme 분기 실적 발표",
        description=_DESCRIPTION + " 추가 합성 배경입니다." * 100 + _OVER_CAP,
        url="https://www.cnbc.com/synthetic-earnings-release.html",
    )


def _forbid_io(*_args: object, **_kwargs: object) -> Never:
    pytest.fail("offline evidence integration attempted real network, Git or provider process")


@pytest.fixture
def isolated_evidence_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket.socket, "connect", _forbid_io)
    monkeypatch.setattr(subprocess, "run", _forbid_io)
    monkeypatch.setenv("INVESTO_SEGMENT_GENERATION_CONCURRENCY", "1")
    monkeypatch.setenv("INVESTO_KOREA_POLICY_RSS_URLS", _KOREA_FEED)
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    monkeypatch.setattr(pipeline, "load_watchlist", lambda: WatchlistConfig())
    monkeypatch.setattr(pipeline, "_load_recent_context_for_run", lambda *_a: None)
    monkeypatch.setattr(pipeline, "_load_market_anchors_for_run", AsyncMock(return_value=({}, {})))
    monkeypatch.setattr(pipeline, "_load_carryover_for_run", lambda *_a: {})
    monkeypatch.setattr(pipeline, "_advance_and_persist_macro_carryover", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "_persist_fact_snapshot_safely", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "_append_daily_coverage_line", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "_run_image_candidate_stage", lambda *_a, **_k: ((), "ok: empty"))
    monkeypatch.setattr(
        pipeline, "_inject_chart_blocks_into_segments", lambda briefings, **_k: (briefings, ())
    )

    async def no_visual_sidecars(briefings: Any, *_a: object, **_k: object) -> Any:
        return briefings, (), {}

    monkeypatch.setattr(pipeline, "_stage_prepare_segment_visual_assets", no_visual_sidecars)
    return tmp_path


class RecordedResponses:
    def __init__(self, responses: Sequence[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert input is not None
        self.prompts.append(input)
        assert self.responses, "unexpected additional provider call"
        return subprocess.CompletedProcess(args, 0, self.responses.pop(0), "")


def _sections() -> dict[str, str]:
    return {
        "market_summary": "공개된 발표 자료를 확인했습니다.",
        "sector_flow": "섹터 전체의 수급 자료는 확인하지 못했습니다.",
        "indicators_events": "추가로 확정된 일정은 확인하지 못했습니다.",
        "notable_tickers": "개별 기업의 후속 발표를 확인할 필요가 있습니다.",
        "today_watch": "후속 공식 자료에서 사업 설명을 확인할 필요가 있습니다.",
    }


def _recorded_v2(
    items: Sequence[NormalizedItem],
) -> tuple[tuple[str, str], EventCandidate | None]:
    """Author synthetic responses using IDs from the real parsed input buffers."""
    events: list[dict[str, Any]] = []
    narratives: list[dict[str, Any]] = []
    candidate = None
    if items[0].source_name == "cnbc-top-news":
        (document,) = prepare_evidence_documents(items, received_at=_OBSERVED)

        def ref(text: str, field: str = "title") -> EvidenceRef:
            start = getattr(document, field).index(text)
            return EvidenceRef(
                document_id=document.document_id,
                revision_id=document.revision_id,
                field=field,
                start=start,
                end=start + len(text),
            )

        fact_ref = ref(_FACT, "detail_excerpt")
        draft = EventCandidateDraft(
            item_ids=(1,),
            event_kind="earnings_result",
            actor_refs=(ref("Acme"),),
            action_refs=(ref("실적 발표"),),
            relation_refs=(fact_ref,),
            impact_refs=(fact_ref,),
            timing="announced",
            relation="direct",
            impact="company",
            facts=(EventFactDraft(predicate="result", evidence_ref=fact_ref, unit="달러"),),
        )
        candidate = build_event_candidates((draft,), items, (document,), observed_at=_OBSERVED)[0]
        events.append(draft.model_dump(mode="json"))
        narratives.append(
            {
                "event_id": candidate.event_id,
                "headline": "Acme 분기 실적 발표",
                "what_happened": _FIRST_SENTENCE,
                "fact_ids": candidate.required_fact_ids,
                "source_refs": [r.model_dump(mode="json") for r in candidate.evidence_refs],
                "meaning": {"text": None, "mode": "unavailable"},
                "reaction": {"text": None, "status": "unavailable"},
            }
        )
    classification = json.dumps(
        {"schema_version": 2, "assignments": {"1": 2}, "unassigned": [], "events": events},
        ensure_ascii=False,
    )
    synthesis = json.dumps(
        {"schema_version": 2, "sections": _sections(), "events": narratives}, ensure_ascii=False
    )
    return (classification, synthesis), candidate


@dataclass(frozen=True)
class EvidenceRun:
    items: tuple[NormalizedItem, ...]
    source_outcomes: tuple[SourceOutcome, ...]
    requests: dict[MarketSegment, GenerationInput]
    runners: dict[MarketSegment, RecordedResponses]
    generated: dict[MarketSegment, GenerationResult]
    bundle: FinalizedPublicBundle
    candidate: EventCandidate | None
    http_requests: tuple[httpx.Request, ...]
    collection_kwargs: dict[str, Any]


async def _run_feed_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    *,
    mode: EventMode = "preview",
    include_korea: bool = False,
    failed_fed: bool = False,
) -> EvidenceRun:
    adapters: list[SourceAdapter] = [CnbcTopNewsAdapter()]
    if include_korea:
        adapters.append(KoreaPolicyRssAdapter())
    if failed_fed:
        adapters.append(FedSpeechRssAdapter())
    http_requests: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        http_requests.append(request)
        if str(request.url) == CnbcTopNewsAdapter._FEED_URL:
            return httpx.Response(200, content=_cnbc_xml())
        if str(request.url) == _KOREA_FEED:
            return httpx.Response(
                200,
                content=_rss(
                    title="금융위원회 금융교육 안내",
                    description="합성 국내 교육 자료 설명입니다. " * 20 + _KOREA_FACT,
                    url="https://www.fsc.go.kr/synthetic-education-release",
                ),
            )
        if request.url.host == "www.federalreserve.gov" and failed_fed:
            return httpx.Response(403, content=_FAILED_FACT.encode())
        pytest.fail("unexpected HTTP source or unqualified body fetch")

    original_client = httpx.AsyncClient
    original_collect = aggregator.collect_sources
    original_generate = generate_briefing_from_input
    collection_kwargs: dict[str, Any] = {}
    requests: dict[MarketSegment, GenerationInput] = {}
    runners: dict[MarketSegment, RecordedResponses] = {}

    async def observe_collect(target: date, **kwargs: Any) -> Any:
        collection_kwargs.update(kwargs)
        return await original_collect(target, **kwargs)

    async def observe_generate(request: GenerationInput) -> GenerationResult:
        assert request.segment is not None
        requests[request.segment] = request
        return await original_generate(request)

    with monkeypatch.context() as scoped:
        scoped.setattr(aggregator, "list_sources", lambda: adapters)
        scoped.setattr(
            httpx,
            "AsyncClient",
            lambda *a, **kw: original_client(*a, transport=httpx.MockTransport(transport), **kw),
        )
        scoped.setattr(pipeline, "_default_collect_sources", observe_collect)
        scoped.setattr(pipeline, "_u2_generate_from_input", observe_generate)
        ctx = PipelineContext(
            target_date=_TARGET,
            site_url_base=HttpUrl("https://example.invalid/investo"),
            event_config=EventExecutionConfig(mode),
            event_observed_at=_OBSERVED,
            run_started_at=_OBSERVED,
            news_replay=True,
        )
        collected = await pipeline.CollectStage().execute(ctx, {})
        assert collected.status == "ok" and collected.data is not None
        items = tuple(cast(list[NormalizedItem], collected.data["items"]))
        outcomes = cast(tuple[SourceOutcome, ...], collected.data["source_outcomes"])
        routed = segment_items(items)
        responses: list[str] = []
        candidate = None
        for segment in ("domestic-equity", "us-equity", "crypto"):
            rows = routed.for_segment(segment)
            if not rows:
                continue
            if mode in {"preview", "active"}:
                recorded, selected = _recorded_v2(rows)
                candidate = selected or candidate
                responses.extend(recorded)
            else:
                responses.extend(
                    (
                        json.dumps({"assignments": {"1": 2}, "unassigned": []}),
                        valid_stage2_markdown(),
                    )
                )
        runner = RecordedResponses(responses)
        ctx = replace(ctx, runner=runner)
        accumulated = {
            **collected.data,
            "artifact_staging_root": root / "staging",
            # Explicit recorded history for this synthetic replay. No Git read
            # occurs, and no event occurrence time is inferred from publication.
            "event_baseline": EventReceiptBaseline("1" * 40, "2" * 64, ()),
        }
        generated = await pipeline.GenerateStage().execute(ctx, accumulated)
        assert generated.status == "ok" and generated.data is not None, generated.error
        # Each nonempty segment consumes exactly two recorded responses. This
        # maps observed prompt slices without changing the production runner.
        index = 0
        for segment in ("domestic-equity", "us-equity", "crypto"):
            key = cast(MarketSegment, segment)
            if not requests[key].items:
                continue
            observed = RecordedResponses(())
            observed.prompts = runner.prompts[index : index + 2]
            runners[key] = observed
            index += 2
        assert len(runner.prompts) == index
        bundle = finalize_public_bundle(
            cast(dict[MarketSegment, Briefing], generated.data["segment_briefings"]),
            context=cast(PublicDocumentContext, generated.data["public_document_context"]),
        )
        assert {doc.segment for doc in bundle.documents} == {
            "domestic-equity",
            "us-equity",
            "crypto",
        }, bundle.segment_outcomes
    return EvidenceRun(
        items,
        outcomes,
        requests,
        runners,
        cast(dict[MarketSegment, GenerationResult], generated.data["event_results"]),
        bundle,
        candidate,
        tuple(http_requests),
        collection_kwargs,
    )


async def test_fact_after_legacy_cut_reaches_actual_two_stage_terminal_output(
    isolated_evidence_pipeline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = await _run_feed_pipeline(monkeypatch, isolated_evidence_pipeline)
    (item,) = run.items
    evidence = item.event_evidence
    assert evidence is not None and run.candidate is not None
    assert item.summary == _DESCRIPTION[:280].strip()
    assert _FACT not in item.title + item.summary
    assert 280 < evidence.detail_excerpt.index(_FACT) < 1200 - len(_FACT)
    assert len(evidence.detail_excerpt) == 1200 and _OVER_CAP not in evidence.detail_excerpt
    assert evidence.received_at == _OBSERVED
    assert evidence.event_time is None and evidence.event_time_basis == "unknown"
    assert run.candidate.evidence_state == "detail_limited"
    assert run.collection_kwargs["evidence_received_at"] == _OBSERVED
    assert run.requests["us-equity"].items == (item,)
    first, second = run.runners["us-equity"].prompts
    assert evidence.detail_excerpt in first and evidence.revision_id in first
    assert _FACT in second and run.candidate.event_id in second
    assert _UNSELECTED not in second and _OVER_CAP not in first + second
    result = run.generated["us-equity"]
    assert result.event_plan is not None
    assert result.event_plan.selected[0].required_fact_ids == run.candidate.required_fact_ids
    doc = next(doc for doc in run.bundle.documents if doc.segment == "us-equity")
    assert doc.surviving_event_ids == (run.candidate.event_id,)
    assert _FIRST_SENTENCE in doc.briefing.rendered_markdown
    assert doc.notification_summary.events[0].fact_summary == _FIRST_SENTENCE
    assert doc.notification_summary.events[0].event_id == run.candidate.event_id
    assert len(run.http_requests) == 1  # Feed request only; no commercial body.


async def test_off_shadow_preserve_legacy_input_prompt_and_terminal_bytes(
    isolated_evidence_pipeline: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="investo.orchestrator.pipeline")
    off = await _run_feed_pipeline(monkeypatch, isolated_evidence_pipeline, mode="off")
    assert "[event_shadow]" not in caplog.text
    caplog.clear()
    shadow = await _run_feed_pipeline(monkeypatch, isolated_evidence_pipeline, mode="shadow")
    messages = [record.getMessage() for record in caplog.records if "[event_shadow]" in record.msg]
    assert any("segment=us-equity" in message and "news_count=1" in message for message in messages)
    assert all(_FACT not in message and _DESCRIPTION not in message for message in messages)
    assert [item.model_dump_json() for item in off.items] == [
        item.model_dump_json() for item in shadow.items
    ]
    assert all(item.event_evidence is None for item in (*off.items, *shadow.items))
    assert "evidence_received_at" not in off.collection_kwargs
    assert "evidence_received_at" not in shadow.collection_kwargs
    assert off.runners["us-equity"].prompts == shadow.runners["us-equity"].prompts
    assert [doc.briefing.rendered_markdown.encode() for doc in off.bundle.documents] == [
        doc.briefing.rendered_markdown.encode() for doc in shadow.bundle.documents
    ]
    assert len(off.http_requests) == len(shadow.http_requests) == 1


async def test_routed_and_failed_sources_cannot_supply_another_items_evidence(
    isolated_evidence_pipeline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = await _run_feed_pipeline(
        monkeypatch, isolated_evidence_pipeline, include_korea=True, failed_fed=True
    )
    assert {item.source_name for item in run.items} == {"cnbc-top-news", "korea-policy-rss"}
    assert {item.source_name for item in run.requests["us-equity"].items} == {"cnbc-top-news"}
    assert {item.source_name for item in run.requests["domestic-equity"].items} == {
        "korea-policy-rss"
    }
    assert run.requests["crypto"].items == ()
    assert (
        next(row for row in run.source_outcomes if row.source_name == "fed-speech-rss").status
        == "failed"
    )
    us_item = run.requests["us-equity"].items[0]
    korea_item = run.requests["domestic-equity"].items[0]
    assert us_item.event_evidence is not None and korea_item.event_evidence is not None
    assert us_item.event_evidence.document_id != korea_item.event_evidence.document_id
    assert _KOREA_FACT in korea_item.event_evidence.detail_excerpt
    assert _KOREA_FACT not in "".join(run.runners["us-equity"].prompts)
    assert _FAILED_FACT not in "".join(
        prompt for runner in run.runners.values() for prompt in runner.prompts
    )
    us_document = next(doc for doc in run.bundle.documents if doc.segment == "us-equity")
    assert us_document.notification_summary.events[0].fact_summary == _FIRST_SENTENCE
    assert _KOREA_FACT not in us_document.briefing.rendered_markdown


def _qualification() -> EnrichmentQualification:
    """Synthetic permission witness only; never used to qualify a real source."""
    return EnrichmentQualification(
        sources=(
            SourceQualification(
                source_name="fed-speech-rss",
                checked_at=_OBSERVED,
                official_discovery_url="https://www.federalreserve.gov/feeds/feeds.htm",
                allowed_host="www.federalreserve.gov",
                allowed_path="/newsevents/speech/",
                content_type="text/html",
                public_rights_basis="Synthetic fixture permission witness; no real body content.",
                extraction_selector_version="fed-article-body-v1",
                fixture_sha256="3" * 64,
                status="qualified",
                reason="Synthetic offline integration qualification.",
            ),
        )
    )


async def _collect_fed_with_body_policy(
    monkeypatch: pytest.MonkeyPatch,
    *,
    policy: EnrichmentPolicy,
    qualification: EnrichmentQualification | None,
    body_status: int = 403,
    body_html: str = "No qualified article selector in this synthetic page.",
) -> tuple[dict[str, Any], tuple[httpx.Request, ...], dict[str, float]]:
    requests: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/feeds/speeches.xml":
            return httpx.Response(
                200,
                content=_rss(
                    title="연준 금융 접근성 연설",
                    description=_FED_FEED_DETAIL,
                    url=_FED_BODY_URL,
                ),
            )
        if request.url.path == "/feeds/testimony.xml":
            return httpx.Response(200, content=b"<rss><channel></channel></rss>")
        if str(request.url) == _FED_BODY_URL:
            return httpx.Response(
                body_status, text=body_html, headers={"content-type": "text/html"}
            )
        pytest.fail("unexpected official feed or body URL")

    original_client = httpx.AsyncClient
    with monkeypatch.context() as scoped:
        scoped.setattr("investo.models.enrichment.EVENT_ENRICHMENT_ACTIVE_READY", True)
        scoped.setattr(aggregator, "list_sources", lambda: [FedSpeechRssAdapter()])
        scoped.setattr(
            httpx,
            "AsyncClient",
            lambda *a, **kw: original_client(*a, transport=httpx.MockTransport(transport), **kw),
        )
        scoped.setattr(pipeline, "load_enrichment_qualification", _forbid_io)
        ctx = PipelineContext(
            target_date=_TARGET,
            site_url_base=HttpUrl("https://example.invalid/investo"),
            event_config=EventExecutionConfig("preview"),
            event_observed_at=_OBSERVED,
            news_replay=True,
            event_enrichment_policy=policy,
            event_qualification=qualification,
        )
        collected = await pipeline.CollectStage().execute(ctx, {})
        assert collected.status == "ok" and collected.data is not None
    return collected.data, tuple(requests), collected.timings


@pytest.mark.parametrize("mode", ["off", "shadow"])
async def test_optional_body_off_shadow_do_not_read_manifest_or_make_body_requests(
    isolated_evidence_pipeline: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    # No supplied manifest: any accidental disk load is explicitly prohibited.
    data, requests, timings = await _collect_fed_with_body_policy(
        monkeypatch, policy=EnrichmentPolicy(mode=cast(Any, mode)), qualification=None
    )
    assert len(requests) == 2 and all(
        request.url.path.startswith("/feeds/") for request in requests
    )
    assert data["event_enrichment_outcomes"] == ()
    assert data["event_enrichment_request_count"] == 0
    assert "collect_event_enrichment" not in timings
    (item,) = data["items"]
    assert item.event_evidence.detail_excerpt == _FED_FEED_DETAIL
    assert item.event_evidence.event_time is None


async def test_unqualified_body_keeps_original_feed_without_http(
    isolated_evidence_pipeline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline, _, _ = await _collect_fed_with_body_policy(
        monkeypatch, policy=EnrichmentPolicy(), qualification=None
    )
    data, requests, _ = await _collect_fed_with_body_policy(
        monkeypatch, policy=EnrichmentPolicy(mode="active"), qualification=EnrichmentQualification()
    )
    assert data["items"] == baseline["items"]
    assert len(requests) == 2 and data["event_enrichment_request_count"] == 0
    (outcome,) = data["event_enrichment_outcomes"]
    assert outcome.status == "enrichment_unavailable" and outcome.reason == "unqualified"
    assert outcome.document_id == data["items"][0].event_evidence.document_id


@pytest.mark.parametrize(
    ("status", "reason"), [(403, "request_failed"), (200, "selector_unavailable")]
)
async def test_failed_official_body_preserves_feed_item_and_source_success(
    isolated_evidence_pipeline: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    reason: str,
) -> None:
    baseline, _, _ = await _collect_fed_with_body_policy(
        monkeypatch, policy=EnrichmentPolicy(), qualification=None
    )
    data, requests, timings = await _collect_fed_with_body_policy(
        monkeypatch,
        policy=EnrichmentPolicy(mode="active"),
        qualification=_qualification(),
        body_status=status,
    )
    assert data["items"] == baseline["items"]
    assert len(requests) == 3 and data["event_enrichment_request_count"] == 1
    assert sum(str(request.url) == _FED_BODY_URL for request in requests) == 1
    assert "collect_event_enrichment" in timings
    (source,) = data["source_outcomes"]
    assert (
        source.source_name == "fed-speech-rss" and source.status == "ok" and source.item_count == 1
    )
    (outcome,) = data["event_enrichment_outcomes"]
    assert outcome.status == "enrichment_unavailable" and outcome.reason == reason
    assert outcome.source_name == source.source_name
    assert outcome.document_id == data["items"][0].event_evidence.document_id
    assert data["items"][0].event_evidence.event_time is None


async def test_qualified_body_revises_only_same_document_typed_evidence(
    isolated_evidence_pipeline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline, _, _ = await _collect_fed_with_body_policy(
        monkeypatch, policy=EnrichmentPolicy(), qualification=None
    )
    body_fact = "합성 원문은 금융 교육의 접근성을 설명했습니다."
    data, requests, _ = await _collect_fed_with_body_policy(
        monkeypatch,
        policy=EnrichmentPolicy(mode="active"),
        qualification=_qualification(),
        body_status=200,
        body_html=(
            '<div id="article"><div class="col-xs-12 col-sm-8 col-md-8">'
            f"<p>{body_fact}</p></div></div>"
        ),
    )
    original, updated = baseline["items"][0], data["items"][0]
    assert original.model_dump(exclude={"event_evidence"}) == updated.model_dump(
        exclude={"event_evidence"}
    )
    assert original.event_evidence.document_id == updated.event_evidence.document_id
    assert original.event_evidence.revision_id != updated.event_evidence.revision_id
    assert updated.event_evidence.detail_excerpt == body_fact
    assert updated.event_evidence.event_time is None
    assert updated.event_evidence.received_at == _OBSERVED
    assert len(requests) == 3 and data["event_enrichment_request_count"] == 1
    (outcome,) = data["event_enrichment_outcomes"]
    assert outcome.status == "enriched" and outcome.reason is None
