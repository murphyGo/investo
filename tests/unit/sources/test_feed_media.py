"""Unit tests for ``investo.sources._feed_media``.

Pins u136 Fixed Contract #2 (Step 1 matrix): media:content only /
media:thumbnail only / both present (content wins) / multiple images
(first only) / non-http URL rejected / URL length cap / non-integer
width·height / credit cap / non-image media:content (mime=video)
skipped. Sample fragments mirror the three verified live feeds
(2026-07-17 probe): Yonhap 마켓+, Yahoo Finance rssindex, The Block.

Step 3 additions: the extension-less zenfs-CDN shape (no ``type`` attr,
image evidence = positive width+height pair — ratified divergence, see
the ``_feed_media`` module docstring) and the :func:`image_metadata`
Contract #3 key mapper.

XML fragments are parsed via ``defusedxml`` (never stdlib ElementTree
— NFR-007 AC-7.6); the parsed element is typed ``Any`` for the same
grep-guard reason as the adapters.
"""

from __future__ import annotations

from typing import Any

from defusedxml.ElementTree import fromstring

from investo.sources._feed_media import FeedImageRef, extract_feed_image, image_metadata

_MRSS = "http://search.yahoo.com/mrss/"


def _item(inner_xml: str) -> Any:
    """Parse an ``<item>`` fragment with the Media RSS namespace bound."""

    return fromstring(f'<item xmlns:media="{_MRSS}">{inner_xml}</item>')


# --- real-feed-shaped happy paths -----------------------------------------


def test_yonhap_style_media_content_only() -> None:
    # Yonhap 마켓+: <media:content url=… type="image/jpeg"> without
    # width/height/credit.
    item = _item(
        "<title>코스피 급등</title>"
        '<media:content url="https://img.yna.co.kr/photo/reuters/2026/07/17/PRU001.jpg"'
        ' type="image/jpeg"/>'
    )
    assert extract_feed_image(item) == FeedImageRef(
        url="https://img.yna.co.kr/photo/reuters/2026/07/17/PRU001.jpg",
        width=None,
        height=None,
        mime="image/jpeg",
        credit=None,
    )


def test_yahoo_style_content_with_dimensions_and_item_level_credit() -> None:
    # Yahoo rssindex: no `type` attr, width/height attrs, item-level
    # <media:credit role="publishing company">.
    item = _item(
        '<media:content url="https://s.yimg.com/uu/api/res/1.2/abc/thumb.jpg"'
        ' width="130" height="86"/>'
        '<media:credit role="publishing company">Reuters</media:credit>'
    )
    assert extract_feed_image(item) == FeedImageRef(
        url="https://s.yimg.com/uu/api/res/1.2/abc/thumb.jpg",
        width=130,
        height=86,
        mime=None,
        credit="Reuters",
    )


def test_theblock_style_media_thumbnail_only() -> None:
    # The Block: <media:thumbnail url=… width="800" height="450">, no
    # <media:content> at all.
    item = _item(
        '<media:thumbnail url="https://www.tbstat.com/wp/uploads/2026/07/btc.jpg"'
        ' width="800" height="450"/>'
    )
    assert extract_feed_image(item) == FeedImageRef(
        url="https://www.tbstat.com/wp/uploads/2026/07/btc.jpg",
        width=800,
        height=450,
        mime=None,
        credit=None,
    )


# --- preference / ordering -------------------------------------------------


def test_content_preferred_over_thumbnail_when_both_present() -> None:
    item = _item(
        '<media:thumbnail url="https://cdn.example.com/small.jpg" width="130" height="86"/>'
        '<media:content url="https://cdn.example.com/full.jpg" type="image/jpeg"/>'
    )
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == "https://cdn.example.com/full.jpg"
    assert ref.mime == "image/jpeg"


