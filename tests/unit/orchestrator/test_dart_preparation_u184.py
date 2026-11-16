"""The real collection seam owns DART HTTP, quarantine and native field buffers."""

import asyncio
import hashlib
import json
import logging
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from investo.briefing.event_context import prepare_context_documents
from investo.briefing.event_input import select_event_input_items
from investo.models.coverage import SourceOutcome
from investo.models.enrichment import EnrichmentPolicy, EnrichmentQualification
from investo.orchestrator.event_evidence import prepare_event_evidence
from investo.sources._dart_document import parse_dart_document
from investo.sources._dart_evidence import dart_runtime_evidence
from investo.sources.event_evidence import (
    load_enrichment_qualification,
    load_source_slot_qualification,
)
from tests.unit.sources.test_dart_document_u173 import NOW, archive_case, item_case

ROOT = Path(__file__).parents[3]
SECRET = "SYNTHETIC_DART_CREDENTIAL_NEVER_EMIT"


def permissions(**changes):
    matrix = load_source_slot_qualification(ROOT / "ops/event_source_slot_qualification.json")
    qualification = load_enrichment_qualification(
        ROOT / "ops/event_dart_preview_qualification.json"
    )
    policy = EnrichmentPolicy(
        mode="preview",
        article_passages=True,
        preview_sources=("dart-disclosure",),
        qualification_sha256=qualification.policy_hash,
    )
    return replace(policy, **changes), qualification, matrix


def listing_case(item=None, **changes):
    item = item or item_case()
    entry = {
        key: value
        for key, value in item.raw_metadata.items()
        if key
        in {"corp_code", "corp_name", "report_nm", "rcept_no", "rcept_dt", "corp_cls", "stock_code"}
    }
    entry["rm"] = "코"
    entry.update(changes)
    return {
        "status": "000",
        "page_no": 1,
        "page_count": 100,
        "total_count": 1,
        "total_page": 1,
        "list": [entry],
    }


async def run_case(
    handler, *, items=None, outcomes=(), policy=None, qualification=None, matrix=None, **kwargs
):
    default_policy, default_qualification, default_matrix = permissions()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await prepare_event_evidence(
            items or (item_case(),),
            outcomes,
            policy=policy or default_policy,
            qualification=qualification or default_qualification,
            received_at=NOW,
            client=client,
            slot_qualification=matrix or default_matrix,
            **kwargs,
        )


def positive_handler(seen):
    def respond(request):
        seen.append(request)
        assert request.url.scheme == "https" and request.url.host == "opendart.fss.or.kr"
        assert request.url.params["crtfc_key"] == SECRET
        assert request.headers["accept-encoding"] == "identity"
        if request.url.path == "/api/list.json":
            assert request.url.params["last_reprt_at"] == "Y"
            return httpx.Response(200, json=listing_case())
        assert request.url.path == "/api/document.xml"
        return httpx.Response(200, content=archive_case())

    return respond


