"""u59 macro lineage diagnostics tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from investo.briefing.lineage import (
    MacroLineageDiagnosis,
    MacroLineageSignal,
    build_macro_lineage_traces,
)
from investo.briefing.segments import CRYPTO, US_EQUITY
from investo.models import NormalizedItem


def _ppi_item() -> NormalizedItem:
    return NormalizedItem(
        source_name="fred-economic-calendar",
        category="calendar",
        title="Producer Price Index release",
        published_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        raw_metadata={
            "release_id": "46",
            "release_name": "Producer Price Index",
            "scheduled_date": "2026-05-13",
        },
    )


@pytest.mark.parametrize(
    ("signal", "diagnosis"),
    [
        (MacroLineageSignal(_ppi_item(), collected=False), "missing_at_source"),
        (
            MacroLineageSignal(_ppi_item(), routed_segment=CRYPTO),
            "dropped_by_segment_routing",
        ),
        (
            MacroLineageSignal(_ppi_item(), routed_segment=US_EQUITY),
            "dropped_by_stage1_candidate_cap",
        ),
        (
            MacroLineageSignal(
                _ppi_item(),
                routed_segment=US_EQUITY,
                selected_stage1_id=7,
            ),
            "dropped_by_stage1_classification",
        ),
        (
            MacroLineageSignal(
                _ppi_item(),
                routed_segment=US_EQUITY,
                selected_stage1_id=7,
                stage1_assignment=2,
            ),
            "dropped_by_stage2_prompt_cap",
        ),
        (
            MacroLineageSignal(
                _ppi_item(),
                routed_segment=US_EQUITY,
                selected_stage1_id=7,
                stage1_assignment=2,
                rendered_in_stage2_grouped_sections=True,
                final_body_mentions=True,
                final_body_has_source_link=False,
            ),
            "llm_omitted",
        ),
        (
            MacroLineageSignal(
                _ppi_item(),
                routed_segment=US_EQUITY,
                selected_stage1_id=7,
                stage1_assignment=2,
                rendered_in_stage2_grouped_sections=True,
                final_body_mentions=True,
                final_body_has_source_link=True,
            ),
            "published",
        ),
    ],
)
def test_macro_lineage_diagnosis_order(
    signal: MacroLineageSignal,
    diagnosis: MacroLineageDiagnosis,
) -> None:
    trace = build_macro_lineage_traces([signal], target_segment=US_EQUITY)[0]

    assert trace.diagnosis == diagnosis


def test_macro_lineage_trace_uses_stable_event_metadata() -> None:
    trace = build_macro_lineage_traces(
        [
            MacroLineageSignal(
                _ppi_item(),
                routed_segment=US_EQUITY,
                selected_stage1_id=7,
                stage1_assignment=2,
                rendered_in_lookahead_block=True,
                final_body_mentions=True,
                final_body_has_source_link=True,
            )
        ],
        target_segment=US_EQUITY,
    )[0]

    assert trace.event_key == ("fred-economic-calendar:release_id=46:scheduled_date=2026-05-13")
    assert trace.label == "Producer Price Index"
    assert trace.release_id == "46"
    assert trace.scheduled_date == "2026-05-13"
    assert trace.stage1_state == "assigned"
    assert trace.to_json_dict()["diagnosis"] == "published"
