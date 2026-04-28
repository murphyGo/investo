"""PII / secret leak guard for u2-generated markdown.

References:
    Functional Design R6 (`u2-briefing/functional-design/business-rules.md`)
    NFR Requirements AC-6.4, AC-7.3 (`u2-briefing/nfr-requirements/nfr-requirements.md`)

Before u2 constructs a ``Briefing``, the synthesized markdown is scanned
for patterns that would leak credentials or PII into the public archive
and Telegram channel. This is defense-in-depth: the Stage 2 prompt
already instructs the LLM not to emit such patterns (FD L3), but we do
not trust prompt-side instructions alone.

The blocklist is a closed regex set (R6). Adding or removing a pattern
requires:

1. A code change here, AND
2. A test update in ``tests/unit/briefing/test_leak_guard.py``, AND
3. An audit-log entry per NFR drift AC-D.4.

Patterns are NOT runtime config — the closed shape is intentional.

A hit is terminal — the caller raises ``BriefingGenerationError(stage=
"post_validation")`` and does NOT retry. Re-running the same prompt is
unlikely to fix a content-level leak; the prompt or upstream item set
needs human review.
"""

from __future__ import annotations

import re
from typing import Final, NamedTuple

# Maximum length of ``match_text`` carried in the LeakGuardHit. Keeps the
# excerpt short enough for safe logging without echoing the full secret.
_MATCH_EXCERPT_LIMIT: Final[int] = 64

# Lookback window for the URL-context exclusion (in characters). 200 is
# enough to catch typical markdown link forms ``[text](https://...)`` and
# inline ``https://...`` URLs where the secret-shaped substring is in
# the path/query.
_URL_LOOKBACK_WINDOW: Final[int] = 200


class LeakGuardHit(NamedTuple):
    """A single matched leak pattern.

    ``match_text`` is truncated to ``_MATCH_EXCERPT_LIMIT`` chars for safe
    downstream logging; the full secret is not re-emitted.
    """

    pattern_name: str
    match_text: str


# R6 regex set, in deterministic priority order. Specific credential
# patterns are checked first so that a JWT-shaped string is reported as
# ``jwt`` (not ``oauth_long_base64``) when both could match. The generic
# long-base64 pattern is last because it is the most false-positive-prone
# and additionally requires URL-context filtering at scan time.
_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("github_pat", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "jwt",
        re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    ),
    # Email: ``[^\s@]+@[^\s@]+\.[^\s@]+`` is the ReDoS-safe refinement of
    # FD R6's ``\S+@\S+\.\S+``. Forbidding ``@`` inside the three segments
    # (which is valid email syntax for the local part in theory but never
    # in practice) eliminates the overlap between the leading ``\S+`` and
    # the post-``@`` ``\S+`` that drives quadratic backtracking on
    # adversarial input. Same matches in practice for the leak-guard
    # purpose. Audit log entry: 2026-04-28 (Step 3 sub-agent review H1).
    ("email", re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")),
    ("korean_phone", re.compile(r"010[- ]?\d{4}[- ]?\d{4}")),
    ("oauth_long_base64", re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")),
)

# Patterns whose matches must be filtered through ``_is_in_url_context``
# at scan time. The generic long-base64 pattern is the only one — paths
# and query strings legitimately contain long base64-alphabet runs.
_URL_CONTEXT_FILTERED: Final[frozenset[str]] = frozenset({"oauth_long_base64"})


def _is_in_url_context(match_start: int, text: str) -> bool:
    """Return True if ``match_start`` is inside an http(s) URL.

    Walks backward from ``match_start`` up to ``_URL_LOOKBACK_WINDOW``
    chars. Returns True iff we find ``://`` with no whitespace between
    it and ``match_start``, AND the chars immediately before ``://`` are
    ``http`` or ``https``. This avoids variable-width lookbehind (which
    Python's stdlib ``re`` does not support) at the cost of a small
    portability/performance trade.
    """
    look_start = max(0, match_start - _URL_LOOKBACK_WINDOW)
    prefix = text[look_start:match_start]
    proto_idx = prefix.rfind("://")
    if proto_idx == -1:
        return False
    between = prefix[proto_idx + len("://") :]
    if any(c.isspace() for c in between):
        return False
    scheme_part = prefix[:proto_idx]
    return scheme_part.endswith("http") or scheme_part.endswith("https")


def scan(markdown: str) -> LeakGuardHit | None:
    """Scan ``markdown`` for known leak patterns.

    Returns the first hit (deterministic order = ``_PATTERNS`` order),
    or ``None`` if no pattern matches. Matches inside http(s) URLs are
    filtered for patterns listed in ``_URL_CONTEXT_FILTERED``.
    """
    for name, pattern in _PATTERNS:
        url_filtered = name in _URL_CONTEXT_FILTERED
        for match in pattern.finditer(markdown):
            if url_filtered and _is_in_url_context(match.start(), markdown):
                continue
            return LeakGuardHit(
                pattern_name=name,
                match_text=match.group()[:_MATCH_EXCERPT_LIMIT],
            )
    return None


__all__ = ["LeakGuardHit", "scan"]
