"""Tests for ``investo.publisher.verifier`` (NFR-004 + AC-4.6).

The substring contract: ``verify_disclaimer(md)`` returns True iff
the canonical ``DISCLAIMER`` constant from ``investo.briefing
.disclaimer`` appears verbatim in ``md``. The CALLER (``write_briefing``
in Step 5) blocks the publish on False; this module is the predicate.

Cross-unit pin: the test imports ``DISCLAIMER`` from u2 directly.
If u2 changes the constant, the verifier follows automatically (no
duplicated literal in u3); regression here would mean either u2
drifted or the import path broke.
"""

from __future__ import annotations

from investo.briefing.disclaimer import DISCLAIMER
from investo.publisher.verifier import verify_disclaimer

# ---------------------------------------------------------------------------
# Trivial cases
# ---------------------------------------------------------------------------


def test_verify_disclaimer_returns_true_for_exact_disclaimer() -> None:
    """The constant itself trivially contains itself as a substring."""
    assert verify_disclaimer(DISCLAIMER) is True


def test_verify_disclaimer_returns_false_for_empty_string() -> None:
    """An empty briefing → not OK to publish."""
    assert verify_disclaimer("") is False


# ---------------------------------------------------------------------------
# Substring semantics
# ---------------------------------------------------------------------------


def test_verify_disclaimer_returns_true_when_disclaimer_in_typical_briefing() -> None:
    """Realistic shape: 6 sections + DISCLAIMER appended at the end."""
    briefing = (
        "## ① 요약\n오늘 시장 요약\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터 동향\n\n"
        "## ④ 지표·이벤트\n지표 이벤트\n\n"
        "## ⑤ 주요 종목\n종목 본문\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전 포인트\n\n" + DISCLAIMER
    )
    assert verify_disclaimer(briefing) is True


def test_verify_disclaimer_returns_true_with_prefix_and_suffix() -> None:
    """The check is a substring search; surrounding text is ignored."""
    wrapped = "BEFORE\n" + DISCLAIMER + "\nAFTER"
    assert verify_disclaimer(wrapped) is True


# ---------------------------------------------------------------------------
# Negative cases — the safety-net properties
# ---------------------------------------------------------------------------


def test_verify_disclaimer_returns_false_for_truncated_disclaimer() -> None:
    """A shortened disclaimer is NOT acceptable. The contract is
    EXACT-substring; lopping off the last 5 chars (which removes the
    final newline + part of the last sentence) breaks the match.
    """
    truncated = DISCLAIMER[:-5]
    assert verify_disclaimer(truncated) is False


def test_verify_disclaimer_returns_false_for_altered_disclaimer() -> None:
    """A single-character change breaks the substring match. Pinning
    this rules out the failure mode where an LLM drifts the
    disclaimer wording subtly.
    """
    # Replace the first Korean character of the disclaimer body.
    altered = DISCLAIMER.replace("본", "X", 1)
    assert verify_disclaimer(altered) is False


def test_verify_disclaimer_returns_false_for_only_header_anchor() -> None:
    """The ``## ⑦ 면책조항`` header alone is NOT enough — the body
    paragraphs must also be present. Catches the scenario where an
    LLM emits the section header but no content.
    """
    header_only = "## ⑦ 면책조항\n"
    assert verify_disclaimer(header_only) is False


# ---------------------------------------------------------------------------
# Cross-unit alignment
# ---------------------------------------------------------------------------


def test_verifier_uses_internal_disclaimer_constant() -> None:
    """Pin the boundary: publisher imports the canonical disclaimer
    from the inward owner, not from a sibling adapter and not by local
    redefinition.
    """
    import inspect

    import investo.publisher.verifier as verifier_module

    source = inspect.getsource(verifier_module)
    assert "from investo._internal.disclaimer import DISCLAIMER" in source


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_verifier_module_exports_expected_names() -> None:
    from investo.publisher import verifier as verifier_module

    assert hasattr(verifier_module, "verify_disclaimer")
