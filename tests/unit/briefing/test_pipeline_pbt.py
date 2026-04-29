"""Property-based tests for ``briefing.pipeline`` (AC-6.2, AC-6.3, AC-6.6).

Both properties run with hypothesis ≥100 examples per the NFR scope
(AC-6.6 — every PBT in this unit reaches at least 100 examples).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from investo.briefing.pipeline import (
    parse_six_sections,
    serialize_items_for_prompt,
)
from investo.briefing.prompts import STAGE2_SECTION_HEADERS
from investo.models import NormalizedItem

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_CATEGORY = st.sampled_from(["news", "price", "macro", "calendar", "earnings"])

# Title/source/summary strategies. Source uses a printable-ASCII alphabet
# to avoid exotic whitespace + unicode normalization complications. Title
# allows broader text but is prefixed so the result is non-blank after
# strip (matches NormalizedItem._reject_blank).
_PRINTABLE = st.characters(
    min_codepoint=0x21,
    max_codepoint=0x7E,
    blacklist_categories=("Cs",),
)
_SOURCE_NAME = st.builds(
    lambda tail: "src-" + tail,
    st.text(alphabet=_PRINTABLE, min_size=0, max_size=20),
)
_TITLE = st.builds(
    lambda tail: "t-" + tail,
    st.text(min_size=0, max_size=30),
)
_SUMMARY = st.one_of(st.none(), st.text(min_size=1, max_size=60))
_URL = st.one_of(st.none(), st.just("https://example.com/a"))
_PUBLISHED_AT = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(UTC),
)


@st.composite
def _normalized_items(draw: st.DrawFn) -> NormalizedItem:
    return NormalizedItem(
        source_name=draw(_SOURCE_NAME),
        category=draw(_CATEGORY),
        title=draw(_TITLE),
        summary=draw(_SUMMARY),
        url=draw(_URL),  # type: ignore[arg-type]
        published_at=draw(_PUBLISHED_AT),
    )


def _section_safe(text: str) -> bool:
    """Reject text that would confuse ``parse_six_sections``.

    A body must not contain any of the six fixed Stage 2 section header
    strings, otherwise the parser would treat the substring as a real
    header start. We do NOT need to forbid `## ` generically — only the
    six exact headers (`## ① 요약`, `## ② ...`, ...) are search anchors.
    """
    if text.strip() == "":
        return False
    return not any(h in text for h in STAGE2_SECTION_HEADERS)


_BODY = st.text(min_size=1, max_size=100).filter(_section_safe)


# ---------------------------------------------------------------------------
# AC-6.2 — serialize_items_for_prompt round-trip
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(items=st.lists(_normalized_items(), max_size=10))
def test_serialize_round_trip_yields_list_of_dicts_with_expected_shape(
    items: list[NormalizedItem],
) -> None:
    """AC-6.2 — ``json.loads(serialize(items))`` is a list of objects
    whose key set is exactly ``{id, category, source, title, summary,
    url, ts}`` and whose length matches the input.

    ``raw_metadata`` is provenance noise; it must NEVER appear in the
    serialized payload regardless of what the source adapter put there.
    """
    serialized = serialize_items_for_prompt(items)
    parsed = json.loads(serialized)

    assert isinstance(parsed, list)
    assert len(parsed) == len(items)
    for obj in parsed:
        assert isinstance(obj, dict)
        assert set(obj.keys()) == {
            "id",
            "category",
            "source",
            "title",
            "summary",
            "url",
            "ts",
        }
        assert "raw_metadata" not in obj


@settings(max_examples=100)
@given(items=st.lists(_normalized_items(), max_size=10))
def test_serialize_round_trip_collapses_none_summary_and_url_to_empty(
    items: list[NormalizedItem],
) -> None:
    """AC-6.2 — when ``original.summary is None`` (or summary was
    whitespace-only and pydantic normalized it to None), the serialized
    object emits ``""`` for ``summary``. Same for ``url``.

    This is the prompt-stability rule from FD R7: the LLM sees a
    deterministic shape regardless of how the upstream adapter encoded
    the absent value.
    """
    serialized = serialize_items_for_prompt(items)
    parsed = json.loads(serialized)
    for original, obj in zip(items, parsed, strict=True):
        if original.summary is None:
            assert obj["summary"] == ""
        else:
            assert obj["summary"] == original.summary
        if original.url is None:
            assert obj["url"] == ""
        else:
            assert obj["url"] == str(original.url)


@settings(max_examples=100)
@given(items=st.lists(_normalized_items(), min_size=1, max_size=10))
def test_serialize_assigns_dense_ids_starting_at_one(
    items: list[NormalizedItem],
) -> None:
    """AC-6.2 — synthetic ``id`` is always ``1..len(items)``, dense and
    in input order. Locks the contract Stage 1's classifier sees.
    """
    parsed = json.loads(serialize_items_for_prompt(items))
    assert [obj["id"] for obj in parsed] == list(range(1, len(items) + 1))


# ---------------------------------------------------------------------------
# AC-6.3 — parse_six_sections round-trip
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(bodies=st.tuples(_BODY, _BODY, _BODY, _BODY, _BODY, _BODY))
def test_parse_six_sections_round_trips_arbitrary_non_blank_bodies(
    bodies: tuple[str, str, str, str, str, str],
) -> None:
    """AC-6.3 — for synthetic markdown built by joining six non-blank
    bodies under the fixed headers, ``parse_six_sections`` returns each
    body's whitespace-stripped form in order.

    The hypothesis generator guarantees no body contains any of the six
    section header strings, so the parser's first-occurrence search per
    header always lands on the constructed boundary.
    """
    parts: list[str] = []
    for header, body in zip(STAGE2_SECTION_HEADERS, bodies, strict=True):
        parts.append(f"{header}\n{body}")
    markdown = "\n\n".join(parts) + "\n"

    parsed = parse_six_sections(markdown)

    assert parsed == tuple(body.strip() for body in bodies)


@settings(max_examples=100)
@given(bodies=st.tuples(_BODY, _BODY, _BODY, _BODY, _BODY, _BODY))
def test_parse_six_sections_returns_six_non_blank_bodies(
    bodies: tuple[str, str, str, str, str, str],
) -> None:
    """Companion canary: the parser's contract guarantees the result
    has exactly 6 entries and each is non-blank. Pinning this here
    means a regression that, say, returns 7 entries or empty strings
    breaks immediately rather than only at the integration boundary.
    """
    parts = [
        f"{header}\n{body}" for header, body in zip(STAGE2_SECTION_HEADERS, bodies, strict=True)
    ]
    markdown = "\n\n".join(parts) + "\n"

    parsed = parse_six_sections(markdown)

    assert len(parsed) == 6
    for body in parsed:
        assert body.strip() != ""
