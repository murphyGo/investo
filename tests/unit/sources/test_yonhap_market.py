"""Tests for ``investo.sources.yonhap_market.YonhapMarketAdapter``.

Pins the algorithm from FD L6.7 (Extension #3 2026-05-01) against:

* The recorded real-feed fixture (``fixtures/api/yonhap-market/feed.xml``,
  re-recorded 2026-07-16 for u136) — field mapping, RFC-822 ``+0900`` →
  tz-aware UTC parsing, KST window filtering, CDATA-wrapped Korean title
  round-trip, and the u136 image-metadata harvest (98/120 items carry
  ``<media:content type="image/jpeg">``; 22 carry none).
* Inline synthetic XML — AC-7.2 (HTML in CDATA-wrapped title stripped),
  AC-7.3 (non-http/https URLs dropped), edge cases (missing required
  fields, naive pubDate, missing ``<dc:creator>`` → key OMITTED, summary
  truncation at 280 chars, malformed XML), and first-image-wins when an
  item carries several ``<media:content>`` children.

u136 contracts pinned here: Contract #3 (``image_*`` raw_metadata keys,
absent field = absent key) and Contract #4 (license-family keys are
NEVER emitted).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError
from investo.sources.yonhap_market import YonhapMarketAdapter
from tests.unit.sources._mock_transport import mock_client as _mock_client

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "yonhap-market"
_REAL_FIXTURE = _FIXTURE_DIR / "feed.xml"


# ---------------------------------------------------------------------------
# Real fixture — happy path
# ---------------------------------------------------------------------------


async def test_fetch_returns_items_within_window() -> None:
    # KST 2026-07-16 → UTC [2026-07-15 15:00, 2026-07-16 15:00). The
    # fixture has many entries dated "Thu, 16 Jul 2026 HH:MM:SS +0900"
    # which fall in this window once converted to UTC.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) >= 3
    assert all(item.source_name == "yonhap-market" for item in items)
    assert all(item.category == "news" for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    # Far-future date; recorded fixture has no entries that recent.
    window = FetchWindow.from_kst_date(date(2027, 1, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_fetch_published_at_is_tz_aware_and_utc() -> None:
    # AC-7.4 — every returned item has tz-aware published_at, in UTC.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.published_at.tzinfo is not None
        assert item.published_at.tzinfo.utcoffset(item.published_at) == timedelta(0)


async def test_fetch_url_is_http_or_https() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.url is not None
        assert str(item.url).startswith(("http://", "https://"))


async def test_fetch_korean_title_round_trip_from_real_fixture() -> None:
    # Exact-string anchor: pin one real Korean-language title from the
    # fixture (CDATA round-trip + UTF-8 decode + strip_html no-op pass).
    # The first item in the recorded feed (2026-07-16 23:09:47 +0900)
    # has the title shown below; if the fixture is re-recorded the
    # assertion must be updated to a then-present title.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    titles = [item.title for item in items]
    assert "뉴욕증시, 반도체주 약세에 하락 출발" in titles


async def test_fetch_raw_metadata_keys_and_value_types() -> None:
    # R8 / DEBT-028 guardrail: raw_metadata values must be flat
    # strings/ints. Allowed keys are a subset of {"guid", "creator"}
    # plus the u136 Contract #3 image keys; the recorded fixture has
    # guid + creator for every item, but per FD L6.7 absence of creator
    # is non-fatal so we accept the subset.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    allowed = {
        "guid",
        "creator",
        "image_url",
        "image_width",
        "image_height",
        "image_mime",
        "image_credit",
    }
    assert items
    for item in items:
        assert set(item.raw_metadata.keys()).issubset(allowed)
        for value in item.raw_metadata.values():
            assert isinstance(value, str | int)
            assert value != ""  # absent keys are omitted, not empty


async def test_fetch_creator_present_in_real_fixture() -> None:
    # The recorded fixture has <dc:creator> for every item — assert
    # the adapter populates raw_metadata.creator (key present + value
    # non-empty). The presence flag is what's contractually pinned;
    # specific creator names may shift as the live feed rolls.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert "creator" in item.raw_metadata
        assert item.raw_metadata["creator"]  # non-empty


# ---------------------------------------------------------------------------
# u136 — <media:content> image-metadata harvest (Contracts #3 and #4)
# ---------------------------------------------------------------------------

# Contract #4 — license-family keys the adapter must NEVER emit: their
# absence keeps visuals/external_image._manifest_from_item at None, so
# the dormant external-image fetch path can never trigger off harvested
# feed metadata.
_FORBIDDEN_LICENSE_KEYS = frozenset(
    {
        "image_license",
        "image_attribution",
        "image_author",
        "image_allowed_use",
        "license",
        "attribution",
        "author",
        "allowed_use",
    }
)


async def test_image_bearing_items_expose_exactly_url_and_mime() -> None:
    # 98/120 recorded items carry <media:content url=… type="image/jpeg">
    # with NO width/height attrs and NO <media:credit> — so exactly
    # image_url + image_mime appear (absent field = absent key).
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    with_image = [item for item in items if "image_url" in item.raw_metadata]
    assert with_image  # the recording has plenty of image-bearing items
    for item in with_image:
        image_url = item.raw_metadata["image_url"]
        assert isinstance(image_url, str)
        assert image_url.startswith("https://img.yna.co.kr/")
        assert item.raw_metadata["image_mime"] == "image/jpeg"
        # This feed never supplies dimensions or credit.
        assert "image_width" not in item.raw_metadata
        assert "image_height" not in item.raw_metadata
        assert "image_credit" not in item.raw_metadata


async def test_image_less_items_have_no_image_keys() -> None:
    # 22/120 recorded items (표/시세표 posts) have no <media:content>;
    # every image key must be absent — never None or empty.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    without_image = [item for item in items if "image_url" not in item.raw_metadata]
    assert without_image  # both branches exist in the recording
    image_keys = {"image_url", "image_width", "image_height", "image_mime", "image_credit"}
    for item in without_image:
        assert not image_keys & set(item.raw_metadata.keys())


async def test_no_license_family_keys_ever_emitted() -> None:
    # Contract #4 safety invariant, pinned against the full recording.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        keys = set(item.raw_metadata.keys())
        assert not keys & _FORBIDDEN_LICENSE_KEYS
        assert not any(key.startswith("visual_image_") for key in keys)


_SYNTH_MULTI_IMAGE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel><title>Synthetic</title>
    <item>
      <title>Two photos</title>
      <link>https://www.yna.co.kr/view/multi.html</link>
      <guid>g1</guid>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
      <media:content url="https://img.yna.co.kr/photo/first.jpg" type="image/jpeg"/>
      <media:content url="https://img.yna.co.kr/photo/second.jpg" type="image/jpeg"/>
    </item>
  </channel>
</rss>
"""


