"""Single chokepoint for secret redaction across reader-/operator-facing surfaces.

This module is the canonical home for the secret-shaped redaction
patterns that surface across the project's four "redact / scan before
publish" sites:

1. ``__main__._redact_diagnostic_text`` — GitHub Step Summary writer
   (operator-visible run summary).
2. ``models.coverage.sanitize_source_error_message`` — public source
   coverage badge / SVG / markdown row failure reasons.
3. ``visuals.provenance.sanitize_provenance_text`` — visual asset
   provenance manifests written to the public archive.
4. ``briefing.leak_guard`` — pre-publish leak guard that scans the
   LLM-synthesized markdown for credential / PII shapes and aborts the
   pipeline on a hit.

Before u27 each of these sites carried its own copy of overlapping (but
non-identical) regex patterns + literal env-var lists, and the patterns
drifted during normal development. This module unifies that policy:
every site delegates to one of two named entry points
(:func:`redact_text` for redact-and-replace surfaces;
:func:`scan_for_leak` for the leak guard's first-hit detector). A
future contributor adding a fifth surface picks the matching policy and
inherits the full pattern set automatically.

Module boundary
---------------
``investo._internal.redaction`` imports only stdlib (``os``, ``re``,
``enum``, ``typing``). It must not import from any unit package
(``sources``, ``briefing``, ``publisher``, ``notifier``,
``orchestrator``, ``visuals``, ``models``) — otherwise ``models``
(which re-exports ``sanitize_source_error_message``) and other unit
packages would form an import cycle.

Single source of truth for "secret env vars"
--------------------------------------------
:data:`SECRET_ENV_VARS` is the project-wide list of environment
variables whose **values** must be redacted from any operator-/reader-
facing diagnostic. ``OPENAI_API_KEY`` (u23 / u27) is redaction-tracked
even though it is *required only* when ``INVESTO_OPENAI_VISUALS=1`` —
its value, when present, must never leak into a manifest or step
summary regardless of opt-in state.

Two operating modes
-------------------
:func:`redact_text` (replace-all)
    Used by surfaces 1-3 above. Substitutes every match with a stable
    redaction marker and returns the rewritten string. Exhaustive —
    every shape in :data:`SECRET_PATTERNS` is applied.

:func:`scan_for_leak` (first-match detector)
    Used by surface 4. Returns the first matched pattern name +
    truncated excerpt, or ``None`` if the markdown is clean. The leak
    guard intentionally scans a narrower pattern set than
    :func:`redact_text` (no Telegram bot/chat ID shapes — those would
    false-positive on legitimate ``api.telegram.org`` links the LLM may
    quote) and applies URL-context filtering to the generic
    long-base64 pattern. Add a pattern to the leak-guard set by
    flipping its ``include_in_leak_scan`` flag in
    :data:`SECRET_PATTERNS`.

Adding a new pattern
--------------------
Append a new entry to :data:`SECRET_PATTERNS` with the appropriate
flags, then update ``tests/unit/_internal/test_redaction.py`` to pin
the redaction across all four surfaces. Per-surface overrides are not
permitted — that would re-introduce the drift this module exists to
prevent.
"""

from __future__ import annotations

import enum
import os
import re
from typing import Final

# ---------------------------------------------------------------------------
# Single source of truth for "names whose values must be scrubbed"
# ---------------------------------------------------------------------------

# The project-wide secret env-var list. These are the names whose
# **values** at runtime are scrubbed verbatim from any redacted text
# (the value-scrub step is per-process: ``os.environ.get(name)`` at
# call time). Order is informational only — redaction is order-
# independent. The set is a superset of the orchestrator's "required at
# boot" list because some entries (``OPENAI_API_KEY``, ``FRED_API_KEY``,
# ``CONGRESS_API_KEY``)
# are optional / opt-in but their values, when present, must still be
# redacted from any operator-facing surface.
SECRET_ENV_VARS: Final[tuple[str, ...]] = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHANNEL_ID",
    "TELEGRAM_OPERATOR_CHAT_ID",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "BEA_API_KEY",
    "FRED_API_KEY",
    "CONGRESS_API_KEY",
    # data.go.kr / KRX adapters (fsc-krx-index-price, fsc-krx-stock-price).
    # The canonical name is ``INVESTO_KRX_SERVICE_KEY``; the legacy
    # ``INVESTO_DATA_GO_KR_SERVICE_KEY`` is consulted as fallback in the
    # adapter modules and must redact identically. Service keys arrive
    # URL-encoded (``abc%2Bdef%2F``-style) and would otherwise survive
    # the regex catalogue intact.
    "INVESTO_KRX_SERVICE_KEY",
    "INVESTO_DATA_GO_KR_SERVICE_KEY",
    # u41 OpenDART disclosure adapter — enrolled ahead of the adapter
    # implementation so any future surface that boots with the GHA
    # secret already injected (cron probes, dry-run scripts) cannot leak
    # the value before the adapter ships.
    "OPENDART_API_KEY",
)