async def test_shared_preparation_retains_all_five_slots_in_native_passage(monkeypatch, caplog):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    caplog.set_level(logging.DEBUG)
    original = item_case()
    before = original.model_dump_json()
    seen = []
    result = await run_case(positive_handler(seen), items=(original,))
    assert result.request_count == len(seen) == 2
    assert result.outcomes[0].status == "enriched" and not result.items[0].event_input_blocked
    assert original.model_dump_json() == before
    assert result.items[0].title == original.title and result.items[0].summary == original.summary
    evidence = result.items[0].event_evidence
    assert evidence is not None and "\n" not in evidence.detail_excerpt
    (native,) = prepare_context_documents(result.items, received_at=NOW, article_passages=True)
    assert native.content_contract_version == 2
    assert len([c for c in native.chunks if c.source_locator.startswith("detail_excerpt:")]) == 1
    assert native.time.published_at.precision == "date"
    assert native.time.occurred_at.precision == native.time.announced_at.precision == "unknown"
    trace = result.outcomes[0].dart
    assert trace is not None and trace.latest_status == "as_observed" and trace.requests == 2
    assert trace.listing_received_at <= trace.document_received_at
    assert evidence.received_at == trace.document_received_at
    assert (
        trace.native_context_sha256 == hashlib.sha256(native.model_dump_json().encode()).hexdigest()
    )
    raw = archive_case()
    parsed = parse_dart_document(
        original,
        raw,
        response_sha256=hashlib.sha256(raw).hexdigest(),
        received_at=evidence.received_at,
    )
    rebuilt = dart_runtime_evidence(parsed)
    assert rebuilt.context == native and sum(map(len, rebuilt.field_refs.values())) == 25
    assert len(parsed.xml_bindings) == 29
    assert parsed.item.event_evidence.detail_excerpt.replace("\n", " ") == evidence.detail_excerpt
    assert len(parsed.item.event_evidence.detail_excerpt) == len(evidence.detail_excerpt)
    assert SECRET not in result.model_dump_json() + caplog.text


@pytest.mark.parametrize(
    "failure",
    [
        "superseded",
        "withdrawn",
        "unknown_rm",
        "missing_rm",
        "bad_rm",
        "empty",
        "provider",
        "missing_target",
        "duplicate",
        "pages",
        "identity",
        "json",
        "duplicate_key",
        "secret",
    ],
)
async def test_latest_failure_blocks_before_document_and_before_classifier(monkeypatch, failure):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    payload = listing_case()
    seen = []
    if failure == "superseded":
        payload["list"][0]["rm"] = "코정"
    if failure == "withdrawn":
        payload["list"][0]["rm"] = "철"
    if failure == "unknown_rm":
        payload["list"][0]["rm"] = "?"
    if failure == "missing_rm":
        payload["list"][0].pop("rm")
    if failure == "bad_rm":
        payload["list"][0]["rm"] = 1
    if failure == "empty":
        payload = {"status": "013"}
    if failure == "provider":
        payload = {"status": "010", "message": SECRET}
    if failure == "missing_target":
        payload["list"][0]["rcept_no"] = "20260902000002"
    if failure == "duplicate":
        payload["list"] *= 2
        payload["total_count"] = 2
    if failure == "pages":
        payload.update(total_count=101, total_page=2)
    if failure == "identity":
        payload["list"][0]["corp_name"] = "다른합성회사"
    if failure == "secret":
        payload["message"] = SECRET
    raw = json.dumps(payload).encode()
    if failure == "json":
        raw = b"{"
    if failure == "duplicate_key":
        raw = b'{"status":"013",' + raw[1:]

    def respond(request):
        seen.append(request)
        assert request.url.path == "/api/list.json"
        return httpx.Response(200, content=raw)

    original = item_case()
    before = original.model_dump_json()
    result = await run_case(respond, items=(original,))
    assert result.request_count == len(seen) == 1
    assert (
        result.outcomes[0].status == "enrichment_unavailable"
        and result.items[0].event_input_blocked
    )
    assert (
        select_event_input_items(result.items, target_date=date(2026, 9, 2), article_v2=True) == ()
    )
    assert original.model_dump_json() == before
    assert result.items[0].model_dump(exclude={"event_input_blocked"}) == original.model_dump(
        exclude={"event_input_blocked"}
    )
    assert SECRET not in result.model_dump_json()


