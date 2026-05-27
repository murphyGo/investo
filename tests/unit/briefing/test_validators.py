"""u85 — briefing-side validator adapter equivalence.

The adapter must produce a ``block`` result EXACTLY when the underlying
``leak_guard.scan`` matches, carrying the same pattern name in its message,
and a ``pass`` otherwise. The detection logic itself is unchanged (proven
by the untouched ``test_leak_guard.py``).
"""

from __future__ import annotations

from investo.briefing.leak_guard import scan as leak_guard_scan
from investo.briefing.validators import (
    LeakGuardValidator,
    build_post_validation_registry,
)

_CLEAN = "## 시황\n오늘 시장은 혼조세였다.\n"
_LEAKY = "연락처: someone@example.com 으로 문의."


def test_clean_markdown_passes() -> None:
    result = LeakGuardValidator(name="leak_guard", markdown=_CLEAN).validate()
    assert result.severity == "pass"
    assert result.findings == ()


def test_leaky_markdown_blocks_with_pattern_name() -> None:
    hit = leak_guard_scan(_LEAKY)
    assert hit is not None  # sanity: underlying check still fires
    result = LeakGuardValidator(name="leak_guard", markdown=_LEAKY).validate()
    assert result.is_block
    assert result.message == f"leak guard matched pattern: {hit.pattern_name}"
    assert result.findings == (hit,)


def test_registry_blocks_on_leak() -> None:
    reg = build_post_validation_registry(_LEAKY)
    results = reg.run()
    assert results[-1].is_block


def test_registry_passes_clean() -> None:
    reg = build_post_validation_registry(_CLEAN)
    assert all(not r.is_block for r in reg.run())
