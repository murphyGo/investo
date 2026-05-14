"""Tests for u58 official U.S. crypto-policy adapters."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.official_policy import (
    CongressGovBillActionsAdapter,
    HouseFinancialServicesPolicyAdapter,
    SenateBankingPolicyAdapter,
)
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "official-policy"
_WINDOW = FetchWindow.from_local_date(date(2026, 5, 14), tz=UTC)
_CONGRESS_URL = "https://api.congress.gov/v3/bill/119/hr/3633/actions"
_SENATE_HEARING_URL = "https://www.banking.senate.gov/hearings/05/08/2026/executive-session"
_SENATE_RELEASE_URL = (
    "https://www.banking.senate.gov/newsroom/majority/"
    "chairman-scott-senators-lummis-tillis-release-market-structure-bill-text-"
    "ahead-of-banking-committee-markup"
)
_HOUSE_RSS_URL = "https://financialservices.house.gov/news/rss.aspx"
_SENTINEL_KEY = "CONGRESS_SECRET_SHOULD_NOT_LEAK_0123456789"


def _mock_client(fixtures: dict[str, bytes], status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url.copy_with(query=None))
        body = fixtures.get(url)
        if body is None:
            return httpx.Response(404, text="missing")
        return httpx.Response(status, content=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_congress_missing_key_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONGRESS_API_KEY", raising=False)
    adapter = CongressGovBillActionsAdapter()

    async with _mock_client({}) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)

    assert "CONGRESS_API_KEY" in str(exc_info.value)
    assert _SENTINEL_KEY not in str(exc_info.value)


async def test_congress_actions_emit_crypto_policy_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONGRESS_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_CONGRESS_BILLS", "119/hr/3633")
    adapter = CongressGovBillActionsAdapter()
    fixtures = {_CONGRESS_URL: (_FIXTURE_DIR / "congress-actions.json").read_bytes()}

    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 1
    item = items[0]
    assert item.source_name == "congress-gov-bill-actions"
    assert item.raw_metadata["policy_priority"] == "crypto_regulation"
    assert item.raw_metadata["official_source"] == "true"
    assert item.raw_metadata["bill_id"] == "119/hr/3633"
    assert _SENTINEL_KEY not in str(item.raw_metadata)


async def test_congress_auth_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONGRESS_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_CONGRESS_BILLS", "119/hr/3633")
    adapter = CongressGovBillActionsAdapter()
    fixtures = {_CONGRESS_URL: b'{"message": "Forbidden"}'}

    async with _mock_client(fixtures, status=403) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)

    error = str(exc_info.value)
    assert "status 403" in error
    assert _SENTINEL_KEY not in error


async def test_congress_empty_actions_returns_no_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONGRESS_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_CONGRESS_BILLS", "119/hr/3633")
    adapter = CongressGovBillActionsAdapter()

    async with _mock_client({_CONGRESS_URL: b'{"actions": []}'}) as client:
        assert await adapter.fetch(client, _WINDOW) == []


async def test_congress_malformed_payload_raises_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONGRESS_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_CONGRESS_BILLS", "119/hr/3633")
    adapter = CongressGovBillActionsAdapter()

    async with _mock_client({_CONGRESS_URL: b"not-json"}) as client:
        with pytest.raises(SourceFetchError, match="malformed JSON"):
            await adapter.fetch(client, _WINDOW)


async def test_senate_policy_parses_hearing_and_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "INVESTO_SENATE_BANKING_WATCH_URLS",
        f"{_SENATE_HEARING_URL},{_SENATE_RELEASE_URL}",
    )
    adapter = SenateBankingPolicyAdapter()
    fixtures = {
        _SENATE_HEARING_URL: (_FIXTURE_DIR / "senate-executive-session.html").read_bytes(),
        _SENATE_RELEASE_URL: (_FIXTURE_DIR / "senate-release.html").read_bytes(),
    }

    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.source_name for item in items] == [
        "senate-banking-policy",
        "senate-banking-policy",
    ]
    hearing = next(item for item in items if item.category == "calendar")
    assert hearing.scheduled_at == datetime(2026, 5, 14, 0, 0, tzinfo=UTC)
    assert hearing.raw_metadata["event_type"] == "committee_markup"
    assert hearing.raw_metadata["committee"] == "Senate Banking"
    assert hearing.raw_metadata["bill_id"] == "hr3633"
    release = next(item for item in items if item.category == "news")
    assert "Market Structure Bill Text" in release.title


async def test_senate_selector_missing_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SENATE_BANKING_WATCH_URLS", _SENATE_HEARING_URL)
    adapter = SenateBankingPolicyAdapter()

    fixtures = {_SENATE_HEARING_URL: b"<html><body>Digital asset</body></html>"}
    async with _mock_client(fixtures) as client:
        assert await adapter.fetch(client, _WINDOW) == []


async def test_house_rss_filters_non_crypto_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS", _HOUSE_RSS_URL)
    adapter = HouseFinancialServicesPolicyAdapter()
    fixtures = {_HOUSE_RSS_URL: (_FIXTURE_DIR / "house-policy-rss.xml").read_bytes()}

    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 1
    item = items[0]
    assert item.source_name == "house-financial-services-policy"
    assert (
        item.title == "Chairman Hill Unveils Bipartisan Digital Asset Market Structure Legislation"
    )
    assert item.raw_metadata["policy_priority"] == "crypto_regulation"
    assert item.raw_metadata["committee"] == "House Financial Services"


async def test_house_rss_empty_feed_returns_no_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS", _HOUSE_RSS_URL)
    adapter = HouseFinancialServicesPolicyAdapter()

    async with _mock_client({_HOUSE_RSS_URL: b"<rss><channel /></rss>"}) as client:
        assert await adapter.fetch(client, _WINDOW) == []


async def test_house_rss_http_error_raises_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS", _HOUSE_RSS_URL)
    adapter = HouseFinancialServicesPolicyAdapter()

    async with _mock_client({_HOUSE_RSS_URL: b"not found"}, status=404) as client:
        with pytest.raises(SourceFetchError, match="status 404"):
            await adapter.fetch(client, _WINDOW)


async def test_house_rss_malformed_xml_raises_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS", _HOUSE_RSS_URL)
    adapter = HouseFinancialServicesPolicyAdapter()

    async with _mock_client({_HOUSE_RSS_URL: b"<rss>"}) as client:
        with pytest.raises(SourceFetchError, match="malformed XML"):
            await adapter.fetch(client, _WINDOW)
