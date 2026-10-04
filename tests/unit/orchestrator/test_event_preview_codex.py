from __future__ import annotations

import importlib.util
import json
import logging
import subprocess
import time
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from investo._internal.codex_auth import write_auth
from investo._internal.llm_config import LlmExecutionConfig
from investo.briefing.codex_cli import CodexRunner
from investo.orchestrator.codex_runtime import CLEANUP_RESERVE_S, RuntimeOperation
from tests.unit.orchestrator.test_codex_runtime_u155 import auth
from tests.unit.orchestrator.test_event_preview_script import _no_publication

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def wrapper() -> ModuleType:
    path = ROOT / "scripts/preview_event_briefing_codex.py"
    spec = importlib.util.spec_from_file_location("private_event_preview_wrapper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("outcome", ["sealed", "blocked", "generation_failure", "auth_failure"])
def test_private_preview_uses_supervisor_and_never_public_pipeline(
    wrapper: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outcome: str,
) -> None:
    repository = tmp_path / "data"
    repository.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True, capture_output=True)
    (repository / ".gitignore").write_text(".tmp/\n")
    home = tmp_path / "auth"
    home.mkdir(mode=0o700)
    write_auth(home / "auth.json", auth())
    config = LlmExecutionConfig("codex", "test-model")
    runner = CodexRunner(config, home, deadline=time.monotonic() + 60)
    preview = wrapper._reviewed_preview()
    calls: list[str] = []

    async def run_preview(**kwargs: object) -> dict[str, object]:
        calls.append("preview")
        assert kwargs["runner"] is runner
        assert kwargs["repository_root"] == repository.resolve()
        if outcome == "generation_failure":
            raise RuntimeError("PRIVATE_MODEL_RESPONSE")
        return {"status": "blocked" if outcome == "blocked" else "sealed", "provider": "codex"}

    async def supervised(*, operation: RuntimeOperation) -> int:
        calls.append("auth_owner")
        rc = await operation(llm_config=config, llm_runner=runner)
        calls.append("auth_preserved")
        return 1 if outcome == "auth_failure" else rc

    monkeypatch.chdir(repository)
    monkeypatch.setattr(preview, "run_preview", run_preview)
    monkeypatch.setattr(wrapper, "_reviewed_preview", lambda: preview)
    monkeypatch.setattr(wrapper, "_supervised", supervised)
    _no_publication(monkeypatch)
    previous_logging = logging.root.manager.disable
    result = wrapper.main(
        [
            "--target-date",
            "2026-10-02",
            "--segment",
            "us-equity",
            "--output-dir",
            ".tmp/preview",
        ]
    )
    captured = capsys.readouterr()
    manifest = json.loads(captured.out)
    assert calls == ["auth_owner", "preview", "auth_preserved"]
    assert (
        result == {"sealed": 0, "blocked": 3, "generation_failure": 1, "auth_failure": 1}[outcome]
    )
    assert manifest["status"] == (outcome if outcome in ("sealed", "blocked") else "failed")
    assert captured.err == "" and "PRIVATE" not in captured.out
    assert logging.root.manager.disable == previous_logging
    assert not (repository / ".tmp").exists()


def test_bad_output_is_rejected_before_auth_restore(
    wrapper: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    async def forbidden(**kwargs: object) -> int:
        pytest.fail("bad output reached auth owner")

    monkeypatch.setattr(wrapper, "_supervised", forbidden)
    assert (
        wrapper.main(
            [
                "--target-date",
                "2026-10-02",
                "--segment",
                "us-equity",
                "--output-dir",
                "archive/preview",
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["code"] == "preview.runtime_input_invalid"


def test_wrapper_import_ignores_the_data_checkout(
    wrapper: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "preview_event_briefing.py").write_text("raise AssertionError('untrusted code')")
    monkeypatch.chdir(tmp_path)
    assert Path(wrapper._reviewed_preview().__file__) == ROOT / "scripts/preview_event_briefing.py"


def test_private_preview_workflow_shares_auth_lock_without_publication_credentials(
    wrapper: ModuleType,
) -> None:
    text = (ROOT / "ops/private-runtime/event-preview.yml").read_text()
    workflow = yaml.safe_load(text)
    production = yaml.safe_load((ROOT / "ops/private-runtime/production-briefing.yml").read_text())
    assert workflow["concurrency"] == production["concurrency"]
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["preview"]
    assert job["environment"] == "codex-runtime"
    assert "github.event.repository.private == true" in job["if"]
    assert "refs/heads/main" in job["if"]
    assert job["env"]["REVIEWED_CODE_SHA"] == "${{ vars.REVIEWED_EVENT_PREVIEW_SHA }}"
    assert "TELEGRAM" not in text and "INVESTO_PUBLIC_PUBLISH_TOKEN" not in text
    assert "REVIEWED_CODE_SHA }}" not in text  # Production pointer is never changed/reused.
    generation = next(step for step in job["steps"] if step.get("id") == "preview")
    assert generation["timeout-minutes"] * 60 > wrapper.PREVIEW_WORK_LIMIT_S + CLEANUP_RESERVE_S
    preflight = next(
        step
        for step in job["steps"]
        if step.get("name") == "Validate recipient and import provenance"
    )
    assert 'test "$(( $(date +%s) - SETUP_STARTED_AT ))" -lt 600' in preflight["run"]
    assert job["timeout-minutes"] * 60 > 600 + wrapper.PREVIEW_WORK_LIMIT_S + CLEANUP_RESERVE_S
    assert (
        'python" -I "$GITHUB_WORKSPACE/runtime-code/scripts/preview_event_briefing_codex.py"'
        in generation["run"]
    )
    artifact = next(step for step in job["steps"] if step.get("name") == "Retain ciphertext only")
    assert artifact["with"]["path"] == "public-data/.tmp/event-preview.sealed"
    assert artifact["with"]["retention-days"] == 1
