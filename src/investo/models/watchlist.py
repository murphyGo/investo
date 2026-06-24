"""Shared watchlist DTOs used by publisher and visual surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

from investo.models.items import NormalizedItem

DEFAULT_BUNDLE_BADGE_LABEL: Final[str] = "기본 바스켓"

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
PublicWatchlistGroup = Literal["direct", "related", "uncertain", "rejected"]
ImpactGroup = Literal["direct", "related", "uncertain", "rejected"]
RejectReason = Literal[
    "short-ticker-boundary",
    "conflicting-symbol",
    "no-source-evidence",
]


@dataclass(frozen=True, slots=True)
class WatchlistMatch:
    """One item matched by one watchlist term."""

    term: str
    kind: WatchlistTermKind
    item: NormalizedItem
    matched_alias: str | None = None
    confidence: Literal["structured", "strict", "alias", "text"] = "text"
    reason: str = "text"
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


@dataclass(frozen=True, slots=True)
class RejectedCandidate:
    """A configured term that resembled an item but was suppressed."""

    term: str
    kind: WatchlistTermKind
    token: str
    source_name: str
    reason: RejectReason
    title_hash: str

    def redacted_line(self) -> str:
        return f"{self.term} ⊘ {self.token} [{self.reason}] · {self.source_name} #{self.title_hash}"


@dataclass(frozen=True, slots=True)
class WatchlistImpactCenter:
    """Daily impact center grouped into public and diagnostic buckets."""

    configured: bool
    direct: tuple[WatchlistMatch, ...] = ()
    related: tuple[WatchlistMatch, ...] = ()
    uncertain: tuple[WatchlistMatch, ...] = ()
    rejected: tuple[RejectedCandidate, ...] = ()
    status: WatchlistImpactStatus = "matched"
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_public_impacts(self) -> bool:
        return bool(self.direct or self.related)

    @property
    def has_diagnostics(self) -> bool:
        return bool(self.uncertain or self.rejected)

    def public_matches(self) -> tuple[WatchlistMatch, ...]:
        return (*self.direct, *self.related)


def public_watchlist_match_label(
    match: WatchlistMatch,
    *,
    group: PublicWatchlistGroup,
) -> str:
    """Reader-safe label for a watchlist match group."""
    if group == "direct":
        return "직접 관련"
    if group == "related":
        return "관련 맥락"
    if group == "uncertain":
        return "관심 목록 보류"
    return "진단 전용"


def public_watchlist_match_group(match: WatchlistMatch) -> PublicWatchlistGroup:
    """Best-effort public group inference for legacy watchlist-impact callers."""
    if match.confidence == "structured":
        return "direct"
    if match.confidence in ("strict", "alias") and match.kind in ("ticker", "asset"):
        return "direct"
    if match.kind in ("sector", "keyword"):
        return "related"
    return "uncertain"


def public_watchlist_match_summary(
    match: WatchlistMatch,
    *,
    group: PublicWatchlistGroup,
) -> str:
    """Reader-safe one-line summary without raw matcher reason or alias metadata."""
    label = public_watchlist_match_label(match, group=group)
    title = match.item.title.strip()
    if len(title) > 120:
        title = title[:117].rstrip() + "…"
    return f"{match.term}: {label} · [{match.item.source_name}] {title}"


__all__ = [
    "DEFAULT_BUNDLE_BADGE_LABEL",
    "CoverageStatusInput",
    "ImpactGroup",
    "PublicWatchlistGroup",
    "RejectReason",
    "RejectedCandidate",
    "WatchlistChannel",
    "WatchlistImpact",
    "WatchlistImpactCenter",
    "WatchlistImpactStatus",
    "WatchlistMatch",
    "WatchlistTermKind",
    "public_watchlist_match_group",
    "public_watchlist_match_label",
    "public_watchlist_match_summary",
]