class RedactionPolicy(enum.StrEnum):
    """Named redaction policy for the chokepoint.

    Members
    -------
    STRICT
        Reader-/operator-facing surfaces (step summary, source coverage
        ``failure_reason``, visual provenance manifests). Long base64
        runs are unconditionally redacted. URL context is **not**
        considered.
    URL_AWARE
        Used by the briefing leak guard, where markdown legitimately
        carries hyperlinks. Long base64 matches inside an http(s) URL
        path / query are skipped to avoid false positives. All
        non-base64 patterns still fire identically (subject to each
        pattern's ``include_in_leak_scan`` flag for the scanner entry
        point).
    """

    STRICT = "strict"
    URL_AWARE = "url_aware"


# ---------------------------------------------------------------------------
# Compiled regex catalogue
# ---------------------------------------------------------------------------

# The bot-token pattern uses ``(?<![\d:])`` instead of ``\b`` because
# the token may be preceded by ``bot`` (a word character) inside a URL
# like ``https://api.telegram.org/bot1234:abc.../sendMessage``; a
# literal ``\b`` would not fire there. ``(?![:\w-])`` at the tail
# prevents overrun into trailing path segments.
_BOT_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\d:])\d{6,}:[A-Za-z0-9_-]{20,}(?![\w-])")
_CHAT_ID_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\w-])-?\d{7,}(?![\w-])")
# GitHub Personal Access Token shapes (classic + fine-grained).
_GITHUB_PAT_RE: Final[re.Pattern[str]] = re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")
# AWS Access Key ID. Always 20 chars, prefix ``AKIA``.
_AWS_KEY_RE: Final[re.Pattern[str]] = re.compile(r"AKIA[0-9A-Z]{16}")
# JWT — three base64-url-safe segments separated by ``.``. ``eyJ`` is
# the literal ``{"`` in base64-url encoding (the JOSE header start).
_JWT_RE: Final[re.Pattern[str]] = re.compile(
    r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)
# ReDoS-safe email (per leak_guard audit log 2026-04-28). Forbidding
# ``@`` inside each of the three segments eliminates the overlap that
# drives quadratic backtracking on adversarial input.
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
# Korean mobile phone numbers. The leading guard intentionally rejects
# matches embedded in crypto/FX decimal prices such as ``0.01012345678``.
_KOREAN_PHONE_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\d.])010[- ]?\d{4}[- ]?\d{4}(?!\d)")
# Generic long base64-ish run (OAuth / JWT / PAT / API-key shapes). The
# 40-char floor avoids matching short tokens. URL-context filtering is
# applied only in URL_AWARE policy.
_LONG_BASE64_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
# ``?key=value`` and ``&key=value`` segments — for HTTP query strings
# where the value can be an API key. Both key and value are redacted
# under the STRICT policy. The leak scanner does not include this
# pattern; URL query strings in the LLM's markdown are common (news
# links) and would false-positive.
_QUERY_REDACT_RE: Final[re.Pattern[str]] = re.compile(r"(\?|&)([^=&\s]+)=([^&\s]+)")


