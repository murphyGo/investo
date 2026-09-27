"""Feed evidence and bounded qualified official-body HTTP."""

from __future__ import annotations

import asyncio
import gzip
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from investo.briefing.event_evidence import prepare_evidence_documents, resolve_evidence_ref
from investo.models.enrichment import EnrichmentPolicy, EnrichmentQualification
from investo.models.event_evidence import make_evidence_document
from investo.models.events import EvidenceRef
from investo.models.items import NormalizedItem
from investo.sources.event_evidence import (
    attach_feed_evidence,
    enrich_event_evidence,
    load_enrichment_qualification,
)
from tests.unit.models.test_enrichment import qualification_record

NOW = datetime(2026, 9, 27, tzinfo=UTC)
POLICY = EnrichmentPolicy("active")


def source_item(source: str = "cftc-policy-rss", number: int = 1) -> NormalizedItem:
    record = qualification_record(source)
    return NormalizedItem(
        source_name=source,
        category="calendar" if source == "fomc-rss" else "news",
        title=f"Official announcement {number}",
        summary="Original feed summary.",
        url=f"https://{record.allowed_host}{record.allowed_path}release-{number}.htm",
        published_at=NOW - timedelta(hours=number),
        raw_metadata={"official_source": "true"},
    )


def body(source: str = "cftc-policy-rss", text: str = "The agency announced a new policy.") -> str:
    if source == "cftc-policy-rss":
        return f'<article><div class="field--name-body"><p>{text}</p></div></article>'
    return '<div id="article"><div class="heading">Unrelated heading</div>' + (
        f'<div class="col-xs-12 col-sm-8 col-md-8"><p>{text}</p></div></div>'
    )


def qualified(*sources: str) -> EnrichmentQualification:
    return EnrichmentQualification(
        sources=tuple(qualification_record(source) for source in sources)
    )


@pytest.fixture
def active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("investo.models.enrichment.EVENT_ENRICHMENT_ACTIVE_READY", True)


def test_feed_off_identity_and_active_281_to_1200_fact_without_summary_change() -> None:
    original = source_item()
    detail = "배경 " * 100 + "공식 발표 수치는 7.5입니다." + " 추가 설명" * 300
    unchanged = attach_feed_evidence(original, detail_excerpt=detail, received_at=None)
    assert unchanged is original and unchanged.model_dump_json() == original.model_dump_json()
    attached = attach_feed_evidence(original, detail_excerpt=detail, received_at=NOW)
    assert attached.summary == original.summary and attached.raw_metadata == original.raw_metadata
    assert attached.source_name == original.source_name and attached.category == original.category
    assert (
        attached.event_evidence is not None and len(attached.event_evidence.detail_excerpt) == 1200
    )
    (evidence,) = prepare_evidence_documents((attached,), received_at=NOW)
    start = evidence.detail_excerpt.index("7.5")
    assert start > 280
    ref = EvidenceRef(
        document_id=evidence.document_id,
        revision_id=evidence.revision_id,
        field="detail_excerpt",
        start=start,
        end=start + 3,
    )
    assert resolve_evidence_ref(ref, (evidence,)) == "7.5"
    assert evidence.event_time is None and evidence.event_time_basis == "unknown"


def test_factory_reexport_and_feed_nfkc_revision_are_compatible() -> None:
    from investo.briefing.event_evidence import make_evidence_document as original_factory

    assert make_evidence_document is original_factory
    item = source_item("fomc-rss").model_copy(update={"raw_metadata": {}})
    first = attach_feed_evidence(
        item, detail_excerpt="\uff21\r\n새 발표", received_at=NOW, source_tier="official"
    )
    later = attach_feed_evidence(
        item, detail_excerpt="A\n새 발표", received_at=NOW, source_tier="official"
    )
    assert first.event_evidence == later.event_evidence
    assert first.event_evidence is not None and first.event_evidence.source_tier == "official"
    assert first.raw_metadata == {}


def test_qualification_loader_reads_closed_bounded_manifest(tmp_path: Path) -> None:
    path = tmp_path / "qualification.json"
    path.write_text(qualified("cftc-policy-rss").model_dump_json())
    assert len(load_enrichment_qualification(path).sources) == 1
    path.write_bytes(b" " * (64 * 1024 + 1))
    with pytest.raises(ValueError, match="qualification unavailable"):
        load_enrichment_qualification(path)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["off", "shadow"])
async def test_off_shadow_no_http_and_exact_original_item(mode: str) -> None:
    item = source_item()

    def forbidden(request: httpx.Request) -> httpx.Response:
        pytest.fail("off/shadow must make zero body requests")

    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        result = await enrich_event_evidence(
            (item,),
            client=client,
            policy=replace(POLICY, mode=mode),
            qualification=qualified("cftc-policy-rss"),
            received_at=NOW,
        )
    assert result.items[0] is item and result.outcomes == () and result.request_count == 0


