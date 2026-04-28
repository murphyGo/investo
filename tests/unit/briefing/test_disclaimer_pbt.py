"""Property-based tests for ``briefing.disclaimer`` (AC-4.1, AC-6.1).

These tests run hypothesis with ≥100 examples per the NFR scope (AC-6.6).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from investo.briefing.disclaimer import DISCLAIMER, append_disclaimer

ANCHOR = "## ⑦ 면책조항"


@settings(max_examples=100)
@given(text=st.text())
def test_append_disclaimer_is_idempotent(text: str) -> None:
    """AC-4.1 / AC-6.1 — ``f(f(x)) == f(x)`` for any string ``x``.

    Holds unconditionally: once the anchor is in the result (either it
    was already there, or we just appended ``DISCLAIMER`` which contains
    it), further calls are no-ops.
    """
    once = append_disclaimer(text)
    twice = append_disclaimer(once)
    assert once == twice


@settings(max_examples=100)
@given(text=st.text().filter(lambda s: ANCHOR not in s))
def test_disclaimer_appended_for_anchorless_input(text: str) -> None:
    """AC-6.1 — for inputs WITHOUT the anchor, the full ``DISCLAIMER``
    is a substring of the result.

    This is the meaningful "presence" guarantee: when u2 receives Stage
    2 LLM output that does not contain section ⑦ (the prompt explicitly
    forbids it; FD R5), the appender produces a result containing the
    canonical disclaimer block.

    The anchor-already-present case is the idempotence half (above) and
    is covered example-based in ``test_disclaimer.py``: u2 trusts the
    input by anchor; u3 publisher's ``verify_disclaimer`` handles
    drift detection.
    """
    result = append_disclaimer(text)
    assert DISCLAIMER in result


@settings(max_examples=100)
@given(text=st.text())
def test_anchor_is_always_in_result(text: str) -> None:
    """Weaker but unconditional: the anchor substring is in every result.

    Either the input had it (idempotence path), or we just appended
    ``DISCLAIMER`` (which begins with the anchor). Useful as a
    canary — if this property breaks, the implementation has regressed.
    """
    assert ANCHOR in append_disclaimer(text)
