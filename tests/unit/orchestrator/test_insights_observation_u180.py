from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = ROOT / "ops/private-runtime/production-briefing.yml"
CANARY = "synthetic-private-observation-canary"


def workflow_steps() -> list[dict]:
    return yaml.load(PRODUCTION.read_text(), Loader=yaml.BaseLoader)["jobs"]["briefing"]["steps"]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        env={
            "PATH": os.defpath,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "Synthetic observer",
            "GIT_AUTHOR_EMAIL": "observer@example.invalid",
            "GIT_COMMITTER_NAME": "Synthetic observer",
            "GIT_COMMITTER_EMAIL": "observer@example.invalid",
        },
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout.strip()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def write_current(repo: Path, module: str, when: datetime) -> dict:
    # This observer binds metadata to the publisher's immutable bytes. Numeric
    # and source-definition validation remain the existing publisher's contract.
    payload = {
        "schema_version": 1,
        "module": module,
        "run_started_at": when.isoformat(),
        "collection_completed_at": when.isoformat(),
        "evaluated_at": when.isoformat(),
        "availability": "available",
        "metrics": [] if module == "calendar" else [{"time": {"exact_at": when.isoformat()}}],
        "events": [{"time": {"exact_at": when.isoformat()}}] if module == "calendar" else [],
        "raw_provider_text": CANARY,
    }
    payload["snapshot_id"] = hashlib.sha256(canonical(payload)).hexdigest()
    data = canonical(payload)
    path = repo / f"site_docs/insights/_data/{module}/current.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "module": module,
        "snapshot_id": payload["snapshot_id"],
        "current_hash": hashlib.sha256(data).hexdigest(),
        "index_hash": "a" * 64,
        "history_hash": None if module == "calendar" else "b" * 64,
    }


@pytest.fixture
def context(tmp_path: Path) -> dict:
    workspace = tmp_path / "workspace"
    runtime, public = workspace / "runtime-code", workspace / "public-data"
    when = datetime.now(UTC) - timedelta(seconds=1)
    for repo in (runtime, public):
        repo.mkdir(parents=True)
        git(repo, "init", "--quiet")
    (runtime / "marker").write_text("synthetic code")
    git(runtime, "add", "marker")
    git(runtime, "commit", "--quiet", "--no-gpg-sign", "-m", "synthetic")
    entries = [write_current(public, module, when) for module in ("macro", "calendar", "crypto")]
    manifest = public / "site_docs/insights/_data/manifest.json"
    manifest.write_bytes(canonical({"schema_version": 1, "modules": entries}))
    policy = public / "ops/insights_source_qualification.json"
    policy.parent.mkdir(parents=True)
    policy.write_text('{"schema_version":1,"qualifications":[]}')
    git(public, "add", ".")
    git(public, "commit", "--quiet", "--no-gpg-sign", "-m", "synthetic")
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    return {
        "workspace": workspace,
        "public": public,
        "manifest": manifest,
        "entries": entries,
        "env": {
            "PATH": os.defpath,
            "UV_PROJECT_ENVIRONMENT": str(Path(sys.executable).parent.parent),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GITHUB_REPOSITORY": "murphyGo/automation-runtime",
            "GITHUB_WORKSPACE": str(workspace),
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_SHA": "c" * 40,
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_OUTPUT": str(tmp_path / "output"),
            "RUNNER_TEMP": str(runner_temp),
            "REVIEWED_CODE_SHA": git(runtime, "rev-parse", "HEAD"),
            "OBS_MODE": "active",
            "OBS_MODULES": "macro,calendar,crypto",
            "OBS_CONFIRMED": "true",
            "OBS_PUBLISHED_SHA": git(public, "rev-parse", "HEAD"),
            "OBS_PIPELINE_STARTED_AT": str(int(when.timestamp()) - 2),
            "OBS_PIPELINE_STATUS": "failed",
            "OBS_PIPELINE_RC": "1",
            "OBS_PAGES_OUTCOME": "success",
            "CODEX_AUTH_JSON": CANARY,
            "TELEGRAM_BOT_TOKEN": CANARY,
            "INVESTO_PUBLIC_PUBLISH_TOKEN": CANARY,
        },
    }


def recommit(context: dict) -> None:
    git(context["public"], "add", ".")
    git(context["public"], "commit", "--quiet", "--no-gpg-sign", "-m", "synthetic change")
    context["env"]["OBS_PUBLISHED_SHA"] = git(context["public"], "rev-parse", "HEAD")


def execute(context: dict) -> tuple[dict | None, dict[str, str]]:
    step = next(s for s in workflow_steps() if s.get("id") == "insights_observation")
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        cwd=context["public"],
        env=context["env"],
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "" and result.stderr == ""
    outputs = dict(
        line.split("=", 1)
        for line in Path(context["env"]["GITHUB_OUTPUT"]).read_text().splitlines()
    )
    if "artifact_path" not in outputs:
        return None, outputs
    path = Path(outputs["artifact_path"])
    assert path.parent.parent == Path(context["env"]["RUNNER_TEMP"])
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    data = path.read_bytes()
    assert len(data) <= 16 * 1024 and CANARY.encode() not in data
    return json.loads(data), outputs


