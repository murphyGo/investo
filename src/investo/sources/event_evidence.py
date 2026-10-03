"""Explicitly opted-in feed evidence; body access requires qualified source records."""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urljoin, urlsplit

import httpx

from investo.models.enrichment import (
    EnrichmentOutcome,
    EnrichmentPolicy,
    EnrichmentQualification,
    EnrichmentReason,
    EnrichmentResult,
    EnrichmentSource,
    SourceQualification,
)
from investo.models.event_evidence import (
    canonical_evidence_url,
    event_digest,
    evidence_clock_utc,
    evidence_date_fields,
    make_evidence_document,
    normalize_evidence_text,
)
from investo.models.items import NormalizedItem
from investo.sources._retry import RetryConfig, retry_get
from investo.sources.protocol import SourceFetchError

SourceTier = Literal["official", "primary", "secondary", "unknown"]
_BODY_SOURCES = frozenset({"fomc-rss", "fed-speech-rss", "sec-newsroom-rss", "cftc-policy-rss"})
_SELECTORS = frozenset({"fed-article-body-v1", "cftc-press-article-body-v1"})


def attach_feed_evidence(
    item: NormalizedItem,
    *,
    detail_excerpt: str,
    received_at: datetime | None,
    source_tier: SourceTier | None = None,
) -> NormalizedItem:
    """Attach source-owned pre-summary-cut text; None preserves the exact legacy item."""
    if received_at is None:
        return item
    publication_day, event_day = evidence_date_fields(item.raw_metadata)
    tier = source_tier or (
        "official"
        if item.raw_metadata.get("official_source") == "true"
        else "primary"
        if item.raw_metadata.get("source_tier") == "primary"
        else "unknown"
    )
    evidence = make_evidence_document(
        source_name=item.source_name,
        title=item.title,
        summary=item.summary or "",
        detail_excerpt=normalize_evidence_text(detail_excerpt)[:1200],
        url=str(item.url) if item.url is not None else None,
        published_at=item.published_at,
        received_at=received_at,
        published_date=publication_day,
        event_time=event_day,
        event_time_basis="source_date" if event_day is not None else "unknown",
        source_tier=tier,
    )
    return item.model_copy(update={"event_evidence": evidence})


def load_enrichment_qualification(path: Path) -> EnrichmentQualification:
    """Read a small closed manifest without retaining rejected input in errors."""
    try:
        if not path.is_file():
            raise ValueError("qualification requires a regular file")
        with path.open("rb") as handle:
            data = handle.read(64 * 1024 + 1)
        if len(data) > 64 * 1024:
            raise ValueError("qualification exceeds byte budget")
        return EnrichmentQualification.model_validate_json(data)
    except (OSError, ValueError):
        raise ValueError("event source qualification unavailable") from None


def _allowed_url(url: str, qualification: SourceQualification) -> bool:
    """Only a literal directly-linked HTTPS locator within its qualified path."""
    try:
        parsed = urlsplit(url)
        return bool(
            qualification.status == "qualified"
            and qualification.allowed_host is not None
            and qualification.allowed_path is not None
            and parsed.scheme == "https"
            and parsed.hostname == qualification.allowed_host
            and parsed.netloc == qualification.allowed_host
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
            and parsed.path.startswith(qualification.allowed_path)
            and re.fullmatch(r"/[A-Za-z0-9_./-]+", parsed.path) is not None
            and ".." not in parsed.path
            and "//" not in parsed.path
        )
    except ValueError:
        return False