def test_multiple_image_contents_first_in_document_order_wins() -> None:
    item = _item(
        '<media:content url="https://cdn.example.com/first.jpg" type="image/jpeg"/>'
        '<media:content url="https://cdn.example.com/second.png" type="image/png"/>'
    )
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == "https://cdn.example.com/first.jpg"


def test_non_image_content_skipped_falls_through_to_thumbnail() -> None:
    # mime=video/mp4 must not shadow a usable thumbnail.
    item = _item(
        '<media:content url="https://cdn.example.com/clip.mp4" type="video/mp4"/>'
        '<media:thumbnail url="https://cdn.example.com/poster.jpg" width="800" height="450"/>'
    )
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == "https://cdn.example.com/poster.jpg"
    assert (ref.width, ref.height) == (800, 450)


def test_non_image_content_without_thumbnail_returns_none() -> None:
    item = _item('<media:content url="https://cdn.example.com/clip.mp4" type="video/mp4"/>')
    assert extract_feed_image(item) is None


def test_invalid_first_content_url_falls_through_to_next_candidate() -> None:
    item = _item(
        '<media:content url="ftp://cdn.example.com/a.jpg" type="image/jpeg"/>'
        '<media:content url="https://cdn.example.com/b.jpg" type="image/jpeg"/>'
    )
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == "https://cdn.example.com/b.jpg"


# --- mime-absent extension gate ---------------------------------------------


def test_typeless_content_with_image_extension_accepted() -> None:
    item = _item('<media:content url="https://cdn.example.com/chart.png"/>')
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == "https://cdn.example.com/chart.png"
    assert ref.mime is None


def test_typeless_content_without_image_extension_rejected() -> None:
    item = _item('<media:content url="https://cdn.example.com/article"/>')
    assert extract_feed_image(item) is None


def test_typeless_extensionless_content_with_dimensions_accepted() -> None:
    # Yahoo Finance zenfs shape: extension-less content-hash URL, no
    # `type` attr — the positive width+height pair is the image
    # evidence (2026-07-16 live recording).
    item = _item(
        '<media:content height="86" url="https://media.zenfs.com/en/reuters.com/9a576b76"'
        ' width="130"/>'
    )
    assert extract_feed_image(item) == FeedImageRef(
        url="https://media.zenfs.com/en/reuters.com/9a576b76",
        width=130,
        height=86,
        mime=None,
        credit=None,
    )


def test_typeless_extensionless_content_with_partial_dimensions_rejected() -> None:
    # Width alone (or a non-positive pair) is not image evidence.
    item = _item('<media:content url="https://cdn.example.com/hash" width="130"/>')
    assert extract_feed_image(item) is None
    item = _item('<media:content url="https://cdn.example.com/hash" width="130" height="0"/>')
    assert extract_feed_image(item) is None


def test_extension_check_ignores_query_string() -> None:
    # urlparse strips the query before the suffix test.
    item = _item('<media:content url="https://cdn.example.com/pic.jpg?w=1200&amp;q=80"/>')
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == "https://cdn.example.com/pic.jpg?w=1200&q=80"


# --- URL validation ----------------------------------------------------------


def test_non_http_url_rejected() -> None:
    item = _item('<media:content url="ftp://cdn.example.com/pic.jpg" type="image/jpeg"/>')
    assert extract_feed_image(item) is None


def test_javascript_scheme_rejected() -> None:
    item = _item('<media:content url="javascript:alert(\'x\')" type="image/jpeg"/>')
    assert extract_feed_image(item) is None


def test_url_whitespace_trimmed() -> None:
    item = _item('<media:content url="  https://cdn.example.com/pic.jpg  " type="image/jpeg"/>')
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == "https://cdn.example.com/pic.jpg"


def test_url_over_1000_chars_rejected() -> None:
    long_url = "https://cdn.example.com/" + "a" * 1000 + ".jpg"
    assert len(long_url) > 1000
    item = _item(f'<media:content url="{long_url}" type="image/jpeg"/>')
    assert extract_feed_image(item) is None


