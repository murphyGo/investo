"""Tests for ``investo.sources.fed_speech_rss.FedSpeechRssAdapter``."""

from __future__ import annotations

from datetime import UTC, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.fed_speech_rss import FedSpeechRssAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "fed-speech-rss"
_SPEECHES_URL = "https://www.federalreserve.gov/feeds/speeches.xml"
_TESTIMONY_URL = "https://www.federalreserve.gov/feeds/testimony.xml"


def _mock_client(
    fixtures: dict[str, bytes],
    *,
    status: int = 200,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = fixtures.get(str(request.url), b"not found")
        return httpx.Response(status, content=body, headers={"content-type": "text/xml"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ny_window(target_date: date) -> FetchWindow:
    return FetchWindow.from_local_date(target_date, ZoneInfo("America/New_York"))


async def test_fetch_returns_official_speech_items_from_recorded_fixtures() -> None:
    adapter = FedSpeechRssAdapter()
    window = _ny_window(date(2026, 6, 6))

    async with _mock_client(
        {
            _SPEECHES_URL: (_FIXTURE_DIR / "speeches.xml").read_bytes(),
            _TESTIMONY_URL: (_FIXTURE_DIR / "testimony.xml").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, window)

    assert items
    assert all(item.source_name == "fed-speech-rss" for item in items)
    assert all(item.category == "news" for item in items)
    assert {item.raw_metadata["official_source"] for item in items} == {"true"}
    assert {item.raw_metadata["feed_type"] for item in items} <= {"speech", "testimony"}
    assert all(str(item.url).startswith("https://www.federalreserve.gov/") for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    adapter = FedSpeechRssAdapter()

    async with _mock_client(
        {
            _SPEECHES_URL: (_FIXTURE_DIR / "speeches.xml").read_bytes(),
            _TESTIMONY_URL: (_FIXTURE_DIR / "testimony.xml").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2027, 1, 1)))

    assert items == []


async def test_fetch_published_at_is_tz_aware_utc() -> None:
    adapter = FedSpeechRssAdapter()

    async with _mock_client(
        {
            _SPEECHES_URL: (_FIXTURE_DIR / "speeches.xml").read_bytes(),
            _TESTIMONY_URL: (_FIXTURE_DIR / "testimony.xml").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 6)))

    assert items
    assert all(item.published_at.tzinfo is not None for item in items)
    assert all(item.published_at.utcoffset() == timedelta(0) for item in items)


async def test_html_fields_are_sanitized() -> None:
    feed = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><item>
<title>&lt;b&gt;Policy&lt;/b&gt; remarks</title>
<link>https://www.federalreserve.gov/newsevents/speech/example.htm</link>
<guid>g1</guid>
<description>&lt;i&gt;At conference&lt;/i&gt;</description>
<category>Speech</category>
<pubDate>Sat, 6 Jun 2026 16:00:00 GMT</pubDate>
</item></channel></rss>
"""
    adapter = FedSpeechRssAdapter()

    async with _mock_client(
        {_SPEECHES_URL: feed, _TESTIMONY_URL: b"<rss><channel /></rss>"}
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 6)))

    assert len(items) == 1
    assert items[0].title == "Policy remarks"
    assert items[0].summary == "At conference"


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = FedSpeechRssAdapter()

    async with _mock_client({_SPEECHES_URL: b"<not xml", _TESTIMONY_URL: b""}) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _ny_window(date(2026, 6, 6)))

    assert exc_info.value.transient is False
    assert "malformed XML" in str(exc_info.value)


async def test_empty_feeds_return_empty() -> None:
    adapter = FedSpeechRssAdapter()
    empty = b"<rss version='2.0'><channel /></rss>"

    async with _mock_client({_SPEECHES_URL: empty, _TESTIMONY_URL: empty}) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 6)))

    assert items == []


async def test_status_error_surfaces_as_source_fetch_error() -> None:
    adapter = FedSpeechRssAdapter()

    async with _mock_client({_SPEECHES_URL: b"temporary"}, status=503) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _ny_window(date(2026, 6, 6)))

    assert exc_info.value.transient is True


async def test_bad_url_and_missing_fields_are_dropped() -> None:
    feed = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item>
<title>Good</title>
<link>https://www.federalreserve.gov/newsevents/speech/good.htm</link>
<pubDate>Sat, 6 Jun 2026 16:00:00 GMT</pubDate>
</item>
<item>
<title>Bad URL</title>
<link>javascript:alert(1)</link>
<pubDate>Sat, 6 Jun 2026 16:00:00 GMT</pubDate>
</item>
<item>
<title>Missing date</title>
<link>https://www.federalreserve.gov/newsevents/speech/missing.htm</link>
</item>
</channel></rss>
"""
    adapter = FedSpeechRssAdapter()

    async with _mock_client(
        {_SPEECHES_URL: feed, _TESTIMONY_URL: b"<rss><channel /></rss>"}
    ) as client:
        items = await adapter.fetch(client, _ny_window(date(2026, 6, 6)))

    assert [item.title for item in items] == ["Good"]
    assert items[0].published_at.tzinfo is UTC
