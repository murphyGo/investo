"""u52 — prompt-side carryover renderer + STAGE2_SYSTEM rule presence.

Pins:

* :func:`format_carryover_section` omits an empty body and returns a
  header + intro + rows block otherwise.
* :data:`STAGE2_SYSTEM` carries each ``CARRY-N`` rule ID (1-4).
* :data:`STAGE2_USER_TEMPLATE` carries the ``{carryover_context}``
  placeholder.
"""

from __future__ import annotations

from investo.briefing.prompts import (
    CARRYOVER_CONTEXT_HEADER,
    STAGE2_SYSTEM,
    STAGE2_USER_TEMPLATE,
    format_carryover_section,
)


def test_format_carryover_section_empty_omits_block() -> None:
    assert format_carryover_section("") == ""


def test_format_carryover_section_with_rows_emits_header_and_body() -> None:
    body = (
        "- [earnings] ARM | 발원=2026-05-06 | 기대=2026-05-07 | 상태=확인됨\n"
        "- [fed] FOMC 의사록 | 발원=2026-05-07 | 기대=2026-05-20 | 상태=이월"
    )
    rendered = format_carryover_section(body)
    assert CARRYOVER_CONTEXT_HEADER in rendered
    assert "ARM" in rendered
    assert "FOMC 의사록" in rendered
    # Header sits before the body rows.
    assert rendered.index(CARRYOVER_CONTEXT_HEADER) < rendered.index("ARM")


def test_stage2_system_carries_all_four_carry_rules() -> None:
    for rule_id in ("CARRY-1", "CARRY-2", "CARRY-3", "CARRY-4"):
        assert rule_id in STAGE2_SYSTEM, f"missing {rule_id} rule in STAGE2_SYSTEM"


def test_stage2_user_template_carryover_placeholder_present() -> None:
    assert "{carryover_context}" in STAGE2_USER_TEMPLATE


def test_format_carryover_section_strips_whitespace() -> None:
    """Body with only whitespace collapses to omitted block."""
    assert format_carryover_section("   \n  \n") == ""
