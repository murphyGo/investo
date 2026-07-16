"""Tests for ``investo.sources.theblock_crypto.TheBlockCryptoAdapter``.

Pins the algorithm from FD L6.8 (Extension #3 2026-05-01) against:

* The recorded real-feed fixture (``fixtures/api/theblock-crypto/feed.xml``,
  re-recorded 2026-07-16 for u136) — field mapping, RFC-822 ``-0400`` →
  tz-aware UTC parsing, KST window filtering, ``utm_*`` query-param
  stripping on every emitted URL, and the u136 image-metadata harvest
  (all 20 items carry a single tbstat-CDN
  ``<media:thumbnail width="800" height="450">`` — the helper's
  thumbnail-fallback branch; Contracts #3 and #4).
* Inline synthetic XML — AC-7.2 (HTML in title stripped), AC-7.3
  (non-http/https URLs dropped), edge cases (missing required fields,
  naive pubDate, missing ``<dc:creator>`` → key OMITTED, missing
  ``<category>`` → ``categories`` key OMITTED, multiple ``<category>``
  → comma-joined, ``<content:encoded>`` IGNORED, summary truncation
  at 280 chars, malformed XML).
* Explicit isolated unit tests of the per-adapter
  :func:`_strip_tracking_params` helper covering all 5 ``utm_*`` keys
  + non-utm preservation + no-query no-op.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError
from investo.sources.theblock_crypto import (
    TheBlockCryptoAdapter,
    _strip_tracking_params,
)
from tests.unit.sources._mock_transport import mock_client as _mock_client

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "theblock-crypto"
_REAL_FIXTURE = _FIXTURE_DIR / "feed.xml"


# ---------------------------------------------------------------------------
# _strip_tracking_params unit tests (FD L6.8 — explicit 5-input matrix)
# ---------------------------------------------------------------------------


def test_strip_tracking_params_utm_only_returns_no_query() -> None:
    # When utm_source AND utm_medium are the only query params, the
    # rebuilt URL has no `?` at all (urlencode of empty list yields
    # "", and urlunparse omits the separator for empty query).
    assert (
        _strip_tracking_params("https://www.theblock.co/post?utm_source=rss&utm_medium=rss")
        == "https://www.theblock.co/post"
    )


def test_strip_tracking_params_preserves_non_utm_params() -> None:
    assert (
        _strip_tracking_params("https://www.theblock.co/post?utm_source=rss&id=123")
        == "https://www.theblock.co/post?id=123"
    )


def test_strip_tracking_params_preserves_non_utm_with_mixed_order() -> None:
    assert (
        _strip_tracking_params(
            "https://www.theblock.co/post?id=123&utm_source=rss&utm_medium=rss&ref=foo"
        )
        == "https://www.theblock.co/post?id=123&ref=foo"
    )


def test_strip_tracking_params_strips_all_five_utm_keys() -> None:
    # utm_campaign, utm_term, utm_content — the three "less common"
    # tracking keys covered by the same helper.
    assert (
        _strip_tracking_params(
            "https://www.theblock.co/post?utm_campaign=x&utm_term=y&utm_content=z"
        )
        == "https://www.theblock.co/post"
    )


def test_strip_tracking_params_no_query_is_noop() -> None:
    assert _strip_tracking_params("https://www.theblock.co/post") == "https://www.theblock.co/post"


# ---------------------------------------------------------------------------
# Real fixture — happy path
# ---------------------------------------------------------------------------


async def test_fetch_returns_items_within_window() -> None:
    # KST 2026-07-16 → UTC [2026-07-15 15:00, 2026-07-16 15:00). The
    # fixture has 20 entries dated -0400 (EDT) on 2026-07-15 and
    # 2026-07-16; 17 fall in this window once converted to UTC.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) >= 3
    assert all(item.source_name == "theblock-crypto" for item in items)
    assert all(item.category == "news" for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    # Far-future date; recorded fixture has no entries that recent.
    window = FetchWindow.from_kst_date(date(2027, 1, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_fetch_published_at_is_tz_aware_and_utc() -> None:
    # AC-7.4 — every returned item has tz-aware published_at, in UTC.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.published_at.tzinfo is not None
        assert item.published_at.tzinfo.utcoffset(item.published_at) == timedelta(0)


async def test_fetch_url_is_http_or_https() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.url is not None
        assert str(item.url).startswith(("http://", "https://"))


async def test_fetch_emitted_urls_have_no_utm_params() -> None:
    # FD L6.8 integration check: every <link> in the recorded fixture
    # ends with "?utm_source=rss&utm_medium=rss", and the adapter MUST
    # strip those params before storing. Asserting the absence of any
    # "utm_" substring in emitted URLs is the canonical end-to-end
    # check that the per-adapter helper actually wired into the
    # _normalize_entry path.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        url_str = str(item.url)
        assert "utm_source" not in url_str
        assert "utm_medium" not in url_str
        assert "utm_campaign" not in url_str
        assert "utm_term" not in url_str
        assert "utm_content" not in url_str


async def test_fetch_raw_metadata_keys_and_value_types() -> None:
    # R8 / DEBT-028 guardrail: raw_metadata values must all be flat
    # strings/ints — not floats / nested dicts. Allowed keys are a
    # subset of {"guid", "creator", "categories"} plus the u136
    # Contract #3 image keys.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    allowed = {
        "guid",
        "creator",
        "categories",
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


async def test_fetch_real_fixture_categories_are_comma_joined() -> None:
    # The recorded fixture has multiple <category> elements per item;
    # the adapter joins them with ",". Pin the comma-join contract
    # against the real fixture (specific values may shift if the live
    # feed is re-recorded, but the comma-join shape is the contract).
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    items_with_categories = [item for item in items if "categories" in item.raw_metadata]
    assert items_with_categories, "expected at least one item with <category>"
    for item in items_with_categories:
        cats = item.raw_metadata["categories"]
        # Sanity: comma-joined, no leading/trailing whitespace, no
        # empty segments (split round-trip yields all non-empty).
        for segment in cats.split(","):
            assert segment.strip() == segment
            assert segment != ""


# ---------------------------------------------------------------------------
# u136 — <media:thumbnail> image-metadata harvest (Contracts #3 and #4)
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


async def test_image_bearing_items_expose_thumbnail_url_and_dimensions() -> None:
    # Every item in the recording carries a single tbstat-CDN
    # <media:thumbnail width="800" height="450"> and NO <media:content>
    # — this is the helper's thumbnail-fallback branch. No `type` attr
    # and no <media:credit> → exactly image_url + image_width +
    # image_height appear (absent field = absent key).
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        image_url = item.raw_metadata["image_url"]
        assert isinstance(image_url, str)
        assert image_url.startswith("https://www.tbstat.com/")
        assert item.raw_metadata["image_width"] == 800
        assert item.raw_metadata["image_height"] == 450
        assert "image_mime" not in item.raw_metadata
        assert "image_credit" not in item.raw_metadata


async def test_no_license_family_keys_ever_emitted() -> None:
    # Contract #4 safety invariant, pinned against the full recording.
    body = _REAL_FIXTURE.read_bytes()
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 7, 16))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        keys = set(item.raw_metadata.keys())
        assert not keys & _FORBIDDEN_LICENSE_KEYS
        assert not any(key.startswith("visual_image_") for key in keys)


_SYNTH_NO_IMAGE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel><title>Synthetic</title>
    <item>
      <title>Post without any media element</title>
      <link>https://www.theblock.co/post/plain</link>
      <guid>tb-plain</guid>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_image_less_item_has_no_image_keys() -> None:
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_NO_IMAGE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    image_keys = {"image_url", "image_width", "image_height", "image_mime", "image_credit"}
    assert not image_keys & set(items[0].raw_metadata.keys())


# ---------------------------------------------------------------------------
# AC-7.2 — HTML in title is stripped
# ---------------------------------------------------------------------------


_SYNTH_HTML_IN_TITLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel><title>Synthetic</title>
    <item>
      <title><![CDATA[<b>BTC rallies</b>]]></title>
      <link>https://www.theblock.co/post/1?utm_source=rss&amp;utm_medium=rss</link>
      <guid>tb-1</guid>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
      <description><![CDATA[short body]]></description>
    </item>
  </channel>
</rss>
"""