class _PatternDef:
    """Internal record for one redactable secret shape.

    ``include_in_leak_scan`` controls whether :func:`scan_for_leak`
    iterates this entry. The redact-and-replace path
    (:func:`redact_text`) always applies every entry.

    ``url_filtered`` controls whether the URL_AWARE policy / the leak
    guard skip matches that lie inside an http(s) URL context. Only
    relevant for shapes that legitimately appear in URL paths/queries
    (the generic long-base64 catch-all).
    """

    __slots__ = ("include_in_leak_scan", "name", "regex", "replacement", "url_filtered")

    def __init__(
        self,
        name: str,
        regex: re.Pattern[str],
        replacement: str,
        *,
        url_filtered: bool,
        include_in_leak_scan: bool,
    ) -> None:
        self.name = name
        self.regex = regex
        self.replacement = replacement
        self.url_filtered = url_filtered
        self.include_in_leak_scan = include_in_leak_scan


# Order matters for :func:`scan_for_leak`: more-specific credential
# shapes are listed before the generic long-base64 fallback so a
# JWT-shaped string is reported as ``jwt`` (not ``oauth_long_base64``)
# when both could match. The redact-and-replace path is also
# order-sensitive — running ``oauth_long_base64`` before ``jwt`` would
# overwrite the JWT shape with a generic redaction marker, losing the
# pattern-name signal that helps debugging from log excerpts.
SECRET_PATTERNS: Final[tuple[_PatternDef, ...]] = (
    _PatternDef(
        "github_pat",
        _GITHUB_PAT_RE,
        "[REDACTED_GITHUB_PAT]",
        url_filtered=False,
        include_in_leak_scan=True,
    ),
    _PatternDef(
        "aws_access_key",
        _AWS_KEY_RE,
        "[REDACTED_AWS_KEY]",
        url_filtered=False,
        include_in_leak_scan=True,
    ),
    _PatternDef(
        "bot_token",
        _BOT_TOKEN_RE,
        "[REDACTED_BOT_TOKEN]",
        url_filtered=False,
        # Excluded from the leak scanner: the LLM-synthesized markdown
        # may quote a Telegram bot URL (``api.telegram.org/bot.../...``)
        # in a news context, and the scanner would fire false-positive.
        # The strict redactor still fires for diagnostic / coverage /
        # provenance text (which never need to preserve a bot URL).
        include_in_leak_scan=False,
    ),
    _PatternDef(
        "jwt",
        _JWT_RE,
        "[REDACTED_JWT]",
        url_filtered=False,
        include_in_leak_scan=True,
    ),
    _PatternDef(
        "email",
        _EMAIL_RE,
        "[REDACTED_EMAIL]",
        url_filtered=False,
        include_in_leak_scan=True,
    ),
    _PatternDef(
        "korean_phone",
        _KOREAN_PHONE_RE,
        "[REDACTED_PHONE]",
        url_filtered=False,
        include_in_leak_scan=True,
    ),
    _PatternDef(
        "chat_id",
        _CHAT_ID_RE,
        "[REDACTED_CHAT_ID]",
        url_filtered=False,
        # Excluded from the leak scanner for the same reason as
        # bot_token — long numeric IDs frequently appear in URL paths
        # (article IDs, FOMC archive ids, etc.).
        include_in_leak_scan=False,
    ),
    _PatternDef(
        "oauth_long_base64",
        _LONG_BASE64_RE,
        "[REDACTED]",
        # Generic catch-all — must be URL-context filtered when scanned
        # against arbitrary markdown to avoid matching legitimate URL
        # path/query segments. Strict redaction still applies it
        # unconditionally.
        url_filtered=True,
        include_in_leak_scan=True,
    ),
)


# ---------------------------------------------------------------------------
# URL-context detection (URL_AWARE policy)
# ---------------------------------------------------------------------------

# Lookback window for the URL-context exclusion (in characters). 200 is
# enough to catch typical markdown link forms ``[text](https://...)``
# and inline ``https://...`` URLs where the secret-shaped substring is
# in the path/query.
_URL_LOOKBACK_WINDOW: Final[int] = 200


