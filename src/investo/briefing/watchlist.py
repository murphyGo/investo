"""Lightweight watchlist relevance helpers for u18."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from investo.models import NormalizedItem

WatchlistTermKind = Literal["ticker", "asset", "sector", "keyword"]

DEFAULT_WATCHLIST_PATH: Final[Path] = Path("config/watchlist.json")
_MAX_RENDERED_MATCHES: Final[int] = 3


class WatchlistConfig(BaseModel):
    """Non-secret personal relevance config."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tickers: tuple[str, ...] = Field(default_factory=tuple)
    assets: tuple[str, ...] = Field(default_factory=tuple)
    sectors: tuple[str, ...] = Field(default_factory=tuple)
    keywords: tuple[str, ...] = Field(default_factory=tuple)

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

    @property
    def is_configured(self) -> bool:
        return bool(self.tickers or self.assets or self.sectors or self.keywords)


@dataclass(frozen=True, slots=True)
class WatchlistMatch:
    """One item matched by one watchlist term."""

    term: str
    kind: WatchlistTermKind
    item: NormalizedItem


@dataclass(frozen=True, slots=True)
class WatchlistImpact:
    """Computed relevance summary for a briefing input set."""

    configured: bool
    matches: tuple[WatchlistMatch, ...]

    @property
    def has_matches(self) -> bool:
        return bool(self.matches)


def load_watchlist(path: Path = DEFAULT_WATCHLIST_PATH) -> WatchlistConfig:
    """Load watchlist config from JSON. Missing file means empty config."""
    if not path.exists():
        return WatchlistConfig()
    with path.open(encoding="utf-8") as fp:
        payload = json.load(fp)
    return WatchlistConfig.model_validate(payload)


def match_watchlist_items(
    items: Sequence[NormalizedItem],
    config: WatchlistConfig,
) -> WatchlistImpact:
    if not config.is_configured:
        return WatchlistImpact(configured=False, matches=())

    matches: list[WatchlistMatch] = []
    seen: set[tuple[str, str, str, str]] = set()
    term_groups: tuple[tuple[WatchlistTermKind, tuple[str, ...]], ...] = (
        ("ticker", config.tickers),
        ("asset", config.assets),
        ("sector", config.sectors),
        ("keyword", config.keywords),
    )
    for item in items:
        text = _item_text(item)
        for kind, terms in term_groups:
            for term in terms:
                if not _matches_term(term, text):
                    continue
                dedupe_key = (kind, term.casefold(), item.source_name, item.title)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                matches.append(WatchlistMatch(term=term, kind=kind, item=item))

    return WatchlistImpact(configured=True, matches=tuple(matches))


def render_watchlist_impact(impact: WatchlistImpact) -> str:
    """Render a concise reader-facing watchlist impact line."""
    if not impact.configured:
        return "관심 목록 미설정 — `config/watchlist.json`을 추가하면 관련 항목을 표시합니다."
    if not impact.matches:
        return "관심 목록과 직접 연결된 수집 항목 없음 — 영향은 별도로 단정하지 않습니다."

    rendered = []
    for match in impact.matches[:_MAX_RENDERED_MATCHES]:
        rendered.append(f"{match.term}: {match.item.title}")
    suffix = "" if len(impact.matches) <= _MAX_RENDERED_MATCHES else " 외"
    return f"{len(impact.matches)}건 확인 — " + "; ".join(rendered) + suffix


def render_watchlist_prompt_context(impact: WatchlistImpact) -> str:
    if not impact.configured:
        return ""
    if not impact.matches:
        return (
            "Watchlist relevance: no collected item directly matched the configured "
            "watchlist. Do not invent personal impact."
        )
    lines = ["Watchlist relevance: highlight these matched collected items first."]
    for match in impact.matches[:_MAX_RENDERED_MATCHES]:
        lines.append(
            f"- {match.term} ({match.kind}) matched [{match.item.source_name}] {match.item.title}"
        )
    return "\n".join(lines)


def _item_text(item: NormalizedItem) -> str:
    return f"{item.source_name} {item.category} {item.title} {item.summary or ''}".casefold()


def _matches_term(term: str, text: str) -> bool:
    normalized = term.casefold()
    if term.isascii() and term.replace("-", "").isalnum():
        pattern = rf"(?<![A-Za-z0-9]){re.escape(normalized)}(?![A-Za-z0-9])"
        return re.search(pattern, text) is not None
    return normalized in text


__all__ = [
    "DEFAULT_WATCHLIST_PATH",
    "WatchlistConfig",
    "WatchlistImpact",
    "WatchlistMatch",
    "WatchlistTermKind",
    "load_watchlist",
    "match_watchlist_items",
    "render_watchlist_impact",
    "render_watchlist_prompt_context",
]
