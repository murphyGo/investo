"""PII / secret leak guard for u2-generated markdown.

References:
    Functional Design R6 (`u2-briefing/functional-design/business-rules.md`)
    NFR Requirements AC-6.4, AC-7.3 (`u2-briefing/nfr-requirements/nfr-requirements.md`)

Before u2 constructs a ``Briefing``, the synthesized markdown is scanned
for patterns that would leak credentials or PII into the public archive
and Telegram channel. This is defense-in-depth: the Stage 2 prompt
already instructs the LLM not to emit such patterns (FD L3), but we do
not trust prompt-side instructions alone.

Pattern set (closed)
--------------------
The blocklist is a closed regex set (R6). The actual patterns live in
the project-wide chokepoint :mod:`investo._internal.redaction`
(u27); this module wraps :func:`scan_for_leak` with the
``LeakGuardHit`` shape u2 callers already consume. Adding or removing
a pattern requires:

1. A code change in the chokepoint (and a flip of
   ``include_in_leak_scan`` if the new pattern should also fire here),
   AND
2. A test update in ``tests/unit/briefing/test_leak_guard.py``, AND
3. An audit-log entry per NFR drift AC-D.4.

Patterns are NOT runtime config — the closed shape is intentional.

Termination contract
--------------------
A hit is terminal — the caller raises ``BriefingGenerationError(stage=
"post_validation")`` and does NOT retry. Re-running the same prompt is
unlikely to fix a content-level leak; the prompt or upstream item set
needs human review.
"""

from __future__ import annotations

from typing import Final, NamedTuple

from investo._internal.redaction import scan_for_leak

# Maximum length of ``match_text`` carried in the LeakGuardHit. Keeps
# the excerpt short enough for safe logging without echoing the full
# secret.
_MATCH_EXCERPT_LIMIT: Final[int] = 64


class LeakGuardHit(NamedTuple):
    """A single matched leak pattern.

    ``match_text`` is truncated to ``_MATCH_EXCERPT_LIMIT`` chars for
    safe downstream logging; the full secret is not re-emitted.
    """

    pattern_name: str
    match_text: str


def scan(markdown: str) -> LeakGuardHit | None:
    """Scan ``markdown`` for known leak patterns.

    Thin wrapper over :func:`investo._internal.redaction.scan_for_leak`
    (u27 chokepoint) that adapts the result to ``LeakGuardHit`` and
    truncates ``match_text`` to :data:`_MATCH_EXCERPT_LIMIT`. Returns
    the first hit (deterministic order = chokepoint
    ``SECRET_PATTERNS`` order, filtered to ``include_in_leak_scan``),
    or ``None`` if no pattern matches.

    URL-context filtering for the generic ``oauth_long_base64`` pattern
    is performed inside the chokepoint per its ``url_filtered`` flag;
    matches inside an http(s) URL are skipped automatically.
    """
    hit = scan_for_leak(markdown)
    if hit is None:
        return None
    return LeakGuardHit(
        pattern_name=hit.pattern_name,
        match_text=hit.match_text[:_MATCH_EXCERPT_LIMIT],
    )


__all__ = ["LeakGuardHit", "scan"]
