"""Cross-unit data shapes for source coverage transparency (u22).

These types travel from the source aggregator through the orchestrator
into briefing / visuals so reader-facing surfaces can explain *why* a
market segment is normal / partial / limited / failed. Defining them here
keeps the project's module-boundary rule intact: only models is the
shared foundation; ``sources``, ``briefing`` and ``visuals`` cannot
import from each other.

Sanitization rules:

* :func:`sanitize_source_error_message` is the single chokepoint for
  failure-reason strings exposed publicly (markdown / SVG cards /
  operator alerts). The actual redaction policy + pattern set lives
  in :mod:`investo._internal.redaction` (u27 chokepoint); this
  function is the surface-specific wrapper that adds whitespace
  collapse + length capping for the SVG / markdown row layout.

* The dataclasses are frozen+slotted so a constructed outcome cannot
  be mutated to inject a secret after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Final, Literal

from investo._internal.redaction import RedactionPolicy, redact_text
from investo.models.items import Category, NormalizedItem

SourceStatus = Literal["ok", "zero", "failed"]

# u32 Step 1 — editorial source-tier classification. Carried on every
# :class:`SourceOutcome` so downstream surfaces (coverage badge, GHA
# Step Summary, briefing footer) can render a tier-mix without
# re-reading a registry. The default tier ``"B"`` matches the most
# common adapter (aggregator/news); the source aggregator stamps the
# editorial value from :mod:`investo.sources.tiers` at collection time.
SourceTier = Literal["S", "A", "B", "C"]

_CATEGORIES: Final[frozenset[str]] = frozenset({"news", "price", "macro", "calendar", "earnings"})
_SOURCE_STATUSES: Final[frozenset[str]] = frozenset({"ok", "zero", "failed"})
_SOURCE_TIERS: Final[frozenset[str]] = frozenset({"S", "A", "B", "C"})

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

    ``tier`` (u32 Step 1) is the editorial classification of the
    source: ``"S"`` for primary regulatory / exchange feeds,
    ``"A"`` for first-party / official feeds, ``"B"`` for reputable
    aggregator / news sources, ``"C"`` for miscellaneous. The
    aggregator stamps the value from
    :mod:`investo.sources.tiers` at collection time; legacy callers
    can omit the field and receive the default ``"B"`` (matches the
    common-case fallback in the registry).
    """

    source_name: str
    category: Category
    status: SourceStatus
    item_count: int = 0
    failure_reason: str | None = None
    transient: bool | None = None
    tier: SourceTier = "B"
    # u54 — Optional UTC timestamp of the latest emitted
    # ``NormalizedItem.published_at``/``scheduled_at``/``occurred_at``.
    # Core price adapters populate this so :func:`build_segment_coverage`
    # can apply the staleness override. ``None`` skips the check
    # (legacy / non-core adapters).
    latest_item_at: datetime | None = None
    # u92 — source-adapter wall-clock elapsed seconds. Optional so
    # legacy reports and tests constructed before u92 remain valid.
    elapsed_s: float | None = None

    def __post_init__(self) -> None:
        if self.category not in _CATEGORIES:
            raise ValueError("category must be one of news, price, macro, calendar, earnings")
        if self.status not in _SOURCE_STATUSES:
            raise ValueError("status must be one of ok, zero, failed")
        if self.tier not in _SOURCE_TIERS:
            raise ValueError("tier must be one of S, A, B, C")
        if self.item_count < 0:
            raise ValueError("item_count must be >= 0")
        if self.latest_item_at is not None and self.latest_item_at.utcoffset() is None:
            raise ValueError("latest_item_at must be timezone-aware")
        if self.elapsed_s is not None and (self.elapsed_s < 0 or not isfinite(self.elapsed_s)):
            raise ValueError("elapsed_s must be finite and >= 0")

        if self.status == "ok":
            if self.item_count <= 0:
                raise ValueError("ok outcome requires item_count > 0")
            if self.failure_reason is not None:
                raise ValueError("ok outcome forbids failure_reason")
            if self.transient is not None:
                raise ValueError("ok outcome forbids transient")
        elif self.status == "zero":
            if self.item_count != 0:
                raise ValueError("zero outcome requires item_count == 0")
            if self.failure_reason is not None:
                raise ValueError("zero outcome forbids failure_reason")
            if self.transient is not None:
                raise ValueError("zero outcome forbids transient")
        else:
            if self.item_count != 0:
                raise ValueError("failed outcome requires item_count == 0")
            if not self.failure_reason or not self.failure_reason.strip():
                raise ValueError("failed outcome requires failure_reason")
            if not isinstance(self.transient, bool):
                raise ValueError("failed outcome requires transient bool")

    @classmethod
    def ok(
        cls,
        source_name: str,
        category: Category,
        item_count: int,
        *,
        tier: SourceTier = "B",
        latest_item_at: datetime | None = None,
        elapsed_s: float | None = None,
    ) -> SourceOutcome:
        """Build an ``ok`` outcome from a non-zero item count."""
        if item_count <= 0:
            raise ValueError("ok outcome requires item_count > 0")
        return cls(
            source_name=source_name,
            category=category,
            status="ok",
            item_count=item_count,
            tier=tier,
            latest_item_at=latest_item_at,
            elapsed_s=elapsed_s,
        )

    @classmethod
    def zero(
        cls,
        source_name: str,
        category: Category,
        *,
        tier: SourceTier = "B",
        latest_item_at: datetime | None = None,
        elapsed_s: float | None = None,
    ) -> SourceOutcome:
        """Build a ``zero`` outcome — adapter ran successfully but emitted no items."""
        return cls(
            source_name=source_name,
            category=category,
            status="zero",
            tier=tier,
            latest_item_at=latest_item_at,
            elapsed_s=elapsed_s,
        )

    @classmethod
    def from_failure(
        cls,
        source_name: str,
        category: Category,
        *,
        message: str,
        transient: bool,
        tier: SourceTier = "B",
        latest_item_at: datetime | None = None,
        elapsed_s: float | None = None,
    ) -> SourceOutcome:
        """Build a ``failed`` outcome with the message pre-sanitized."""
        return cls(
            source_name=source_name,
            category=category,
            status="failed",
            failure_reason=sanitize_source_error_message(message),
            transient=transient,
            tier=tier,
            latest_item_at=latest_item_at,
            elapsed_s=elapsed_s,
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

    Delegates the redaction policy to
    :func:`investo._internal.redaction.redact_text` (u27 chokepoint —
    :data:`RedactionPolicy.STRICT`), which removes:

    * any current value of an env var in
      :data:`investo._internal.redaction.SECRET_ENV_VARS` (R13 — same
      policy as the GHA Step Summary writer + the visual provenance
      manifest sanitizer)
    * Telegram bot-token / chat-id shapes
    * GitHub PAT, AWS access key, JWT, email, Korean phone shapes
    * generic long base64 runs (OAuth / JWT / PAT shapes)
    * query string ``?key=value&...`` segments (which can carry API
      keys)

    On top of the chokepoint output this function adds two surface-
    specific transforms: whitespace collapse so the result fits one
    markdown row, and truncation to :data:`_MAX_REASON_CHARS`
    characters.

    Policy note — relationship to :mod:`investo.briefing.leak_guard`:
    this sanitizer targets reader-facing badge / SVG / markdown row
    surfaces and is intentionally **more aggressive** than the leak
    guard. ``leak_guard`` runs the same chokepoint under the
    URL_AWARE policy (to avoid false-positives on legitimate URL
    paths), whereas this function uses STRICT (which redacts long
    base64 runs unconditionally). The conservative policy is safe
    here because ``failure_reason`` text is a reader surface that
    does not need to preserve the URL itself — only enough context to
    say *what went wrong* — so erring on the side of redaction loses
    no signal a reader would act on.
    """
    text = redact_text(message, policy=RedactionPolicy.STRICT)
    text = " ".join(text.split())
    if len(text) > _MAX_REASON_CHARS:
        text = text[: _MAX_REASON_CHARS - 1].rstrip() + "…"
    return text


__all__ = [
    "SourceCollectionReport",
    "SourceOutcome",
    "SourceStatus",
    "SourceTier",
    "sanitize_source_error_message",
]
