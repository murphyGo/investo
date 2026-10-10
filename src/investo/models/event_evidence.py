"""Source-neutral evidence identity and normalization, without pipeline imports."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from urllib.parse import unquote_plus, urlsplit, urlunsplit

from investo.models.event_context import EventContextDocument
from investo.models.events import EvidenceDocument
from investo.models.items import NormalizedItem
from investo.models.macro import macro_prompt_payload


def make_event_context_document(
    evidence: EvidenceDocument,
    *,
    role_chunks: Sequence[tuple[str, str, str]] = (),
    metadata: Mapping[str, object] | None = None,
    item: NormalizedItem | None = None,
) -> EventContextDocument:
    """Convert source-owned evidence without giving an LLM chunk authority.

    Explicit roles are exact substrings of the legacy source fields, with
    ``field:start:end`` locators. Metadata accepts only the existing source
    fact namespaces. A new transmitted revision binds all retained bytes.
    """
    from investo.models.event_context import (
        ContextRef,
        EventContextDocument,
        EventTimeContext,
        EventTimeValue,
        EvidenceChunk,
        ReferencePeriod,
    )

    rows: list[dict[str, object]] = []
    limited = evidence.evidence_budget_limited
    if role_chunks:
        for role, text, locator in role_chunks:
            try:
                field, raw_start, raw_end = locator.split(":")
                start, end = int(raw_start), int(raw_end)
                if field not in {"title", "summary", "detail_excerpt"}:
                    raise ValueError
                source = getattr(evidence, field)
                if start < 0 or end <= start or source[start:end] != text or end > len(source):
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError("role chunk must match its exact source locator") from None
            rows.append({"role": role, "text": text, "source_locator": locator})
    else:
        for field, role in (
            ("title", "identity"),
            ("summary", "fact"),
            ("detail_excerpt", "background"),
        ):
            source = getattr(evidence, field)
            if source.strip():
                text = source[:1200]
                rows.append(
                    {"role": role, "text": text, "source_locator": f"{field}:0:{len(text)}"}
                )
                limited |= text != source
    # Keep the field labels, since equal values can belong to different metrics.
    allowed = {
        "macro_event_status",
        "macro_event_period",
        "macro_event_unit",
        "macro_event_metric",
        "macro_event_key",
        "fact_status",
        "fact_period",
        "fact_unit",
        "fact_metric",
        "reference_period",
        "official_release_id",
        "event_time_role",
        "event_occurrence_stage",
        "event_cross_reference",
        "event_thread_id",
        "unit",
        "series_id",
    }
    source_metadata: dict[str, object] = {
        key: value
        for key, value in (metadata or {}).items()
        if key in allowed and isinstance(value, (str, int, float)) and not isinstance(value, bool)
    }
    if item is not None:
        macro = macro_prompt_payload(item)
        if macro:
            source_metadata.update({f"macro_{key}": value for key, value in macro.items()})
            if "actual" in macro and macro.get("status") in {"actual", "forecast", "scheduled"}:
                source_metadata["macro_actual_status"] = macro["status"]
            for slot in ("forecast", "consensus"):
                if slot in macro:
                    source_metadata[f"macro_{slot}_status"] = "forecast"
    if evidence.event_time_basis != "unknown":
        assert evidence.event_time is not None
        source_metadata["event_time"] = evidence.event_time.isoformat()
        source_metadata["event_precision"] = (
            "exact" if isinstance(evidence.event_time, datetime) else "date"
        )
    metadata_text = json.dumps(
        source_metadata, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    if source_metadata:
        if len(metadata_text) > 1200 or len(rows) >= 4:
            raise ValueError("source metadata exceeds the context chunk budget")
        rows.append({"role": "fact", "text": metadata_text, "source_locator": "source_metadata"})
    chunks = tuple(
        EvidenceChunk.model_validate(
            {
                **row,
                "chunk_id": event_digest(evidence.document_id, row["source_locator"], row["role"]),
                "text_sha256": hashlib.sha256(str(row["text"]).encode("utf-8")).hexdigest(),
            }
        )
        for row in rows
    )
    revision = event_digest(
        tuple((chunk.chunk_id, chunk.role, chunk.text_sha256) for chunk in chunks)
    )

    def source_ref(key: str) -> tuple[ContextRef, ...]:
        chunk = next((chunk for chunk in chunks if chunk.source_locator == "source_metadata"), None)
        if chunk is None:
            return ()
        value = source_metadata[key]
        encoded = json.dumps(value, ensure_ascii=False)
        field_prefix = json.dumps(key) + ":"
        needle = encoded[1:-1] if isinstance(value, str) else encoded
        start = chunk.text.index(field_prefix) + len(field_prefix) + int(isinstance(value, str))
        if start < 0 or not 1 <= len(needle) <= 240:
            raise ValueError("source metadata cannot be referenced")
        return (
            ContextRef(
                document_id=evidence.document_id,
                revision_id=revision,
                chunk_id=chunk.chunk_id,
                start=start,
                end=start + len(needle),
            ),
        )

    event_point = EventTimeValue()
    if evidence.event_time is not None and evidence.event_time_basis != "unknown":
        event_point = EventTimeValue(
            value=evidence.event_time,
            precision="exact" if isinstance(evidence.event_time, datetime) else "date",
            source_refs=source_ref("event_time"),
        )
    period_key = next(
        (
            key
            for key in ("reference_period", "macro_release_period", "macro_event_period")
            if key in source_metadata
        ),
        None,
    )
    period_value = source_metadata.get(period_key) if period_key else None
    period = ReferencePeriod()
    if isinstance(period_value, str):
        assert period_key is not None
        period = ReferencePeriod(value=period_value, source_refs=source_ref(period_key))
    time_role = source_metadata.get("event_time_role", "occurred")
    return EventContextDocument(
        document_id=evidence.document_id,
        revision_id=revision,
        origin_revision_id=evidence.origin_revision_id or evidence.revision_id,
        source_name=evidence.source_name,
        url=evidence.url,
        source_tier=evidence.source_tier,
        source_status=evidence.source_status,
        chunks=chunks,
        evidence_budget_limited=limited,
        time=EventTimeContext(
            occurred_at=event_point if time_role == "occurred" else EventTimeValue(),
            announced_at=event_point if time_role == "announced" else EventTimeValue(),
            published_at=EventTimeValue(
                value=evidence.published_date or evidence.published_at,
                precision="date" if evidence.published_date else "exact",
            ),
            received_at=EventTimeValue(value=evidence.received_at, precision="exact"),
            reference_period=period,
        ),
    )


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