def test_url_at_exactly_1000_chars_accepted() -> None:
    prefix = "https://cdn.example.com/"
    url = prefix + "a" * (1000 - len(prefix) - 4) + ".jpg"
    assert len(url) == 1000
    item = _item(f'<media:content url="{url}" type="image/jpeg"/>')
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == url


def test_missing_url_attribute_returns_none() -> None:
    item = _item('<media:content type="image/jpeg"/>')
    assert extract_feed_image(item) is None


def test_item_without_media_elements_returns_none() -> None:
    item = _item("<title>이미지 없는 기사</title><link>https://example.com/a</link>")
    assert extract_feed_image(item) is None


# --- width / height parsing ---------------------------------------------------


def test_non_integer_dimensions_degrade_to_none_url_kept() -> None:
    item = _item(
        '<media:content url="https://cdn.example.com/pic.jpg" type="image/jpeg"'
        ' width="abc" height=""/>'
    )
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.url == "https://cdn.example.com/pic.jpg"
    assert ref.width is None
    assert ref.height is None


def test_non_positive_dimensions_degrade_to_none() -> None:
    item = _item('<media:thumbnail url="https://cdn.example.com/pic.jpg" width="0" height="-450"/>')
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.width is None
    assert ref.height is None


# --- credit -------------------------------------------------------------------


def test_credit_trimmed_and_capped_at_240_chars() -> None:
    long_credit = "x" * 300
    item = _item(
        '<media:content url="https://cdn.example.com/pic.jpg" type="image/jpeg"/>'
        f"<media:credit>  {long_credit}  </media:credit>"
    )
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.credit == "x" * 240


def test_credit_nested_in_media_content_preferred_over_item_level() -> None:
    item = _item(
        '<media:content url="https://cdn.example.com/pic.jpg" type="image/jpeg">'
        "<media:credit>AFP</media:credit>"
        "</media:content>"
        "<media:credit>Yahoo</media:credit>"
    )
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.credit == "AFP"


def test_whitespace_only_credit_becomes_none() -> None:
    item = _item(
        '<media:content url="https://cdn.example.com/pic.jpg" type="image/jpeg"/>'
        "<media:credit>   </media:credit>"
    )
    ref = extract_feed_image(item)
    assert ref is not None
    assert ref.credit is None


# --- image_metadata — Contract #3 key mapper ---------------------------------


def test_image_metadata_full_ref_emits_all_five_keys() -> None:
    ref = FeedImageRef(
        url="https://cdn.example.com/pic.jpg",
        width=800,
        height=450,
        mime="image/jpeg",
        credit="Reuters",
    )
    assert image_metadata(ref) == {
        "image_url": "https://cdn.example.com/pic.jpg",
        "image_width": 800,
        "image_height": 450,
        "image_mime": "image/jpeg",
        "image_credit": "Reuters",
    }


def test_image_metadata_minimal_ref_emits_only_image_url() -> None:
    # Absent field = absent key — never None / empty values (R8).
    ref = FeedImageRef(
        url="https://cdn.example.com/pic.jpg",
        width=None,
        height=None,
        mime=None,
        credit=None,
    )
    assert image_metadata(ref) == {"image_url": "https://cdn.example.com/pic.jpg"}


def test_image_metadata_never_emits_license_family_keys() -> None:
    # Contract #4 safety invariant at the mapper level: whatever the
    # ref carries, only image_* presentation keys come out — no
    # license / attribution / author / allowed_use (or visual_image_*)
    # keys that could arm the dormant external-image fetch path.
    ref = FeedImageRef(
        url="https://cdn.example.com/pic.jpg",
        width=1,
        height=1,
        mime="image/png",
        credit="AFP",
    )
    keys = set(image_metadata(ref).keys())
    assert keys == {"image_url", "image_width", "image_height", "image_mime", "image_credit"}
    assert not any(key.startswith("visual_image_") for key in keys)
    assert not keys & {"image_license", "image_attribution", "image_author", "image_allowed_use"}
