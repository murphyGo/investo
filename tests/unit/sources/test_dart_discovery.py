from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, timedelta

import httpx
import pytest

from investo.sources import aggregator
from investo.sources._dart_discovery import DartDiscoveryAdapter
from investo.sources._dart_document import MAX_BYTES
from investo.sources._dart_evidence import DART_PARSER_VERSIONS
from investo.sources._window import FetchWindow
from investo.sources.dart_disclosure import DartDisclosureAdapter
from investo.sources.protocol import SourceFetchError

TRUST = "dart-trust-termination-6.2-v1"
TRUST_REPORT = "주요사항보고서(자기주식취득신탁계약해지결정)"
CB_REPORT = "[기재정정]주요사항보고서(전환사채권발행결정)"
WINDOW = FetchWindow.from_kst_date(date(2026, 11, 26))


def entry(number, report=TRUST_REPORT):
    return {
        "corp_code": "01234567",
        "corp_name": "테스트기업",
        "corp_cls": "K",
        "rcept_no": f"20261126{number:06d}",
        "rcept_dt": "20261126",
        "report_nm": report,
        "rm": "코",
    }


def page(rows, total=None, number=1):
    count = len(rows) if total is None else total
    return {
        "status": "000",
        "page_no": number,
        "page_count": 100,
        "total_count": count,
        "total_page": (count + 99) // 100,
        "list": rows,
    }


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", "DISCOVERY_TEST_TOKEN")


async def fetch(responses, parser=TRUST):
    requests = []

    def handle(request):
        requests.append(request)
        response = responses[len(requests) - 1]
        if isinstance(response, Exception):
            raise response
        return (
            response if isinstance(response, httpx.Response) else httpx.Response(200, json=response)
        )

    adapter = DartDiscoveryAdapter(parser, transport=httpx.MockTransport(handle))
    async with httpx.AsyncClient() as unused:
        result = await adapter.fetch_with_coverage(unused, WINDOW)
    return result, requests


async def test_support_beyond_general_first_hundred_and_thirty_item_cap():
    result, requests = await fetch(
        [
            page([entry(i, "주요사항보고서(유상증자결정)") for i in range(200, 300)], total=101),
            page([entry(1)], total=101, number=2),
        ]
    )
    assert [i.raw_metadata["rcept_no"] for i in result.items] == ["20261126000001"]
    assert result.window_coverage.completeness == "full"
    assert result.window_coverage.pages == 2
    for i, request in enumerate(requests, 1):
        assert str(request.url.copy_with(query=None)) == DartDisclosureAdapter._ENDPOINT
        assert request.url.params == httpx.QueryParams(
            {
                "crtfc_key": "DISCOVERY_TEST_TOKEN",
                "bgn_de": "20261126",
                "end_de": "20261126",
                "pblntf_detail_ty": "B001",
                "last_reprt_at": "N",
                "sort": "date",
                "sort_mth": "desc",
                "page_no": str(i),
                "page_count": "100",
            }
        )
        assert request.headers["accept-encoding"] == "identity"
    item = result.items[0]
    assert item.raw_metadata["published_at_precision"] == "date"
    assert item.published_at == WINDOW.start_utc


@pytest.mark.parametrize("parser", sorted(DART_PARSER_VERSIONS))
async def test_selected_profile_eligibility_precedes_cap(parser):
    selected = TRUST_REPORT if parser == TRUST else CB_REPORT
    other = CB_REPORT if parser == TRUST else TRUST_REPORT
    result, _ = await fetch(
        [
            page(
                [
                    *[entry(i, other) for i in range(1, 40)],
                    entry(40, "[첨부추가]" + TRUST_REPORT),
                    entry(41, selected),
                ]
            )
        ],
        parser,
    )
    assert [i.raw_metadata["rcept_no"] for i in result.items] == ["20261126000041"]


