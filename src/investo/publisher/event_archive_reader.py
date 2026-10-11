"""Canonical publisher entry for bounded, hash-bound native archive reads."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo._internal import event_archive
from investo._internal.event_archive import EventArchiveRead as EventArchiveRead
from investo._internal.event_archive import published_edition_bytes as published_edition_bytes
from investo.models.segments import MarketSegment
from investo.publisher import paths


def event_edition_sidecar_path(
    segment: MarketSegment, target_date: date, *, archive_root: Path | None = None
) -> Path:
    return event_archive.event_edition_sidecar_path(
        segment,
        target_date,
        archive_root=paths.ARCHIVE_ROOT if archive_root is None else archive_root,
    )


def read_published_event_edition(
    segment: MarketSegment, target_date: date, *, archive_root: Path | None = None
) -> EventArchiveRead:
    return event_archive.read_published_event_edition(
        segment,
        target_date,
        archive_root=paths.ARCHIVE_ROOT if archive_root is None else archive_root,
    )