@pytest.mark.asyncio
async def test_qualified_zero_never_requests_and_preserves_feed(active: None) -> None:
    item = source_item()

    def forbidden(request: httpx.Request) -> httpx.Response:
        pytest.fail("unqualified source must make zero body requests")

    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        result = await enrich_event_evidence(
            (item,),
            client=client,
            policy=POLICY,
            qualification=EnrichmentQualification(),
            received_at=NOW,
        )
    assert result.items[0] is item and result.request_count == 0
    assert result.outcomes[0].reason == "unqualified"


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["fomc-rss", "fed-speech-rss", "cftc-policy-rss"])
async def test_scoped_body_preserves_source_identity(source: str, active: None) -> None:
    item = attach_feed_evidence(source_item(source), detail_excerpt="Feed detail.", received_at=NOW)
    html = "<nav>Unrelated market forecast</nav>" + body(source, "A confirmed decision.")
    html = html.replace(
        "A confirmed decision.", "A confirmed decision.<script>fake actual 999</script>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html; charset=utf-8"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            (item,), client=client, policy=POLICY, qualification=qualified(source), received_at=NOW
        )
    updated = result.items[0]
    assert updated.event_evidence is not None and item.event_evidence is not None
    assert updated.event_evidence.document_id == item.event_evidence.document_id
    assert updated.event_evidence.revision_id != item.event_evidence.revision_id
    assert updated.event_evidence.detail_excerpt == "A confirmed decision."
    assert updated.summary == item.summary and updated.raw_metadata == item.raw_metadata
    assert updated.category == item.category and updated.event_evidence.event_time is None
    assert result.outcomes[0].status == "enriched" and result.request_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://www.cftc.gov/PressRoom/PressReleases/a",
        "https://127.0.0.1/PressRoom/PressReleases/a",
        "https://localhost/PressRoom/PressReleases/a",
        "https://user:password@www.cftc.gov/PressRoom/PressReleases/a",
        "https://www.cftc.gov.evil.invalid/PressRoom/PressReleases/a",
        "https://www.cftc.gov/PressRoom/PressReleases/a?target=private",
        "https://www.cftc.gov/unqualified/a",
        "https://www.cftc.gov/PressRoom/PressReleases/%252e%252e/private",
        "https://www.cftc.gov/PressRoom/PressReleases/a#section",
        "https://www.cftc.gov:8443/PressRoom/PressReleases/a",
    ],
)
async def test_ssrf_and_unqualified_locators_never_request(url: str, active: None) -> None:
    item = source_item().model_copy(update={"url": url})

    def forbidden(request: httpx.Request) -> httpx.Response:
        pytest.fail("rejected locator must make zero requests")

    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        result = await enrich_event_evidence(
            (item,),
            client=client,
            policy=POLICY,
            qualification=qualified("cftc-policy-rss"),
            received_at=NOW,
        )
    assert result.items[0] is item and result.request_count == 0
    assert result.outcomes[0].reason == "url_rejected"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,mime,html,reason",
    [
        (403, "text/html", "restricted", "request_failed"),
        (404, "text/html", "missing", "request_failed"),
        (200, "application/pdf", "not HTML", "content_type"),
        (200, "text/html", "<main>Selector changed</main>", "selector_unavailable"),
        (200, "text/html", body() + body(), "selector_unavailable"),
        (200, "text/html", body(text=""), "empty_excerpt"),
    ],
)
async def test_failures_preserve_feed_and_closed_outcome_without_retry(
    status: int,
    mime: str,
    html: str,
    reason: str,
    active: None,
) -> None:
    item = source_item()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text=html, headers={"content-type": mime})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            (item,),
            client=client,
            policy=POLICY,
            qualification=qualified("cftc-policy-rss"),
            received_at=NOW,
        )
    assert result.items[0] is item and calls == result.request_count == 1
    assert result.outcomes[0].reason == reason
    assert html not in result.outcomes[0].model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "redirect", ["/PressRoom/PressReleases/final", "https://127.0.0.1/private"]
)
async def test_one_redirect_stays_in_same_allowlist_and_counts_budget(
    redirect: str, active: None
) -> None:
    calls: list[str] = []
    item = source_item()

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(302, headers={"location": redirect})
        return httpx.Response(200, text=body(), headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            (item,),
            client=client,
            policy=POLICY,
            qualification=qualified("cftc-policy-rss"),
            received_at=NOW,
        )
    assert result.request_count == len(calls) == (2 if redirect.startswith("/") else 1)
    assert result.outcomes[0].reason == (None if len(calls) == 2 else "redirect_rejected")


