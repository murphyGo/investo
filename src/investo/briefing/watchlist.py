"""Lightweight watchlist relevance helpers (u18 + u28 usability foundation).

u28 introduces four behaviour deltas on top of the u18 baseline so first-time
users still see the feature exists and so noisy partial matches do not produce
false-confidence callouts:

1. Onboarding nudge — when ``WatchlistConfig`` is empty (``is_empty``), the
   site callout still renders an explicit "관심 목록 미설정" nudge while the
   Telegram surface stays clean (``render_watchlist_impact(channel="telegram")``
   returns an empty string for that branch).
2. Alias mapping — ``aliases`` (user-provided) is merged with a built-in
   ``DEFAULT_CORE_ALIASES`` bundle (BTC↔Bitcoin↔비트코인, ETH↔Ethereum↔이더리움,
   NVDA↔엔비디아 etc.) so a Korean user registering "BTC" also catches
   "Bitcoin" / "비트코인" mentions.
3. Korean word boundary — Hangul terms only match if the surrounding
   characters are NOT Hangul (so "삼성" no longer mis-fires on "삼성전자").
   Per-term ``exact_match_terms`` opts a term into strict equality matching.
4. Coverage branch — ``match_watchlist_items`` accepts ``coverage_status``;
   in ``limited`` / ``failed`` segments the caller renders "데이터 수집 부족으로 매칭
   판단 보류" instead of asserting absence.

Pure helpers — no I/O beyond the ``load_watchlist`` JSON read.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from investo.models import NormalizedItem

_logger = logging.getLogger(__name__)

WatchlistTermKind = Literal["ticker", "asset", "sector", "keyword"]
WatchlistImpactStatus = Literal[
    "unconfigured",
    "default_bundle",
    "matched",
    "no_match",
    "coverage_hold",
]
WatchlistChannel = Literal["site", "telegram"]
CoverageStatusInput = Literal["normal", "partial", "limited", "failed"]

DEFAULT_WATCHLIST_PATH: Final[Path] = Path("config/watchlist.json")
WATCHLIST_CONFIG_ENV: Final[str] = "INVESTO_WATCHLIST_CONFIG"
DEFAULT_BUNDLE_BADGE_LABEL: Final[str] = "기본 바스켓"
_SITE_MAX_RENDERED_MATCHES: Final[int] = 5
_TELEGRAM_MAX_RENDERED_MATCHES: Final[int] = 3

# Default alias bundle — keys are the canonical (display) term, values are
# additional surface forms scanned by the matcher when the user's config does
# not override the entry. Korean / English / common-name pairs the persona
# bundle calls out explicitly. Keys must match the casefold form the matcher
# normalises to (`BTC` → `btc`); values are matched verbatim post-casefold.
DEFAULT_CORE_ALIASES: Final[Mapping[str, tuple[str, ...]]] = {
    # crypto
    "BTC": ("Bitcoin", "비트코인"),
    "ETH": ("Ethereum", "이더리움"),
    "SOL": ("Solana", "솔라나"),
    # US mega-cap equity
    "NVDA": ("NVIDIA", "엔비디아"),
    "TSLA": ("Tesla", "테슬라"),
    "AAPL": ("Apple", "애플"),
    "MSFT": ("Microsoft", "마이크로소프트"),
    "GOOGL": ("Alphabet", "Google", "구글", "알파벳"),
    "META": ("Meta", "메타", "Facebook"),
    "AMZN": ("Amazon", "아마존"),
}

# Strict ASCII alphanumeric ticker / asset patterns (length ≥ 3) preserve the
# u18 word-boundary regex; length ≤ 2 inputs are routed through a stricter
# capitalize-only check (see ``_match_short_ticker``) to avoid false positives
# like "F" matching every word starting with F.
_SHORT_TICKER_THRESHOLD: Final[int] = 2

# Hangul ranges - Hangul Syllables (AC00-D7A3), Hangul Jamo (1100-11FF),
# Hangul Compatibility Jamo (3130-318F). Used to enforce a syllable-boundary
# heuristic so "삼성" does not match inside "삼성전자".
_HANGUL_CHAR_RE: Final[re.Pattern[str]] = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")


class WatchlistScope(BaseModel):
    """u33 Step 4 — a named sub-watchlist for sector / account scoping.

    Augments the root :class:`WatchlistConfig` term lists with a
    secondary set scoped to a subset of market segments. The matcher
    applies scope-level terms only when ``segments`` is empty (all
    segments) or contains the segment under consideration. Scope-level
    weights override the root weights for the same term.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tickers: tuple[str, ...] = Field(default_factory=tuple)
    assets: tuple[str, ...] = Field(default_factory=tuple)
    sectors: tuple[str, ...] = Field(default_factory=tuple)
    keywords: tuple[str, ...] = Field(default_factory=tuple)
    weights: dict[str, float] = Field(default_factory=dict)
    segments: tuple[str, ...] = Field(default_factory=tuple)


