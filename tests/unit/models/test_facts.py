from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from investo.models.facts import FactSnapshot, VerifiedFactBundle


def _snapshot(**overrides: object) -> FactSnapshot:
    observed = datetime(2026, 6, 18, tzinfo=UTC)
    values = {
        "fact_id": "fed.current_chair",
        "value": "Kevin Warsh",
        "label_ko": "케빈 워시",
        "aliases": ("Warsh",),
        "role": "Chairman",
        "source_name": "fed-board-leadership",
        "source_url": "https://www.federalreserve.gov/aboutthefed/bios/board/default.htm",
        "source_tier": "S",
        "observed_at": observed,
        "expires_at": observed + timedelta(hours=24),
        "status": "fresh",
        "raw_evidence_label": "Kevin Warsh, Chairman",
    }
    values.update(overrides)
    return FactSnapshot(**values)  # type: ignore[arg-type]


def test_fact_snapshot_rejects_naive_datetimes() -> None:
    with pytest.raises(ValidationError):
        _snapshot(observed_at=datetime(2026, 6, 18))


def test_fact_snapshot_rejects_non_positive_expiry_window() -> None:
    observed = datetime(2026, 6, 18, tzinfo=UTC)
    with pytest.raises(ValidationError):
        _snapshot(observed_at=observed, expires_at=observed)


def test_verified_fact_bundle_fresh_honors_expiry() -> None:
    fact = _snapshot()
    bundle = VerifiedFactBundle(target_date=date(2026, 6, 18), facts=(fact,))

    assert bundle.fresh("fed.current_chair", fact.observed_at + timedelta(hours=1)) == fact
    assert bundle.fresh("fed.current_chair", fact.expires_at) is None


def test_verified_fact_bundle_serialization_round_trip() -> None:
    fact = _snapshot(aliases=("Warsh", "Kevin Warsh"))
    bundle = VerifiedFactBundle(target_date=date(2026, 6, 18), facts=(fact,))

    restored = VerifiedFactBundle.model_validate_json(bundle.model_dump_json())

    assert restored == bundle
    assert restored.facts[0].aliases == ("Warsh", "Kevin Warsh")
