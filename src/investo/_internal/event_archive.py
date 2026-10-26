"""Read only sealed native sidecars; missing or corrupt data grants no authority."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from investo.models.event_document import PublishedEventEdition
from investo.models.segments import SEGMENT_LABELS, MarketSegment


@dataclass(frozen=True, slots=True)
class EventArchiveRead:
    status: Literal["available", "missing", "hash_mismatch", "unsupported_schema"]
    edition: PublishedEventEdition | None = None


def event_edition_sidecar_path(
    segment: MarketSegment, target_date: date, *, archive_root: Path | None = None
) -> Path:
    if segment not in SEGMENT_LABELS or not isinstance(target_date, date):
        raise ValueError("edition.path_invalid")
    root = Path("archive") if archive_root is None else archive_root
    return root / "_meta" / "event_editions_v3" / segment / f"{target_date.isoformat()}.json"


def published_edition_bytes(edition: PublishedEventEdition) -> bytes:
    if edition.projection_sha256 != edition.canonical_projection_hash:
        raise ValueError("edition.projection_hash_mismatch")
    data = (
        json.dumps(
            edition.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    if len(data) > 1024 * 1024:
        raise ValueError("edition.sidecar_budget_exhausted")
    return data


def read_published_event_edition(
    segment: MarketSegment, target_date: date, *, archive_root: Path | None = None
) -> EventArchiveRead:
    root = Path("archive") if archive_root is None else archive_root
    sidecar = event_edition_sidecar_path(segment, target_date, archive_root=root)
    try:
        if sidecar.stat().st_size > 1024 * 1024:
            return EventArchiveRead("hash_mismatch")
        data = json.loads(sidecar.read_bytes())
        if not isinstance(data, dict) or data.get("schema_version") != 3:
            return EventArchiveRead("unsupported_schema")
        version = data.get("content_contract_version", 1)
        if type(version) is not int or version not in (1, 2):
            return EventArchiveRead("unsupported_schema")
        edition = PublishedEventEdition.model_validate(data)
        expected_path = (
            f"archive/{segment}/{target_date.year}/{target_date.month:02d}/"
            f"{target_date.isoformat()}.md"
        )
        markdown_path = (
            root
            / segment
            / str(target_date.year)
            / f"{target_date.month:02d}"
            / f"{target_date.isoformat()}.md"
        )
        if (
            edition.segment != segment
            or edition.target_date != target_date
            or edition.archive_relative_path != expected_path
            or edition.projection_sha256 != edition.canonical_projection_hash
            or edition.markdown_sha256 != sha256(markdown_path.read_bytes()).hexdigest()
        ):
            return EventArchiveRead("hash_mismatch")
        return EventArchiveRead("available", edition)
    except FileNotFoundError:
        return EventArchiveRead("missing")
    except (OSError, ValueError, ValidationError):
        return EventArchiveRead("hash_mismatch")
