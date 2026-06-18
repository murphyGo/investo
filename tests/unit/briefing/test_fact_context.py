from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from investo.briefing.fact_context import (
    VerifiedFactConflictError,
    build_verified_fact_bundle,
    render_fact_context_block,
)
from investo.models import NormalizedItem


def _fact_item(
    value: str = "Kevin Warsh",
    *,
    expires_delta: timedelta = timedelta(hours=24),
) -> NormalizedItem:
    observed = datetime(2026, 6, 18, tzinfo=UTC)
    return NormalizedItem(
        source_name="fed-board-leadership",
        category="macro",
        title=f"Current Federal Reserve Chair: {value}",
        summary=f"{value}, Chairman",
        url="https://www.federalreserve.gov/aboutthefed/bios/board/default.htm",
        published_at=observed,
        raw_metadata={
            "fact_id": "fed.current_chair",
            "fact_value": value,
            "fact_label_ko": "케빈 워시" if value == "Kevin Warsh" else "",
            "fact_role": "Chairman",
            "fact_status": "fresh",
            "fact_source_tier": "S",
            "fact_expires_at": (observed + expires_delta).isoformat(),
            "raw_evidence_label": f"{value}, Chairman",
        },
    )


def test_build_verified_fact_bundle_and_render_fresh_block() -> None:
    now = datetime(2026, 6, 18, 1, tzinfo=UTC)
    bundle = build_verified_fact_bundle((_fact_item(),), date(2026, 6, 18), now)

    rendered = render_fact_context_block(bundle, now)

    assert "## 검증된 현재 팩트" in rendered
    assert "fed.current_chair: Kevin Warsh" in rendered
    assert "케빈 워시" in rendered
    assert len(rendered) <= 600


def test_render_missing_or_stale_fact_blocks_person_name() -> None:
    now = datetime(2026, 6, 19, 1, tzinfo=UTC)
    bundle = build_verified_fact_bundle((_fact_item(),), date(2026, 6, 18), now)

    rendered = render_fact_context_block(bundle, now)

    assert "unverified; do not name the current Fed chair" in rendered


def test_conflicting_fresh_fact_values_raise() -> None:
    now = datetime(2026, 6, 18, 1, tzinfo=UTC)

    with pytest.raises(VerifiedFactConflictError):
        build_verified_fact_bundle(
            (_fact_item("Kevin Warsh"), _fact_item("Jerome Powell")),
            date(2026, 6, 18),
            now,
        )
