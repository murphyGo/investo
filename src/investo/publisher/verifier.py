"""Disclaimer verification (NFR-004) — runtime safety net at the
publish boundary.

The canonical ``DISCLAIMER`` constant lives in ``investo.briefing
.disclaimer``. u3 SHOULD NOT redefine or copy it; importing the
single source of truth ensures u2 and u3 stay aligned automatically
across edits.

This module is the runtime substring check; the model-side invariant
(``Briefing.rendered_markdown contains DISCLAIMER``) is tracked
separately in DEBT-001 and would make this module a redundant
defense-in-depth layer once enforced. Until then, ``write_briefing``
in Step 5 calls this check FIRST and refuses to write if it returns
False.

Reference:
    docs/requirements.md NFR-004 — disclaimer enforcement is
        the publish-boundary hard block
    aidlc-docs/inception/application-design/component-methods.md
        — `verify_disclaimer(briefing_md: str) -> bool`
    AC-4.6 (cross-unit boundary) in u2's NFR requirements
"""

from __future__ import annotations

from investo.briefing.disclaimer import DISCLAIMER


def verify_disclaimer(briefing_md: str) -> bool:
    """Return True iff the canonical ``DISCLAIMER`` block is a
    substring of ``briefing_md``.

    Pure boolean predicate. The CALLER (``write_briefing``) blocks
    the publish on False — this function does NOT raise, so it stays
    cheap to compose into other validation flows (e.g. a future
    pre-commit hook or a test-only sanity check).
    """
    return DISCLAIMER in briefing_md


__all__ = ["verify_disclaimer"]
