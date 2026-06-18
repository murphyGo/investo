"""Tests for ``investo.sources.sec_newsroom_rss.SecNewsroomRssAdapter``."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError
from investo.sources.sec_newsroom_rss import SecNewsroomRssAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "sec-newsroom-rss"
_PRESS_URL = "https://www.sec.gov/news/pressreleases.rss"
_SPEECHES_URL = "https://www.sec.gov/news/speeches-statements.rss"


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
        return httpx.Response(status, content=body, headers={"content-type": "application/rss+xml"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ny_window(target_date: date) -> FetchWindow:
    return FetchWindow.from_local_date(target_date, ZoneInfo("America/New_York"))


async def test_fetch_returns_official_sec_newsroom_items_from_recorded_fixtures() -> None:
    adapter = SecNewsroomRssAdapter()

    async with _mock_client(
        {
            _PRESS_URL: (_FIXTURE_DIR / "pressreleases.rss").read_bytes(),
            _SPEECHES_URL: (_FIXTURE_DIR / "speeches-statements.rss").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert items
    assert all(item.source_name == "sec-newsroom-rss" for item in items)
    assert all(item.category == "news" for item in items)
    assert {item.raw_metadata["official_source"] for item in items} == {"true"}
    assert {item.raw_metadata["feed_type"] for item in items} <= {
        "press_release",
        "speech_statement",
    }
    assert all(str(item.url).startswith("https://www.sec.gov/") for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    adapter = SecNewsroomRssAdapter()

    async with _mock_client(
        {
            _PRESS_URL: (_FIXTURE_DIR / "pressreleases.rss").read_bytes(),
            _SPEECHES_URL: (_FIXTURE_DIR / "speeches-statements.rss").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2027, 1, 1)))

    assert items == []


async def test_fetch_published_at_is_tz_aware_utc() -> None:
    adapter = SecNewsroomRssAdapter()

    async with _mock_client(
        {
            _PRESS_URL: (_FIXTURE_DIR / "pressreleases.rss").read_bytes(),
            _SPEECHES_URL: (_FIXTURE_DIR / "speeches-statements.rss").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert items
    assert all(item.published_at.tzinfo is not None for item in items)
    assert all(item.published_at.utcoffset() == timedelta(0) for item in items)


async def test_crypto_policy_items_receive_priority_metadata() -> None:
    feed = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item>
<title>SEC Announces Crypto Market Structure Roundtable</title>
<link>https://www.sec.gov/newsroom/press-releases/crypto-market-structure</link>
<description>Digital asset market structure discussion.</description>
<pubDate>Thu, 11 Jun 2026 10:55:00 -0400</pubDate>
<guid isPermaLink="false">crypto-guid</guid>
</item>
<item>
<title>SEC Announces Investor Advisory Committee Members</title>
<link>https://www.sec.gov/newsroom/press-releases/iac-members</link>
<description>Investor education update.</description>
<pubDate>Thu, 11 Jun 2026 10:55:00 -0400</pubDate>
<guid isPermaLink="false">generic-guid</guid>
</item>
</channel></rss>
"""
    adapter = SecNewsroomRssAdapter()

    async with _mock_client({_PRESS_URL: feed, _SPEECHES_URL: b"<rss><channel /></rss>"}) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert [item.title for item in items] == [
        "SEC Announces Crypto Market Structure Roundtable",
        "SEC Announces Investor Advisory Committee Members",
    ]
    assert items[0].raw_metadata["policy_priority"] == "crypto_regulation"
    assert "policy_priority" not in items[1].raw_metadata


async def test_generic_market_structure_item_does_not_receive_crypto_policy_metadata() -> None:
    feed = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><item>
<title>Statement on Options Market Structure</title>
<link>https://www.sec.gov/newsroom/speeches-statements/options-market-structure</link>
<description>Equity options market structure discussion.</description>
<pubDate>Thu, 11 Jun 2026 10:55:00 -0400</pubDate>
<guid isPermaLink="false">options-guid</guid>
</item></channel></rss>
"""
    adapter = SecNewsroomRssAdapter()

    async with _mock_client({_PRESS_URL: feed, _SPEECHES_URL: b"<rss><channel /></rss>"}) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert len(items) == 1
    assert "policy_priority" not in items[0].raw_metadata


async def test_requests_carry_sec_fair_access_user_agent() -> None:
    captured: list[httpx.Request] = []
    adapter = SecNewsroomRssAdapter()
    empty = b"<rss version='2.0'><channel /></rss>"

    async with _mock_client(
        {_PRESS_URL: empty, _SPEECHES_URL: empty},
        captured=captured,
    ) as client:
        await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert [str(request.url) for request in captured] == [_PRESS_URL, _SPEECHES_URL]
    assert all(
        request.headers["user-agent"] == "investo investo@example.com"
        for request in captured
    )


async def test_html_fields_are_sanitized() -> None:
    feed = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><item>
<title>&lt;b&gt;SEC&lt;/b&gt; statement</title>
<link>https://www.sec.gov/newsroom/speeches-statements/example</link>
<description>&lt;i&gt;Commissioner&lt;/i&gt; remarks</description>
<pubDate>Thu, 11 Jun 2026 08:55:43 -0400</pubDate>
</item></channel></rss>
"""
    adapter = SecNewsroomRssAdapter()

    async with _mock_client({_PRESS_URL: b"<rss><channel /></rss>", _SPEECHES_URL: feed}) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert len(items) == 1
    assert items[0].title == "SEC statement"
    assert items[0].summary == "Commissioner remarks"


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = SecNewsroomRssAdapter()

    async with _mock_client({_PRESS_URL: b"<not xml", _SPEECHES_URL: b""}) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert exc_info.value.transient is False
    assert "malformed XML" in str(exc_info.value)


async def test_empty_feeds_return_empty() -> None:
    adapter = SecNewsroomRssAdapter()
    empty = b"<rss version='2.0'><channel /></rss>"

    async with _mock_client({_PRESS_URL: empty, _SPEECHES_URL: empty}) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert items == []


async def test_status_error_surfaces_as_source_fetch_error() -> None:
    adapter = SecNewsroomRssAdapter()

    async with _mock_client({_PRESS_URL: b"temporary"}, status=503) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert exc_info.value.transient is True


async def test_bad_url_and_missing_fields_are_dropped() -> None:
    feed = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item>
<title>Good</title>
<link>https://www.sec.gov/newsroom/press-releases/good</link>
<pubDate>Thu, 11 Jun 2026 10:55:00 -0400</pubDate>
</item>
<item>
<title>Bad URL</title>
<link>javascript:alert(1)</link>
<pubDate>Thu, 11 Jun 2026 10:55:00 -0400</pubDate>
</item>
<item>
<title>Missing date</title>
<link>https://www.sec.gov/newsroom/press-releases/missing</link>
</item>
</channel></rss>
"""
    adapter = SecNewsroomRssAdapter()

    async with _mock_client({_PRESS_URL: feed, _SPEECHES_URL: b"<rss><channel /></rss>"}) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 11)))

    assert [item.title for item in items] == ["Good"]
