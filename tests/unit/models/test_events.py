"""Strict immutable foundation contracts, without item-model import cycles."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from investo.models.events import EvidenceDocument, EvidenceRef


@pytest.mark.parametrize("start,end", [(-1, 1), (0, 0), (4, 3), (0, 241), (True, 3), (0, "3")])
def test_span_bounds_and_strict_offsets(start: object, end: object) -> None:
    with pytest.raises(ValidationError):
        EvidenceRef.model_validate(
            dict(document_id="a" * 64, revision_id="b" * 64, field="title", start=start, end=end)
        )


def test_refs_are_deeply_immutable_and_forbid_invented_quote() -> None:
    ref = EvidenceRef(document_id="a" * 64, revision_id="b" * 64, field="title", start=0, end=1)
    with pytest.raises(ValidationError):
        ref.start = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EvidenceRef.model_validate({**ref.model_dump(), "quote": "invented"})


@pytest.mark.parametrize(
    "event_time,basis",
    [
        (None, "source_exact"),
        (datetime(2026, 9, 20), "source_exact"),
        (date(2026, 9, 20), "unknown"),
        (datetime(2026, 9, 20, tzinfo=UTC), "source_date"),
    ],
)
def test_time_precision_is_explicit(event_time: object, basis: str) -> None:
    with pytest.raises(ValidationError):
        EvidenceDocument.model_validate(
            dict(
                document_id="a" * 64,
                revision_id="b" * 64,
                source_name="source",
                title="title",
                published_at=datetime(2026, 9, 20, tzinfo=UTC),
                received_at=datetime(2026, 9, 21, tzinfo=UTC),
                event_time=event_time,
                event_time_basis=basis,
            )
        )
