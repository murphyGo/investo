"""Federal Reserve Board leadership fact adapter.

The adapter extracts the current Board chair from the Federal Reserve Board
Members page. It emits a normal ``NormalizedItem`` carrying structured fact
metadata so downstream briefing code can build a verified fact bundle without
asking the LLM to infer officeholders from memory.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from html.parser import HTMLParser
from typing import ClassVar, Final

import httpx

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_USER_AGENT: Final[str] = "Investo/1.0 (+https://murphygo.github.io/investo)"
_ENDPOINT: Final[str] = "https://www.federalreserve.gov/aboutthefed/bios/board/default.htm"
_ROLE: Final[str] = "Chairman, Board of Governors of the Federal Reserve System"
_KOREAN_LABELS: Final[dict[str, str]] = {
    "Kevin Warsh": "케빈 워시",
}


class _BoardMembersTextParser(HTMLParser):
    """Collect bounded visible text from Fed board-member anchors/list rows."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture_depth = 0
        self._parts: list[str] = []
        self.labels: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"a", "li", "h3", "h4"}:
            self._capture_depth += 1
            if self._capture_depth == 1:
                self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_depth > 0:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag not in {"a", "li", "h3", "h4"} or self._capture_depth == 0:
            return
        self._capture_depth -= 1
        if self._capture_depth == 0:
            label = _normalize_label(" ".join(self._parts))
            if label:
                self.labels.append(label)
            self._parts = []


@register
class FedBoardLeadershipAdapter:
    """Adapter for the Fed Board Members source-of-record page."""

    name: ClassVar[str] = "fed-board-leadership"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            _ENDPOINT,
            source_name=self.name,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        labels = _extract_labels(response.text)
        chairman_labels = [label for label in labels if _parse_chairman_label(label) is not None]
        unique = tuple(dict.fromkeys(chairman_labels))
        if not unique:
            return []
        if len(unique) > 1:
            raise SourceFetchError(
                source_name=self.name,
                message=f"ambiguous chairman labels: {len(unique)}",
                transient=False,
            )

        label = unique[0]
        value = _parse_chairman_label(label)
        if value is None:
            return []
        observed_at = datetime.combine(window.target_date, time.min, tzinfo=UTC)
        expires_at = observed_at + timedelta(hours=24)
        label_ko = _KOREAN_LABELS.get(value)
        raw_metadata: dict[str, str] = {
            "fact_id": "fed.current_chair",
            "fact_value": value,
            "fact_role": _ROLE,
            "fact_status": "fresh",
            "fact_source_tier": "S",
            "fact_expires_at": expires_at.isoformat(),
            "raw_evidence_label": label,
        }
        if label_ko is not None:
            raw_metadata["fact_label_ko"] = label_ko
        return [
            NormalizedItem(
                source_name=self.name,
                category="macro",
                title=f"Current Federal Reserve Chair: {value}",
                summary=label,
                url=_ENDPOINT,
                published_at=observed_at,
                raw_metadata=raw_metadata,
            )
        ]


def _extract_labels(html: str) -> tuple[str, ...]:
    parser = _BoardMembersTextParser()
    try:
        parser.feed(html)
    except Exception as exc:
        raise SourceFetchError(
            source_name=FedBoardLeadershipAdapter.name,
            message=f"malformed HTML: {exc}",
            transient=False,
            cause=exc,
        ) from exc
    return tuple(parser.labels)


def _parse_chairman_label(label: str) -> str | None:
    if not label.endswith(", Chairman"):
        return None
    value = label.removesuffix(", Chairman").strip()
    return value or None


def _normalize_label(raw: str) -> str:
    return " ".join(raw.split())


__all__ = [
    "FedBoardLeadershipAdapter",
]
