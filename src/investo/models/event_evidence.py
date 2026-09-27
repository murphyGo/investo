"""Source-neutral evidence identity and normalization, without pipeline imports."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from datetime import UTC, date, datetime
from urllib.parse import unquote_plus, urlsplit, urlunsplit

from investo.models.events import EvidenceDocument


def event_digest(*values: object) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_evidence_url(url: str | None) -> str | None:
    """Remove fragments/tracking only; preserve meaningful query ordering."""
    if url is None:
        return None
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
        raise ValueError("event evidence URL must be a public HTTP source locator")
    query = "&".join(
        part
        for part in parsed.query.split("&")
        if not unquote_plus(part.split("=", 1)[0]).casefold().startswith("utm_")
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def normalize_evidence_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")


def evidence_clock_utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("event clock must be timezone-aware")
    return value.astimezone(UTC)


def evidence_date_fields(metadata: Mapping[str, object]) -> tuple[date | None, date | None]:
    """Preserve explicitly supplied source dates; never infer an event date."""
    publication_day: date | None = None
    event_day: date | None = None
    if metadata.get("published_at_precision") == "date":
        try:
            raw_day = metadata["published_date"]
            if not isinstance(raw_day, str):
                raise ValueError("source date must be text")
            publication_day = date.fromisoformat(raw_day)
            if metadata.get("event_time_basis") == "source_date":
                raw_event_day = metadata["event_date"]
                if not isinstance(raw_event_day, str):
                    raise ValueError("source event date must be text")
                event_day = date.fromisoformat(raw_event_day)
        except (KeyError, TypeError, ValueError):
            raise ValueError("date precision evidence requires a valid source date") from None
    return publication_day, event_day


def make_evidence_document(
    *,
    source_name: str,
    title: str,
    summary: str = "",
    detail_excerpt: str = "",
    url: str | None = None,
    published_at: datetime,
    received_at: datetime,
    published_date: date | None = None,
    event_time: date | datetime | None = None,
    event_time_basis: str = "unknown",
    source_tier: str = "unknown",
    source_status: str = "ok",
) -> EvidenceDocument:
    """Build source-owned evidence before prompt bounding; never infer event time."""
    canonical_url = canonical_evidence_url(url)
    identity = canonical_url or (title, evidence_clock_utc(published_at).isoformat())
    title, summary, detail_excerpt = map(normalize_evidence_text, (title, summary, detail_excerpt))
    return EvidenceDocument.model_validate(
        {
            "document_id": event_digest(source_name, identity),
            "revision_id": event_digest(title, summary, detail_excerpt),
            "source_name": source_name,
            "url": canonical_url,
            "published_at": published_at,
            "published_date": published_date,
            "received_at": received_at,
            "event_time": event_time,
            "event_time_basis": event_time_basis,
            "source_tier": source_tier,
            "source_status": source_status,
            "title": title,
            "summary": summary,
            "detail_excerpt": detail_excerpt,
        }
    )
