"""Frozen three-market recorded replay crosses the actual generation and seal."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _event_coverage_replay import load_native_event_replay, replay_native_event_case

MANIFEST = Path(__file__).resolve().parents[1] / "fixtures/event_briefing_v3/manifest.json"
RECORDS = load_native_event_replay(MANIFEST)


@pytest.mark.asyncio
@pytest.mark.parametrize("record", RECORDS, ids=[r.case_id for r in RECORDS])
async def test_recorded_native_matrix(record):
    result = await replay_native_event_case(record)
    assert result.passed, result


def test_recording_hash_and_market_matrix_cannot_be_silently_changed(tmp_path):
    (tmp_path / "manifest.json").write_bytes(MANIFEST.read_bytes())
    (tmp_path / "records.json").write_bytes((MANIFEST.parent / "records.json").read_bytes() + b" ")
    with pytest.raises(ValueError, match="recording_identity"):
        load_native_event_replay(tmp_path / "manifest.json")
    assert len(RECORDS) >= 36
    assert len({r.scenario_id for r in RECORDS}) == 12
