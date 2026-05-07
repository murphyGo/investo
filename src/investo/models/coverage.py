"""Cross-unit data shapes for source coverage transparency (u22).

These types travel from the source aggregator through the orchestrator
into briefing / visuals so reader-facing surfaces can explain *why* a
market segment is normal / partial / insufficient. Defining them here
keeps the project's module-boundary rule intact: only models is the
shared foundation; ``sources``, ``briefing`` and ``visuals`` cannot
import from each other.

Sanitization rules:

* :func:`sanitize_source_error_message` is the single chokepoint for
  failure-reason strings exposed publicly (markdown / SVG cards /
  operator alerts). It scrubs current values of secret env vars (R13)
  plus secret-shaped tokens (Telegram bot/chat, OAuth/JWT/PAT, HTTP
  query strings). Outcomes constructed via :meth:`SourceOutcome.from_failure`
  are guaranteed to carry an already-sanitized ``failure_reason``.

* The dataclasses are frozen+slotted so a constructed outcome cannot
  be mutated to inject a secret after the fact.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Final, Literal

from investo.models.items import Category, NormalizedItem

SourceStatus = Literal["ok", "zero", "failed"]

# Secret-shaped patterns to scrub from any reason string. Mirrors the
# patterns enforced in ``__main__._redact_diagnostic_text`` (used for
# u17 GitHub Step Summary) so the same redaction policy applies whether
# the diagnostic surfaces in GHA or in a public archive page.
# The bot-token pattern uses ``(?<![\d:])`` instead of ``\b`` because the
# token may be preceded by ``bot`` (a word character) in URLs like
# ``https://api.telegram.org/bot1234:abc.../sendMessage``; a literal
# ``\b`` would not fire there. ``(?![:\w-])`` at the tail prevents
# overrun into trailing path segments.
_BOT_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\d:])\d{6,}:[A-Za-z0-9_-]{20,}(?![\w-])")
_CHAT_ID_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\w-])-?\d{7,}(?![\w-])")
# Generic long base64-ish runs; mirrors briefing.leak_guard's
# ``oauth_long_base64`` pattern so any string a leaked OAuth/JWT/PAT
# could match is masked. The 40-char floor keeps innocuous error text
# unaffected.
_LONG_BASE64_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
_QUERY_REDACT_RE: Final[re.Pattern[str]] = re.compile(r"(\?|&)([^=&\s]+)=([^&\s]+)")

# Env vars whose values must never appear in a public outcome. The
# orchestrator validates these at boot, and adapters read them at fetch
# time per R13.
_SECRET_ENV_VARS: Final[tuple[str, ...]] = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHANNEL_ID",
    "TELEGRAM_OPERATOR_CHAT_ID",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "FRED_API_KEY",
)

# Maximum length of the public-facing failure reason string. Anything
# longer is truncated with an ellipsis. Keeps SVG rendering predictable
# and prevents an unexpectedly large stderr from blowing up a markdown
# row.
_MAX_REASON_CHARS: Final[int] = 120


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    """One adapter's collection verdict for the run.

    ``status`` is a closed three-way enum; ``failure_reason`` is set
    only when ``status == "failed"`` and is always pre-sanitized via
    :func:`sanitize_source_error_message` (see
    :meth:`SourceOutcome.from_failure`).
    """

    source_name: str
    category: Category
    status: SourceStatus
    item_count: int = 0
    failure_reason: str | None = None
    transient: bool | None = None

    @classmethod
    def ok(cls, source_name: str, category: Category, item_count: int) -> SourceOutcome:
        """Build an ``ok`` outcome from a non-zero item count."""
        if item_count <= 0:
            raise ValueError("ok outcome requires item_count > 0")
        return cls(source_name=source_name, category=category, status="ok", item_count=item_count)

    @classmethod
    def zero(cls, source_name: str, category: Category) -> SourceOutcome:
        """Build a ``zero`` outcome — adapter ran successfully but emitted no items."""
        return cls(source_name=source_name, category=category, status="zero")

    @classmethod
    def from_failure(
        cls,
        source_name: str,
        category: Category,
        *,
        message: str,
        transient: bool,
    ) -> SourceOutcome:
        """Build a ``failed`` outcome with the message pre-sanitized."""
        return cls(
            source_name=source_name,
            category=category,
            status="failed",
            failure_reason=sanitize_source_error_message(message),
            transient=transient,
        )


@dataclass(frozen=True, slots=True)
class SourceCollectionReport:
    """Aggregator output bundling items with per-source outcomes.

    ``items`` is the union returned by the legacy ``fetch_all``;
    ``outcomes`` is one entry per registered adapter, in registry
    order.
    """

    items: tuple[NormalizedItem, ...]
    outcomes: tuple[SourceOutcome, ...]

    @property
    def empty(self) -> bool:
        return not self.items

    def outcomes_for(self, source_names: frozenset[str]) -> tuple[SourceOutcome, ...]:
        """Filter outcomes to a subset by adapter ``name``."""
        return tuple(outcome for outcome in self.outcomes if outcome.source_name in source_names)


def sanitize_source_error_message(message: str) -> str:
    """Scrub secret-shaped substrings from a public-facing reason string.

    Removes:

    * any current value of the secret env vars listed in
      :data:`_SECRET_ENV_VARS` (R13 — same policy as the GHA Step
      Summary writer)
    * Telegram bot-token / chat-id shapes
    * generic long base64 runs (OAuth / JWT / PAT shapes)
    * query string ``?key=value&...`` segments (which can carry API keys)

    Also collapses whitespace so the result fits one markdown row, then
    truncates to :data:`_MAX_REASON_CHARS` characters.

    Policy note — relationship to :mod:`investo.briefing.leak_guard`:
    this sanitizer targets reader-facing badge / SVG / markdown row
    surfaces and is intentionally **more aggressive** than
    ``leak_guard``. ``leak_guard`` deliberately avoids matching long
    base64-ish runs that appear inside URL contexts (to dodge
    false-positives on legitimate URL paths), whereas this function
    redacts them unconditionally. The conservative policy is safe here
    because ``failure_reason`` text is a reader surface that does not
    need to preserve the URL itself — only enough context to say *what
    went wrong* — so erring on the side of redaction loses no signal a
    reader would act on.
    """
    text = message
    for env_var in _SECRET_ENV_VARS:
        value = os.environ.get(env_var, "").strip()
        if value:
            text = text.replace(value, "[REDACTED]")
    text = _BOT_TOKEN_RE.sub("[REDACTED_BOT_TOKEN]", text)
    text = _CHAT_ID_RE.sub("[REDACTED_CHAT_ID]", text)
    text = _LONG_BASE64_RE.sub("[REDACTED]", text)
    text = _QUERY_REDACT_RE.sub(r"\1[REDACTED]=[REDACTED]", text)
    text = " ".join(text.split())
    if len(text) > _MAX_REASON_CHARS:
        text = text[: _MAX_REASON_CHARS - 1].rstrip() + "…"
    return text


__all__ = [
    "SourceCollectionReport",
    "SourceOutcome",
    "SourceStatus",
    "sanitize_source_error_message",
]
