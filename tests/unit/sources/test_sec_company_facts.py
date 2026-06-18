"""Tests for ``investo.sources.sec_company_facts.SecCompanyFactsAdapter``."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

import investo.sources.sec_company_facts as sec_company_facts
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError
from investo.sources.sec_company_facts import SecCompanyFactsAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "sec-company-facts"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0000320193.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"


@pytest.fixture(autouse=True)
def _disable_sec_request_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep() -> None:
        return None

    monkeypatch.setattr(sec_company_facts, "_sleep_between_sec_requests", no_sleep)


def _mock_client(
    fixtures: dict[str, bytes],
    *,
    status: int = 200,
    captured: list[httpx.Request] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        body = fixtures.get(str(request.url), b"not found")
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_returns_bounded_company_fact_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEC_COMPANY_CIKS", "AAPL:0000320193")
    adapter = SecCompanyFactsAdapter()

    async with _mock_client(
        {
            _SUBMISSIONS_URL: (_FIXTURE_DIR / "AAPL-submissions.json").read_bytes(),
            _FACTS_URL: (_FIXTURE_DIR / "AAPL-companyfacts.json").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert len(items) == 1
    item = items[0]
    assert item.source_name == "sec-company-facts"
    assert item.category == "macro"
    assert item.title.startswith("AAPL SEC company facts:")
    assert item.raw_metadata["ticker"] == "AAPL"
    assert item.raw_metadata["cik"] == "0000320193"
    assert item.raw_metadata["official_source"] == "true"
    assert item.summary is not None
    assert "revenue=" in item.summary
    assert "latest_filing=" in item.summary


async def test_requests_carry_sec_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_SEC_COMPANY_CIKS", "AAPL:0000320193")
    captured: list[httpx.Request] = []
    adapter = SecCompanyFactsAdapter()

    async with _mock_client(
        {
            _SUBMISSIONS_URL: (_FIXTURE_DIR / "AAPL-submissions.json").read_bytes(),
            _FACTS_URL: (_FIXTURE_DIR / "AAPL-companyfacts.json").read_bytes(),
        },
        captured=captured,
    ) as client:
        await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert [str(request.url) for request in captured] == [_SUBMISSIONS_URL, _FACTS_URL]
    assert all(
        request.headers["user-agent"] == "investo investo@example.com"
        for request in captured
    )


async def test_sec_requests_are_rate_limited_between_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEC_COMPANY_CIKS", "AAPL:0000320193,MSFT:0000789019")
    sleep_calls = 0

    async def record_sleep() -> None:
        nonlocal sleep_calls
        sleep_calls += 1

    monkeypatch.setattr(sec_company_facts, "_sleep_between_sec_requests", record_sleep)
    adapter = SecCompanyFactsAdapter()
    fixtures = {
        "https://data.sec.gov/submissions/CIK0000320193.json": (
            _FIXTURE_DIR / "AAPL-submissions.json"
        ).read_bytes(),
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json": (
            _FIXTURE_DIR / "AAPL-companyfacts.json"
        ).read_bytes(),
        "https://data.sec.gov/submissions/CIK0000789019.json": (
            _FIXTURE_DIR / "AAPL-submissions.json"
        ).read_bytes(),
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json": (
            _FIXTURE_DIR / "AAPL-companyfacts.json"
        ).read_bytes(),
    }

    async with _mock_client(fixtures) as client:
        await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert sleep_calls == 3


async def test_adapter_total_budget_times_out_slow_sec_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEC_COMPANY_CIKS", "AAPL:0000320193")
    monkeypatch.setattr(sec_company_facts, "_ADAPTER_TOTAL_BUDGET_SECONDS", 0.01)
    adapter = SecCompanyFactsAdapter()

    async def handler(request: httpx.Request) -> httpx.Response:
        await sec_company_facts.asyncio.sleep(0.05)
        return httpx.Response(
            200,
            content=(_FIXTURE_DIR / "AAPL-submissions.json").read_bytes(),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert exc_info.value.transient is True
    assert "adapter budget" in str(exc_info.value)


async def test_missing_concepts_still_emits_compact_company_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEC_COMPANY_CIKS", "AAPL:0000320193")
    submissions = (
        b'{"name":"Apple Inc.","tickers":["AAPL"],"exchanges":["Nasdaq"],'
        b'"filings":{"recent":{"form":["10-K"],"filingDate":["2025-10-31"]}}}'
    )
    facts = b'{"facts":{}}'
    adapter = SecCompanyFactsAdapter()

    async with _mock_client({_SUBMISSIONS_URL: submissions, _FACTS_URL: facts}) as client:
        items = await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert len(items) == 1
    assert items[0].summary == "exchange=Nasdaq; latest_filing=10-K 2025-10-31"


async def test_malformed_json_raises_source_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEC_COMPANY_CIKS", "AAPL:0000320193")
    adapter = SecCompanyFactsAdapter()

    async with _mock_client({_SUBMISSIONS_URL: b"{bad", _FACTS_URL: b"{}"}) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert exc_info.value.transient is False


async def test_one_bad_company_does_not_drop_other_company_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEC_COMPANY_CIKS", "BAD:0000000000,AAPL:0000320193")
    adapter = SecCompanyFactsAdapter()
    bad_submission_url = "https://data.sec.gov/submissions/CIK0000000000.json"
    fixtures = {
        _SUBMISSIONS_URL: (_FIXTURE_DIR / "AAPL-submissions.json").read_bytes(),
        _FACTS_URL: (_FIXTURE_DIR / "AAPL-companyfacts.json").read_bytes(),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == bad_submission_url:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(
            200,
            content=fixtures[str(request.url)],
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert [item.raw_metadata["ticker"] for item in items] == ["AAPL"]


async def test_status_error_raises_source_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_SEC_COMPANY_CIKS", "AAPL:0000320193")
    adapter = SecCompanyFactsAdapter()

    async with _mock_client({_SUBMISSIONS_URL: b"forbidden"}, status=403) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert exc_info.value.transient is False


async def test_env_config_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "INVESTO_SEC_COMPANY_CIKS",
        ",".join(f"T{i}:0000320193" for i in range(20)),
    )
    captured: list[httpx.Request] = []
    adapter = SecCompanyFactsAdapter()

    async with _mock_client(
        {
            _SUBMISSIONS_URL: (_FIXTURE_DIR / "AAPL-submissions.json").read_bytes(),
            _FACTS_URL: (_FIXTURE_DIR / "AAPL-companyfacts.json").read_bytes(),
        },
        captured=captured,
    ) as client:
        await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert len(captured) == 16
