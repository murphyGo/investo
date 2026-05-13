"""Anchor tests for the pure helpers in ``briefing.pipeline``.

Covered helpers:

* ``serialize_items_for_prompt`` (FD R7) — Stage 1 prompt-side JSON.
* ``_parse_classification`` — Stage 1 stdout → ``ClassificationResult``.
* ``build_section_plan`` (FD E3, L1.5) — group items into Stage 2 buckets.
* ``parse_six_sections`` (FD L3 / R1) — split Stage 2 markdown.

PBT round-trips for ``serialize_items_for_prompt`` (AC-6.2) and
``parse_six_sections`` (AC-6.3) live in ``test_pipeline_pbt.py``.
Failure-contract / budget / sentinel-grep tests live in their own files.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from investo.briefing.pipeline import (
    ClassificationResult,
    SectionPlan,
    _parse_classification,
    _render_grouped_sections,
    _render_unassigned,
    _select_llm_candidate_items,
    build_section_plan,
    parse_six_sections,
    serialize_items_for_prompt,
)
from investo.models import NormalizedItem

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _item(
    *,
    source_name: str = "test-source",
    category: str = "news",
    title: str = "title",
    summary: str | None = None,
    url: str | None = None,
    published_at: datetime | None = None,
) -> NormalizedItem:
    """Build a NormalizedItem with sensible test defaults.

    All fields are overridable; ``published_at`` defaults to a fixed UTC
    instant so id ordering in tests is deterministic.
    """
    if published_at is None:
        published_at = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    return NormalizedItem(
        source_name=source_name,
        category=category,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        url=url,  # type: ignore[arg-type]
        published_at=published_at,
    )


# ---------------------------------------------------------------------------
# serialize_items_for_prompt (FD R7)
# ---------------------------------------------------------------------------


def test_serialize_empty_items_returns_empty_json_array() -> None:
    """Empty input → ``"[]"`` (the JSON empty-array literal)."""
    assert serialize_items_for_prompt([]) == "[]"


def test_serialize_single_item_has_expected_key_set() -> None:
    """Each serialized object exposes exactly the FD R7 contract keys."""
    item = _item(
        source_name="acme",
        category="news",
        title="hello",
        summary="brief",
        url="https://example.com/a",
    )
    payload = json.loads(serialize_items_for_prompt([item]))

    assert isinstance(payload, list) and len(payload) == 1
    assert set(payload[0].keys()) == {
        "id",
        "category",
        "source",
        "title",
        "summary",
        "url",
        "ts",
    }
    assert "raw_metadata" not in payload[0]


def test_serialize_assigns_synthetic_ids_starting_at_one() -> None:
    """Synthetic ``id`` is ``enumerate(items, start=1)`` and not from input."""
    items = [
        _item(title="first"),
        _item(title="second"),
        _item(title="third"),
    ]
    payload = json.loads(serialize_items_for_prompt(items))

    assert [obj["id"] for obj in payload] == [1, 2, 3]


def test_serialize_collapses_none_summary_and_url_to_empty_string() -> None:
    """``None`` summary/url → ``""`` for prompt stability."""
    item = _item(summary=None, url=None)
    payload = json.loads(serialize_items_for_prompt([item]))

    assert payload[0]["summary"] == ""
    assert payload[0]["url"] == ""


def test_serialize_renders_published_at_as_utc_isoformat() -> None:
    """``ts`` is RFC 3339 UTC even for non-UTC source timestamps.

    KST = UTC+9. A source emitting KST midnight should serialize as the
    prior day's UTC 15:00. Pinning this rules out timezone drift.
    """
    plus_nine = timezone(timedelta(hours=9))
    item = _item(published_at=datetime(2026, 4, 26, 0, 0, tzinfo=plus_nine))

    payload = json.loads(serialize_items_for_prompt([item]))

    assert payload[0]["ts"] == "2026-04-25T15:00:00+00:00"


def test_select_llm_candidate_items_caps_one_noisy_source() -> None:
    items = [
        _item(source_name="nasdaq-earnings-calendar", title=f"earnings-{idx}") for idx in range(30)
    ]
    items.append(_item(source_name="yahoo-finance-news", title="market news"))

    selected = _select_llm_candidate_items(items)

    assert len(selected) == 25
    assert [item.title for item in selected[:24]] == [f"earnings-{idx}" for idx in range(24)]
    assert selected[-1].source_name == "yahoo-finance-news"


def test_select_llm_candidate_items_caps_total_size() -> None:
    items = [
        _item(source_name=f"source-{source_idx}", title=f"{source_idx}-{item_idx}")
        for source_idx in range(10)
        for item_idx in range(24)
    ]

    selected = _select_llm_candidate_items(items)

    assert len(selected) == 96
    assert selected[-1].title == "3-23"


def test_serialize_byte_exact_snapshot_for_fixture_hash_stability() -> None:
    """Pin JSON bytes that feed FakeClaudeRunner prompt hashing."""
    plus_nine = timezone(timedelta(hours=9))
    item = _item(
        source_name="market-data",
        category="price",
        title="AAPL close",
        summary="Summary",
        url="https://example.com/a",
        published_at=datetime(2026, 4, 26, 0, 0, tzinfo=plus_nine),
    )

    serialized = serialize_items_for_prompt([item])

    assert serialized == (
        '[{"id": 1, "category": "price", "source": "market-data", '
        '"title": "AAPL close", "summary": "Summary", '
        '"url": "https://example.com/a", "ts": "2026-04-25T15:00:00+00:00"}]'
    )


def test_serialize_excludes_raw_metadata_provenance_bag() -> None:
    """``raw_metadata`` is provenance noise for the LLM — must be dropped."""
    item = NormalizedItem(
        source_name="rss",
        category="news",
        title="title",
        published_at=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
        raw_metadata={"adapter_version": "1.2.3", "feed_url": "https://x.example"},
    )
    serialized = serialize_items_for_prompt([item])

    assert "raw_metadata" not in serialized
    assert "adapter_version" not in serialized
    assert "feed_url" not in serialized


def test_serialize_preserves_korean_characters() -> None:
    """``ensure_ascii=False`` keeps Korean titles readable in the prompt."""
    item = _item(title="삼성전자 실적 발표")
    payload_str = serialize_items_for_prompt([item])

    # Raw substring should appear, not a ``\\uXXXX`` escape.
    assert "삼성전자 실적 발표" in payload_str


# ---------------------------------------------------------------------------
# _parse_classification
# ---------------------------------------------------------------------------


def test_parse_classification_happy_path() -> None:
    """Well-formed JSON → ``ClassificationResult`` with the expected ids."""
    stdout = json.dumps({"assignments": {"1": 4, "2": 4}, "unassigned": [3]})
    result = _parse_classification(stdout, item_count=3)

    assert isinstance(result, ClassificationResult)
    assert result.assignments == {1: 4, 2: 4}
    assert result.unassigned == [3]


def test_parse_classification_accepts_json_inside_markdown_fence() -> None:
    """Production LLM stdout may wrap the JSON object in a code fence."""
    stdout = """\