async def test_multi_image_item_harvests_first_image_only() -> None:
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_MULTI_IMAGE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata["image_url"] == "https://img.yna.co.kr/photo/first.jpg"
    assert items[0].raw_metadata["image_mime"] == "image/jpeg"


# ---------------------------------------------------------------------------
# AC-7.2 — HTML in CDATA-wrapped title is stripped
# ---------------------------------------------------------------------------


_SYNTH_HTML_IN_TITLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel><title>Synthetic</title>
    <item>
      <title><![CDATA[<b>\xec\xa0\x9c\xeb\xaa\xa9</b>]]></title>
      <link>https://www.yna.co.kr/view/A.html</link>
      <guid isPermaLink="true">https://www.yna.co.kr/view/A.html</guid>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
      <dc:creator>\xea\xb8\xb0\xec\x9e\x90</dc:creator>
      <description><![CDATA[short body]]></description>
    </item>
  </channel>
</rss>
"""


async def test_html_in_cdata_title_is_stripped() -> None:
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_HTML_IN_TITLE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "제목"


# ---------------------------------------------------------------------------
# AC-7.3 — non-http/https schemes dropped
# ---------------------------------------------------------------------------


_SYNTH_BAD_URL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel><title>Synthetic</title>
    <item>
      <title><![CDATA[\xec\xa2\x8b\xec\x9d\x80 \xea\xb8\xb0\xec\x82\xac]]></title>
      <link>https://www.yna.co.kr/view/good.html</link>
      <guid>g1</guid>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
      <dc:creator>\xea\xb8\xb0\xec\x9e\x90</dc:creator>
    </item>
    <item>
      <title>file URL entry</title>
      <link>file:///etc/passwd</link>
      <guid>g2</guid>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
    </item>
    <item>
      <title>javascript URL entry</title>
      <link>javascript:alert(1)</link>
      <guid>g3</guid>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_non_http_https_urls_dropped() -> None:
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_BAD_URL) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "좋은 기사"


# ---------------------------------------------------------------------------
# Missing <dc:creator> → key OMITTED (NOT empty string)
# ---------------------------------------------------------------------------


_SYNTH_MIXED_CREATOR = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel><title>Synthetic</title>
    <item>
      <title>With creator</title>
      <link>https://www.yna.co.kr/view/with.html</link>
      <guid>g1</guid>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
      <dc:creator>Reporter A</dc:creator>
    </item>
    <item>
      <title>Without creator</title>
      <link>https://www.yna.co.kr/view/without.html</link>
      <guid>g2</guid>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_missing_creator_key_is_omitted_not_empty_string() -> None:
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_MIXED_CREATOR) as client:
        items = await adapter.fetch(client, window)

    by_title = {item.title: item for item in items}
    assert set(by_title.keys()) == {"With creator", "Without creator"}

    with_creator = by_title["With creator"]
    assert with_creator.raw_metadata.get("creator") == "Reporter A"

    without_creator = by_title["Without creator"]
    # The key MUST be absent — not an empty string. Per FD L6.7.
    assert "creator" not in without_creator.raw_metadata


# ---------------------------------------------------------------------------
# Summary truncation at 280 chars
# ---------------------------------------------------------------------------


def _long_description_xml() -> bytes:
    long_text = "가" * 400  # 400-char Korean description
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<channel><title>Synthetic</title>"
        "<item>"
        "<title>Long body</title>"
        "<link>https://www.yna.co.kr/view/long.html</link>"
        "<guid>g1</guid>"
        "<pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>"
        f"<description><![CDATA[{long_text}]]></description>"
        "</item>"
        "</channel></rss>"
    )
    return body.encode("utf-8")


async def test_summary_is_truncated_to_280_chars() -> None:
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_long_description_xml()) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    summary = items[0].summary
    assert summary is not None
    assert len(summary) == 280
    assert summary == "가" * 280


# ---------------------------------------------------------------------------
# Edge cases: naive pubDate, missing fields, empty channel, malformed XML
# ---------------------------------------------------------------------------


async def test_naive_or_garbage_pubdate_is_dropped() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Naive RFC-822 (no offset)</title>
      <link>https://www.yna.co.kr/view/x.html</link>
      <pubDate>Fri, 1 May 2026 12:00:00</pubDate>
      <guid>g1</guid>
    </item>
    <item>
      <title>Wholly unparseable pubDate</title>
      <link>https://www.yna.co.kr/view/y.html</link>
      <pubDate>not a date at all</pubDate>
      <guid>g2</guid>
    </item>
  </channel>
</rss>
"""
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_missing_required_fields_dropped() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Has everything</title>
      <link>https://www.yna.co.kr/view/x.html</link>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
    </item>
    <item>
      <title>Missing pubDate</title>
      <link>https://www.yna.co.kr/view/y.html</link>
    </item>
    <item>
      <link>https://www.yna.co.kr/view/z.html</link>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
    </item>
    <item>
      <title>Missing link</title>
      <pubDate>Fri, 1 May 2026 12:00:00 +0900</pubDate>
    </item>
  </channel>
</rss>
"""
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Has everything"


async def test_empty_channel_returns_empty_list() -> None:
    body = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<rss version="2.0"><channel><title>Empty</title></channel></rss>'
    )
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = YonhapMarketAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(b"<not xml") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    assert "malformed XML" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Adapter identity (ClassVar attributes)
# ---------------------------------------------------------------------------


def test_adapter_class_attributes() -> None:
    assert YonhapMarketAdapter.name == "yonhap-market"
    assert YonhapMarketAdapter.category == "news"
    assert YonhapMarketAdapter._FEED_URL == "https://www.yna.co.kr/rss/market.xml"
