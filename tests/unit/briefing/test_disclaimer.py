"""Anchor tests for ``briefing.disclaimer`` (NFR-004 AC-4.2, AC-4.3, AC-4.5).

Property-based tests live in ``test_disclaimer_pbt.py``.
"""

from __future__ import annotations

import re

from investo.briefing.disclaimer import DISCLAIMER, append_disclaimer

# --- DISCLAIMER constant shape ------------------------------------------------


def test_disclaimer_is_non_empty_str() -> None:
    """AC-4.5 — ``DISCLAIMER`` is a populated string."""
    assert isinstance(DISCLAIMER, str)
    assert len(DISCLAIMER) > 0


def test_disclaimer_contains_section_header() -> None:
    """The constant must contain the ``## ⑦ 면책조항`` anchor (FD R5)."""
    assert "## ⑦ 면책조항" in DISCLAIMER


def test_disclaimer_starts_with_section_header() -> None:
    """Header is the first line — guarantees ``DISCLAIMER`` rendered as
    a top-level markdown section regardless of caller padding.
    """
    assert DISCLAIMER.startswith("## ⑦ 면책조항\n")


# --- append_disclaimer — example-based AC-4.2 / AC-4.3 ------------------------


def test_append_to_empty_yields_disclaimer_substring() -> None:
    """AC-4.2 — empty input still produces the full disclaimer."""
    result = append_disclaimer("")
    assert DISCLAIMER in result


def test_append_to_typical_briefing_ends_with_disclaimer() -> None:
    """AC-4.3 — disclaimer header is the LAST ``## `` header in the
    rendered result, never embedded mid-string.
    """
    body = (
        "## ① 요약\n오늘 요약\n\n"
        "## ② 전일 핵심 이슈\n이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n이벤트\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n"
    )
    result = append_disclaimer(body)
    # `\S+` captures one whitespace-delimited token after `## `. Works
    # here because the section markers are single CJK numerals (①-⑦)
    # without internal whitespace.
    headers = re.findall(r"^## (\S+)", result, flags=re.MULTILINE)
    assert headers == ["①", "②", "③", "④", "⑤", "⑥", "⑦"]
    assert DISCLAIMER in result


def test_append_to_no_sections_yields_disclaimer() -> None:
    """AC-4.2 — input that's not a briefing at all still gets the
    disclaimer appended (e.g. a future raw-prose mode).
    """
    result = append_disclaimer("just some prose with no headers")
    assert DISCLAIMER in result
    headers = re.findall(r"^## (\S+)", result, flags=re.MULTILINE)
    assert headers == ["⑦"]


# --- append_disclaimer — idempotence example cases ----------------------------


def test_idempotent_after_normal_append() -> None:
    """``f(f(x)) == f(x)`` for typical briefing input."""
    body = "## ① 요약\n내용\n"
    once = append_disclaimer(body)
    twice = append_disclaimer(once)
    assert once == twice


def test_idempotent_when_anchor_already_present_with_correct_body() -> None:
    """Input already contains the full DISCLAIMER → no double-append."""
    text = "intro\n\n" + DISCLAIMER
    assert append_disclaimer(text) == text


def test_idempotent_when_anchor_present_with_drifted_body() -> None:
    """LLM hallucination case — input contains the anchor but a
    different body. ``append_disclaimer`` is anchor-anchored (FD R5),
    so it does NOT add another disclaimer block. u3 publisher's
    ``verify_disclaimer`` is the defense-in-depth check that catches
    body drift and blocks publish (NFR-004 cross-unit boundary).
    """
    text_with_anchor_only = "## ⑦ 면책조항\n잘못된 본문\n"
    result = append_disclaimer(text_with_anchor_only)
    assert result == text_with_anchor_only
    # Sanity: the result does NOT contain the canonical DISCLAIMER —
    # this is u3's job to flag, not u2's.
    assert DISCLAIMER not in result


def test_append_returns_str() -> None:
    assert isinstance(append_disclaimer("anything"), str)