def test_scheduled_receipt_binds_exact_code_and_all_modules_despite_briefing_failure(context: dict):
    report, outputs = execute(context)
    assert report is not None and outputs["capture_status"] == "captured"
    assert report["scheduled_candidate"] is True
    assert report["execution_code_sha"] == context["env"]["REVIEWED_CODE_SHA"]
    assert report["published_sha"] == context["env"]["OBS_PUBLISHED_SHA"]
    assert report["pipeline_status"] == "failed" and report["pipeline_exit_code"] == 1
    assert [row["module"] for row in report["module_evidence"]] == ["macro", "calendar", "crypto"]
    assert all(row["collected_in_this_run"] for row in report["module_evidence"])
    assert report["acceptance"] == "pending_source_receipt_and_pages_review"


@pytest.mark.parametrize(
    ("name", "value"),
    [("GITHUB_EVENT_NAME", "workflow_dispatch"), ("GITHUB_RUN_ATTEMPT", "2")],
)
def test_manual_or_retry_does_not_become_scheduled_candidate(context: dict, name: str, value: str):
    context["env"][name] = value
    report, _ = execute(context)
    assert report is not None and report["status"] == "captured"
    assert report["scheduled_candidate"] is False


def test_old_module_from_baseline_cannot_be_counted_for_current_run(context: dict):
    context["entries"][0] = write_current(
        context["public"], "macro", datetime.now(UTC) - timedelta(days=1)
    )
    context["manifest"].write_bytes(canonical({"schema_version": 1, "modules": context["entries"]}))
    recommit(context)
    report, _ = execute(context)
    assert report is not None and report["status"] == "captured"
    assert report["scheduled_candidate"] is False
    assert report["module_evidence"][0]["collected_in_this_run"] is False


@pytest.mark.parametrize("signal", ["", "false"])
def test_no_confirmed_signal_has_no_module_evidence(context: dict, signal: str):
    context["env"]["OBS_CONFIRMED"] = signal
    context["env"]["OBS_PUBLISHED_SHA"] = CANARY
    report, _ = execute(context)
    assert report is not None and report["status"] == "not_confirmed"
    assert report["scheduled_candidate"] is False and report["module_evidence"] == []


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REVIEWED_CODE_SHA", "d" * 40),
        ("OBS_PUBLISHED_SHA", CANARY),
        ("OBS_MODULES", "macro,crypto,../private"),
        ("OBS_MODULES", "macro,macro"),
        ("OBS_MODE", "shadow"),
        ("GITHUB_REPOSITORY", "murphyGo/investo"),
        ("GITHUB_RUN_ID", CANARY),
    ],
)
def test_invalid_identity_or_mode_is_closed_unavailable(context: dict, name: str, value: str):
    context["env"][name] = value
    report, _ = execute(context)
    assert report == {
        "schema_version": 1,
        "status": "unavailable",
        "reason": "invalid_or_missing_evidence",
        "scheduled_candidate": False,
    }


@pytest.mark.parametrize("damage", ["hash", "snapshot", "oversize", "duplicate_key", "nonfinite"])
def test_invalid_git_evidence_does_not_make_candidate(context: dict, damage: str):
    path = context["public"] / "site_docs/insights/_data/macro/current.json"
    if damage == "hash":
        context["entries"][0]["current_hash"] = "f" * 64
    elif damage == "snapshot":
        data = json.loads(path.read_bytes())
        data["snapshot_id"] = "f" * 64
        path.write_bytes(canonical(data))
        context["entries"][0]["current_hash"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif damage == "oversize":
        path.write_bytes(b" " * (256 * 1024 + 1))
    else:
        data = (
            b'{"schema_version":1,"schema_version":1}'
            if damage == "duplicate_key"
            else b'{"x":NaN}'
        )
        path.write_bytes(data)
        context["entries"][0]["current_hash"] = hashlib.sha256(data).hexdigest()
    context["manifest"].write_bytes(canonical({"schema_version": 1, "modules": context["entries"]}))
    recommit(context)
    report, _ = execute(context)
    assert report is not None and report["status"] == "unavailable"
    assert report["scheduled_candidate"] is False


@pytest.mark.parametrize("started", ["", "invalid", "expired", "future"])
def test_missing_or_insufficient_work_allowance_skips_git_and_artifact(context: dict, started: str):
    value = {
        "expired": str(int(time.time()) - 225 * 60 + 60),
        "future": str(int(time.time()) + 60),
    }.get(started, started)
    context["env"]["OBS_PIPELINE_STARTED_AT"] = value
    context["env"]["GITHUB_WORKSPACE"] = "/does-not-exist"
    report, outputs = execute(context)
    assert report is None and outputs == {"capture_status": "skipped_allowance"}


def test_upload_is_only_a_single_bounded_metadata_file_and_keeps_primary_exit_step():
    steps = workflow_steps()
    capture = next(s for s in steps if s.get("id") == "insights_observation")
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert capture["if"] == "always()" and capture["continue-on-error"] == "true"
    assert capture["timeout-minutes"] == upload["timeout-minutes"] == "1"
    assert upload["continue-on-error"] == "true"
    assert upload["if"] == "always() && steps.insights_observation.outputs.artifact_path != ''"
    assert upload["with"]["path"] == "${{ steps.insights_observation.outputs.artifact_path }}"
    assert upload["with"]["include-hidden-files"] == "false"
    assert upload["with"]["retention-days"] == "7"
    assert all("secrets." not in value for value in capture["env"].values())
    assert steps[-1]["name"] == "Re-emit pipeline exit code" and steps[-1]["if"] == "always()"
    for code in (0, 1, 2):
        result = subprocess.run(
            ["bash", "-c", steps[-1]["run"]],
            env={"PATH": os.defpath, "PIPELINE_RC": str(code)},
            capture_output=True,
            timeout=3,
        )
        assert result.returncode == code