async def test_html_in_title_is_stripped() -> None:
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_HTML_IN_TITLE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "BTC rallies"
    # And the utm params got stripped end-to-end.
    assert str(items[0].url) == "https://www.theblock.co/post/1"


# ---------------------------------------------------------------------------
# AC-7.3 — non-http/https schemes dropped
# ---------------------------------------------------------------------------


_SYNTH_BAD_URL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel><title>Synthetic</title>
    <item>
      <title>Good entry</title>
      <link>https://www.theblock.co/post/good?utm_source=rss</link>
      <guid>tb-good</guid>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
    </item>
    <item>
      <title>file URL entry</title>
      <link>file:///etc/passwd</link>
      <guid>tb-file</guid>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
    </item>
    <item>
      <title>javascript URL entry</title>
      <link>javascript:alert(1)</link>
      <guid>tb-js</guid>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_non_http_https_urls_dropped() -> None:
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_BAD_URL) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Good entry"
    assert str(items[0].url) == "https://www.theblock.co/post/good"


# ---------------------------------------------------------------------------
# Missing <dc:creator> → key OMITTED (NOT empty string)
# Missing <category> → "categories" key OMITTED
# ---------------------------------------------------------------------------


_SYNTH_MIXED_CREATOR_AND_CATEGORIES = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel><title>Synthetic</title>
    <item>
      <title>With creator and categories</title>
      <link>https://www.theblock.co/post/a</link>
      <guid>tb-a</guid>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
      <dc:creator>Reporter A</dc:creator>
      <category><![CDATA[Markets]]></category>
      <category><![CDATA[DeFi]]></category>
      <category><![CDATA[Bitcoin]]></category>
    </item>
    <item>
      <title>Without creator nor categories</title>
      <link>https://www.theblock.co/post/b</link>
      <guid>tb-b</guid>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_missing_creator_key_is_omitted_not_empty_string() -> None:
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_MIXED_CREATOR_AND_CATEGORIES) as client:
        items = await adapter.fetch(client, window)

    by_title = {item.title: item for item in items}
    assert set(by_title.keys()) == {
        "With creator and categories",
        "Without creator nor categories",
    }

    with_creator = by_title["With creator and categories"]
    assert with_creator.raw_metadata.get("creator") == "Reporter A"

    without_creator = by_title["Without creator nor categories"]
    # The key MUST be absent — not an empty string. Per FD L6.8.
    assert "creator" not in without_creator.raw_metadata


