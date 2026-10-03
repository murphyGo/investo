"""Provider coverage witnesses use actual bounded fetches, never RSS inference."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from investo._internal.source_specs import news_window_source_recipients
from investo.models import NormalizedItem
from investo.models.coverage import SourceFetchResult, SourceWindowCoverage
from investo.models.news_window import NewsObservationWindow, news_item_in_window
from investo.sources import dart_disclosure
from investo.sources._registry import register
from investo.sources._window import FetchWindow
from investo.sources.aggregator import collect_sources
from investo.sources.dart_disclosure import DartDisclosureAdapter
from investo.sources.fomc_rss import FomcRssAdapter
from investo.sources.official_policy import (
    CongressGovBillActionsAdapter,
    HouseFinancialServicesPolicyAdapter,
    SenateBankingPolicyAdapter,
)
from investo.sources.protocol import SourceFetchError

_START = datetime(2026, 9, 25, 15, tzinfo=UTC)
_END = datetime(2026, 9, 26, 15, tzinfo=UTC)
_TARGET = date(2026, 9, 24)  # Deliberately different from the observation date.
_WINDOW = FetchWindow(_START, _END, _TARGET, news_observation=True)
_NEWS = NewsObservationWindow(_START, _START, _END, "replay", "source-test")
_POLICY_FIXTURES = Path(__file__).parent / "fixtures" / "api" / "official-policy"


def _item(source: str = "cnbc-top-news") -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category="news",
        title="Recorded synthetic official announcement",
        url="https://example.test/announcement",
        published_at=_START + timedelta(hours=1),
    )


def _entry(index: int, *, relevant: bool = True) -> dict[str, str]:
    return {
        "report_nm": "자기주식취득결정" if relevant else "분기보고서",
        "rcept_no": f"20260926{index:06d}",
        "rcept_dt": "20260926",
        "corp_name": "가상기업",
        "corp_code": "00000001",
        "corp_cls": "Y",
    }


def _page(entries: list[dict[str, str]], *, page: int = 1, total: int | None = None) -> dict:
    total = len(entries) if total is None else total
    return {
        "status": "000",
        "page_no": page,
        "page_count": 100,
        "total_count": total,
        "total_page": (total + 99) // 100,
        "list": entries,
    }


def _rss_item(when: str, *, link: str = "https://example.test/release") -> str:
    return (
        "<item><title>Digital asset policy announcement</title>"
        f"<link>{link}</link><pubDate>{when}</pubDate>"
        "<description>Recorded synthetic news.</description></item>"
    )


def _xml_client(items: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, text=f"<rss><channel>{items}</channel></rss>")
        )
    )


async def test_opted_capability_is_called_once_and_off_keeps_legacy_fetch() -> None:
    calls: list[tuple[str, FetchWindow]] = []

    @register
    class Capability:
        name = "cnbc-top-news"
        category = "news"

        async def fetch(self, client, window):
            calls.append(("legacy", window))
            return [_item()]

        async def fetch_with_coverage(self, client, window):
            calls.append(("coverage", window))
            return SourceFetchResult(
                (_item(),), SourceWindowCoverage(self.name, window.start_utc, window.end_utc)
            )

    report = await collect_sources(_TARGET, news_windows={Capability.name: _NEWS})
    assert calls == [("coverage", _WINDOW)]
    assert report.items == (_item(),)
    assert report.window_coverages[0].completeness == "unknown"
    off = await collect_sources(_TARGET)
    assert [name for name, _ in calls] == ["coverage", "legacy"]
    assert not calls[-1][1].news_observation
    assert off.window_coverages == ()


@pytest.mark.parametrize("empty", [False, True])
async def test_legacy_capability_is_unknown_even_with_oldest_before_start(empty: bool) -> None:
    calls = 0

    @register
    class Legacy:
        name = "cnbc-top-news"
        category = "news"

        async def fetch(self, client, window):
            nonlocal calls
            calls += 1
            return (
                []
                if empty
                else [_item().model_copy(update={"published_at": _START - timedelta(days=9)})]
            )

    report = await collect_sources(_TARGET, news_windows={Legacy.name: _NEWS})
    assert calls == 1
    assert report.window_coverages[0].completeness == "unknown"
    assert report.window_coverages[0].pages == 0


@pytest.mark.parametrize("wrong_shape", [False, True])
async def test_capability_mismatch_cannot_produce_full_report(wrong_shape: bool) -> None:
    @register
    class Invalid:
        name = "cnbc-top-news"
        category = "news"

        async def fetch(self, client, window):
            raise AssertionError("must not retry using legacy fetch")

        async def fetch_with_coverage(self, client, window):
            if wrong_shape:
                return []
            return SourceFetchResult(
                (),
                SourceWindowCoverage(
                    self.name,
                    _START - timedelta(days=1),
                    _END,
                    pages=1,
                    completeness="full",
                    basis="provider_pagination",
                ),
            )

    report = await collect_sources(_TARGET, news_windows={Invalid.name: _NEWS})
    assert report.outcomes[0].status == "failed"
    assert report.window_coverages == (SourceWindowCoverage(Invalid.name, _START, _END),)


async def test_all_recipient_hold_makes_zero_calls_without_fake_zero_outcome() -> None:
    @register
    class Held:
        name = "fomc-rss"
        category = "calendar"

        async def fetch(self, client, window):
            raise AssertionError("held source must not be fetched")

    report = await collect_sources(_TARGET, held_news_sources=frozenset({Held.name}))
    assert report.items == report.outcomes == report.window_coverages == ()


async def test_price_cannot_opt_into_news_window_by_accident() -> None:
    with pytest.raises(ValueError, match="explicit source opt-in"):
        await collect_sources(_TARGET, news_windows={"yfinance-price": _NEWS})


def test_descriptor_recipients_keep_fed_event_sharing_and_exclude_snapshots() -> None:
    recipients = news_window_source_recipients()
    assert (
        recipients["fomc-rss"]
        == recipients["fed-speech-rss"]
        == frozenset({"domestic-equity", "us-equity", "crypto"})
    )
    assert recipients["dart-disclosure"] == frozenset({"domestic-equity"})
    assert not {"yfinance-price", "fred", "economic-calendar", "treasury-yield"} & recipients.keys()
    with pytest.raises(TypeError):
        recipients["forged"] = frozenset()  # type: ignore[index]


@pytest.mark.parametrize(
    "change",
    [
        {"pages": 0},
        {"basis": "none"},
        {"cap_reached": True},
        {"parse_failures": 1},
        {"requested_start": _END},
        {"requested_start": datetime(2026, 9, 26)},
        {"earliest_observed": _END, "latest_observed": _START},
        {"pages": True},
    ],
)
def test_full_coverage_requires_consistent_bounded_provider_evidence(change: dict) -> None:
    arguments = dict(
        source_name="dart-disclosure",
        requested_start=_START,
        end_utc=_END,
        pages=1,
        completeness="full",
        basis="provider_pagination",
    )
    with pytest.raises(ValueError):
        SourceWindowCoverage(**(arguments | change))


@pytest.mark.parametrize(
    "items",
    [
        "",
        _rss_item("Thu, 24 Sep 2026 01:00:00 GMT"),
        _rss_item("Sat, 26 Sep 2026 12:00:00 GMT") + _rss_item("Thu, 24 Sep 2026 01:00:00 GMT"),
    ],
)
async def test_finite_rss_empty_oldest_and_pinned_rows_never_prove_full(items: str) -> None:
    async with _xml_client(items) as client:
        result = await FomcRssAdapter().fetch_with_coverage(client, _WINDOW)
    assert result.window_coverage.completeness == "unknown"
    assert result.window_coverage.basis == "none"


async def test_finite_rss_parse_loss_is_partial_and_end_is_exclusive() -> None:
    raw = _rss_item("Fri, 25 Sep 2026 15:00:00 GMT") + _rss_item("Sat, 26 Sep 2026 15:00:00 GMT")
    async with _xml_client(raw + "<item><title>Broken release</title></item>") as client:
        result = await FomcRssAdapter().fetch_with_coverage(client, _WINDOW)
    assert len(result.items) == 1
    assert result.items[0].published_at == _START
    assert result.window_coverage.parse_failures == 1
    assert result.window_coverage.completeness == "partial"


async def test_dart_real_bounds_date_overlap_and_provider_exhaustion(monkeypatch) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    requests: list[httpx.Request] = []
    window = replace(_WINDOW, start_utc=datetime(2026, 9, 26, 12, tzinfo=UTC))

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=_page([_entry(1)]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await DartDisclosureAdapter().fetch_with_coverage(client, window)
    assert requests[0].url.params["bgn_de"] == requests[0].url.params["end_de"] == "20260926"
    assert len(result.items) == 1  # 09:00 KST is outside, but the recorded date overlaps.
    item = result.items[0]
    assert item.published_at < window.start_utc
    assert item.raw_metadata["published_at_precision"] == "date"
    assert item.raw_metadata["published_date"] == item.raw_metadata["event_date"] == "2026-09-26"
    assert item.raw_metadata["event_time_basis"] == "source_date"
    assert item.raw_metadata["published_timezone"] == "Asia/Seoul"
    assert news_item_in_window(
        item, replace(_NEWS, logical_start=window.start_utc, requested_start=window.start_utc)
    )
    assert not news_item_in_window(
        item,
        replace(_NEWS, logical_start=_END, requested_start=_END, end_utc=_END + timedelta(hours=1)),
    )
    assert result.window_coverage.completeness == "full"
    assert (
        result.window_coverage.earliest_observed is result.window_coverage.latest_observed is None
    )


async def test_dart_two_pages_require_stable_totals_and_all_receipts(monkeypatch) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    pages = []

    def handler(request):
        page = int(request.url.params["page_no"])
        pages.append(page)
        entries = (
            [_entry(i, relevant=i == 1) for i in range(1, 101)] if page == 1 else [_entry(101)]
        )
        return httpx.Response(200, json=_page(entries, page=page, total=101))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
    assert pages == [1, 2]
    assert len(result.items) == 2
    assert result.window_coverage.completeness == "full"
    assert result.window_coverage.pages == 2


@pytest.mark.parametrize(
    "defect", ["missing-pagination", "duplicate", "malformed", "changed-total", "short-page"]
)
async def test_dart_loss_or_inconsistent_provider_metadata_is_partial(monkeypatch, defect) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")

    def handler(request):
        page = int(request.url.params["page_no"])
        if defect == "changed-total":
            entries = (
                [_entry(i, relevant=False) for i in range(1, 101)]
                if page == 1
                else [_entry(101), _entry(102)]
            )
            payload = _page(entries, page=page, total=101 if page == 1 else 102)
        else:
            payload = _page([_entry(1), _entry(2)])
            if defect == "missing-pagination":
                del payload["total_page"]
            elif defect == "duplicate":
                payload["list"][1] = _entry(1)
            elif defect == "malformed":
                payload["list"][1]["rcept_dt"] = "invalid"
            else:
                payload["list"].pop()
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
    assert result.window_coverage.completeness == "partial"
    assert result.window_coverage.parse_failures > 0


@pytest.mark.parametrize("item_cap", [True, False])
async def test_dart_item_and_page_caps_never_advance_full(monkeypatch, item_cap) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    calls = []

    def handler(request):
        page = int(request.url.params["page_no"])
        calls.append(page)
        entries = [
            _entry(i, relevant=item_cap) for i in range((page - 1) * 100 + 1, page * 100 + 1)
        ]
        return httpx.Response(200, json=_page(entries, page=page, total=100 if item_cap else 400))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
    assert calls == ([1] if item_cap else [1, 2, 3])
    assert len(result.items) == (30 if item_cap else 0)
    assert result.window_coverage.cap_reached
    assert result.window_coverage.completeness == "partial"


async def test_dart_provider_no_results_has_query_evidence_unlike_empty_rss(monkeypatch) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"status": "013", "message": "No results"})
        )
    ) as client:
        result = await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
    assert result.items == ()
    assert result.window_coverage.completeness == "full"
    assert result.window_coverage.pages == 1
    assert result.window_coverage.basis == "provider_pagination"


@pytest.mark.parametrize("after_page", [False, True])
async def test_dart_outer_budget_includes_transport_and_preserves_partial_page(
    monkeypatch, after_page
) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(DartDisclosureAdapter, "_WINDOW_BUDGET_S", 0.03)
    calls = []

    async def handler(request):
        calls.append(int(request.url.params["page_no"]))
        if after_page and len(calls) == 1:
            return httpx.Response(
                200, json=_page([_entry(i, relevant=i == 1) for i in range(1, 101)], total=101)
            )
        await asyncio.sleep(1)
        raise AssertionError("deadline must cancel transport")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        started = asyncio.get_running_loop().time()
        if after_page:
            result = await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
            assert len(result.items) == 1
            assert result.window_coverage.completeness == "partial"
        else:
            with pytest.raises(SourceFetchError):
                await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
        assert asyncio.get_running_loop().time() - started < 0.5
    assert len(calls) == (2 if after_page else 1)


async def test_dart_external_cancellation_propagates(monkeypatch) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    entered = asyncio.Event()

    async def handler(request):
        entered.set()
        await asyncio.Future()
        raise AssertionError("cancelled transport resumed")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        task = asyncio.create_task(DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.parametrize("retry_after", [False, True])
async def test_dart_budget_includes_retry_backoff_and_existing_shorter_deadline(
    monkeypatch, retry_after
) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(
        dart_disclosure,
        "DEFAULT_CONFIG",
        replace(dart_disclosure.DEFAULT_CONFIG, total_budget_s=0.03),
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, headers={"Retry-After": "30"} if retry_after else {})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        started = asyncio.get_running_loop().time()
        with pytest.raises(SourceFetchError):
            await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
        assert asyncio.get_running_loop().time() - started < 0.5
    assert len(calls) == 1


@pytest.mark.parametrize("contradiction", ["empty-with-items", "empty-with-total", "outside-query"])
async def test_dart_inconsistent_query_evidence_never_proves_full(
    monkeypatch, contradiction
) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    payload = _page([_entry(1)])
    if contradiction == "empty-with-items":
        payload["status"] = "013"
    elif contradiction == "empty-with-total":
        payload = {"status": "013", "total_count": 1}
    else:
        payload["list"][0]["rcept_dt"] = "20260925"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        result = await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
    assert result.window_coverage.completeness == "partial"
    assert result.window_coverage.parse_failures > 0


async def test_dart_exactly_thirty_exhausted_items_are_not_false_cap(monkeypatch) -> None:
    monkeypatch.setenv("OPENDART_API_KEY", "synthetic-test-key")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_page([_entry(i) for i in range(30)]))
        )
    ) as client:
        result = await DartDisclosureAdapter().fetch_with_coverage(client, _WINDOW)
    assert len(result.items) == 30
    assert not result.window_coverage.cap_reached
    assert result.window_coverage.completeness == "full"


async def test_policy_actual_dates_use_strict_window_not_scheduled_lookahead(monkeypatch) -> None:
    monkeypatch.setenv("CONGRESS_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("INVESTO_CONGRESS_BILLS", "119/hr/3633")
    actions = [
        {"actionDate": day, "text": "Digital asset policy adopted.", "type": "Vote"}
        for day in ("2026-09-25", "2026-09-26", "2026-09-27")
    ]
    window = replace(_WINDOW, start_utc=datetime(2026, 9, 26, 14, tzinfo=UTC))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"actions": actions}))
    ) as client:
        result = await CongressGovBillActionsAdapter().fetch_with_coverage(client, window)
    assert len(result.items) == 1
    assert result.items[0].raw_metadata["published_date"] == "2026-09-26"
    assert result.items[0].raw_metadata["event_time_basis"] == "source_date"
    assert result.window_coverage.completeness == "unknown"


async def test_senate_actual_release_excluded_but_scheduled_lookahead_preserved(
    monkeypatch,
) -> None:
    hearing = "https://www.banking.senate.gov/hearings/05/08/2026/executive-session"
    release = "https://www.banking.senate.gov/newsroom/majority/release"
    monkeypatch.setenv("INVESTO_SENATE_BANKING_WATCH_URLS", f"{hearing},{release}")
    fixtures = {
        hearing: (_POLICY_FIXTURES / "senate-executive-session.html").read_bytes(),
        release: (_POLICY_FIXTURES / "senate-release.html").read_bytes(),
    }
    window = FetchWindow.from_local_date(date(2026, 5, 11), tz=ZoneInfo("America/New_York"))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=fixtures[str(request.url)])
        )
    ) as client:
        result = await SenateBankingPolicyAdapter().fetch_with_coverage(client, window)
    assert len(result.items) == 1
    assert result.items[0].category == "calendar"
    assert result.items[0].scheduled_at == datetime(2026, 5, 14, tzinfo=UTC)
    assert "published_at_precision" not in result.items[0].raw_metadata
    assert result.window_coverage.completeness == "unknown"


@pytest.mark.parametrize("defect", ["cap", "parse", "subrequest"])
async def test_policy_partial_evidence_cannot_be_unknown_or_full(monkeypatch, defect) -> None:
    url = "https://financialservices.house.gov/news/rss.aspx"
    monkeypatch.setenv(
        "INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS",
        url + (",https://financialservices.house.gov/missing" if defect == "subrequest" else ""),
    )
    count = 13 if defect == "cap" else 1
    raw = "".join(
        _rss_item("Sat, 26 Sep 2026 12:00:00 GMT", link=f"https://example.test/{index}")
        for index in range(count)
    )
    if defect == "parse":
        raw += "<item><title>Broken</title></item>"

    def handler(request):
        if request.url.path == "/missing":
            return httpx.Response(404)
        return httpx.Response(200, text=f"<rss><channel>{raw}</channel></rss>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await HouseFinancialServicesPolicyAdapter().fetch_with_coverage(client, _WINDOW)
    assert result.items
    assert result.window_coverage.completeness == "partial"
    if defect == "cap":
        assert result.window_coverage.cap_reached
        assert len(result.items) == 12
    if defect == "parse":
        assert result.window_coverage.parse_failures == 1


@pytest.mark.parametrize("valid_sibling", [False, True])
async def test_house_invalid_normalized_url_is_exactly_one_partial_loss(
    monkeypatch, valid_sibling
) -> None:
    monkeypatch.setenv(
        "INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS",
        "https://financialservices.house.gov/news/rss.aspx",
    )
    raw = _rss_item("Sat, 26 Sep 2026 12:00:00 GMT", link="https://")
    if valid_sibling:
        raw += _rss_item("Sat, 26 Sep 2026 12:00:00 GMT")
    async with _xml_client(raw) as client:
        result = await HouseFinancialServicesPolicyAdapter().fetch_with_coverage(client, _WINDOW)
    assert len(result.items) == int(valid_sibling)
    assert result.window_coverage.parse_failures == 1
    assert result.window_coverage.completeness == "partial"


@pytest.mark.parametrize("exclusion", ["unrelated", "outside-window"])
async def test_house_intentionally_excluded_rows_are_not_normalization_loss(
    monkeypatch, exclusion
) -> None:
    monkeypatch.setenv(
        "INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS",
        "https://financialservices.house.gov/news/rss.aspx",
    )
    raw = _rss_item(
        "Thu, 24 Sep 2026 12:00:00 GMT"
        if exclusion == "outside-window"
        else "Sat, 26 Sep 2026 12:00:00 GMT",
        link="https://",
    )
    if exclusion == "unrelated":
        raw = raw.replace("Digital asset policy announcement", "Office reopening announcement")
    async with _xml_client(raw) as client:
        result = await HouseFinancialServicesPolicyAdapter().fetch_with_coverage(client, _WINDOW)
    assert result.items == ()
    assert result.window_coverage.parse_failures == 0
    assert result.window_coverage.completeness == "unknown"