class WatchlistConfig(BaseModel):
    """Non-secret personal relevance config."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tickers: tuple[str, ...] = Field(default_factory=tuple)
    assets: tuple[str, ...] = Field(default_factory=tuple)
    sectors: tuple[str, ...] = Field(default_factory=tuple)
    keywords: tuple[str, ...] = Field(default_factory=tuple)
    # u28 — alias map. Keys are canonical surface terms; values are alternate
    # surface forms scanned alongside. User-provided aliases override the
    # default bundle entry by canonical key.
    aliases: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    # u28 — explicit per-term opt-in for strict equality (suppresses any
    # substring or boundary match). Stored casefolded.
    exact_match_terms: tuple[str, ...] = Field(default_factory=tuple)
    # u33 Step 1 — optional position weight per term. Maps the canonical
    # surface form (uppercased for ASCII tickers, raw for Korean / mixed
    # case keywords) to a non-negative float. Higher weight → higher
    # priority in rendered match callouts. Terms not present in this map
    # default to 0 (and sort *after* explicitly weighted terms; tie-
    # broken by alphabetical order). Pure metadata — no portfolio /
    # accounting / cost-basis logic, just a "what should I see first?"
    # hint that reuses already-collected items.
    weights: dict[str, float] = Field(default_factory=dict)
    # u33 Step 4 — named sub-watchlists for sector / account scoping.
    # Keys are arbitrary scope names (``"core"``, ``"semis"``, ``"long"``)
    # and values carry their own term lists + an optional segment
    # binding. The default (root) lists still apply across all
    # segments; scoped lists augment the root, never override.
    # ``segments`` filters scope-level matches to a subset of
    # market segments — empty / unset means "all segments".
    scopes: dict[str, WatchlistScope] = Field(default_factory=dict)
    is_default_bundle: bool = Field(default=False, exclude=True, repr=False)

    @field_validator("tickers", "assets", "sectors", "keywords")
    @classmethod
    def _normalize_terms(cls, value: tuple[str, ...], info: ValidationInfo) -> tuple[str, ...]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            term = raw.strip()
            if not term:
                continue
            key = term.casefold()
            if key in seen:
                continue
            seen.add(key)
            if info.field_name in {"tickers", "assets"} and term.isascii():
                term = term.upper()
            normalized.append(term)
        return tuple(normalized)

    @field_validator("aliases")
    @classmethod
    def _normalize_aliases(
        cls, value: dict[str, tuple[str, ...]] | dict[str, list[str]]
    ) -> dict[str, tuple[str, ...]]:
        normalized: dict[str, tuple[str, ...]] = {}
        for raw_key, raw_values in value.items():
            key = raw_key.strip()
            if not key:
                continue
            if key.isascii():
                key = key.upper()
            seen: set[str] = set()
            cleaned: list[str] = []
            for entry in raw_values:
                stripped = entry.strip()
                if not stripped:
                    continue
                fold = stripped.casefold()
                if fold in seen or fold == key.casefold():
                    continue
                seen.add(fold)
                cleaned.append(stripped)
            if cleaned:
                normalized[key] = tuple(cleaned)
        return normalized

    @field_validator("weights")
    @classmethod
    def _normalize_weights(cls, value: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for raw_key, raw_weight in value.items():
            key = raw_key.strip()
            if not key:
                continue
            if key.isascii():
                key = key.upper()
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError):
                continue
            if weight < 0:
                continue
            normalized[key] = weight
        return normalized

    @field_validator("exact_match_terms")
    @classmethod
    def _normalize_exact_match(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in value:
            stripped = raw.strip()
            if not stripped:
                continue
            fold = stripped.casefold()
            if fold in seen:
                continue
            seen.add(fold)
            out.append(fold)
        return tuple(out)

    @property
    def is_configured(self) -> bool:
        return bool(self.tickers or self.assets or self.sectors or self.keywords)

    def is_empty(self) -> bool:
        """True iff the user has not registered any term (alias-only is empty)."""
        return not self.is_configured

    @classmethod
    def from_default_bundle(cls) -> WatchlistConfig:
        """Return the Day-1 default bundle without writing config to disk."""
        return cls(tickers=tuple(DEFAULT_CORE_ALIASES), is_default_bundle=True)

    def for_segment_scope(self, segment: str | None) -> WatchlistConfig:
        """u33 Step 4 — merge applicable scopes into a flat config.

        Returns a new :class:`WatchlistConfig` containing the root
        terms + every scope whose ``segments`` is empty or contains
        ``segment``. Scope-level weights override the root weights
        for the same term. Aliases / exact_match_terms / scopes carry
        over from the root unchanged.
        """
        if not self.scopes:
            return self
        applicable: list[WatchlistScope] = []
        for scope in self.scopes.values():
            if not scope.segments or (segment is not None and segment in scope.segments):
                applicable.append(scope)
        if not applicable:
            return self
        merged_tickers = list(self.tickers)
        merged_assets = list(self.assets)
        merged_sectors = list(self.sectors)
        merged_keywords = list(self.keywords)
        merged_weights = dict(self.weights)
        for scope in applicable:
            for term in scope.tickers:
                if term not in merged_tickers:
                    merged_tickers.append(term)
            for term in scope.assets:
                if term not in merged_assets:
                    merged_assets.append(term)
            for term in scope.sectors:
                if term not in merged_sectors:
                    merged_sectors.append(term)
            for term in scope.keywords:
                if term not in merged_keywords:
                    merged_keywords.append(term)
            merged_weights.update(scope.weights)
        return WatchlistConfig.model_validate(
            {
                "tickers": tuple(merged_tickers),
                "assets": tuple(merged_assets),
                "sectors": tuple(merged_sectors),
                "keywords": tuple(merged_keywords),
                "aliases": dict(self.aliases),
                "exact_match_terms": tuple(self.exact_match_terms),
                "weights": merged_weights,
                # Don't pass `scopes` recursively — the merged config is
                # already flattened.
            }
        )

    def effective_aliases(self) -> dict[str, tuple[str, ...]]:
        """Merge built-in :data:`DEFAULT_CORE_ALIASES` with user overrides.

        User-provided ``aliases`` take precedence per canonical key. Returns a
        fresh dict so callers cannot mutate the cached defaults.
        """
        merged: dict[str, tuple[str, ...]] = dict(DEFAULT_CORE_ALIASES)
        for key, value in self.aliases.items():
            merged[key] = value
        return merged


@dataclass(frozen=True, slots=True)
class WatchlistMatch:
    """One item matched by one watchlist term."""

    term: str
    kind: WatchlistTermKind
    item: NormalizedItem
    matched_alias: str | None = None
    # u33 Step 1 — copied from ``WatchlistConfig.weights[term]`` at
    # match time. Defaults to 0.0 (term not weighted by user). Render
    # paths use this to sort match callouts so high-conviction
    # positions surface first.
    weight: float = 0.0


@dataclass(frozen=True, slots=True)
class WatchlistImpact:
    """Computed relevance summary for a briefing input set."""

    configured: bool
    matches: tuple[WatchlistMatch, ...]
    status: WatchlistImpactStatus = "matched"

    @property
    def has_matches(self) -> bool:
        return bool(self.matches)


def load_watchlist(path: Path | None = None) -> WatchlistConfig:
    """Load watchlist config from JSON.

    Missing / blank / unreadable / empty config activates the built-in
    default bundle so first-time users get useful ⑤ matches without creating a
    ``watchlist.json`` file.
    """
    path = _resolve_watchlist_path(path)
    if not path.exists():
        return _default_bundle_with_log("watchlist config not found")
    try:
        with path.open(encoding="utf-8") as fp:
            payload = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return _default_bundle_with_log("watchlist config unreadable")
    config = WatchlistConfig.model_validate(payload or {})
    if config.is_empty():
        return _default_bundle_with_log("watchlist config empty")
    return config


def match_watchlist_items(
    items: Sequence[NormalizedItem],
    config: WatchlistConfig,
    *,
    coverage_status: CoverageStatusInput | None = None,
) -> WatchlistImpact:
    """Match collected items against the user's watchlist config.

    ``coverage_status in {'limited', 'failed'}`` — the caller has signalled
    this segment has too little / unreliable core data to answer the "is my
    watchlist relevant?" question. The matcher returns a ``coverage_hold``
    impact so renderers can switch to the "데이터 수집 부족으로 매칭 판단
    보류" branch instead of asserting absence. u54 — legacy single-tier
    ``'insufficient'`` migrated to ``'failed'``; the new ``'limited'``
    tier (core source missing/stale) is *also* treated as hold because
    a watchlist judgement made on stale/missing core prices would
    mislead the reader.
    """
    if config.is_empty():
        return WatchlistImpact(configured=False, matches=(), status="unconfigured")

    if coverage_status in ("limited", "failed"):
        return WatchlistImpact(configured=True, matches=(), status="coverage_hold")

    aliases = config.effective_aliases()
    exact_match_set = set(config.exact_match_terms)

    matches: list[WatchlistMatch] = []
    seen: set[tuple[str, str, str, str]] = set()
    term_groups: tuple[tuple[WatchlistTermKind, tuple[str, ...]], ...] = (
        ("ticker", config.tickers),
        ("asset", config.assets),
        ("sector", config.sectors),
        ("keyword", config.keywords),
    )
    for item in items:
        text_cf = _item_text_casefold(item)
        text_raw = _item_text_raw(item)
        for kind, terms in term_groups:
            for term in terms:
                exact_only = term.casefold() in exact_match_set
                hit_term, hit_alias = _match_term_with_aliases(
                    term=term,
                    kind=kind,
                    aliases=aliases,
                    text_cf=text_cf,
                    text_raw=text_raw,
                    exact_only=exact_only,
                )
                if hit_term is None:
                    continue
                dedupe_key = (kind, term.casefold(), item.source_name, item.title)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                weight = config.weights.get(term.upper() if term.isascii() else term, 0.0)
                matches.append(
                    WatchlistMatch(
                        term=term,
                        kind=kind,
                        item=item,
                        matched_alias=hit_alias,
                        weight=weight,
                    )
                )

    # u33 Step 1 — high-weight matches surface first. Tie-break is
    # deterministic: alphabetical term casefold, then source name, then
    # title. We sort *after* matching so the dedup logic above still
    # walks items in collection order.
    matches.sort(key=lambda m: (-m.weight, m.term.casefold(), m.item.source_name, m.item.title))

    if config.is_default_bundle:
        if not matches:
            return WatchlistImpact(configured=False, matches=(), status="unconfigured")
        return WatchlistImpact(configured=True, matches=tuple(matches), status="default_bundle")

    status: WatchlistImpactStatus = "matched" if matches else "no_match"
    return WatchlistImpact(configured=True, matches=tuple(matches), status=status)


def render_watchlist_impact(
    impact: WatchlistImpact,
    *,
    channel: WatchlistChannel = "site",
    now_utc: datetime | None = None,
) -> str:
    """Render a concise reader-facing watchlist impact line.

    ``channel='site'`` (default) — first-viewport site callout. Caps rendering
    to 5 matches and emits the onboarding nudge when ``unconfigured``.
    ``channel='telegram'`` — Telegram suffix. Caps to 3 matches and returns
    an empty string for the unconfigured branch (u28: Telegram surface stays
    clean for first-time readers).

    u33 Step 2 — when ``now_utc`` is supplied, matches whose item has a
    ``scheduled_at`` within 7 days of ``now_utc`` get a ``D-N`` suffix
    appended to the term (e.g. ``NVDA D-3: NVDA earnings``). Past
    items remain unchanged (no negative D values).
    """
    cap = _SITE_MAX_RENDERED_MATCHES if channel == "site" else _TELEGRAM_MAX_RENDERED_MATCHES

    if impact.status == "unconfigured":
        if channel == "telegram":
            return ""
        return "관심 목록 미설정 — `config/watchlist.json`을 추가하면 보유 종목 영향이 표시됩니다."
    if impact.status == "coverage_hold":
        return "데이터 수집 부족으로 매칭 판단 보류 — 추가 수집 후 재평가됩니다."
    if not impact.matches:
        return "관심 목록과 직접 연결된 수집 항목 없음 — 영향은 별도로 단정하지 않습니다."

    rendered = []
    for match in impact.matches[:cap]:
        d_suffix = _watchlist_d_suffix(match, now_utc=now_utc)
        rendered.append(f"{match.term}{d_suffix}: {match.item.title}")
    suffix = "" if len(impact.matches) <= cap else " 외"
    badge = f" ({DEFAULT_BUNDLE_BADGE_LABEL})" if impact.status == "default_bundle" else ""
    return f"{len(impact.matches)}건 확인{badge} — " + "; ".join(rendered) + suffix


def _resolve_watchlist_path(path: Path | None) -> Path:
    if path is not None:
        return path
    raw_env = os.environ.get(WATCHLIST_CONFIG_ENV, "").strip()
    return Path(raw_env) if raw_env else DEFAULT_WATCHLIST_PATH


def _default_bundle_with_log(reason: str) -> WatchlistConfig:
    _logger.info("%s, using DEFAULT_CORE_ALIASES (%d terms)", reason, len(DEFAULT_CORE_ALIASES))
    return WatchlistConfig.from_default_bundle()


def _watchlist_d_suffix(match: WatchlistMatch, *, now_utc: datetime | None) -> str:
    """u33 Step 2 — render ``" D-N"`` for a forward-scheduled match item."""
    if now_utc is None:
        return ""
    scheduled = match.item.scheduled_at
    if scheduled is None:
        return ""
    delta = scheduled - now_utc
    if delta.total_seconds() < 0:
        return ""
    days = int(delta.total_seconds() // 86400)
    if days > 7:
        return ""
    return f" D-{days}"


def render_watchlist_prompt_context(impact: WatchlistImpact) -> str:
    if not impact.configured:
        return ""
    if impact.status == "coverage_hold":
        return (
            "Watchlist relevance: this segment has insufficient collected data; "
            "do not infer personal impact for the user's watchlist."
        )
    if not impact.matches:
        return (
            "Watchlist relevance: no collected item directly matched the configured "
            "watchlist. Do not invent personal impact."
        )
    lines = ["Watchlist relevance: highlight these matched collected items first."]
    for match in impact.matches[:_SITE_MAX_RENDERED_MATCHES]:
        lines.append(
            f"- {match.term} ({match.kind}) matched [{match.item.source_name}] {match.item.title}"
        )
    return "\n".join(lines)


def _item_text_casefold(item: NormalizedItem) -> str:
    return f"{item.source_name} {item.category} {item.title} {item.summary or ''}".casefold()


def _item_text_raw(item: NormalizedItem) -> str:
    """Original-case version used for short-ticker capitalize checks."""
    return f"{item.source_name} {item.category} {item.title} {item.summary or ''}"


def _match_term_with_aliases(
    *,
    term: str,
    kind: WatchlistTermKind,
    aliases: Mapping[str, tuple[str, ...]],
    text_cf: str,
    text_raw: str,
    exact_only: bool,
) -> tuple[str | None, str | None]:
    """Return ``(term, alias)`` if matched. ``alias`` is non-None only for
    alias hits. Canonical term hits short-circuit the alias scan (term wins).

    ``kind`` propagates to :func:`_matches_term` so short (≤2 ASCII) inputs
    branch correctly: ticker/asset stay case-sensitive (raw text) to avoid
    "F"→"for" false positives, while keyword/sector use casefolded
    word-boundary matching so "EV" matches lowercase "ev" in summaries.
    Aliases inherit the canonical term's ``kind``.
    """
    if _matches_term(term, kind=kind, text_cf=text_cf, text_raw=text_raw, exact_only=exact_only):
        return term, None
    if exact_only:
        return None, None
    canonical_key = term.upper() if term.isascii() else term
    alt_forms = aliases.get(canonical_key, ())
    for alt in alt_forms:
        if _matches_term(alt, kind=kind, text_cf=text_cf, text_raw=text_raw, exact_only=False):
            return term, alt
    return None, None


def _matches_term(
    term: str,
    *,
    kind: WatchlistTermKind,
    text_cf: str,
    text_raw: str,
    exact_only: bool,
) -> bool:
    """Check ``term`` against an item's text with u28 boundary heuristics.

    Branches:

    - exact_only — strict casefold equality on any whitespace-separated token.
    - ASCII alphanumeric, length > 2 — u18 word-boundary regex (no neighbour
      letters / digits).
    - ASCII alphanumeric, length ≤ 2, ticker/asset — capitalize guard: the
      original-case ticker must appear with non-alphanumeric boundaries in
      the raw text (suppresses "F" matching every "for"/"From" but preserves
      "F " or "(F)").
    - ASCII alphanumeric, length ≤ 2, keyword/sector — u28 fix: short
      keywords/sectors are semantic concepts, not exchange tickers, so they
      use the same casefolded word-boundary regex as longer terms (so "EV"
      matches "new ev launch").
    - Hangul / non-ASCII — substring match wrapped in a Hangul-syllable
      boundary check (no Hangul char immediately before or after).
    """
    if not term:
        return False
    normalized = term.casefold()

    if exact_only:
        # Match if any whitespace-separated token equals the term casefolded.
        return any(token.strip(".,!?;:()[]{}") == normalized for token in text_cf.split())

    if term.isascii() and term.replace("-", "").isalnum():
        if len(term) <= _SHORT_TICKER_THRESHOLD and kind in {"ticker", "asset"}:
            return _matches_short_ticker(term, text_raw)
        pattern = rf"(?<![A-Za-z0-9]){re.escape(normalized)}(?![A-Za-z0-9])"
        return re.search(pattern, text_cf) is not None

    return _matches_korean_term(normalized, text_cf)


def _matches_short_ticker(term: str, text_raw: str) -> bool:
    """Strict capitalize / boundary match for 1-2 character ASCII tickers.

    The token must appear with the original case (e.g. ``F``, ``T``, ``BA``)
    surrounded by non-alphanumeric characters in the raw text. This blocks
    common false positives like ``F`` matching ``For`` / ``From``.
    """
    pattern = rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
    return re.search(pattern, text_raw) is not None


def _matches_korean_term(term_cf: str, text_cf: str) -> bool:
    """Substring match with Hangul-syllable word-boundary heuristic.

    Defensive guard: empty ``term_cf`` returns False directly. Callers
    (``_matches_term``) already filter empty terms, but ``str.find("")``
    returns ``0`` for any text — the boundary check would then incorrectly
    succeed on an empty input. Pinning False here keeps the helper safe in
    isolation.
    """
    if not term_cf:
        return False
    start = 0
    term_len = len(term_cf)
    while True:
        idx = text_cf.find(term_cf, start)
        if idx < 0:
            return False
        before_ok = idx == 0 or not _HANGUL_CHAR_RE.match(text_cf[idx - 1])
        after_idx = idx + term_len
        after_ok = after_idx >= len(text_cf) or not _HANGUL_CHAR_RE.match(text_cf[after_idx])
        if before_ok and after_ok:
            return True
        start = idx + 1


__all__ = [
    "DEFAULT_BUNDLE_BADGE_LABEL",
    "DEFAULT_CORE_ALIASES",
    "DEFAULT_WATCHLIST_PATH",
    "WATCHLIST_CONFIG_ENV",
    "CoverageStatusInput",
    "WatchlistChannel",
    "WatchlistConfig",
    "WatchlistImpact",
    "WatchlistImpactStatus",
    "WatchlistMatch",
    "WatchlistTermKind",
    "load_watchlist",
    "match_watchlist_items",
    "render_watchlist_impact",
    "render_watchlist_prompt_context",
]
