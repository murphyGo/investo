"""Private operational preview uses the real finalizer without publication."""

from __future__ import annotations

import importlib.util
import json
import logging
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType
from typing import Never

import pytest

from investo.briefing.errors import BriefingGenerationError
from investo.models.coverage import SourceCollectionReport, SourceOutcome
from tests.integration.test_event_generation import _case, _ReplayRunner

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "preview_event_briefing.py"
_NOW = datetime(2026, 9, 22, 6, tzinfo=UTC)
_TARGET = date(2026, 9, 21)


@pytest.fixture
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("preview_event_briefing_script", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text(".tmp/\n", encoding="utf-8")
    return root


def _forbidden(*args: object, **kwargs: object) -> Never:
    pytest.fail("private preview reached publication or an unexpected external call")


def _no_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("investo.orchestrator.pipeline.run_pipeline", _forbidden)
    for stage in ("CollectStage", "GenerateStage", "PublishStage", "NotifyStage"):
        monkeypatch.setattr(f"investo.orchestrator.pipeline.{stage}.execute", _forbidden)
    monkeypatch.setattr("investo.notifier.BriefingPublisher.send", _forbidden)
    monkeypatch.setattr("investo.notifier.OperatorAlerter.alert", _forbidden)


async def _empty_anchors(target_date: date) -> tuple[dict[str, object], dict[str, object]]:
    assert target_date == _TARGET
    return {}, {}


async def test_live_boundary_fixture_collects_once_and_seals_without_publication(
    script: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case()
    calls: list[tuple[date, datetime]] = []

    async def collect(
        target_date: date, *, evidence_received_at: datetime
    ) -> SourceCollectionReport:
        calls.append((target_date, evidence_received_at))
        return SourceCollectionReport(
            items=(case.item,),
            outcomes=(
                SourceOutcome.ok(case.item.source_name, "news", 1),
                SourceOutcome("fixture-zero", "news", "zero"),
                SourceOutcome(
                    "fixture-failed", "news", "failed", failure_reason="PRIVATE", transient=False
                ),
            ),
        )

    # Register this synthetic source in the existing routing test seam; all
    # evidence, generation, rendering, trust gates and sealing stay real.
    import investo.briefing.segments as segments

    monkeypatch.setattr(
        segments, "_US_ONLY_SOURCES", segments._US_ONLY_SOURCES | {case.item.source_name}
    )
    monkeypatch.setattr(script, "collect_sources", collect)
    monkeypatch.setattr(script, "_load_market_anchors_for_run", _empty_anchors)
    _no_publication(monkeypatch)
    runner = _ReplayRunner([case.classification, case.synthesis])
    output = repository / ".tmp" / "event-preview" / "fixture"
    before = (repository / ".gitignore").read_bytes()
    result = await script.run_preview(
        target_date=_TARGET,
        segment="us-equity",
        output_dir=output,
        repository_root=repository,
        observed_at=_NOW,
        runner=runner,
    )
    assert calls == [(_TARGET, _NOW)]
    assert len(runner.prompts) == 2
    assert result["status"] == "sealed"
    assert result["event_coverage"]["terminal_event_count"] == 1
    assert result["event_baseline_available"] is False
    assert result["source_status_counts"] == {"ok": 1, "zero": 1, "failed": 1}
    assert result["human_semantic_review"] == "pending"
    assert result["publication_committed"] is False
    assert result["notification_sent"] is False
    assert result["production_cursor_written"] is False
    assert result["production_receipt_written"] is False
    assert set(path.name for path in output.iterdir()) == {"preview.md", "manifest.json"}
    markdown = (output / "preview.md").read_text(encoding="utf-8")
    assert case.event_id in markdown
    assert "123.45" in markdown
    assert "RAW_EVENT_RESPONSE_MUST_NOT_ESCAPE" not in markdown
    manifest = (output / "manifest.json").read_text(encoding="utf-8")
    assert json.loads(manifest) == result
    assert len(manifest.encode()) < script._MAX_MANIFEST_BYTES
    assert "Acme" not in manifest
    assert "https://" not in manifest
    assert "trace" not in result["event_coverage"]
    assert (repository / ".gitignore").read_bytes() == before
    assert not (repository / "archive").exists()
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir())


async def test_empty_collection_is_sealed_limitation_without_model_call(
    script: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def collect(*args: object, **kwargs: object) -> SourceCollectionReport:
        return SourceCollectionReport(items=(), outcomes=())

    monkeypatch.setattr(script, "collect_sources", collect)
    monkeypatch.setattr(script, "_load_market_anchors_for_run", _empty_anchors)
    _no_publication(monkeypatch)
    result = await script.run_preview(
        target_date=_TARGET,
        segment="us-equity",
        output_dir=repository / ".tmp" / "empty",
        repository_root=repository,
        observed_at=_NOW,
        runner=_forbidden,
    )
    assert result["status"] == "sealed"
    assert result["event_coverage"]["state"] == "classification_unavailable"
    assert result["event_coverage"]["selected_count"] is None
    assert result["human_semantic_review"] == "pending"


@pytest.mark.parametrize("relative", ["archive/preview", ".tmp", ".tmp/../archive/preview"])
async def test_rejects_public_and_escaping_output_before_collection(
    script: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    monkeypatch.setattr(script, "collect_sources", _forbidden)
    with pytest.raises(script.PreviewInputError):
        await script.run_preview(
            target_date=_TARGET,
            segment="us-equity",
            output_dir=Path(relative),
            repository_root=repository,
        )
    assert not (repository / "archive").exists()


@pytest.mark.parametrize("alias", ["root", "parent", "leaf"])
def test_rejects_symlinks_into_tracked_tree(
    script: ModuleType, repository: Path, alias: str
) -> None:
    archive = repository / "archive"
    archive.mkdir()
    private = repository / ".tmp"
    if alias == "root":
        private.symlink_to(archive, target_is_directory=True)
        output = private / "new"
    else:
        private.mkdir()
        link = private / "link"
        link.symlink_to(archive, target_is_directory=True)
        output = link / "new" if alias == "parent" else link
    with pytest.raises(script.PreviewInputError):
        script._private_path(output, repository)
    assert not list(archive.iterdir())


def test_rejects_existing_directory_and_force_tracked_deleted_outputs(
    script: ModuleType, repository: Path
) -> None:
    output = repository / ".tmp" / "existing"
    output.mkdir(parents=True)
    with pytest.raises(script.PreviewInputError):
        script._private_path(output, repository)
    tracked = repository / ".tmp" / "tracked"
    tracked.mkdir()
    file = tracked / "preview.md"
    file.write_text("synthetic", encoding="utf-8")
    subprocess.run(["git", "add", "-f", str(file)], cwd=repository, check=True, capture_output=True)
    file.unlink()
    tracked.rmdir()
    with pytest.raises(script.PreviewInputError):
        script._private_path(tracked, repository)


def test_rejects_unignored_private_output(script: ModuleType, repository: Path) -> None:
    (repository / ".gitignore").write_text("", encoding="utf-8")
    with pytest.raises(script.PreviewInputError):
        script._private_path(repository / ".tmp" / "new", repository)


async def test_output_limit_rejects_without_writing_markdown(
    script: ModuleType, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def collect(*args: object, **kwargs: object) -> SourceCollectionReport:
        return SourceCollectionReport(items=(), outcomes=())

    monkeypatch.setattr(script, "collect_sources", collect)
    monkeypatch.setattr(script, "_load_market_anchors_for_run", _empty_anchors)
    monkeypatch.setattr(script, "_MAX_MARKDOWN_BYTES", 1)
    output = repository / ".tmp" / "oversize"
    with pytest.raises(ValueError, match="output limit"):
        await script.run_preview(
            target_date=_TARGET,
            segment="us-equity",
            output_dir=output,
            repository_root=repository,
            runner=_forbidden,
            observed_at=_NOW,
        )
    assert not list(output.iterdir())


def test_cli_redacts_invalid_arguments_and_library_errors(
    script: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert script.main(["--target-date", "PRIVATE_INVALID_DATE"]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "status": "rejected",
        "code": "preview.input_invalid",
    }

    async def fail(**kwargs: object) -> Never:
        logging.error("PRIVATE_SOURCE_BODY")
        raise RuntimeError("PRIVATE_NATIVE_OUTPUT")

    monkeypatch.setattr(script, "run_preview", fail)
    previous = logging.root.manager.disable
    assert (
        script.main(
            [
                "--target-date",
                "2026-09-21",
                "--segment",
                "us-equity",
                "--output-dir",
                ".tmp/preview",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "status": "failed",
        "code": "preview.execution_failed",
        "error_type": "unexpected",
    }
    assert captured.err == ""
    assert logging.root.manager.disable == previous


@pytest.mark.parametrize("stage", ["classification", "synthesis", "post_validation", "budget"])
def test_generation_error_manifest_keeps_only_bounded_stage_and_attempts(
    script: ModuleType, stage: str
) -> None:
    error = BriefingGenerationError(
        stage=stage,  # type: ignore[arg-type]
        attempt_count=3,
        last_stdout="PRIVATE_MODEL_RESPONSE",
        last_stderr="PRIVATE_NATIVE_ERROR",
        cause=RuntimeError("PRIVATE_CAUSE"),
    )
    manifest = script._failure_manifest(error)
    assert manifest == {
        "status": "failed",
        "code": "preview.execution_failed",
        "error_type": "briefing_generation",
        "stage": stage,
        "attempt_count": 3,
    }
    error.stage = "PRIVATE_INVALID_STAGE"  # type: ignore[assignment]
    error.attempt_count = 101
    manifest = script._failure_manifest(error)
    assert manifest["stage"] is None
    assert manifest["attempt_count"] is None
    assert "PRIVATE" not in json.dumps(manifest)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("PRIVATE"), "timeout"),
        (subprocess.TimeoutExpired("PRIVATE", 1), "timeout"),
        (OSError("PRIVATE"), "io"),
        (ValueError("PRIVATE"), "validation"),
        (RuntimeError("PRIVATE"), "unexpected"),
    ],
)
def test_error_type_is_a_fixed_category(
    script: ModuleType, error: Exception, expected: str
) -> None:
    manifest = script._failure_manifest(error)
    assert manifest["error_type"] == expected
    assert "PRIVATE" not in json.dumps(manifest)