def is_in_url_context(match_start: int, text: str) -> bool:
    """Return True if ``match_start`` lies inside an http(s) URL.

    Walks backward from ``match_start`` up to :data:`_URL_LOOKBACK_WINDOW`
    chars. Returns True iff we find ``://`` with no whitespace between
    it and ``match_start``, AND the chars immediately before ``://`` are
    ``http`` or ``https``. Avoids variable-width lookbehind (which
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


# ---------------------------------------------------------------------------
# Public API: redact-and-replace
# ---------------------------------------------------------------------------


def _sub_with_url_filter(regex: re.Pattern[str], replacement: str, text: str) -> str:
    """Apply ``regex.sub(replacement, text)`` skipping http(s) URL matches.

    Helper for the URL_AWARE branch of :func:`redact_text`. Defined at
    module scope so the substitution callback's closure captures only
    its parameters (``text``, ``replacement``) rather than a mutating
    loop variable in the caller.
    """

    def _replace(match: re.Match[str]) -> str:
        if is_in_url_context(match.start(), text):
            return match.group()
        return replacement

    return regex.sub(_replace, text)


def redact_text(text: str, *, policy: RedactionPolicy = RedactionPolicy.STRICT) -> str:
    """Redact every secret-shaped substring in ``text``.

    Steps, in order:

    1. Replace any current value of an env var listed in
       :data:`SECRET_ENV_VARS` (read at call time via
       ``os.environ.get``) with ``[REDACTED]``. Empty / unset env vars
       are skipped — there is no "empty" value to redact.
    2. Apply each regex in :data:`SECRET_PATTERNS`, in declaration
       order. Under :data:`RedactionPolicy.URL_AWARE`, matches whose
       ``url_filtered=True`` AND that fall inside an http(s) URL are
       skipped (preserves legitimate links in the leak-guard surface).
    3. Apply the query-string redactor (``?key=value`` /
       ``&key=value``) which scrubs both key and value to handle
       endpoints that pass an API key as a query parameter.

    Whitespace collapse and length truncation are **deliberately not**
    performed here — those are surface-specific (e.g. the source
    coverage ``failure_reason`` has a 120-char SVG-row cap). Callers
    wrap :func:`redact_text` and apply their own caps.
    """
    if not text:
        return text

    redacted = text
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            redacted = redacted.replace(value, "[REDACTED]")

    for defn in SECRET_PATTERNS:
        if policy is RedactionPolicy.URL_AWARE and defn.url_filtered:
            redacted = _sub_with_url_filter(defn.regex, defn.replacement, redacted)
        else:
            redacted = defn.regex.sub(defn.replacement, redacted)

    redacted = _QUERY_REDACT_RE.sub(r"\1[REDACTED]=[REDACTED]", redacted)
    return redacted


# ---------------------------------------------------------------------------
# Public API: leak scanner (first-hit)
# ---------------------------------------------------------------------------


class LeakHit:
    """One matched leak pattern (immutable record).

    ``match_text`` is truncated by the caller before logging — this
    record carries the raw matched substring for the caller to
    summarize. The caller is responsible for not re-emitting the full
    secret in operator-visible logs.
    """

    __slots__ = ("match_text", "pattern_name")

    def __init__(self, pattern_name: str, match_text: str) -> None:
        self.pattern_name = pattern_name
        self.match_text = match_text

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LeakHit):
            return NotImplemented
        return self.pattern_name == other.pattern_name and self.match_text == other.match_text

    def __hash__(self) -> int:
        return hash((self.pattern_name, self.match_text))

    def __repr__(self) -> str:
        # Use ``!r`` on match_text so callers see the exact bytes when
        # debugging a leak-guard rejection.
        return f"LeakHit(pattern_name={self.pattern_name!r}, match_text={self.match_text!r})"


def scan_for_leak(text: str) -> LeakHit | None:
    """Return the first leak-shape match in ``text``, or ``None``.

    Iterates :data:`SECRET_PATTERNS` in declaration order, filtering to
    entries with ``include_in_leak_scan=True``. Patterns flagged
    ``url_filtered=True`` skip matches that lie inside an http(s) URL
    context (per :func:`is_in_url_context`). The first remaining match
    short-circuits — order in :data:`SECRET_PATTERNS` defines the
    pattern-name precedence visible to callers.
    """
    for defn in SECRET_PATTERNS:
        if not defn.include_in_leak_scan:
            continue
        for match in defn.regex.finditer(text):
            if defn.url_filtered and is_in_url_context(match.start(), text):
                continue
            return LeakHit(pattern_name=defn.name, match_text=match.group())
    return None


__all__ = [
    "SECRET_ENV_VARS",
    "SECRET_PATTERNS",
    "LeakHit",
    "RedactionPolicy",
    "is_in_url_context",
    "redact_text",
    "scan_for_leak",
]
