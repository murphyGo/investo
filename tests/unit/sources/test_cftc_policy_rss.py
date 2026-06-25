"""Tests for ``investo.sources.cftc_policy_rss.CftcPolicyRssAdapter``."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.cftc_policy_rss import CftcPolicyRssAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "cftc-policy-rss"
_GENERAL_URL = "https://www.cftc.gov/RSS/RSSGP/rssgp.xml"
_ENFORCEMENT_URL = "https://www.cftc.gov/RSS/RSSENF/rssenf.xml"
_SPEECH_URL = "https://www.cftc.gov/RSS/RSSST/rssst.xml"


def _mock_client(
    fixtures: dict[str, bytes],
    *,
    status_by_url: dict[str, int] | None = None,
    captured: list[httpx.Request] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        url = str(request.url)
        status = (status_by_url or {}).get(url, 200)
        body = fixtures.get(url, b"not found")
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/rss+xml; charset=utf-8"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ny_window(target_date: date) -> FetchWindow:
    return FetchWindow.from_local_date(target_date, ZoneInfo("America/New_York"))


def _fixture_map() -> dict[str, bytes]:
    return {
        _GENERAL_URL: (_FIXTURE_DIR / "general_press.rss").read_bytes(),
        _ENFORCEMENT_URL: (_FIXTURE_DIR / "enforcement_press.rss").read_bytes(),
        _SPEECH_URL: (_FIXTURE_DIR / "speech_testimony.rss").read_bytes(),
    }


async def test_fetch_returns_official_cftc_policy_items_from_fixtures() -> None:
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(_fixture_map()) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert [item.source_name for item in items] == ["cftc-policy-rss"] * 4
    assert {item.category for item in items} == {"news"}
    assert {item.raw_metadata["official_source"] for item in items} == {"true"}
    assert {item.raw_metadata["feed_type"] for item in items} == {
        "general_press",
        "enforcement_press",
        "speech_testimony",
    }
    assert all(str(item.url).startswith("https://www.cftc.gov/") for item in items)


async def test_fetch_published_at_is_tz_aware_utc() -> None:
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(_fixture_map()) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert items
    assert all(item.published_at.tzinfo is not None for item in items)
    assert all(item.published_at.utcoffset() == timedelta(0) for item in items)


async def test_partial_feed_failure_preserves_successful_sibling_items() -> None:
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(
        _fixture_map(),
        status_by_url={_ENFORCEMENT_URL: 503},
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert items
    assert {item.raw_metadata["feed_type"] for item in items} == {
        "general_press",
        "speech_testimony",
    }


async def test_all_feed_failures_raise_single_source_fetch_error() -> None:
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(
        {_GENERAL_URL: b"down", _ENFORCEMENT_URL: b"down", _SPEECH_URL: b"down"},
        status_by_url={_GENERAL_URL: 503, _ENFORCEMENT_URL: 503, _SPEECH_URL: 503},
    ) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert exc_info.value.source_name == "cftc-policy-rss"
    assert exc_info.value.transient is True


async def test_malformed_feed_is_isolated_when_siblings_succeed() -> None:
    adapter = CftcPolicyRssAdapter()
    fixtures = _fixture_map()
    fixtures[_GENERAL_URL] = b"<not xml"

    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert items
    assert {item.raw_metadata["feed_type"] for item in items} == {
        "enforcement_press",
        "speech_testimony",
    }


async def test_fetch_window_outside_returns_empty() -> None:
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(_fixture_map()) as client:
        items = await adapter.fetch(client, _ny_window(date(2027, 1, 1)))

    assert items == []


async def test_dedupe_uses_canonical_url_then_title_and_sorts_newest_first() -> None:
    duplicate_feed = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item>
<title>Duplicate CFTC Digital Asset Release</title>
<link>https://www.cftc.gov/PressRoom/PressReleases/dup</link>
<description>Digital asset policy.</description>
<pubDate>Thu, 11 Jun 2026 09:00:00 -0400</pubDate>
</item>
<item>
<title>Duplicate CFTC Digital Asset Release</title>
<link>https://www.cftc.gov/PressRoom/PressReleases/dup?copy=1</link>
<description>Digital asset policy duplicate title.</description>
<pubDate>Thu, 11 Jun 2026 10:00:00 -0400</pubDate>
</item>
</channel></rss>
"""
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(
        {
            _GENERAL_URL: duplicate_feed,
            _ENFORCEMENT_URL: b"<rss><channel /></rss>",
            _SPEECH_URL: b"<rss><channel /></rss>",
        }
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert [item.title for item in items] == ["Duplicate CFTC Digital Asset Release"]


async def test_crypto_policy_items_receive_bounded_priority_metadata() -> None:
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(_fixture_map()) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    crypto_item = next(item for item in items if "Digital Asset" in item.title)
    generic_item = next(item for item in items if "Agricultural" in item.title)
    assert crypto_item.raw_metadata["policy_priority"] == "crypto_regulation"
    assert crypto_item.raw_metadata["policy_source"] == "cftc"
    assert "policy_priority" not in generic_item.raw_metadata


async def test_metadata_is_string_only_and_requests_use_public_headers() -> None:
    captured: list[httpx.Request] = []
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(_fixture_map(), captured=captured) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert all(
        isinstance(key, str) and isinstance(value, str)
        for item in items
        for key, value in item.raw_metadata.items()
    )
    assert [str(request.url) for request in captured] == [
        _GENERAL_URL,
        _ENFORCEMENT_URL,
        _SPEECH_URL,
    ]
    assert all("Investo/1.0" in request.headers["user-agent"] for request in captured)


async def test_bad_url_missing_fields_and_naive_dates_are_dropped() -> None:
    feed = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item>
<title>Good CFTC Release</title>
<link>https://www.cftc.gov/PressRoom/PressReleases/good</link>
<description>General update.</description>
<pubDate>Thu, 11 Jun 2026 10:55:00 -0400</pubDate>
</item>
<item>
<title>Bad URL</title>
<link>javascript:alert(1)</link>
<pubDate>Thu, 11 Jun 2026 10:55:00 -0400</pubDate>
</item>
<item>
<title>Missing Date</title>
<link>https://www.cftc.gov/PressRoom/PressReleases/missing-date</link>
</item>
<item>
<title>Naive Date</title>
<link>https://www.cftc.gov/PressRoom/PressReleases/naive-date</link>
<pubDate>Thu, 11 Jun 2026 10:55:00</pubDate>
</item>
</channel></rss>
"""
    adapter = CftcPolicyRssAdapter()

    async with _mock_client(
        {
            _GENERAL_URL: feed,
            _ENFORCEMENT_URL: b"<rss><channel /></rss>",
            _SPEECH_URL: b"<rss><channel /></rss>",
        }
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert [item.title for item in items] == ["Good CFTC Release"]
