"""Tests for ``investo.sources._sanitize.strip_html``.

Pins NFR-007 AC-7.2 behavior: feed-derived HTML in titles and summaries
must be reduced to plain text before being stored on
:class:`investo.models.NormalizedItem`.
"""

from __future__ import annotations

from investo.sources._sanitize import strip_html

# ---------------------------------------------------------------------------
# Empty / whitespace input
# ---------------------------------------------------------------------------


def test_empty_string_returns_empty() -> None:
    assert strip_html("") == ""


def test_whitespace_only_returns_empty() -> None:
    assert strip_html("   \n\t  ") == ""


# ---------------------------------------------------------------------------
# Plain text passthrough
# ---------------------------------------------------------------------------


def test_plain_text_passes_through() -> None:
    assert strip_html("Hello, world.") == "Hello, world."


# ---------------------------------------------------------------------------
# Tag stripping (AC-7.2 core)
# ---------------------------------------------------------------------------


def test_simple_tag_stripped_keeps_content() -> None:
    assert strip_html("<b>title</b>") == "title"


def test_nested_tags_stripped_keeps_content() -> None:
    assert strip_html("<p>Hello <b>world</b>!</p>") == "Hello world!"


def test_self_closing_tag_stripped() -> None:
    # bleach strips <br/> without inserting whitespace.
    assert strip_html("a<br/>b") == "ab"
    assert strip_html("a<br>b") == "ab"


def test_attributes_stripped_with_tag() -> None:
    # The `javascript:` URL is harmless once the <a> wrapper is gone.
    assert strip_html('<a href="javascript:alert(1)">click</a>') == "click"


def test_html_comment_stripped() -> None:
    assert strip_html("Hello<!-- a comment -->World") == "HelloWorld"


def test_script_tag_content_neutralized() -> None:
    # bleach with tags=[], strip=True drops the <script> wrapper but
    # keeps the inner text — the result contains no `<` / `>` so
    # cannot be re-parsed as HTML by any downstream renderer.
    result = strip_html("<script>alert(1)</script>")
    assert "<" not in result
    assert ">" not in result
    assert result == "alert(1)"


def test_style_tag_content_neutralized() -> None:
    result = strip_html("<style>body{}</style>")
    assert "<" not in result
    assert result == "body{}"


# ---------------------------------------------------------------------------
# Entity decoding
# ---------------------------------------------------------------------------


def test_named_entity_amp_decoded() -> None:
    assert strip_html("Tom &amp; Jerry") == "Tom & Jerry"


def test_named_entity_lt_gt_decoded() -> None:
    # Already-escaped angle brackets become literal — useful for items
    # whose source already pre-escaped untrusted content.
    assert strip_html("&lt;tag&gt;") == "<tag>"


def test_numeric_entity_decoded() -> None:
    assert strip_html("&#39;quoted&#39;") == "'quoted'"


def test_double_escaped_entity_decoded_once() -> None:
    # html.unescape is single-level — a doubly-escaped string decodes
    # one layer only. This matches conventional HTML entity semantics.
    assert strip_html("&amp;amp;") == "&amp;"


# ---------------------------------------------------------------------------
# Unicode preservation (R8: NormalizedItem fields are str)
# ---------------------------------------------------------------------------


def test_unicode_korean_preserved() -> None:
    assert strip_html("<p>안녕하세요</p>") == "안녕하세요"


def test_unicode_emoji_preserved() -> None:
    assert strip_html("<p>Hello 🎉 world</p>") == "Hello 🎉 world"


def test_mixed_unicode_with_html_entity() -> None:
    assert strip_html("한글 &amp; 한자") == "한글 & 한자"


# ---------------------------------------------------------------------------
# Whitespace normalization
# ---------------------------------------------------------------------------


def test_collapse_internal_spaces() -> None:
    assert strip_html("hello    world") == "hello world"


def test_collapse_newlines() -> None:
    assert strip_html("hello\n\nworld") == "hello world"


def test_collapse_tabs() -> None:
    assert strip_html("hello\tworld") == "hello world"


def test_strip_outer_whitespace() -> None:
    assert strip_html("  hello world  ") == "hello world"


# ---------------------------------------------------------------------------
# Lone metacharacters
# ---------------------------------------------------------------------------


def test_lone_angle_bracket_preserved() -> None:
    # bleach escapes a lone `<` to `&lt;`; html.unescape turns it back.
    # The result is a literal `<` — acceptable since AC-7.2 is about
    # neutralizing markup, not stripping every character that *looks*
    # like markup.
    assert strip_html("<") == "<"
    assert strip_html("<<") == "<<"


def test_comparison_expression_preserved() -> None:
    # Realistic adapter input: a price comparison or math expression
    # using `<` should round-trip as text, not be eaten by the parser.
    assert strip_html("price < 100") == "price < 100"
    assert strip_html("a < b > c") == "a < b > c"


# ---------------------------------------------------------------------------
# Idempotence (sanitize twice = sanitize once)
# ---------------------------------------------------------------------------


def test_idempotent_on_clean_input() -> None:
    text = "Tom & Jerry — 안녕"
    assert strip_html(strip_html(text)) == strip_html(text)


def test_idempotent_on_dirty_input() -> None:
    once = strip_html("<b>Tom</b> &amp; <i>Jerry</i>")
    twice = strip_html(once)
    assert once == twice == "Tom & Jerry"