async def test_categories_comma_joined_when_multiple_omitted_when_zero() -> None:
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_MIXED_CREATOR_AND_CATEGORIES) as client:
        items = await adapter.fetch(client, window)

    by_title = {item.title: item for item in items}
    with_cats = by_title["With creator and categories"]
    assert with_cats.raw_metadata.get("categories") == "Markets,DeFi,Bitcoin"

    without_cats = by_title["Without creator nor categories"]
    # The key MUST be absent — not an empty string. Per FD L6.8.
    assert "categories" not in without_cats.raw_metadata


# ---------------------------------------------------------------------------
# <content:encoded> is IGNORED — only <description> is consumed
# ---------------------------------------------------------------------------


_SYNTH_CONTENT_ENCODED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel><title>Synthetic</title>
    <item>
      <title>Both desc and content:encoded</title>
      <link>https://www.theblock.co/post/c</link>
      <guid>tb-c</guid>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
      <description><![CDATA[Short body]]></description>
      <content:encoded><![CDATA[Long body that the adapter MUST IGNORE entirely]]></content:encoded>
    </item>
  </channel>
</rss>
"""


async def test_content_encoded_is_ignored_description_used() -> None:
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_CONTENT_ENCODED) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].summary == "Short body"
    assert items[0].summary != "Long body that the adapter MUST IGNORE entirely"


# ---------------------------------------------------------------------------
# Summary truncation at 280 chars
# ---------------------------------------------------------------------------


def _long_description_xml() -> bytes:
    long_text = "x" * 400  # 400-char ASCII description
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0">'
        "<channel><title>Synthetic</title>"
        "<item>"
        "<title>Long body</title>"
        "<link>https://www.theblock.co/post/long</link>"
        "<guid>tb-long</guid>"
        "<pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>"
        f"<description><![CDATA[{long_text}]]></description>"
        "</item>"
        "</channel></rss>"
    )
    return body.encode("utf-8")


async def test_summary_is_truncated_to_280_chars() -> None:
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_long_description_xml()) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    summary = items[0].summary
    assert summary is not None
    assert len(summary) == 280
    assert summary == "x" * 280


# ---------------------------------------------------------------------------
# Edge cases: naive pubDate, missing fields, empty channel, malformed XML
# ---------------------------------------------------------------------------


async def test_naive_or_garbage_pubdate_is_dropped() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Naive RFC-822 (no offset)</title>
      <link>https://www.theblock.co/post/x</link>
      <pubDate>Fri, 01 May 2026 10:00:00</pubDate>
      <guid>tb-x</guid>
    </item>
    <item>
      <title>Wholly unparseable pubDate</title>
      <link>https://www.theblock.co/post/y</link>
      <pubDate>not a date at all</pubDate>
      <guid>tb-y</guid>
    </item>
  </channel>
</rss>
"""
    adapter = TheBlockCryptoAdapter()
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
      <link>https://www.theblock.co/post/x</link>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
    </item>
    <item>
      <title>Missing pubDate</title>
      <link>https://www.theblock.co/post/y</link>
    </item>
    <item>
      <link>https://www.theblock.co/post/z</link>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
    </item>
    <item>
      <title>Missing link</title>
      <pubDate>Fri, 01 May 2026 10:00:00 -0400</pubDate>
    </item>
  </channel>
</rss>
"""
    adapter = TheBlockCryptoAdapter()
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
    adapter = TheBlockCryptoAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = TheBlockCryptoAdapter()
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
    assert TheBlockCryptoAdapter.name == "theblock-crypto"
    assert TheBlockCryptoAdapter.category == "news"
    assert TheBlockCryptoAdapter._FEED_URL == "https://www.theblock.co/rss.xml"