async def test_supported_output_cap_is_bounded_and_sorted():
    result, requests = await fetch([page([entry(i) for i in range(31)])])
    assert len(result.items) == 30 and len(requests) == 1
    assert result.items[0].raw_metadata["rcept_no"] == "20261126000030"
    assert result.items[-1].raw_metadata["rcept_no"] == "20261126000001"
    assert result.window_coverage.cap_reached
    assert result.window_coverage.completeness == "partial"


async def test_three_page_cap_without_supported_form():
    result, requests = await fetch(
        [
            page([entry(i, "분기보고서") for i in range(p * 100, (p + 1) * 100)], 400, p + 1)
            for p in range(3)
        ]
    )
    assert not result.items and len(requests) == 3
    assert result.window_coverage.cap_reached
    assert result.window_coverage.completeness == "partial"


@pytest.mark.parametrize(
    "payload",
    [{"status": "013"}, {"status": "013", "list": [], "total_count": 0, "total_page": "0"}],
)
async def test_empty_filtered_query_is_not_failure(payload):
    result, requests = await fetch([payload])
    assert not result.items and len(requests) == 1
    assert result.window_coverage.completeness == "full"


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"status": []},
        {"status": "010", "message": "DISCOVERY_TEST_TOKEN"},
        {"status": "013", "list": [entry(1)]},
        {"status": "013", "total_count": True},
        {**page([entry(1)]), "total_count": "9" * 5000},
        {**page([entry(1)]), "page_count": 99},
        {**page([entry(1)]), "total_page": 2},
        {**page([entry(1)]), "page_no": 2},
        {**page([entry(1)]), "total_count": 2},
        page([entry(1), entry(1)]),
        page([{**entry(1), "rcept_dt": "20261125"}]),
        page([{**entry(1), "corp_code": "invalid"}]),
        page([{**entry(1), "corp_cls": "Z"}]),
        page([None]),
    ],
)
async def test_invalid_first_page_fails_closed_without_echo(payload):
    with pytest.raises(SourceFetchError) as caught:
        await fetch([payload])
    assert "DISCOVERY_TEST_TOKEN" not in str(caught.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "https://evil.invalid"}),
        httpx.Response(503),
        httpx.Response(200, text="not json"),
        httpx.Response(200, content=b'{"status":"013","status":"000"}'),
        httpx.Response(200, content=b'{"status":"013","message":"DISCOVERY_TEST_\\u0054OKEN"}'),
        httpx.Response(200, content=b"x" * (MAX_BYTES + 1)),
        httpx.ReadError("DISCOVERY_TEST_TOKEN"),
    ],
)
async def test_response_boundaries_and_transport_errors_are_sanitized(response):
    with pytest.raises(SourceFetchError) as caught:
        await fetch([response])
    assert "DISCOVERY_TEST_TOKEN" not in str(caught.value)


@pytest.mark.parametrize(
    "next_page",
    [
        page([entry(101)], 102, 2),
        page([entry(1)], 101, 2),
        {"status": "013"},
        httpx.ReadTimeout("private"),
    ],
)
async def test_bad_later_page_keeps_only_prior_valid_page(next_page):
    rows = [entry(1)] + [entry(i, "분기보고서") for i in range(2, 101)]
    result, requests = await fetch([page(rows, 101), next_page])
    assert len(requests) == 2
    assert [i.raw_metadata["rcept_no"] for i in result.items] == ["20261126000001"]
    assert result.window_coverage.completeness == "partial"
    assert result.window_coverage.parse_failures == 1


@pytest.mark.parametrize("budget", ["_WINDOW_BUDGET_S", "_REQUEST_TIMEOUT_S"])
async def test_timeouts_bound_slow_response(monkeypatch, budget):
    monkeypatch.setattr(DartDiscoveryAdapter, budget, 0.01)
    requests = []

    async def handle(request):
        requests.append(request)
        await asyncio.sleep(1)
        return httpx.Response(200, json=page([entry(1)]))

    adapter = DartDiscoveryAdapter(TRUST, transport=httpx.MockTransport(handle))
    async with httpx.AsyncClient() as unused:
        with pytest.raises(SourceFetchError):
            await asyncio.wait_for(adapter.fetch_with_coverage(unused, WINDOW), 0.5)
    assert len(requests) == 1