class _BodyParser(HTMLParser):
    """Two qualified selectors, no script execution or generic page fallback."""

    _VOID = frozenset(
        {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
    )
    _HIDDEN = frozenset(
        {
            "script",
            "style",
            "noscript",
            "nav",
            "header",
            "footer",
            "aside",
            "form",
            "svg",
            "template",
        }
    )

    def __init__(self, selector: str, limit: int) -> None:
        super().__init__(convert_charrefs=True)
        self.selector, self.limit = selector, limit
        self.stack: list[tuple[str, str | None, bool]] = []
        self.selected_depth: int | None = None
        self.matches = 0
        self.complete = False
        self.text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if len(self.stack) >= 256:
            raise ValueError("official body nesting exceeds parser bound")
        attributes = dict(attrs)
        classes = frozenset((attributes.get("class") or "").split())
        selected = (
            self.selector == "fed-article-body-v1"
            and tag == "div"
            and bool(self.stack)
            and self.stack[-1][1] == "article"
            and {"col-xs-12", "col-sm-8", "col-md-8"} <= classes
            and "heading" not in classes
        ) or (
            self.selector == "cftc-press-article-body-v1"
            and "field--name-body" in classes
            and any(parent[0] == "article" for parent in self.stack)
        )
        hidden = (
            tag in self._HIDDEN
            or "hidden" in attributes
            or attributes.get("aria-hidden") == "true"
            or re.search(
                r"(?:display\s*:\s*none|visibility\s*:\s*hidden)",
                attributes.get("style") or "",
                re.IGNORECASE,
            )
            is not None
        )
        if selected:
            self.matches += 1
            if self.matches == 1:
                self.selected_depth = len(self.stack)
        if tag not in self._VOID:
            self.stack.append((tag, attributes.get("id"), hidden))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                if self.selected_depth is not None and index <= self.selected_depth:
                    self.complete = True
                    self.selected_depth = None
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if self.selected_depth is None or any(row[2] for row in self.stack):
            return
        if len(self.text) < self.limit:
            text = re.sub(r"\s+", " ", normalize_evidence_text(data)).strip()
            if text:
                self.text = (self.text + " " + text).strip()[: self.limit]


def _body_excerpt(
    response: httpx.Response, qualification: SourceQualification, limit: int
) -> tuple[str | None, EnrichmentReason | None]:
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != qualification.content_type:
        return None, "content_type"
    parser = _BodyParser(qualification.extraction_selector_version or "", limit)
    try:
        parser.feed(response.text)
        parser.close()
    except (ValueError, RecursionError, AssertionError):
        return None, "selector_unavailable"
    if parser.matches != 1 or not parser.complete:
        return None, "selector_unavailable"
    return (parser.text, None) if parser.text else (None, "empty_excerpt")


@dataclass(frozen=True, slots=True)
class _Candidate:
    index: int
    item: NormalizedItem
    source: EnrichmentSource
    document_id: str


def _candidates(
    items: Sequence[NormalizedItem], cap: int, records: Mapping[str, SourceQualification]
) -> tuple[_Candidate, ...]:
    # A newer testimony or other non-qualified URL cannot spend the body quota
    # of an older, directly linked qualified release from the same RSS feed.
    grouped: dict[str, tuple[list[_Candidate], list[_Candidate]]] = {}
    seen: set[tuple[str, str, bool]] = set()
    for index, item in sorted(
        enumerate(items),
        key=lambda row: (
            -row[1].published_at.timestamp(),
            row[1].source_name,
            str(row[1].url),
            row[1].title,
        ),
    ):
        if item.source_name not in _BODY_SOURCES or item.scheduled_at is not None:
            continue
        url = str(item.url) if item.url else None
        try:
            identity = canonical_evidence_url(url) or (item.title, item.published_at.isoformat())
        except ValueError:
            identity = (item.title, item.published_at.isoformat())
        document_id = event_digest(item.source_name, identity)
        record = records.get(item.source_name)
        eligible = bool(
            record is not None
            and record.extraction_selector_version in _SELECTORS
            and _allowed_url(url or "", record)
        )
        key = item.source_name, document_id, eligible
        if key in seen:
            continue
        seen.add(key)
        lanes = grouped.setdefault(item.source_name, ([], []))
        lanes[0 if eligible else 1].append(
            _Candidate(index, item, cast("EnrichmentSource", item.source_name), document_id)
        )
    selected: dict[str, list[_Candidate]] = {}
    for source, (eligible_items, rejected_items) in grouped.items():
        selected[source] = eligible_items[:cap]
        eligible_ids = {item.document_id for item in eligible_items}
        rejected = [item for item in rejected_items if item.document_id not in eligible_ids]
        selected[source].extend(rejected[: cap - len(selected[source])])
    return tuple(
        bucket[offset]
        for offset in range(cap)
        for _source, bucket in sorted(selected.items())
        if offset < len(bucket)
    )


async def enrich_event_evidence(
    items: Sequence[NormalizedItem],
    *,
    client: httpx.AsyncClient,
    policy: EnrichmentPolicy,
    qualification: EnrichmentQualification,
    received_at: datetime,
    deadline: float | None = None,
) -> EnrichmentResult:
    """Bounded official body reads; each failure retains the original feed item."""
    if policy.mode != "active":
        return EnrichmentResult(items=tuple(items))
    policy.validate_activation()
    received_at = evidence_clock_utc(received_at)
    if client.follow_redirects:
        raise ValueError("event enrichment requires automatic redirects disabled")
    if deadline is not None and (type(deadline) not in {float, int} or not math.isfinite(deadline)):
        raise ValueError("event enrichment deadline must be finite monotonic time")
    stop_at = min(
        time.monotonic() + policy.total_budget_s, deadline if deadline is not None else math.inf
    )
    records: dict[str, SourceQualification] = {
        record.source_name: record for record in qualification.sources
    }
    candidates = _candidates(items, policy.max_items_per_source, records)
    results: dict[int, tuple[NormalizedItem, EnrichmentReason | None]] = {}
    semaphore = asyncio.Semaphore(policy.concurrency)
    request_count = 0

    async def enrich(candidate: _Candidate) -> None:
        nonlocal request_count
        item, record = candidate.item, records.get(candidate.source)
        reason: EnrichmentReason | None = "unqualified"
        if record is None or record.status != "qualified":
            results[candidate.index] = item, reason
            return
        if record.extraction_selector_version not in _SELECTORS:
            results[candidate.index] = item, "selector_unavailable"
            return
        url = str(item.url) if item.url else ""
        if not _allowed_url(url, record):
            results[candidate.index] = item, "url_rejected"
            return
        async with semaphore:
            for hop in range(policy.max_redirects + 1):
                remaining = stop_at - time.monotonic()
                if request_count >= policy.max_requests or remaining <= 0:
                    reason = "budget_exhausted"
                    break
                request_count += 1
                try:
                    response = await retry_get(
                        client,
                        url,
                        source_name=candidate.source,
                        config=RetryConfig(
                            timeout_s=min(policy.request_timeout_s, remaining),
                            retries=0,
                            backoffs=(),
                            total_budget_s=min(policy.request_timeout_s, remaining),
                            max_response_bytes=policy.max_response_bytes,
                        ),
                    )
                except SourceFetchError as exc:
                    reason = (
                        "timed_out"
                        if isinstance(exc.cause, (TimeoutError, httpx.TimeoutException))
                        else "request_failed"
                    )
                    break
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    redirected = urljoin(url, location) if location else ""
                    if hop >= policy.max_redirects or not _allowed_url(redirected, record):
                        reason = "redirect_rejected"
                        break
                    url = redirected
                    continue
                if response.status_code != 200:
                    reason = "request_failed"
                    break
                excerpt, reason = _body_excerpt(response, record, policy.max_excerpt_chars)
                if excerpt is not None:
                    try:
                        enriched = attach_feed_evidence(
                            item,
                            detail_excerpt=excerpt,
                            received_at=received_at,
                            source_tier="official",
                        )
                    except ValueError:
                        reason = "evidence_invalid"
                        break
                    if (
                        enriched.event_evidence is None
                        or enriched.event_evidence.document_id != candidate.document_id
                    ):
                        reason = "evidence_invalid"
                        break
                    results[candidate.index] = enriched, None
                    return
                break
            results[candidate.index] = item, reason

    tasks = [asyncio.create_task(enrich(candidate)) for candidate in candidates]
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=max(0, stop_at - time.monotonic()))
    except TimeoutError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    enriched_items = list(items)
    outcomes: list[EnrichmentOutcome] = []
    for candidate in candidates:
        item, reason = results.get(candidate.index, (candidate.item, "timed_out"))
        enriched_items[candidate.index] = item
        outcomes.append(
            EnrichmentOutcome(
                source_name=candidate.source,
                document_id=candidate.document_id,
                status="enriched" if reason is None else "enrichment_unavailable",
                reason=reason,
            )
        )
    return EnrichmentResult(
        items=tuple(enriched_items), outcomes=tuple(outcomes), request_count=request_count
    )