@pytest.mark.parametrize(
    "reason",
    ["failed", "skipped", "preblocked", "no_permission", "no_key", "passages_off", "deadline"],
)
async def test_zero_http_paths_still_quarantine_unsafe_dart(monkeypatch, reason):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = permissions()
    original = item_case()
    outcomes = ()
    kwargs = {}
    if reason in {"failed", "skipped"}:
        outcomes = (
            SourceOutcome(
                "dart-disclosure",
                "news",
                reason,
                **(
                    {"skip_reason": "operator_disabled"}
                    if reason == "skipped"
                    else {"failure_reason": "synthetic", "transient": False}
                ),
            ),
        )
    if reason == "preblocked":
        original = original.model_copy(update={"event_input_blocked": True})
    if reason == "no_permission":
        qualification = EnrichmentQualification()
        policy = replace(policy, qualification_sha256=qualification.policy_hash)
    if reason == "no_key":
        monkeypatch.delenv("OPENDART_API_KEY")
    if reason == "passages_off":
        policy = replace(policy, article_passages=False)
    if reason == "deadline":
        kwargs["deadline"] = 0.0

    def forbidden(request):
        pytest.fail("zero HTTP path opened transport")

    result = await run_case(
        forbidden,
        items=(original,),
        outcomes=outcomes,
        policy=policy,
        qualification=qualification,
        matrix=matrix,
        **kwargs,
    )
    assert result.request_count == 0 and result.items[0].event_input_blocked


@pytest.mark.parametrize("cap", [1, 100, 500])
async def test_complete_projection_cannot_violate_excerpt_cap(monkeypatch, cap):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = permissions(max_excerpt_chars=cap)
    seen = []
    result = await run_case(
        positive_handler(seen), policy=policy, qualification=qualification, matrix=matrix
    )
    assert result.request_count == 2 and result.outcomes[0].reason == "evidence_invalid"
    assert result.items[0].event_input_blocked


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "blocked"),
        ("slot_qualification_sha256", "0" * 64),
        ("fixture_sha256", "0" * 64),
        ("source_code_sha", "0" * 40),
        ("parser_version", "unapproved"),
        ("rights_scope", "unapproved raw redistribution"),
    ],
)
async def test_stale_or_unapproved_transport_never_opens_http(monkeypatch, field, value):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = permissions()
    qualification = qualification.model_copy(
        update={"dart": qualification.dart.model_copy(update={field: value})}
    )
    policy = replace(policy, qualification_sha256=qualification.policy_hash)

    def forbidden(request):
        pytest.fail("unbound permission opened HTTP")

    result = await run_case(forbidden, policy=policy, qualification=qualification, matrix=matrix)
    assert result.request_count == 0 and result.outcomes[0].reason == "unqualified"
    assert result.items[0].event_input_blocked


def test_optional_permission_and_block_flag_preserve_legacy_bytes():
    legacy = EnrichmentQualification()
    assert legacy.model_dump_json() == '{"schema_version":1,"sources":[]}'
    assert legacy.policy_hash == hashlib.sha256(b'{"schema_version":1,"sources":[]}').hexdigest()
    item = item_case()
    assert '"event_input_blocked"' not in item.model_dump_json()
    assert (
        '"event_input_blocked"'
        not in item.model_copy(update={"event_input_blocked": False}).model_dump_json()
    )
    for value in ("true", 1, None):
        with pytest.raises(ValidationError):
            type(item).model_validate({**item.model_dump(), "event_input_blocked": value})