async def test_missing_key_and_bad_window_do_not_request(monkeypatch):
    def forbidden(request):
        pytest.fail("invalid configuration reached transport")

    adapter = DartDiscoveryAdapter(TRUST, transport=httpx.MockTransport(forbidden))
    async with httpx.AsyncClient() as client:
        for window in (
            replace(WINDOW, news_observation=True),
            replace(WINDOW, end_utc=WINDOW.end_utc + timedelta(days=1)),
        ):
            with pytest.raises(SourceFetchError):
                await adapter.fetch_with_coverage(client, window)
        monkeypatch.delenv("OPENDART_API_KEY")
        with pytest.raises(SourceFetchError):
            await adapter.fetch_with_coverage(client, WINDOW)
    with pytest.raises(ValueError):
        DartDiscoveryAdapter("unknown")


async def test_collection_replacement_does_not_mutate_registry_and_preserves_skip(monkeypatch):
    original = DartDisclosureAdapter()
    monkeypatch.setattr(aggregator, "list_sources", lambda: [original])
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=page([entry(1)]))

    discovery = DartDiscoveryAdapter(TRUST, transport=httpx.MockTransport(handle))
    report = await aggregator.collect_sources(WINDOW.target_date, dart_discovery=discovery)
    assert report.outcomes[0].status == "ok" and report.outcomes[0].item_count == 1
    assert report.window_coverages[0].completeness == "full"
    assert type(aggregator.list_sources()[0]) is DartDisclosureAdapter
    monkeypatch.setenv("INVESTO_SOURCE_DISABLE", "dart-disclosure")
    skipped = await aggregator.collect_sources(WINDOW.target_date, dart_discovery=discovery)
    assert skipped.outcomes[0].status == "skipped" and not skipped.items
    assert not skipped.window_coverages and len(requests) == 1


@pytest.mark.parametrize(
    "kwargs", [{"news_windows": {}}, {"held_news_sources": frozenset({"dart-disclosure"})}]
)
async def test_preview_discovery_cannot_change_cursor_window_contract(kwargs):
    with pytest.raises(ValueError):
        await aggregator.collect_sources(
            WINDOW.target_date, dart_discovery=DartDiscoveryAdapter(TRUST), **kwargs
        )


async def test_collector_failed_discovery_has_failed_outcome_not_zero(monkeypatch):
    monkeypatch.setattr(aggregator, "list_sources", lambda: [DartDisclosureAdapter()])
    discovery = DartDiscoveryAdapter(
        TRUST, transport=httpx.MockTransport(lambda r: httpx.Response(503))
    )
    report = await aggregator.collect_sources(WINDOW.target_date, dart_discovery=discovery)
    assert not report.items and report.outcomes[0].status == "failed"
    assert report.window_coverages[0].completeness == "unknown"


async def test_unrelated_carry_over_receipt_does_not_discard_supported_form():
    # A receipt identifier is not the provider's rcept_dt publication field.
    # Real B001 responses can include prior-day identifiers on today's date.
    rows = [
        entry(1),
        {**entry(2, "[기재정정]주요사항보고서(영업양도결정)"), "rcept_no": "20261125000002"},
    ]
    result, requests = await fetch([page(rows)])
    assert len(requests) == 1 and len(result.items) == 1
    assert result.items[0].raw_metadata["rcept_no"] == "20261126000001"
    assert result.window_coverage.completeness == "full"


async def test_selected_form_still_requires_existing_parser_identity_contract():
    result, requests = await fetch([page([{**entry(1), "rcept_no": "20261125000001"}])])
    assert len(requests) == 1 and result.items == ()
    assert result.window_coverage.completeness == "full"