```json
{"assignments": {"1": 4}, "unassigned": [2]}
```
"""
    result = _parse_classification(stdout, item_count=2)

    assert result.assignments == {1: 4}
    assert result.unassigned == [2]


def test_parse_classification_accepts_json_with_surrounding_text() -> None:
    """Recover when the model adds prose around an otherwise valid object."""
    stdout = 'Here is the JSON:\n{"assignments": {"1": 2}, "unassigned": []}\nDone.'
    result = _parse_classification(stdout, item_count=1)

    assert result.assignments == {1: 2}
    assert result.unassigned == []


def test_parse_classification_accepts_python_literal_integer_keys() -> None:
    """Recover when Claude emits a Python-dict-like object."""
    stdout = '{"assignments":{1:5,2:2,3:4},"unassigned":[4]}'
    result = _parse_classification(stdout, item_count=4)

    assert result.assignments == {1: 5, 2: 2, 3: 4}
    assert result.unassigned == [4]


def test_parse_classification_empty_assignments_is_valid() -> None:
    """Empty assignments + empty unassigned is a valid (degenerate) result."""
    stdout = json.dumps({"assignments": {}, "unassigned": []})
    result = _parse_classification(stdout, item_count=0)

    assert result.assignments == {}
    assert result.unassigned == []


def test_parse_classification_rejects_invalid_section_id() -> None:
    """Section id outside ``{2, 3, 4, 5}`` triggers a ValidationError."""
    stdout = json.dumps({"assignments": {"1": 6}, "unassigned": []})
    with pytest.raises(ValidationError) as exc:
        _parse_classification(stdout, item_count=1)

    # The field validator raises ``ValueError`` which pydantic wraps.
    assert "{2, 3, 4, 5}" in str(exc.value)


def test_parse_classification_rejects_unknown_item_id() -> None:
    """Item id outside ``1..item_count`` triggers a plain ValueError."""
    stdout = json.dumps({"assignments": {"99": 4}, "unassigned": []})
    with pytest.raises(ValueError) as exc:
        _parse_classification(stdout, item_count=3)

    assert "outside 1..3" in str(exc.value)
    assert "99" in str(exc.value)


def test_parse_classification_rejects_unknown_unassigned_id() -> None:
    """Unassigned ids are also bounds-checked against ``1..item_count``."""
    stdout = json.dumps({"assignments": {}, "unassigned": [42]})
    with pytest.raises(ValueError) as exc:
        _parse_classification(stdout, item_count=3)

    assert "42" in str(exc.value)


def test_parse_classification_rejects_malformed_json() -> None:
    """Non-JSON stdout raises ``json.JSONDecodeError``; caller routes to retry."""
    with pytest.raises(json.JSONDecodeError):
        _parse_classification("not json at all", item_count=1)


def test_parse_classification_rejects_oversized_stdout_before_json_parse() -> None:
    """Oversized Stage 1 output is malformed before it reaches json.loads."""
    oversized = " " * (64 * 1024 + 1)
    with pytest.raises(ValueError, match="Stage 1 stdout exceeds"):
        _parse_classification(oversized, item_count=1)


def test_parse_classification_rejects_extra_keys() -> None:
    """``ConfigDict(extra="forbid")`` blocks unknown top-level keys."""
    stdout = json.dumps({"assignments": {"1": 4}, "unassigned": [], "extra_field": "boom"})
    with pytest.raises(ValidationError):
        _parse_classification(stdout, item_count=1)


# ---------------------------------------------------------------------------
# 2026-05-09 GHA postmortem — inverted-schema auto-recovery
# ---------------------------------------------------------------------------


def test_parse_classification_recovers_from_inverted_schema_str_keys() -> None:
    """LLM emits ``{<section_id_str>: [<item_ids>, ...]}`` instead of the
    spec'd ``{<item_id>: <section_id>}``. The auto-flip should rewrite
    the payload and let pydantic accept it.
    """
    stdout = json.dumps({"assignments": {"3": [9, 10, 11], "5": [2, 7]}, "unassigned": [1]})
    result = _parse_classification(stdout, item_count=11)

    assert isinstance(result, ClassificationResult)
    assert result.assignments == {9: 3, 10: 3, 11: 3, 2: 5, 7: 5}
    assert result.unassigned == [1]


def test_parse_classification_recovers_from_inverted_schema_int_keys() -> None:
    """Same inverted shape but emitted via Python-literal int keys
    (the ``ast.literal_eval`` recovery path).
    """
    stdout = "{'assignments': {3: [9, 10], 5: [2]}, 'unassigned': []}"
    result = _parse_classification(stdout, item_count=10)

    assert result.assignments == {9: 3, 10: 3, 2: 5}
    assert result.unassigned == []


def test_parse_classification_does_not_flip_when_item_id_appears_in_multiple_sections() -> None:
    """Ambiguous inversion (item 9 appears under both section 3 and
    section 5) must NOT be silently resolved. The original
    ValidationError surfaces so the caller's retry loop sees the real
    schema mismatch.
    """
    stdout = json.dumps({"assignments": {"3": [9, 10], "5": [9]}, "unassigned": []})
    with pytest.raises(ValidationError):
        _parse_classification(stdout, item_count=10)


def test_parse_classification_does_not_flip_when_keys_outside_2_5() -> None:
    """Auto-flip only kicks in when every key is a valid Stage 1
    section-id (``{2, 3, 4, 5}``). A payload with key=1 is treated as a
    regular (item-id-keyed) payload and the original validation error
    surfaces — list-shaped values for an item-id key are not the
    spec'd schema.
    """
    stdout = json.dumps({"assignments": {"1": [9]}, "unassigned": []})
    with pytest.raises(ValidationError):
        _parse_classification(stdout, item_count=9)


# ---------------------------------------------------------------------------
# build_section_plan (FD E3, L1.5)
# ---------------------------------------------------------------------------


def test_build_section_plan_groups_items_into_correct_buckets() -> None:
    """Items 1, 2, 3 → sections 2, 3, 4 → 3 buckets each with 1 item."""
    items = [_item(title=f"item-{i}") for i in range(3)]
    classification = ClassificationResult(assignments={1: 2, 2: 3, 3: 4}, unassigned=[])

    plan = build_section_plan(items, classification, target_date=date(2026, 4, 25))

    assert isinstance(plan, SectionPlan)
    assert plan.target_date == date(2026, 4, 25)
    assert plan.items_by_section[2] == (items[0],)
    assert plan.items_by_section[3] == (items[1],)
    assert plan.items_by_section[4] == (items[2],)
    assert plan.items_by_section[5] == ()
    assert plan.unassigned == ()


def test_build_section_plan_sorts_items_published_at_descending() -> None:
    """Within each bucket, newer items come first (FD L1.5 ordering)."""
    older = _item(title="older", published_at=datetime(2026, 4, 25, 9, 0, tzinfo=UTC))
    newer = _item(title="newer", published_at=datetime(2026, 4, 25, 18, 0, tzinfo=UTC))
    middle = _item(title="middle", published_at=datetime(2026, 4, 25, 12, 0, tzinfo=UTC))
    classification = ClassificationResult(assignments={1: 4, 2: 4, 3: 4}, unassigned=[])

    plan = build_section_plan([older, newer, middle], classification, target_date=date(2026, 4, 25))

    assert plan.items_by_section[4] == (newer, middle, older)


def test_build_section_plan_preserves_unassigned_items() -> None:
    """Unassigned ids carry through to the plan as ordered tuple."""
    items = [_item(title=f"item-{i}") for i in range(3)]
    classification = ClassificationResult(assignments={1: 2}, unassigned=[2, 3])

    plan = build_section_plan(items, classification, target_date=date(2026, 4, 25))

    assert plan.unassigned == (items[1], items[2])


def test_build_section_plan_returns_frozen_dataclass() -> None:
    """``SectionPlan`` is frozen — assignment must raise FrozenInstanceError."""
    from dataclasses import FrozenInstanceError

    plan = build_section_plan(
        [],
        ClassificationResult(assignments={}, unassigned=[]),
        target_date=date(2026, 4, 25),
    )
    with pytest.raises(FrozenInstanceError):
        plan.target_date = date(2026, 4, 26)  # type: ignore[misc]


def test_render_grouped_sections_includes_source_urls_for_citations() -> None:
    item = _item(
        source_name="nasdaq-stocks-news",
        title="S&P 500 sets record",
        summary="Major indexes advanced.",
        url="https://example.com/story",
    )

    rendered = _render_grouped_sections({2: (item,), 3: (), 4: (), 5: ()})

    assert "[nasdaq-stocks-news] S&P 500 sets record" in rendered
    assert "(https://example.com/story)" in rendered
    assert "Major indexes advanced." in rendered


def test_render_grouped_sections_caps_stage2_evidence_budget() -> None:
    items_by_section = {
        section: tuple(
            _item(
                source_name=f"src-{section}",
                title=f"section-{section}-item-{idx}",
                summary="x" * 400,
                url="https://example.com/" + ("a" * 220),
            )
            for idx in range(20)
        )
        for section in (2, 3, 4, 5)
    }

    rendered = _render_grouped_sections(items_by_section)

    assert rendered.count("  - [src-") == 48
    assert "section-2-item-13" in rendered
    assert "section-2-item-14" not in rendered
    assert "section-5-item-5" in rendered
    assert "section-5-item-6" not in rendered
    assert "(6 additional classified items omitted for prompt budget)" in rendered
    assert "(14 additional classified items omitted for prompt budget)" in rendered
    assert "x" * 300 not in rendered
    assert "a" * 200 not in rendered


def test_render_unassigned_caps_stage2_context_budget() -> None:
    items = tuple(_item(title=f"unassigned-{idx}") for idx in range(12))

    rendered = _render_unassigned(items)

    assert rendered.count("  - [test-source]") == 8
    assert "unassigned-7" in rendered
    assert "unassigned-8" not in rendered
    assert "(4 additional unassigned items omitted for prompt budget)" in rendered


# ---------------------------------------------------------------------------
# parse_six_sections (FD L3 / R1)
# ---------------------------------------------------------------------------


_VALID_SIX_SECTION_MARKDOWN = (
    "## ① 요약\n오늘 시장 요약\n\n"
    "## ② 전일 핵심 이슈\n핵심 이슈 본문\n\n"
    "## ③ 섹터/수급 동향\n섹터 본문\n\n"
    "## ④ 지표·이벤트\n지표 본문\n\n"
    "## ⑤ 주요 종목\n종목 본문\n\n"
    "## ⑥ 오늘의 관전 포인트\n관전 포인트 본문\n"
)


def test_parse_six_sections_happy_path_returns_six_bodies_in_order() -> None:
    """Well-formed markdown → six body strings in section order."""
    bodies = parse_six_sections(_VALID_SIX_SECTION_MARKDOWN)

    assert bodies == (
        "오늘 시장 요약",
        "핵심 이슈 본문",
        "섹터 본문",
        "지표 본문",
        "종목 본문",
        "관전 포인트 본문",
    )


def test_parse_six_sections_returns_tuple_of_exactly_six() -> None:
    """Return type contract: 6-tuple of str."""
    bodies = parse_six_sections(_VALID_SIX_SECTION_MARKDOWN)
    assert isinstance(bodies, tuple)
    assert len(bodies) == 6
    assert all(isinstance(body, str) for body in bodies)


def test_parse_six_sections_rejects_missing_header() -> None:
    """Removing section ④ → ``ValueError`` naming the missing header."""
    markdown = _VALID_SIX_SECTION_MARKDOWN.replace("## ④ 지표·이벤트\n지표 본문\n\n", "")
    with pytest.raises(ValueError) as exc:
        parse_six_sections(markdown)
    assert "## ④ 지표·이벤트" in str(exc.value)


def test_parse_six_sections_rejects_blank_body() -> None:
    """Section header present but empty body → ``ValueError``."""
    markdown = _VALID_SIX_SECTION_MARKDOWN.replace(
        "## ④ 지표·이벤트\n지표 본문\n\n", "## ④ 지표·이벤트\n\n"
    )
    with pytest.raises(ValueError) as exc:
        parse_six_sections(markdown)
    assert "## ④ 지표·이벤트" in str(exc.value)
    assert "blank" in str(exc.value)


def test_parse_six_sections_rejects_whitespace_only_body() -> None:
    """Whitespace-only body counts as blank (strip() → "" → reject)."""
    markdown = _VALID_SIX_SECTION_MARKDOWN.replace(
        "## ⑤ 주요 종목\n종목 본문\n\n", "## ⑤ 주요 종목\n   \t  \n\n"
    )
    with pytest.raises(ValueError) as exc:
        parse_six_sections(markdown)
    assert "blank" in str(exc.value)


def test_parse_six_sections_rejects_headers_in_wrong_order() -> None:
    """Headers present but out of canonical order → ``ValueError``."""
    # Swap sections ② and ③.
    markdown = (
        "## ① 요약\n요약\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ② 전일 핵심 이슈\n이슈\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n"
    )
    with pytest.raises(ValueError) as exc:
        parse_six_sections(markdown)
    assert "out of order" in str(exc.value)


def test_parse_six_sections_rejects_inline_duplicate_header() -> None:
    """H1 regression — a Stage 2 body containing another section's header
    inline must reject, not silently fuse adjacent bodies.

    Scenario: body ① mentions ``## ② 전일 핵심 이슈`` mid-prose (e.g.,
    the LLM is referring to "the next section"). Without the count
    check, ``markdown.find`` returns the inline position, fusing the
    real ② header into body ①'s region.
    """
    markdown = (
        "## ① 요약\n요약 본문 다음 ## ② 전일 핵심 이슈 도 보세요\n\n"
        "## ② 전일 핵심 이슈\n이슈 본문\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n"
    )
    with pytest.raises(ValueError) as exc:
        parse_six_sections(markdown)
    assert "## ② 전일 핵심 이슈" in str(exc.value)
    assert "appears 2 times" in str(exc.value)


def test_parse_six_sections_normalizes_nfd_input_to_nfc() -> None:
    """H2 regression — markdown emitted in NFD form (jamo decomposition)
    must still parse, because the constants are NFC and Python string
    matching is codepoint-exact.

    Without the ``unicodedata.normalize("NFC", ...)`` defense, an LLM
    that emits the same logical Korean characters in decomposed form
    would burn all 3 retries on a "missing section header" error.
    """
    import unicodedata

    nfd_markdown = unicodedata.normalize("NFD", _VALID_SIX_SECTION_MARKDOWN)
    # Sanity: the NFD form does NOT contain the NFC header substring.
    assert "## ① 요약" not in nfd_markdown
    # But parse_six_sections still accepts it via NFC normalization.
    bodies = parse_six_sections(nfd_markdown)
    assert bodies == (
        "오늘 시장 요약",
        "핵심 이슈 본문",
        "섹터 본문",
        "지표 본문",
        "종목 본문",
        "관전 포인트 본문",
    )


# ---------------------------------------------------------------------------
# ClassificationResult shape pin (defensive)
# ---------------------------------------------------------------------------


def test_classification_result_is_frozen() -> None:
    """``ClassificationResult`` is a frozen pydantic model — assignment fails."""
    result = ClassificationResult(assignments={1: 4}, unassigned=[])
    with pytest.raises(ValidationError):
        result.assignments = {2: 5}  # type: ignore[misc]


def test_classification_result_rejects_extra_fields() -> None:
    """``extra="forbid"`` is enforced on construction, not just parse."""
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({"assignments": {}, "unassigned": [], "junk": 1})


def test_classification_result_field_validator_rejects_bad_section_ids() -> None:
    """Constructor path also enforces section-id constraint, not only parse path."""
    with pytest.raises(ValidationError):
        ClassificationResult(assignments={1: 1}, unassigned=[])


# ---------------------------------------------------------------------------
# Public surface pin (catch accidental removals from __all__)
# ---------------------------------------------------------------------------


def test_pipeline_module_exports_expected_names() -> None:
    """Public surface stays stable — Step 8.5 review locks this further."""
    from investo.briefing import pipeline

    assert hasattr(pipeline, "ClassificationResult")
    assert hasattr(pipeline, "SectionPlan")
    assert hasattr(pipeline, "build_section_plan")
    assert hasattr(pipeline, "generate_briefing")
    assert hasattr(pipeline, "parse_six_sections")
    assert hasattr(pipeline, "serialize_items_for_prompt")
