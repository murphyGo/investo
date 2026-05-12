"""Disclaimer verification (NFR-004) — runtime safety net at the
publish boundary.

The canonical disclaimer constants (``DISCLAIMER`` /
``DISCLAIMER_CRYPTO``) live in ``investo.briefing.disclaimer``. u3
SHOULD NOT redefine or copy them; importing the single source of truth
ensures u2 and u3 stay aligned automatically across edits.

This module is the runtime substring check; the model-side invariant
(``Briefing.rendered_markdown`` contains the appropriate disclaimer) is
tracked separately in DEBT-001 and would make this module a redundant
defense-in-depth layer once enforced. Until then, ``write_briefing``
in Step 5 calls this check FIRST and refuses to write if it returns
False.

u56 — added segment + legacy parameters. The 1-arg call site
(``verify_disclaimer(text)``) keeps the *exact* historic byte-equal
behaviour (equity footer substring); the new optional parameters opt
into segment-aware checking. The publisher's new
``verify_short_disclaimer_first_viewport`` is an *additive* gate that
runs alongside the canonical footer check — never substituting it.

Reference:
    docs/requirements.md NFR-004 — disclaimer enforcement is
        the publish-boundary hard block
    aidlc-docs/inception/application-design/component-methods.md
        — `verify_disclaimer(briefing_md: str) -> bool`
    AC-4.6 (cross-unit boundary) in u2's NFR requirements
"""

from __future__ import annotations

from investo.briefing.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO
from investo.briefing.segments import MarketSegment
from investo.publisher.reader_format import (
    SHORT_DISCLAIMER_CRYPTO,
    SHORT_DISCLAIMER_EQUITY,
)

# Detector substrings — short, unique. Used by
# ``verify_short_disclaimer_first_viewport`` so the gate stays robust
# to whitespace/wrap differences in the rendered output.
_SHORT_DETECT_EQUITY = "정보 제공용 자동 시황이며 매매 권유가 아닙니다"
_SHORT_DETECT_CRYPTO = "정보 제공용 자동 시황이며 가상자산 매매 권유가 아닙니다"

# First-viewport budget. The reader's first scroll-position roughly
# corresponds to the first 30 lines of rendered markdown; the gate
# enforces that the short disclaimer lives within that window.
_FIRST_VIEWPORT_LINES = 30


def verify_disclaimer(
    briefing_md: str,
    segment: MarketSegment | None = None,
    *,
    legacy: bool = False,
) -> bool:
    """Return True iff the segment-appropriate canonical disclaimer
    block is a substring of ``briefing_md``.

    Pure boolean predicate. The CALLER (``write_briefing``) blocks
    the publish on False — this function does NOT raise, so it stays
    cheap to compose into other validation flows (e.g. a future
    pre-commit hook or a test-only sanity check).

    ``segment=None`` (the historic 1-arg call) checks against the
    equity footer for byte-equal backward compatibility.

    ``legacy=True`` accepts the equity footer regardless of
    ``segment``; this is what the weekly-digest / monthly-index
    re-readers pass when re-validating pre-2026-05-13 archive files,
    which all carry the equity footer (the 가상자산이용자보호법
    cutoff is not retroactive — see COMPLIANCE_CUTOFF_DATE in
    ``briefing.disclaimer``).
    """
    if legacy:
        # Cutoff archive files: accept either footer; the equity
        # version is the historic shape.
        return DISCLAIMER in briefing_md or DISCLAIMER_CRYPTO in briefing_md
    if segment == "crypto":
        return DISCLAIMER_CRYPTO in briefing_md
    # us-equity / domestic-equity / None — equity footer.
    return DISCLAIMER in briefing_md


def verify_short_disclaimer_first_viewport(briefing_md: str, segment: MarketSegment) -> bool:
    """Return True iff the short segment-aware disclaimer appears in
    the first viewport.

    The first viewport is approximated as the first
    :data:`_FIRST_VIEWPORT_LINES` rendered lines of the markdown. This
    is an *additive* gate (u56) — it runs alongside the canonical
    footer check, never substituting it. The string detector is a
    short substring, not a byte-equal match, so trivial wrapping or
    whitespace tweaks in the rendered surface do not fail the gate.
    """
    detect = _SHORT_DETECT_CRYPTO if segment == "crypto" else _SHORT_DETECT_EQUITY
    head = "\n".join(briefing_md.splitlines()[:_FIRST_VIEWPORT_LINES])
    return detect in head


# Re-exports for the short disclaimer constants so callers can import
# the gate + the text from a single module.
__all__ = [
    "SHORT_DISCLAIMER_CRYPTO",
    "SHORT_DISCLAIMER_EQUITY",
    "verify_disclaimer",
    "verify_short_disclaimer_first_viewport",
]