async def test_second_request_needs_a_shared_permit_and_013_shapes_are_distinct(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    seen = []
    result = await run_case(positive_handler(seen), policy=permissions(max_requests=1)[0])
    assert len(seen) == result.request_count == 1
    assert result.outcomes[0].reason == "budget_exhausted" and result.items[0].event_input_blocked
    for payload, status in [
        ({"status": "013"}, "missing"),
        ({"status": "013", "list": [{}], "total_count": 1}, "unknown"),
    ]:
        result = await run_case(lambda req, payload=payload: httpx.Response(200, json=payload))
        assert (
            result.outcomes[0].dart.latest_status == status and result.items[0].event_input_blocked
        )


async def test_cancellation_drains_http_and_leaves_logger_levels_unchanged(monkeypatch, caplog):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    caplog.set_level(logging.DEBUG)
    entered = asyncio.Event()
    cancelled = []
    levels = {name: logging.getLogger(name).level for name in ("httpx", "httpcore.connection")}

    async def respond(request):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    task = asyncio.create_task(run_case(respond))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled == [True]
    assert levels == {name: logging.getLogger(name).level for name in levels}
    logging.getLogger("httpx").warning("unsafe transport %s", SECRET)
    assert SECRET not in caplog.text


async def test_five_sources_ten_candidates_share_six_requests_and_two_connections(monkeypatch):
    from investo.models.enrichment import SourceQualification
    from investo.models.items import NormalizedItem
    from tests.unit.models.test_enrichment import qualification_record
    from tests.unit.sources.test_event_evidence import body, source_item

    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = permissions()
    sources = ("fomc-rss", "fed-speech-rss", "cftc-policy-rss", "sec-newsroom-rss")
    records = [qualification_record(name) for name in sources[:3]]
    sec = SourceQualification.model_validate(
        {
            **records[0].model_dump(),
            "source_name": "sec-newsroom-rss",
            "official_discovery_url": "https://www.sec.gov/about/rss-feeds",
            "allowed_host": "www.sec.gov",
        }
    )
    records.append(sec)
    qualification = qualification.model_copy(update={"sources": tuple(records)})
    policy = replace(
        policy,
        preview_sources=(*sources, "dart-disclosure"),
        qualification_sha256=qualification.policy_hash,
    )
    items = [source_item(name, number) for name in sources[:3] for number in (1, 2)]
    items.extend(
        NormalizedItem(
            source_name="sec-newsroom-rss",
            category="news",
            title=f"SEC synthetic {number}",
            url=f"https://www.sec.gov{sec.allowed_path}release-{number}.htm",
            published_at=NOW,
        )
        for number in (1, 2)
    )
    darts = (item_case(), item_case(rcept_no="20260902000002"))
    items.extend(darts)
    active = peak = calls = 0

    async def respond(request):
        nonlocal active, peak, calls
        active += 1
        peak = max(peak, active)
        calls += 1
        try:
            await asyncio.sleep(0.002)
            if request.url.path == "/api/list.json":
                payload = listing_case()
                payload["list"] = [listing_case(item)["list"][0] for item in darts]
                payload["total_count"] = 2
                return httpx.Response(200, json=payload)
            if request.url.path == "/api/document.xml":
                return httpx.Response(
                    200, content=archive_case(name=request.url.params["rcept_no"] + ".xml")
                )
            return httpx.Response(
                200,
                text=body("cftc-policy-rss" if "cftc" in request.url.host else "fomc-rss"),
                headers={"content-type": "text/html"},
            )
        finally:
            active -= 1

    result = await run_case(
        respond, items=tuple(items), policy=policy, qualification=qualification, matrix=matrix
    )
    assert calls == result.request_count == 6 and peak <= 2 and active == 0
    assert len(result.outcomes) == 10
    for item in result.items:
        if item.source_name == "dart-disclosure" and item.event_evidence is None:
            assert item.event_input_blocked


async def test_superseded_item_reaches_native_source_limited_without_model_calls(monkeypatch):
    from investo.briefing.generation_contract import GenerationInput
    from investo.briefing.watchlist import WatchlistConfig
    from investo.models.event_config import EventGenerationPolicy
    from investo.orchestrator.event_preview import preview_event_briefing

    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    result = await run_case(lambda req: httpx.Response(200, json=listing_case(rm="정")))

    def forbidden(*args, **kwargs):
        pytest.fail("blocked DART reached a language model")

    preview = await preview_event_briefing(
        GenerationInput(
            target_date=date(2026, 9, 2),
            segment="domestic-equity",
            items=result.items,
            watchlist_config=WatchlistConfig(),
            runner=forbidden,
            event_observed_at=NOW,
            event_generation_policy=EventGenerationPolicy(
                mode="preview", document_schema=3, profile="article_v2"
            ),
        )
    )
    assert preview.generation.document.availability.status == "source_limited"
    assert (
        preview.finalized.documents[0].edition_view.edition.availability.status == "source_limited"
    )
