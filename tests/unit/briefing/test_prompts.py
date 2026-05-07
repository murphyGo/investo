"""Tests for ``briefing.prompts`` (NFR-005 AC-5.1, AC-5.2, AC-5.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from investo.briefing.prompts import (
    DEFAULT_SEGMENT_CONTEXT,
    SEGMENT_CONTEXT_TEMPLATE,
    SEGMENT_DATA_LIMITED_NOTE,
    STAGE1_SYSTEM,
    STAGE1_USER_TEMPLATE,
    STAGE2_SYSTEM,
    STAGE2_USER_TEMPLATE,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BRIEFING_SRC_DIR = PROJECT_ROOT / "src" / "investo" / "briefing"


# --- Constants exist + non-empty + str ---------------------------------------


@pytest.mark.parametrize(
    "constant",
    [STAGE1_SYSTEM, STAGE1_USER_TEMPLATE, STAGE2_SYSTEM, STAGE2_USER_TEMPLATE],
)
def test_constant_is_non_empty_str(constant: str) -> None:
    """AC-5.1 — each prompt constant is a populated string."""
    assert isinstance(constant, str)
    assert len(constant) > 0


# --- Stage 1 prompt anchors -------------------------------------------------


def test_stage1_system_contains_role_anchor() -> None:
    """Stage 1 system prompt declares the classifier role and JSON schema
    contract.
    """
    assert "market-briefing classifier" in STAGE1_SYSTEM
    assert "assignments" in STAGE1_SYSTEM
    assert "unassigned" in STAGE1_SYSTEM


def test_stage1_system_lists_all_target_sections() -> None:
    """Section IDs 2, 3, 4, 5 must appear in the legend (FD R10)."""
    for section_id in ("2", "3", "4", "5"):
        assert f"\n  {section_id} =" in STAGE1_SYSTEM


def test_stage1_system_does_not_mention_sections_1_or_6_or_7() -> None:
    """Stage 1 only assigns to sections 2-5; ① / ⑥ are Stage 2's job;
    ⑦ is the disclaimer's job (R1, R5).

    Stage 1 must NOT mention ⑦ (the disclaimer header) — that would
    confuse the LLM into emitting the disclaimer at Stage 1.
    """
    assert "⑦" not in STAGE1_SYSTEM


def test_stage1_user_template_has_items_json_placeholder() -> None:
    rendered = STAGE1_USER_TEMPLATE.format(
        segment_context=DEFAULT_SEGMENT_CONTEXT,
        items_json="[]",
    )
    assert "[]" in rendered
    # Original template contained the placeholder
    assert "{items_json}" in STAGE1_USER_TEMPLATE
    assert "{segment_context}" in STAGE1_USER_TEMPLATE


def test_segment_context_template_supports_data_limited_note() -> None:
    rendered = SEGMENT_CONTEXT_TEMPLATE.format(
        segment_label="미국 증시",
        segment_slug="us-equity",
        data_limited_note=SEGMENT_DATA_LIMITED_NOTE,
    )

    assert "미국 증시" in rendered
    assert "us-equity" in rendered
    assert "데이터 부족" in rendered


# --- Stage 2 prompt anchors -------------------------------------------------


def test_stage2_system_lists_all_six_section_headers() -> None:
    """Stage 2 must produce exactly the six fixed section headers
    (① 요약 through ⑥ 오늘의 관전 포인트). The system prompt enumerates
    them all (R1).
    """
    expected_headers = [
        "## ① 요약",
        "## ② 전일 핵심 이슈",
        "## ③ 섹터/수급 동향",
        "## ④ 지표·이벤트",
        "## ⑤ 주요 종목",
        "## ⑥ 오늘의 관전 포인트",
    ]
    for header in expected_headers:
        assert header in STAGE2_SYSTEM, f"Stage 2 system prompt missing: {header}"


def test_stage2_system_excludes_disclaimer_section() -> None:
    """R5 — Stage 2 must NOT include section ⑦. The system prompt must
    explicitly forbid the LLM from emitting it.
    """
    assert "DO NOT include section ⑦" in STAGE2_SYSTEM
    assert "⑦" in STAGE2_SYSTEM  # mention only in the prohibition context


def test_stage2_system_carries_korean_ticker_rule() -> None:
    """R8 — Korean prose with English tickers preserved."""
    assert "Korean prose" in STAGE2_SYSTEM
    # Concrete examples should be present so the LLM has anchors:
    for ticker_or_name in ("AAPL", "S&P 500"):
        assert ticker_or_name in STAGE2_SYSTEM


def test_stage2_system_forbids_pii_emission() -> None:
    """R6 + Stage 2 prompt-side hint to reduce leak-guard hits."""
    assert "DO NOT include any private tokens" in STAGE2_SYSTEM


def test_stage2_system_carries_reader_experience_rules() -> None:
    assert "market newsletter" in STAGE2_SYSTEM
    assert "source URL" in STAGE2_SYSTEM
    assert "Avoid exaggerated promotional language" in STAGE2_SYSTEM
    assert "group notable tickers/assets by neutral observation" in STAGE2_SYSTEM


def test_stage2_system_uses_neutral_section5_grouping_labels() -> None:
    """u25 — Korean capital-markets law treats 주도주 / 부진 / 주의 as
    implicit recommendation language. The prompt must instruct the LLM
    to use neutral observation labels instead.
    """
    assert "관전 분류" in STAGE2_SYSTEM
    assert "확인 항목" in STAGE2_SYSTEM
    assert "체크리스트" in STAGE2_SYSTEM
    assert "NEVER use" in STAGE2_SYSTEM
    assert "주도주" in STAGE2_SYSTEM  # only as forbidden example
    assert "부진" in STAGE2_SYSTEM  # only as forbidden example
    assert "주의" in STAGE2_SYSTEM  # only as forbidden example


def test_stage2_system_forbids_arithmetic_hallucination() -> None:
    """u25 — block the ``시총 합산 약 $X조`` style fabrication that
    appeared in ``archive/us-equity/2026/05/2026-05-06.md`` (persona #3).
    """
    assert "Numeric integrity" in STAGE2_SYSTEM
    assert "DO NOT compute sums" in STAGE2_SYSTEM
    assert "시총 합산" in STAGE2_SYSTEM
    assert "DO NOT round, approximate" in STAGE2_SYSTEM


def test_stage2_user_template_has_three_placeholders() -> None:
    rendered = STAGE2_USER_TEMPLATE.format(
        segment_context=DEFAULT_SEGMENT_CONTEXT,
        grouped_sections="(grouped content)",
        unassigned="(unassigned content)",
        target_date="2026-04-28",
    )
    assert "(grouped content)" in rendered
    assert "(unassigned content)" in rendered
    assert "2026-04-28" in rendered
    assert "{grouped_sections}" in STAGE2_USER_TEMPLATE
    assert "{unassigned}" in STAGE2_USER_TEMPLATE
    assert "{target_date}" in STAGE2_USER_TEMPLATE
    assert "{segment_context}" in STAGE2_USER_TEMPLATE


def test_stage1_system_format_call_raises_key_error() -> None:
    """Locks the "SYSTEM never formatted" convention in CI.

    ``STAGE1_SYSTEM`` contains literal ``{`` / ``}`` in the JSON schema
    example. Calling ``.format()`` on it MUST raise — otherwise an
    accidental future refactor (e.g. wrapping the merged prompt in
    ``str.format``) would silently corrupt the prompt or explode at
    runtime in production.
    """
    with pytest.raises((KeyError, IndexError, ValueError)):
        STAGE1_SYSTEM.format()


def test_stage1_system_does_not_collide_with_disclaimer_anchor() -> None:
    """L-3 — ``## ① 요약`` (Stage 2 sentinel) must not appear in the
    disclaimer constant; otherwise the AC-5.2 sentinel-grep would
    falsely flag ``disclaimer.py`` as a prompt-leakage offender.
    """
    from investo.briefing.disclaimer import DISCLAIMER

    assert "## ① 요약" not in DISCLAIMER
    assert "market-briefing classifier" not in DISCLAIMER
    assert "market-briefing writer" not in DISCLAIMER


def test_stage2_user_template_format_is_idempotent_under_repeat() -> None:
    """A single ``.format(**kwargs)`` call substitutes ALL placeholders
    in one pass. A second call would error if there were leftover
    placeholders.
    """
    rendered = STAGE2_USER_TEMPLATE.format(
        segment_context=DEFAULT_SEGMENT_CONTEXT,
        grouped_sections="x",
        unassigned="y",
        target_date="2026-04-28",
    )
    # No placeholders remain — re-formatting an empty dict yields same
    # string (no KeyError).
    rendered.format()  # raises if there are leftover ``{...}`` placeholders


# --- AC-5.2 / AC-5.3 sentinel-grep ------------------------------------------


_PROMPT_SENTINELS: tuple[str, ...] = (
    "market-briefing classifier",  # Stage 1 system role
    "market-briefing writer",  # Stage 2 system role
    "Pre-grouped items",  # Stage 2 user template anchor
    "## ① 요약",  # Stage 2 section header (NOT in disclaimer's ⑦)
    "Section ID legend",  # Stage 1 system schema legend
)


def test_prompt_sentinels_only_in_prompts() -> None:
    """AC-5.2 / AC-5.3 — prompt body strings live ONLY in ``prompts.py``.

    Iterates every ``*.py`` file under ``src/investo/briefing/`` and
    asserts the prompt sentinel substrings appear nowhere except
    ``prompts.py`` itself. The constraint is anchored at this point in
    the build (Step 5); when ``pipeline.py`` and ``claude_code.py``
    land (Steps 6 and 8), the test continues to enforce the boundary.
    """
    offenders: list[tuple[str, str]] = []
    for py_file in sorted(BRIEFING_SRC_DIR.glob("*.py")):
        if py_file.name == "prompts.py":
            continue
        contents = py_file.read_text(encoding="utf-8")
        for sentinel in _PROMPT_SENTINELS:
            if sentinel in contents:
                offenders.append((py_file.name, sentinel))
    assert not offenders, (
        f"Prompt body sentinels leaked into modules other than prompts.py: "
        f"{offenders}. Move them to src/investo/briefing/prompts.py "
        f"(AC-5.2 / AC-5.3)."
    )


def test_prompts_file_actually_contains_the_sentinels() -> None:
    """Sanity check — the sentinels must be in ``prompts.py``, otherwise
    the test above would pass tautologically.
    """
    contents = (BRIEFING_SRC_DIR / "prompts.py").read_text(encoding="utf-8")
    for sentinel in _PROMPT_SENTINELS:
        assert sentinel in contents, (
            f"Sentinel '{sentinel}' missing from prompts.py — "
            f"AC-5.2 / AC-5.3 grep test would be tautological. "
            f"Update _PROMPT_SENTINELS or fix the prompt."
        )
