"""u59 macro lineage publish-side persistence tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from investo.briefing.lineage import MacroLineageDiagnosis, MacroLineageTrace
from investo.briefing.segments import US_EQUITY
from investo.orchestrator import pipeline as pipeline_module
from investo.publisher import paths


def _trace(diagnosis: MacroLineageDiagnosis = "published") -> MacroLineageTrace:
    return MacroLineageTrace(
        event_key="fred-economic-calendar:release_id=46:scheduled_date=2026-05-13",
        label="Producer Price Index",
        source_name="fred-economic-calendar",
        release_id="46",
        scheduled_date="2026-05-13",
        collected=True,
        routed_segment=US_EQUITY,
        selected_for_stage1=True,
        selected_stage1_id=7,
        stage1_assignment=4,
        stage1_state="assigned",
        rendered_in_stage2_grouped_sections=True,
        rendered_in_lookahead_block=False,
        final_body_mentions=True,
        final_body_has_source_link=True,
        diagnosis=diagnosis,
    )


def test_write_macro_lineage_traces_uses_run_trace_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(paths, "ARCHIVE_ROOT", tmp_path)

    written = pipeline_module._write_macro_lineage_traces(
        date(2026, 5, 13),
        segment=US_EQUITY,
        traces=[_trace()],
    )

    assert written == tmp_path / "_meta" / "run_traces" / "2026-05-13" / "us-equity.json"
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["target_date"] == "2026-05-13"
    assert payload["segment"] == "us-equity"
    assert payload["watched_events"][0]["diagnosis"] == "published"


def test_log_macro_lineage_trace_is_compact(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="investo.orchestrator.pipeline")

    pipeline_module._log_macro_lineage_trace(US_EQUITY, _trace("llm_omitted"))

    assert "[diagnostics]" in caplog.text
    assert "diagnosis=llm_omitted" in caplog.text
