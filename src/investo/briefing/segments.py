"""Market-segment routing for u7 segmented briefings."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal

from investo._internal.source_outcomes import (
    SegmentScopedOutcomes,
    scope_source_outcomes,
    segment_source_outcomes,
)
from investo._internal.source_specs import (
    SourceItemRouting,
    source_names_for_item_routing,
    source_names_for_item_segment,
    source_names_for_outcome_segment,
)
from investo.briefing._text.patterns import (
    CRYPTO_TICKER_PAIR as _CRYPTO_TICKER_RE,
)
from investo.briefing._text.patterns import (
    KOREAN_EXCHANGE_TICKER as _KOREAN_EXCHANGE_TICKER,
)
from investo.briefing._text.patterns import (
    US_TICKER as _US_TICKER,
)
from investo.models import Category, NormalizedItem, SourceOutcome
from investo.models.macro import is_required_macro_actual, macro_event_status
from investo.models.segments import (
    CATEGORY_LABELS,
    COVERAGE_REASON_LABELS,
    COVERAGE_STATUS_LABELS,
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    SEVERITY_READER_EXPLANATIONS,
    US_EQUITY,
    CoverageReasonCode,
    CoverageStatus,
    MarketSegment,
    SegmentCoverage,
)

# u43 — registry of lookahead-aware adapters. Only adapters listed here
# have the ability to emit forward-scheduled items
# (``NormalizedItem.scheduled_at is not None``); the
# ``LOOKAHEAD_DATA_MISSING`` reason fires only when at least one of
# these adapters is mapped to the segment via the source allow-list.
# Adding a new lookahead adapter requires adding it here so the reason
# code starts firing on its segment(s).
LOOKAHEAD_AWARE_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "fomc-calendar",
        "fred-economic-calendar",
        "nasdaq-earnings-calendar",
        "treasury-auctions",
    }
)
_MISSING_CATEGORY_TO_REASON: Final[dict[Category, CoverageReasonCode]] = {
    "news": "MISSING_NEWS",
    "price": "MISSING_PRICE",
    "macro": "MISSING_MACRO",
    "calendar": "MISSING_CALENDAR",
    "earnings": "MISSING_EARNINGS",
}
_QUIET_ZERO_SOURCES: Final[frozenset[str]] = frozenset({"dart-disclosure"})

SEGMENT_THRESHOLDS: Final[dict[MarketSegment, int]] = {
    DOMESTIC_EQUITY: 3,
    US_EQUITY: 3,
    CRYPTO: 2,
}
SEGMENT_REQUIRED_CATEGORIES: Final[dict[MarketSegment, tuple[Category, ...]]] = {
    DOMESTIC_EQUITY: ("news", "price"),
    US_EQUITY: ("news", "price"),
    CRYPTO: ("news", "price"),
}
# u54 — Frozen "core" sources whose health drives severity downgrades.
# Membership policy:
#   - domestic-equity: 1 required source. ``fsc-krx-index-price``
#     failed/zero ⇒ no ``normal`` possible (single canonical KRX index
#     feed today; ``krx-foreign-flows`` is narrative-critical but not
#     core, so it drives ``partial`` not ``limited``).
#   - us-equity: 2 listed sources, **at-least-one** must be ``ok`` for
#     ``normal``. Both failed/zero ⇒ ``limited``. Both ``failed`` and
#     summed item_count = 0 ⇒ ``failed``.
#   - crypto: CoinGecko + Stooq are core. Binance remains collected when
#     reachable, but GitHub Actions runners regularly receive HTTP 451, so it
#     must not be the source that downgrades otherwise usable crypto coverage.
SEGMENT_CORE_SOURCES: Final[dict[MarketSegment, frozenset[str]]] = {
    DOMESTIC_EQUITY: frozenset({"fsc-krx-index-price"}),
    US_EQUITY: frozenset({"yfinance-price", "stooq-price"}),
    CRYPTO: frozenset({"coingecko-price", "stooq-price"}),
}
SEGMENT_MACRO_ACTUAL_SOURCES: Final[dict[MarketSegment, frozenset[str]]] = {
    DOMESTIC_EQUITY: frozenset({"krx-foreign-flows"}),
    US_EQUITY: frozenset(
        {
            "bea-macro-actuals",
            "bls-macro-actuals",
            "cboe-volatility-indices",
            "cftc-cot-positioning",
            "eia-petroleum-weekly",
            "fred-macro",
            "nyfed-reference-rates",
            "treasury-rates",
        }
    ),
    CRYPTO: frozenset({"defillama-market-structure", "treasury-rates"}),
}

# u54 — Per-segment staleness window for core price sources. If a core
# source's ``latest_item_at`` is older than ``now - window``, severity
# is forced ≥ ``limited``. Windows are intentionally generous to absorb
# weekend / overnight gaps in market data.
#   - us-equity: 30h (covers KST Mon-after-weekend gap).
#   - domestic-equity: 30h (KST overnight + weekend tolerance).
#   - crypto: 6h (24/7 market, expect fresh).
SEGMENT_CORE_STALENESS_WINDOW: Final[dict[MarketSegment, timedelta]] = {
    DOMESTIC_EQUITY: timedelta(hours=30),
    US_EQUITY: timedelta(hours=30),
    CRYPTO: timedelta(hours=6),
}

# u45 — Source allow-lists are split into single-segment vs shared.
#
# A source listed in exactly one ``_*_ONLY_SOURCES`` set is *anchored* to
# that segment; ``segment_items()`` will route its items to that segment
# only (never duplicate). A source listed in
# ``_SHARED_SOURCES_BY_SEGMENT`` is intentionally fan-out across the
# named segments — today only ``treasury-rates`` (UST curve narrative
# matters for both us-equity and crypto liquidity discussion). Adding a
# new shared source means: (a) register it explicitly here and (b) bump
# the regression test in ``test_segments_exclusivity.py``.
_DOMESTIC_ONLY_SOURCES: Final[frozenset[str]] = source_names_for_item_segment(
    DOMESTIC_EQUITY,
    routing="single-segment",
)
_US_ONLY_SOURCES: Final[frozenset[str]] = source_names_for_item_segment(
    US_EQUITY,
    routing="single-segment",
) | source_names_for_item_routing("us-with-crypto-signal")
_CRYPTO_ONLY_SOURCES: Final[frozenset[str]] = source_names_for_item_segment(
    CRYPTO,
    routing="single-segment",
)
_SHARED_SOURCES_BY_SEGMENT: Final[dict[MarketSegment, frozenset[str]]] = {
    DOMESTIC_EQUITY: source_names_for_item_segment(DOMESTIC_EQUITY, routing="shared-segments"),
    US_EQUITY: source_names_for_item_segment(US_EQUITY, routing="shared-segments"),
    CRYPTO: source_names_for_item_segment(CRYPTO, routing="shared-segments"),
}


def _single_source_for_routing(routing: SourceItemRouting) -> str:
    sources = source_names_for_item_routing(routing)
    if len(sources) != 1:
        raise RuntimeError(f"expected exactly one {routing} source, got {sorted(sources)}")
    return next(iter(sources))


_CFTC_POSITIONING_SOURCE: Final[str] = _single_source_for_routing("cftc-contract-group")
_CFTC_US_GROUPS: Final[frozenset[str]] = frozenset(
    {"equity_index", "volatility", "rates", "fx", "energy", "metals"}
)
_CFTC_CRYPTO_GROUPS: Final[frozenset[str]] = frozenset({"crypto"})

# Backward-compatible aggregate views — the union of single + shared
# membership for each segment. Consumers (e.g.
# :func:`segment_source_outcomes`, watchlist routing) keep using these.
_DOMESTIC_SOURCES: Final[frozenset[str]] = (
    _DOMESTIC_ONLY_SOURCES | _SHARED_SOURCES_BY_SEGMENT["domestic-equity"]
)
_US_SOURCES: Final[frozenset[str]] = _US_ONLY_SOURCES | _SHARED_SOURCES_BY_SEGMENT["us-equity"]
_CRYPTO_SOURCES: Final[frozenset[str]] = _CRYPTO_ONLY_SOURCES | _SHARED_SOURCES_BY_SEGMENT["crypto"]
_OUTCOME_EXTRA_SOURCES_BY_SEGMENT: Final[dict[MarketSegment, frozenset[str]]] = {
    "domestic-equity": source_names_for_outcome_segment(DOMESTIC_EQUITY) - _DOMESTIC_SOURCES,
    "us-equity": source_names_for_outcome_segment(US_EQUITY) - _US_SOURCES,
    # ``stooq-price`` is a mixed US/crypto snapshot adapter. Routing remains
    # title-driven in ``segment_items()`` so US tickers do not leak into
    # crypto, but the aggregate source outcome is relevant to crypto coverage
    # because the adapter also emits BTC-USD / ETH-USD rows.
    "crypto": source_names_for_outcome_segment(CRYPTO) - _CRYPTO_SOURCES,
}
_SEGMENT_SOURCES: Final[dict[MarketSegment, frozenset[str]]] = {
    "domestic-equity": _DOMESTIC_SOURCES | _OUTCOME_EXTRA_SOURCES_BY_SEGMENT["domestic-equity"],
    "us-equity": _US_SOURCES | _OUTCOME_EXTRA_SOURCES_BY_SEGMENT["us-equity"],
    "crypto": _CRYPTO_SOURCES | _OUTCOME_EXTRA_SOURCES_BY_SEGMENT["crypto"],
}
# u79 — ``_KOREAN_EXCHANGE_TICKER`` / ``_US_TICKER`` / ``_CRYPTO_TICKER_RE``
# now single-sourced in :mod:`investo.briefing._text.patterns`; imported at
# module top under their historic local aliases so the routing logic below
# is unchanged.
_US_MARKET_TERMS: Final[tuple[str, ...]] = (
    "dow",
    "federal reserve",
    "fomc",
    "nasdaq",
    "nyse",
    "s&p 500",
    "sec ",
    "treasury",
    "vix",
)
_CRYPTO_TERMS: Final[tuple[str, ...]] = (
    "bitcoin",
    "btc",
    "crypto",
    "defi",
    "ethereum",
    "eth",
    "solana",
    "stablecoin",
    "token",
)
_CRYPTO_CROSS_MARKET_TERMS: Final[tuple[str, ...]] = (
    "liquidity",
    "rate",
    "risk asset",
    "treasury",
)

_THRESHOLD_EXCLUDED_SOURCES: Final[frozenset[str]] = frozenset(
    {
        # Static reference/context sources improve provenance and factual
        # grounding, but should not make sparse live coverage look normal.
        "nasdaq-symbol-directory",
        "sec-company-facts",
    }
)

# u45 — strong crypto signal (used to *move* a us-only-source item to
# crypto when the body is unambiguously crypto-narrative). Three
# independent triggers, all checked case-insensitively against title /
# body:
#
#  1. Title starts with one of the canonical crypto tokens (English).
#  2. ``BTC`` or ``ETH`` ticker present as ASCII word boundary anywhere
#     in title or summary.
#  3. Title carries an explicit price-phrase substring (handles cases
#     such as "Bitcoin and ethereum prices today" where (1) still
#     matches but the ETH part would not).
#
# The prefix regex assumes English titles. Korean-language crypto news
# sources do not exist in the registry today; if one is added (e.g.
# 한경코인) the prefix list needs Korean tokens too — see DEBT note in
# ``aidlc-docs/construction/u45-segment-routing-exclusivity/code/summary.md``.
_CRYPTO_TITLE_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(bitcoin|ethereum|btc|eth|crypto|stablecoin|defi)\b",
    re.IGNORECASE,
)
_CRYPTO_PRICE_PHRASES: Final[tuple[str, ...]] = (
    "bitcoin price",
    "ethereum price",
    "btc price",
    "eth price",
    "bitcoin and ethereum",
)


@dataclass(frozen=True, slots=True)
class SegmentedItems:
    """Items routed to each market segment."""

    domestic_equity: tuple[NormalizedItem, ...]
    us_equity: tuple[NormalizedItem, ...]
    crypto: tuple[NormalizedItem, ...]

    def for_segment(self, segment: MarketSegment) -> tuple[NormalizedItem, ...]:
        if segment == DOMESTIC_EQUITY:
            return self.domestic_equity
        if segment == US_EQUITY:
            return self.us_equity
        return self.crypto

    def is_data_limited(self, segment: MarketSegment) -> bool:
        """Return True when the routed segment is below the ``normal`` bar.

        Structural-only judgement — decided purely from the routed item
        count and missing required categories. Source-level outcomes
        (``SOURCE_FAILED`` / ``SOURCE_ZERO``) surface in
        :attr:`SegmentCoverage.reason_codes` for transparency but do
        **not** influence this routing decision; a segment with all
        required items can still carry a ``SOURCE_FAILED`` reason and
        will still report ``is_data_limited == False``.
        """
        return self.coverage_for_segment(segment).status != "normal"

    def coverage_for_segment(
        self,
        segment: MarketSegment,
        *,
        source_outcomes: Sequence[SourceOutcome] = (),
        body_used_count: int = 0,
        now_utc: datetime | None = None,
        macro_sensitive_claim_made: bool = False,
    ) -> SegmentCoverage:
        return build_segment_coverage(
            segment,
            self.for_segment(segment),
            source_outcomes=segment_source_outcomes(segment, source_outcomes),
            body_used_count=body_used_count,
            now_utc=now_utc,
            macro_sensitive_claim_made=macro_sensitive_claim_made,
        )


MacroActualHealthStatus = Literal["not_required", "ok", "missing", "zero", "failed", "stale"]


@dataclass(frozen=True, slots=True)
class MacroActualHealth:
    """Segment-scoped macro actual health.

    The resolver is intentionally separate from core price/news
    coverage: missing macro actuals become severity input only when the
    segment made a macro-sensitive claim or carried an explicit
    required macro actual.
    """

    status: MacroActualHealthStatus
    reason_code: CoverageReasonCode | None = None

    @property
    def affects_severity(self) -> bool:
        return self.reason_code in {
            "MACRO_ACTUAL_MISSING",
            "MACRO_ACTUAL_ZERO",
            "MACRO_ACTUAL_FAILED",
            "MACRO_ACTUAL_STALE",
        }


def segment_items(items: Sequence[NormalizedItem]) -> SegmentedItems:
    """Route source items into deterministic market segments.

    u45 — Routing is *priority-based and source-anchored*. A single item
    lands in at most one segment **unless** its source is registered in
    :data:`_SHARED_SOURCES_BY_SEGMENT` (today: ``treasury-rates``), in
    which case it fans out to every named shared segment. CFTC
    positioning is the exception: it is a multi-market source, but rows
    route by ``raw_metadata["contract_group"]`` so crypto futures never
    pollute US-equity evidence and equity/rates/commodity rows never
    pollute crypto evidence.

    Decision order (first match wins):

    1. **CFTC contract-group routing** — official positioning rows route
       by contract group.
    2. **Shared sources fan-out** — items from a shared source appear in
       every segment that registers it.
    3. **Single-segment crypto source** — anchored to crypto.
    4. **Single-segment domestic source** — anchored to domestic-equity.
    5. **Single-segment us-equity source** — anchored to us-equity, *but
       moved to crypto* if the title/body carries a strong crypto
       signal (closes Item #54 / #76 / #82 leak from 2026-05-08).
    6. **Keyword fallback** — for items whose source is in none of the
       allow-lists. Domestic ticker → domestic; strong crypto signal →
       crypto; us-equity ticker / market term → us-equity. Remaining
       orphans are dropped (preserves the existing "low-signal item is
       not surfaced" contract).

    The keyword-fallback path is the *only* place where
    ``_US_MARKET_TERMS`` (``federal reserve`` / ``fomc`` / ``treasury`` /
    ``sec ``) is allowed to anchor a us-equity entry — and only after a
    strong crypto signal has been ruled out. This is the structural fix
    for the dual-routing bug: a ``theblock-crypto`` item mentioning
    "SEC" never reaches the keyword path, so it cannot leak into
    us-equity.
    """
    domestic: list[NormalizedItem] = []
    us: list[NormalizedItem] = []
    crypto: list[NormalizedItem] = []
    buckets: dict[MarketSegment, list[NormalizedItem]] = {
        "domestic-equity": domestic,
        "us-equity": us,
        "crypto": crypto,
    }

    for item in items:
        text = _item_text(item)

        # 1) Multi-market CFTC rows route by contract group, not by source
        # name fan-out. This preserves segment evidence purity while the
        # source outcome remains visible to both US and crypto coverage.
        cftc_segment = _cftc_segment_for_item(item)
        if cftc_segment is not None:
            buckets[cftc_segment].append(item)
            continue

        # 2) Shared sources fan-out (intentional cross-routing).
        matched_shared = _matched_shared_segments(item.source_name)
        if matched_shared:
            for segment in matched_shared:
                buckets[segment].append(item)
            continue

        # u58 — official crypto-policy metadata is a crypto-routing
        # override. Legislative items often say "market structure" or
        # "Digital Asset" without BTC/ETH/price tokens, so source/title
        # keyword routing alone would under-recall them.
        if _has_crypto_policy_priority(item):
            crypto.append(item)
            continue

        # 3-5) Source-anchored single-segment routing.
        if item.source_name in _CRYPTO_ONLY_SOURCES:
            crypto.append(item)
            continue
        if item.source_name in _DOMESTIC_ONLY_SOURCES:
            domestic.append(item)
            continue
        if item.source_name in _US_ONLY_SOURCES:
            if _has_strong_crypto_signal(item):
                crypto.append(item)
            else:
                us.append(item)
            continue

        # 6) Keyword fallback for items whose source is in no allow-list.
        if _matches_domestic_keyword(item):
            domestic.append(item)
        elif _has_strong_crypto_signal(item):
            crypto.append(item)
        elif _matches_us_equity_keyword(item, text):
            us.append(item)
        elif _matches_crypto_keyword(text):
            crypto.append(item)
        # else: orphan — intentionally dropped.

    return SegmentedItems(
        domestic_equity=tuple(domestic),
        us_equity=tuple(us),
        crypto=tuple(crypto),
    )


def _matched_shared_segments(source_name: str) -> tuple[MarketSegment, ...]:
    """Return the deterministic segment tuple a shared source fans out to.

    Empty tuple when the source is not shared (callers fall through to
    single-segment / keyword routing). Order matches the natural
    segment ordering ``(domestic-equity, us-equity, crypto)`` to keep
    routing deterministic regardless of dict iteration order.
    """
    matched: list[MarketSegment] = []
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        if source_name in _SHARED_SOURCES_BY_SEGMENT[segment]:
            matched.append(segment)
    return tuple(matched)


def _cftc_segment_for_item(item: NormalizedItem) -> MarketSegment | None:
    if item.source_name != _CFTC_POSITIONING_SOURCE:
        return None
    group = item.raw_metadata.get("contract_group")
    if group in _CFTC_CRYPTO_GROUPS:
        return CRYPTO
    if group in _CFTC_US_GROUPS:
        return US_EQUITY
    return None


def _has_crypto_policy_priority(item: NormalizedItem) -> bool:
    return (
        item.raw_metadata.get("policy_priority") == "crypto_regulation"
        and item.raw_metadata.get("official_source") == "true"
    )


def build_segment_coverage(
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    *,
    source_outcomes: Sequence[SourceOutcome] = (),
    body_used_count: int = 0,
    now_utc: datetime | None = None,
    macro_sensitive_claim_made: bool = False,
) -> SegmentCoverage:
    """Build coverage for a routed segment.

    ``source_outcomes`` is the optional u22 hook. It must be segment-scoped:
    use :func:`scope_source_outcomes` / :func:`segment_source_outcomes` to
    derive the subset from a full :class:`investo.models.SourceCollectionReport`.
    A global mixed-segment outcome list raises ``ValueError`` here instead of
    leaking another segment's source status into reader-visible coverage.
    Reason codes are derived from both the routed item set (structural
    deficiencies) and the per-source outcomes (operational deficiencies); the
    resulting ``reason_codes`` tuple is deterministic and order-stable.

    u54 — ``status`` is the 4-tier severity (``normal`` / ``partial`` /
    ``limited`` / ``failed``). The decision is driven by *core source
    health* + structural deficiency + (optional) staleness, not by raw
    item count alone:

    * **failed** — all core sources in ``failed`` state, *or* zero
      items routed.
    * **limited** — at least one core source ``failed``, *or* all core
      sources are zero-item, *or* a core source's ``latest_item_at`` is
      older than the per-segment staleness window.
    * **partial** — core sources healthy but a required category is
      missing / routed items below threshold / a non-core source
      failed or returned zero.
    * **normal** — all of the above pass.

    ``now_utc`` (optional) enables the staleness check; legacy callers
    omit it and the staleness path is skipped.

    ``reason_codes`` is an *additional transparency signal*. It can
    carry ``SOURCE_FAILED`` / ``SOURCE_ZERO`` even when ``status ==
    "normal"`` (a non-core source flaked) — intended behaviour, not an
    inconsistency.
    """
    outcomes_tuple = tuple(_validate_segment_scoped_outcomes(segment, source_outcomes))
    categories = tuple(sorted({item.category for item in items}))
    source_count = len({item.source_name for item in items})
    required_categories = SEGMENT_REQUIRED_CATEGORIES[segment]
    missing_categories = tuple(
        category for category in required_categories if category not in categories
    )

    # Count split (AC-1).
    targeted_count = len(outcomes_tuple)
    succeeded_count = sum(1 for o in outcomes_tuple if o.status == "ok")
    zero_count = sum(1 for o in outcomes_tuple if o.status == "zero")
    failed_count = sum(1 for o in outcomes_tuple if o.status == "failed")

    # u54 — core source health + staleness inputs to the severity tree.
    core_set = SEGMENT_CORE_SOURCES.get(segment, frozenset())
    core_outcomes = tuple(o for o in outcomes_tuple if o.source_name in core_set)
    has_core_registered = bool(core_outcomes)
    failed_core_count = sum(1 for o in core_outcomes if o.status == "failed")
    zero_core_count = sum(1 for o in core_outcomes if o.status == "zero")
    ok_core_count = sum(1 for o in core_outcomes if o.status == "ok")
    all_core_failed = has_core_registered and failed_core_count == len(core_outcomes)
    all_core_bad = has_core_registered and ok_core_count == 0  # failed or zero or stale
    core_stale = _core_staleness_violated(segment, core_outcomes, now_utc=now_utc)
    macro_actual_health = resolve_macro_actual_health(
        segment,
        items,
        outcomes_tuple,
        macro_sensitive_claim_made=macro_sensitive_claim_made,
    )
    macro_actual_sources = SEGMENT_MACRO_ACTUAL_SOURCES.get(segment, frozenset())
    non_macro_zero_count = sum(
        1
        for outcome in outcomes_tuple
        if (
            outcome.status == "zero"
            and outcome.source_name not in macro_actual_sources
            and outcome.source_name not in _QUIET_ZERO_SOURCES
        )
    )
    news_zero_or_missing = "news" in missing_categories or non_macro_zero_count > 0

    status = _resolve_severity(
        segment=segment,
        items=items,
        has_core_registered=has_core_registered,
        all_core_failed=all_core_failed,
        failed_core_count=failed_core_count,
        all_core_bad=all_core_bad,
        zero_core_count=zero_core_count,
        core_stale=core_stale,
        macro_actual_health=macro_actual_health,
        missing_categories=missing_categories,
        news_zero_or_missing=news_zero_or_missing,
        outcomes=outcomes_tuple,
    )

    return SegmentCoverage(
        segment=segment,
        status=status,
        item_count=len(items),
        source_count=source_count,
        categories=categories,
        missing_categories=missing_categories,
        reason_codes=_derive_reason_codes(
            segment=segment,
            items=items,
            missing_categories=missing_categories,
            source_outcomes=outcomes_tuple,
            core_outcomes=core_outcomes,
            all_core_failed=all_core_failed,
            failed_core_count=failed_core_count,
            zero_core_count=zero_core_count,
            core_stale=core_stale,
            macro_actual_health=macro_actual_health,
        ),
        source_outcomes=outcomes_tuple,
        targeted_count=targeted_count,
        succeeded_count=succeeded_count,
        zero_count=zero_count,
        failed_count=failed_count,
        body_used_count=max(body_used_count, 0),
    )


def _resolve_severity(
    *,
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    has_core_registered: bool,
    all_core_failed: bool,
    failed_core_count: int,
    all_core_bad: bool,
    zero_core_count: int,
    core_stale: bool,
    macro_actual_health: MacroActualHealth,
    missing_categories: tuple[Category, ...],
    news_zero_or_missing: bool,
    outcomes: tuple[SourceOutcome, ...],
) -> CoverageStatus:
    """u54 — Deterministic severity decision tree (AC-2 / AC-3).

    Order of evaluation matters: the first matching condition wins, so
    the strictest case ("all core failed") fires before more permissive
    ones. Inputs are pre-computed booleans/counts to keep the body of
    this function readable as a truth table.

    Legacy compat: when *no* core sources are registered for the
    segment (e.g. unit-test segments with empty outcome tuples), the
    function falls back to the legacy item-count-driven tree so
    existing tests that build ``SegmentCoverage`` from items alone
    continue to compute the expected ``normal/partial/failed`` verdict.
    """
    # Item-count fallback (no outcomes wired) — preserves legacy
    # behaviour: zero items → failed (was ``insufficient``); below
    # threshold or missing required categories → partial; otherwise
    # → normal.
    if not has_core_registered:
        if not items:
            return "failed"
        if _threshold_item_count(items) < SEGMENT_THRESHOLDS[segment] or missing_categories:
            return "partial"
        return "normal"

    # Outcomes wired — full severity tree.
    # Row 1: every core source failed → failed (regardless of items).
    if all_core_failed:
        return "failed"
    # Row 1b: all routed outcomes failed and zero items → failed.
    if outcomes and all(o.status == "failed" for o in outcomes) and not items:
        return "failed"
    # Row 6 (item-zero terminal): no items routed → failed.
    if not items:
        return "failed"
    # Row 2: any core failed (but not all) → limited.
    if failed_core_count >= 1:
        return "limited"
    # Row 3: all core zero (none failed, none ok) → limited.
    if all_core_bad and zero_core_count == len(
        [o for o in outcomes if o.source_name in SEGMENT_CORE_SOURCES.get(segment, frozenset())]
    ):
        return "limited"
    # Staleness override: any core stale → ≥ limited.
    if core_stale:
        return "limited"
    # Macro actuals are a separate coverage axis from price/news core
    # data. They downgrade only after the resolver has established that
    # this segment actually needed macro actual support.
    if macro_actual_health.affects_severity:
        return "limited"
    # Row 4 / Row 5: news category missing or some source flaked, but
    # core healthy → partial.
    if missing_categories or news_zero_or_missing:
        return "partial"
    # Below structural threshold → partial.
    if _threshold_item_count(items) < SEGMENT_THRESHOLDS[segment]:
        return "partial"
    return "normal"


def _core_staleness_violated(
    segment: MarketSegment,
    core_outcomes: tuple[SourceOutcome, ...],
    *,
    now_utc: datetime | None,
) -> bool:
    """u54 — Return True when any core source's latest item is stale.

    ``now_utc=None`` disables the check (legacy callers). Sources with
    ``latest_item_at=None`` are skipped (no signal). When at least one
    core source has a fresh ``latest_item_at`` within the window, the
    segment is considered fresh even if a sibling is stale — staleness
    fires only when *every* core source with a populated timestamp is
    out of window.
    """
    if now_utc is None:
        return False
    window = SEGMENT_CORE_STALENESS_WINDOW.get(segment)
    if window is None:
        return False
    timed = [o for o in core_outcomes if o.latest_item_at is not None]
    if not timed:
        return False
    floor = now_utc - window
    stale = [o for o in timed if (o.latest_item_at is not None and o.latest_item_at < floor)]
    if not stale:
        return False
    fresh = [o for o in timed if (o.latest_item_at is not None and o.latest_item_at >= floor)]
    return not fresh


def core_staleness_window(segment: MarketSegment) -> timedelta:
    """Public accessor for the per-segment core staleness window."""
    return SEGMENT_CORE_STALENESS_WINDOW[segment]


def resolve_macro_actual_health(
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    source_outcomes: Sequence[SourceOutcome],
    *,
    macro_sensitive_claim_made: bool = False,
) -> MacroActualHealth:
    """Resolve macro actual health without making macro a core category.

    Missing/zero/failed macro actual sources are informational on normal
    days. They affect severity only when a required macro actual is
    present/stale or downstream analysis explicitly says the body made
    a macro-sensitive claim.
    """
    required_items = tuple(item for item in items if is_required_macro_actual(item))
    stale_required = any(macro_event_status(item) == "stale" for item in required_items)
    needs_macro_actual = macro_sensitive_claim_made or bool(required_items)
    if not needs_macro_actual:
        return MacroActualHealth("not_required")
    if stale_required:
        return MacroActualHealth("stale", "MACRO_ACTUAL_STALE")
    if any(macro_event_status(item) == "actual" for item in required_items):
        return MacroActualHealth("ok")

    macro_sources = SEGMENT_MACRO_ACTUAL_SOURCES.get(segment, frozenset())
    macro_outcomes = tuple(
        outcome for outcome in source_outcomes if outcome.source_name in macro_sources
    )
    if any(outcome.status == "failed" for outcome in macro_outcomes):
        return MacroActualHealth("failed", "MACRO_ACTUAL_FAILED")
    if macro_outcomes and all(outcome.status == "zero" for outcome in macro_outcomes):
        return MacroActualHealth("zero", "MACRO_ACTUAL_ZERO")
    if any(outcome.status == "ok" for outcome in macro_outcomes):
        return MacroActualHealth("ok")
    return MacroActualHealth("missing", "MACRO_ACTUAL_MISSING")


def filter_lookahead_items(
    items: Sequence[NormalizedItem],
) -> tuple[NormalizedItem, ...]:
    """u43 / DEBT-067 M3 — single-filter chokepoint for forward-scheduled items.

    Returns the subset of ``items`` whose ``scheduled_at`` is set
    (forward-looking events: FOMC meetings, earnings calendar entries,
    token unlocks). Both the briefing-side ``_render_lookahead_context_block``
    (Stage 2 prompt narrative) and the notifier-side
    ``_imminent_event_tag`` (Telegram D-N tag selector) consume the
    filter result derived from this single call so the two surfaces can
    never silently disagree about which forward items count as
    "lookahead". Adding a new criterion to "what counts as lookahead"
    happens here; both surfaces inherit the change automatically.
    """
    return tuple(item for item in items if item.scheduled_at is not None)


def _validate_segment_scoped_outcomes(
    segment: MarketSegment,
    outcomes: Sequence[SourceOutcome],
) -> SegmentScopedOutcomes:
    allow_list = _SEGMENT_SOURCES[segment]
    scoped = tuple(outcomes)
    offenders = tuple(
        outcome.source_name for outcome in scoped if outcome.source_name not in allow_list
    )
    if offenders:
        names = ", ".join(sorted(set(offenders)))
        raise ValueError(f"source outcomes not scoped to {segment}: {names}")
    return SegmentScopedOutcomes(scoped)


def _derive_reason_codes(
    *,
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    missing_categories: tuple[Category, ...],
    source_outcomes: Sequence[SourceOutcome],
    core_outcomes: tuple[SourceOutcome, ...] = (),
    all_core_failed: bool = False,
    failed_core_count: int = 0,
    zero_core_count: int = 0,
    core_stale: bool = False,
    macro_actual_health: MacroActualHealth | None = None,
) -> tuple[CoverageReasonCode, ...]:
    macro_health = macro_actual_health or MacroActualHealth("not_required")
    codes: list[CoverageReasonCode] = []
    if not items:
        codes.append("ZERO_ITEMS")
    elif _threshold_item_count(items) < SEGMENT_THRESHOLDS[segment]:
        codes.append("BELOW_THRESHOLD")
    for category in missing_categories:
        codes.append(_MISSING_CATEGORY_TO_REASON[category])
    if any(outcome.status == "failed" for outcome in source_outcomes):
        codes.append("SOURCE_FAILED")
    if any(
        outcome.status == "zero" and outcome.source_name not in _QUIET_ZERO_SOURCES
        for outcome in source_outcomes
    ):
        codes.append("SOURCE_ZERO")
    if _domestic_disclosure_quiet(segment, source_outcomes):
        codes.append("DOMESTIC_DISCLOSURE_QUIET")
    # u54 — core / staleness reasons, deterministic order.
    if all_core_failed:
        codes.append("ALL_FAILED")
    if failed_core_count >= 1:
        codes.append("CORE_FAILED")
    if core_outcomes and zero_core_count == len(core_outcomes):
        codes.append("CORE_ZERO")
    if core_stale:
        codes.append("CORE_STALE")
    if macro_health.reason_code is not None:
        codes.append(macro_health.reason_code)
    if _lookahead_data_missing(segment, items, source_outcomes):
        codes.append("LOOKAHEAD_DATA_MISSING")
    return tuple(codes)


def _threshold_item_count(items: Sequence[NormalizedItem]) -> int:
    return sum(1 for item in items if item.source_name not in _THRESHOLD_EXCLUDED_SOURCES)


def _domestic_disclosure_quiet(
    segment: MarketSegment,
    source_outcomes: Sequence[SourceOutcome],
) -> bool:
    if segment != DOMESTIC_EQUITY:
        return False
    return any(
        outcome.source_name == "dart-disclosure" and outcome.status == "zero"
        for outcome in source_outcomes
    )


def _lookahead_data_missing(
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    source_outcomes: Sequence[SourceOutcome],
) -> bool:
    """u43 — emit ``LOOKAHEAD_DATA_MISSING`` only under both conditions.

    Trigger conditions (both required):

    * **At least one lookahead-aware adapter was attempted for this
      segment.** Determined from ``source_outcomes``: any outcome whose
      ``source_name`` is in :data:`LOOKAHEAD_AWARE_SOURCES` and whose
      ``status`` is not absent (the aggregator records every registered
      adapter, so any present outcome counts as "attempted"). This
      anti-regression guard prevents the reason code from firing on a
      segment that simply has no lookahead-aware adapter registered.
    * **The segment routed zero forward-scheduled items.** A forward
      item is one with ``scheduled_at is not None``. The check looks
      at the items already routed to ``segment``, so the reason
      reflects what *this* segment will surface.

    Note: the ``segment`` argument is part of the helper's signature so
    callers cannot forget to scope the check; the actual filtering of
    ``source_outcomes`` and ``items`` to the segment must happen at the
    caller (mirroring how the enclosing :func:`_derive_reason_codes`
    receives pre-filtered inputs).
    """
    # ``segment`` is currently used only for the docstring contract; the
    # caller has pre-filtered both arguments to the segment scope. Keep
    # the parameter present so a future refactor can re-validate the
    # scope inside this helper without changing callers.
    del segment
    has_lookahead_aware_adapter = any(
        outcome.source_name in LOOKAHEAD_AWARE_SOURCES for outcome in source_outcomes
    )
    if not has_lookahead_aware_adapter:
        return False
    has_forward_item = any(item.scheduled_at is not None for item in items)
    return not has_forward_item


def _item_text(item: NormalizedItem) -> str:
    return f"{item.source_name} {item.title} {item.summary or ''}".lower()


def _has_strong_crypto_signal(item: NormalizedItem) -> bool:
    """Return True when title/summary unambiguously talk about crypto.

    Used by ``segment_items`` both as the override for us-only-source
    items and as the keyword-fallback crypto check. Three independent
    triggers (any one match → True): canonical token at the start of
    the title; ``BTC`` or ``ETH`` ticker as ASCII word-boundary; or one
    of the canonical price-phrase substrings in the lower-cased title.
    Body / summary participates only via the ticker check — narrative
    mentions of "bitcoin" deep in a us-equity recap should not flip the
    routing.
    """
    title = item.title or ""
    if _CRYPTO_TITLE_PREFIX_RE.match(title):
        return True
    title_lower = title.lower()
    if any(phrase in title_lower for phrase in _CRYPTO_PRICE_PHRASES):
        return True
    haystack = f"{title} {item.summary or ''}"
    return bool(_CRYPTO_TICKER_RE.search(haystack))


def _matches_domestic_keyword(item: NormalizedItem) -> bool:
    """Keyword-fallback domestic routing — Korean exchange ticker only."""
    return bool(_KOREAN_EXCHANGE_TICKER.search(f"{item.title} {item.summary or ''}"))


def _matches_us_equity_keyword(item: NormalizedItem, text: str) -> bool:
    """Keyword-fallback us-equity routing.

    Honours both the curated US ticker list and ``_US_MARKET_TERMS``.
    This path is reached only when the source is in no allow-list and
    the strong-crypto-signal check has already failed — so the
    ``federal reserve`` / ``fomc`` / ``sec `` / ``treasury`` keywords
    can no longer drag a crypto-source item into us-equity.
    """
    if _US_TICKER.search(f"{item.title} {item.summary or ''}"):
        return True
    return any(term in text for term in _US_MARKET_TERMS)


def _matches_crypto_keyword(text: str) -> bool:
    """Keyword-fallback crypto routing.

    Backstop for items missed by the strong-signal check (e.g. a body
    mention of ``stablecoin`` without a leading title token, or the
    ``_CRYPTO_CROSS_MARKET_TERMS + Fed`` combo). Reached only after the
    domestic / strong-crypto / us-equity branches have all declined,
    which means an item routed here cannot also land in us-equity in
    the same pass — closing the dual-routing path.
    """
    if any(term in text for term in _CRYPTO_TERMS):
        return True
    return any(term in text for term in _CRYPTO_CROSS_MARKET_TERMS) and (
        "fed" in text or "fomc" in text or "federal reserve" in text
    )


__all__ = [
    "CATEGORY_LABELS",
    "COVERAGE_REASON_LABELS",
    "COVERAGE_STATUS_LABELS",
    "CRYPTO",
    "DOMESTIC_EQUITY",
    "LOOKAHEAD_AWARE_SOURCES",
    "SEGMENT_CORE_SOURCES",
    "SEGMENT_CORE_STALENESS_WINDOW",
    "SEGMENT_LABELS",
    "SEGMENT_MACRO_ACTUAL_SOURCES",
    "SEGMENT_REQUIRED_CATEGORIES",
    "SEGMENT_THRESHOLDS",
    "SEVERITY_READER_EXPLANATIONS",
    "US_EQUITY",
    "CoverageReasonCode",
    "CoverageStatus",
    "MacroActualHealth",
    "MacroActualHealthStatus",
    "MarketSegment",
    "SegmentCoverage",
    "SegmentScopedOutcomes",
    "SegmentedItems",
    "build_segment_coverage",
    "core_staleness_window",
    "filter_lookahead_items",
    "resolve_macro_actual_health",
    "scope_source_outcomes",
    "segment_items",
    "segment_source_outcomes",
]
