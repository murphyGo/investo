"""Frozen synthetic input replays through generation, terminal HTML and DTOs."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Never

import pytest
from scripts._event_coverage_replay import (
    ReplayCase,
    ReplayRecord,
    load_event_replay,
    rendered_html_text,
    replay_event_case,
    replay_event_manifest,
)

_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _ROOT / "tests/fixtures/event_briefing/manifest.json"
_CASES = load_event_replay(_MANIFEST)
_PRIVATE_SENTINEL = "SYNTHETIC_PRIVATE_FAILURE_SENTINEL"


def _forbidden(*args: object, **kwargs: object) -> Never:
    pytest.fail("offline replay reached external I/O")


@pytest.mark.parametrize(("case", "record"), _CASES, ids=[case.case_id for case, _ in _CASES])
async def test_recorded_event_matrix_uses_real_generation_finalizer_html_and_dto(
    case: ReplayCase,
    record: ReplayRecord,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    initial_paths = set(tmp_path.rglob("*"))
    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(Path, "write_text", _forbidden)
    monkeypatch.setattr(Path, "write_bytes", _forbidden)
    for stage in ("CollectStage", "GenerateStage", "PublishStage", "NotifyStage"):
        monkeypatch.setattr(f"investo.orchestrator.pipeline.{stage}.execute", _forbidden)
    result = await replay_event_case(case, record)
    assert result.passed, asdict(result)
    assert len(result.segments) == len(case.expectations)
    serialized = json.dumps(asdict(result))
    assert _PRIVATE_SENTINEL not in serialized
    # The suite's autouse fixture creates an empty runtime-log directory before
    # this test. The replay must not add any file, including inside that path.
    assert set(tmp_path.rglob("*")) == initial_paths


def test_manifest_separates_eighteen_published_outputs_from_twelve_input_scenarios() -> None:
    manifest = json.loads(_MANIFEST.read_text())
    assert manifest["fixture_author"] == "AI-authored synthetic"
    assert manifest["human_review"] == "pending"
    assert manifest["human_semantic_score"] is None
    assert len(manifest["rubric"]) == 5
    assert len(manifest["scenarios"]) == 12
    assert len(_CASES) == 25
    inventory = manifest["output_inventory"]
    assert len(inventory) == len({row["path"] for row in inventory}) == 18
    assert {row["purpose"] for row in inventory} == {"published_output_inventory_only"}
    assert {row["source_revision"] for row in inventory} == {
        "c286f5003973c3d7a5fc0c7db2eeda0e6e9bb64c"
    }
    assert all(len(row["sha256"]) == 64 and row["path"].startswith("archive/") for row in inventory)
    assert all("first_issue_heading" not in row for row in inventory)
    # The oracle is read from the frozen manifest, never synthesized from the
    # generated result by the running checker.
    for case, _ in _CASES:
        for expected in case.expectations.values():
            assert expected.selected_expected is None or expected.selected_expected <= 5
            assert len(expected.terminal_event_ids) <= 5


def test_html_checks_visible_fact_text_without_exposing_html_identity_comments() -> None:
    visible = rendered_html_text(
        "<!-- investo:block event:aaaaaaaaaaaaaaaaaaaaaaaa -->\n"
        "## 합성 자료\n\nAT&amp;T의 매출은 **10억** 달러입니다.\n\n"
        "[공식](https://example.invalid/source)"
    )
    assert "AT&T의 매출은 10억 달러입니다." in visible
    assert "investo:block" not in visible
    assert "https://" not in visible


async def test_changed_required_fact_or_removed_summary_identity_fails_independent_oracle() -> None:
    case, record = next(pair for pair in _CASES if pair[0].case_id == "services-1")
    expected = case.expectations["us-equity"]
    wrong = expected.model_copy(update={"required_facts": ("합성 원문에 없는 필수 사실입니다.",)})
    modified = case.model_copy(update={"expectations": {"us-equity": wrong}})
    result = await replay_event_case(modified, record)
    assert not result.passed
    assert "replay.required_fact_missing" in result.segments[0].codes

    wrong = expected.model_copy(update={"terminal_event_ids": ()})
    result = await replay_event_case(
        case.model_copy(update={"expectations": {"us-equity": wrong}}), record
    )
    assert not result.passed
    assert "replay.terminal_identity" in result.segments[0].codes
    assert "replay.summary_identity" in result.segments[0].codes


def _copy_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    manifest = json.loads(_MANIFEST.read_text())
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    (tmp_path / "records.json").write_bytes((_MANIFEST.parent / "records.json").read_bytes())
    return path, manifest


def test_recording_tamper_and_path_escape_are_rejected(tmp_path: Path) -> None:
    path, manifest = _copy_fixture(tmp_path)
    (tmp_path / "records.json").write_text("{}")
    with pytest.raises(ValueError, match="recording_identity"):
        load_event_replay(path)
    manifest["input_recording"] = "../private.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest_contract"):
        load_event_replay(path)


async def test_case_exception_reports_only_closed_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken(*args: object, **kwargs: object) -> Never:
        raise RuntimeError(_PRIVATE_SENTINEL)

    monkeypatch.setattr("scripts._event_coverage_replay.replay_event_case", broken)
    results = await replay_event_manifest(_MANIFEST)
    assert len(results) == 25
    assert all(result.codes == ("replay.execution_failed",) for result in results)
    assert _PRIVATE_SENTINEL not in json.dumps([asdict(result) for result in results])


def test_cli_reports_separate_counts_and_no_recorded_prose() -> None:
    process = subprocess.run(
        [sys.executable, str(_ROOT / "scripts/check_event_coverage.py")],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    lines = [json.loads(line) for line in process.stdout.splitlines()]
    assert lines[-1] == {
        "codes": [],
        "human_semantic_review": "pending",
        "input_replay_variants": 25,
        "output_inventory_count": 18,
        "passed_variants": 25,
        "scenario_groups": 12,
    }
    for sentinel in (_PRIVATE_SENTINEL, "가상사", "실제 매출", "source_refs", "detail_excerpt"):
        assert sentinel not in process.stdout + process.stderr


def test_cli_validation_failure_never_prints_fixture_input_values(tmp_path: Path) -> None:
    path, manifest = _copy_fixture(tmp_path)
    recording = json.loads((tmp_path / "records.json").read_text())
    recording["rate-sep"]["segments"][0]["items"][0]["category"] = _PRIVATE_SENTINEL
    raw = json.dumps(recording).encode()
    (tmp_path / "records.json").write_bytes(raw)
    manifest["input_recording_sha256"] = hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(manifest))
    process = subprocess.run(
        [sys.executable, str(_ROOT / "scripts/check_event_coverage.py"), "--manifest", str(path)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 1
    assert json.loads(process.stdout) == {"codes": ["replay.input_invalid"]}
    assert _PRIVATE_SENTINEL not in process.stdout + process.stderr