@pytest.mark.asyncio
async def test_bundle_six_requests_concurrent_two_latest_two_per_source(active: None) -> None:
    sources = ("fomc-rss", "fed-speech-rss", "cftc-policy-rss")
    items = tuple(source_item(source, number) for source in sources for number in (3, 2, 1))
    calls: list[str] = []
    inflight = peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal inflight, peak
        calls.append(str(request.url))
        inflight += 1
        peak = max(peak, inflight)
        await asyncio.sleep(0.01)
        inflight -= 1
        source = "cftc-policy-rss" if request.url.host == "www.cftc.gov" else "fomc-rss"
        return httpx.Response(
            200, text=body(source, "내용 " * 1000), headers={"content-type": "text/html"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            items, client=client, policy=POLICY, qualification=qualified(*sources), received_at=NOW
        )
    assert len(calls) == result.request_count == 6 and peak == 2
    assert all("release-3" not in url for url in calls)
    assert len(result.outcomes) == 6
    assert all(
        len(item.event_evidence.detail_excerpt) == 1200
        for item in result.items
        if item.event_evidence
    )


@pytest.mark.asyncio
async def test_redirects_share_six_request_budget(active: None) -> None:
    sources = ("fomc-rss", "fed-speech-rss", "cftc-policy-rss")
    items = tuple(source_item(source, number) for source in sources for number in (1, 2))
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": str(request.url) + "-again"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            items, client=client, policy=POLICY, qualification=qualified(*sources), received_at=NOW
        )
    assert calls == result.request_count == 6 and result.items == items
    assert all(row.reason in {"redirect_rejected", "budget_exhausted"} for row in result.outcomes)


@pytest.mark.asyncio
async def test_decoded_500kib_cap_rejects_compressed_body(active: None) -> None:
    item = source_item()
    compressed = gzip.compress(body(text="x" * (500 * 1024 + 1)).encode())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=compressed,
            headers={"content-type": "text/html", "content-encoding": "gzip"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            (item,),
            client=client,
            policy=POLICY,
            qualification=qualified("cftc-policy-rss"),
            received_at=NOW,
        )
    assert result.items[0] is item and result.outcomes[0].reason == "request_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("outer_deadline", [False, True])
async def test_request_and_existing_deadline_cancel_bounded_work(
    outer_deadline: bool, active: None
) -> None:
    item = source_item()
    cancelled = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal cancelled
        try:
            await asyncio.sleep(1)
        finally:
            cancelled = True
        return httpx.Response(200, text=body(), headers={"content-type": "text/html"})

    started = time.monotonic()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            (item,),
            client=client,
            policy=replace(POLICY, request_timeout_s=0.03 if not outer_deadline else 8),
            qualification=qualified("cftc-policy-rss"),
            received_at=NOW,
            deadline=started + 0.03 if outer_deadline else None,
        )
    assert time.monotonic() - started < 0.4 and cancelled
    assert result.items[0] is item and result.outcomes[0].reason == "timed_out"


@pytest.mark.asyncio
async def test_automatic_redirect_client_is_rejected_before_request(active: None) -> None:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        with pytest.raises(ValueError, match="redirects disabled"):
            await enrich_event_evidence(
                (source_item(),),
                client=client,
                policy=POLICY,
                qualification=qualified("cftc-policy-rss"),
                received_at=NOW,
            )


@pytest.mark.asyncio
async def test_malformed_html_preserves_original_and_successful_sibling(active: None) -> None:
    malformed = source_item(number=1)
    sibling = source_item(number=2)

    def handler(request: httpx.Request) -> httpx.Response:
        prefix = "<![unexpected]>" if request.url.path.endswith("release-1.htm") else ""
        return httpx.Response(200, text=prefix + body(), headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            (malformed, sibling),
            client=client,
            policy=POLICY,
            qualification=qualified("cftc-policy-rss"),
            received_at=NOW,
        )
    assert result.items[0] is malformed
    assert result.items[1].event_evidence is not None
    assert result.outcomes[0].reason == "selector_unavailable"
    assert result.outcomes[1].status == "enriched"
    assert result.request_count == 2


@pytest.mark.asyncio
async def test_individual_absolute_deadline_closes_continuous_slow_stream(active: None) -> None:
    class SlowStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            for _ in range(30):
                await asyncio.sleep(0.01)
                yield b"small chunk"

        async def aclose(self) -> None:
            self.closed = True

    stream = SlowStream()
    item = source_item()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream, headers={"content-type": "text/html"})

    started = time.monotonic()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            (item,),
            client=client,
            policy=replace(POLICY, request_timeout_s=0.04, total_budget_s=0.2),
            qualification=qualified("cftc-policy-rss"),
            received_at=NOW,
        )
    assert time.monotonic() - started < 0.18
    assert stream.closed and result.items[0] is item
    assert result.outcomes[0].reason == "timed_out"


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["cftc-policy-rss", "fed-speech-rss"])
async def test_newer_unqualified_paths_do_not_starve_older_qualified_release(
    source: str,
    active: None,
) -> None:
    newer = tuple(
        source_item(source, number).model_copy(
            update={
                "url": f"https://{qualification_record(source).allowed_host}/unqualified/speech-{number}"
            }
        )
        for number in (1, 2)
    )
    older = source_item(source, 3)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=body(source), headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await enrich_event_evidence(
            (*newer, older),
            client=client,
            policy=POLICY,
            qualification=qualified(source),
            received_at=NOW,
        )
    assert calls == [str(older.url)] and result.request_count == 1
    assert result.items[0] is newer[0] and result.items[1] is newer[1]
    assert result.items[2].event_evidence is not None
    assert result.outcomes[0].status == "enriched"
