"""The existing RSS response carries bounded evidence without a second request."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import httpx
import pytest

from investo.briefing.event_evidence import evidence_document_from_item
from investo.sources import aggregator
from investo.sources._window import FetchWindow
from investo.sources.cftc_policy_rss import CftcPolicyRssAdapter
from investo.sources.cnbc_top_news import CnbcTopNewsAdapter
from investo.sources.fed_speech_rss import FedSpeechRssAdapter
from investo.sources.fomc_rss import FomcRssAdapter
from investo.sources.korea_policy_rss import KoreaPolicyRssAdapter
from investo.sources.protocol import SourceAdapter
from investo.sources.sec_newsroom_rss import SecNewsroomRssAdapter

_ADAPTER_CASES = (
    FomcRssAdapter(),
    FedSpeechRssAdapter(),
    SecNewsroomRssAdapter(),
    CftcPolicyRssAdapter(),
    CnbcTopNewsAdapter(),
    KoreaPolicyRssAdapter(),
)


@pytest.mark.parametrize(
    "adapter",
    _ADAPTER_CASES,
    ids=lambda adapter: adapter.name,
)
async def test_opt_in_evidence_keeps_long_feed_detail_without_changing_legacy_item(
    adapter: SourceAdapter,
) -> None:
    detail = "배경 설명. " * 60 + "가상사는 서비스 가를 정식 출시했습니다." + " 추가 맥락." * 150
    xml = (
        '<rss version="2.0"><channel><item><title>가상사 서비스 소식</title>'
        "<link>https://example.invalid/official-item</link>"
        "<pubDate>Fri, 25 Sep 2026 10:00:00 GMT</pubDate>"
        f"<description><![CDATA[<p>{detail}</p>]]></description>"
        "</item></channel></rss>"
    )
    requests: list[str] = []

    def serve(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, text=xml, headers={"Content-Type": "application/rss+xml"})

    clock = datetime(2026, 9, 26, tzinfo=UTC)
    window = FetchWindow.from_kst_date(date(2026, 9, 25))
    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
        legacy = await adapter.fetch(client, window)
        off_request_count = len(requests)
        active = await adapter.fetch(client, replace(window, evidence_received_at=clock))
    assert len(requests) == 2 * off_request_count
    assert legacy and len(legacy) == len(active)
    for old, new in zip(legacy, active, strict=True):
        assert old.event_evidence is None
        assert "event_evidence" not in old.model_dump()
        assert new.summary == old.summary and len(new.summary or "") <= 280
        assert new.model_copy(update={"event_evidence": None}).model_dump() == old.model_dump()
        evidence = evidence_document_from_item(new, received_at=clock)
        assert evidence.received_at == clock
        assert len(evidence.detail_excerpt) == 1200
        assert "서비스 가를 정식 출시" in evidence.detail_excerpt
        assert "서비스 가를 정식 출시" not in (old.summary or "")
        assert evidence.event_time is None and evidence.event_time_basis == "unknown"


def _mixed_evidence_xml() -> str:
    rows = "".join(
        f"<item><title>Digital asset synthetic {label} announcement</title>"
        f"<link>{url}</link><pubDate>Fri, 25 Sep 2026 10:00:00 GMT</pubDate>"
        "<description>Synthetic feed detail.</description></item>"
        for label, url in (
            ("bad", "https://u:p@example.invalid/bad"),
            ("good", "https://example.invalid/good"),
        )
    )
    return f"<rss><channel>{rows}</channel></rss>"


@pytest.mark.parametrize("adapter", _ADAPTER_CASES, ids=lambda adapter: adapter.name)
async def test_invalid_evidence_entry_preserves_valid_siblings_and_legacy_bytes(
    adapter: SourceAdapter,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A URL accepted by legacy HttpUrl cannot abort the opted-in source."""
    clock = datetime(2026, 9, 26, tzinfo=UTC)
    window = FetchWindow.from_kst_date(date(2026, 9, 25))
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text=_mixed_evidence_xml()))
    original_client = httpx.AsyncClient
    async with original_client(transport=transport) as client:
        legacy = await adapter.fetch(client, window)
    assert {str(item.url) for item in legacy} == {
        "https://u:p@example.invalid/bad",
        "https://example.invalid/good",
    }
    legacy_bytes = [item.model_dump_json() for item in legacy]
    monkeypatch.setattr(aggregator, "list_sources", lambda: [adapter])
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: original_client(*a, transport=transport, **kw)
    )
    active = await aggregator.collect_sources(window.target_date, evidence_received_at=clock)
    assert active.items and {str(item.url) for item in active.items} == {
        "https://example.invalid/good"
    }
    assert [
        item.model_copy(update={"event_evidence": None}).model_dump_json() for item in active.items
    ] == [item.model_dump_json() for item in legacy if str(item.url).endswith("/good")]
    assert all(item.event_evidence is not None for item in active.items)
    assert len(active.outcomes) == 1
    assert active.outcomes[0].status == "ok"
    assert active.outcomes[0].item_count == len(active.items)
    assert "u:p" not in caplog.text
    # The opt-in run cannot mutate adapter state or the original legacy rows.
    async with original_client(transport=transport) as client:
        legacy_again = await adapter.fetch(client, window)
    assert [item.model_dump_json() for item in legacy_again] == legacy_bytes
    assert all(item.event_evidence is None for item in legacy_again)


async def test_fomc_evidence_rejection_is_one_partial_parse_loss() -> None:
    window = replace(
        FetchWindow.from_kst_date(date(2026, 9, 25)),
        evidence_received_at=datetime(2026, 9, 26, tzinfo=UTC),
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=_mixed_evidence_xml()))
    ) as client:
        result = await FomcRssAdapter().fetch_with_coverage(client, window)
    assert len(result.items) == 1
    assert str(result.items[0].url) == "https://example.invalid/good"
    assert result.window_coverage.parse_failures == 1
    assert result.window_coverage.completeness == "partial"
