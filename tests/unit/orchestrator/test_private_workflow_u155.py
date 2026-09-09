from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "ops/private-runtime/daily-briefing.yml"


def test_template_is_private_serialized_manual_and_has_no_public_credentials() -> None:
    raw = TEMPLATE.read_text()
    workflow = yaml.load(raw, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["concurrency"] == {
        "group": "investo-codex-auth-v1",
        "cancel-in-progress": "false",
    }
    job = workflow["jobs"]["qualification"]
    assert job["environment"] == "codex-runtime"
    assert "github.event.repository.private == true" in job["if"]
    assert job["env"]["INVESTO_DRY_RUN"] == "1"
    assert "TELEGRAM_BOT_TOKEN" not in raw
    assert "INVESTO_PUBLIC_PUBLISH_TOKEN" not in raw
    assert "upload-artifact" not in raw and "gh workflow run" not in raw
    assert "${{ inputs." not in "\n".join(step.get("run", "") for step in job["steps"])
    for step in job["steps"]:
        if "uses" in step:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])


def test_workflow_shell_scripts_parse_and_have_valid_python_arguments() -> None:
    workflow = yaml.load(TEMPLATE.read_text(), Loader=yaml.BaseLoader)
    scripts = [step["run"] for step in workflow["jobs"]["qualification"]["steps"] if "run" in step]
    for script in scripts:
        result = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert " + " not in script
        for code in re.findall(r" -c '([^']*)'", script):
            compile(code, "<workflow-python>", "exec")
    download = next(script for script in scripts if "codex.tar.gz" in script)
    assert "sha256sum --check" in download
    assert "rust-v0.153.4/codex-x86_64-unknown-linux-musl.tar.gz" in download
    assert "@openai/codex" not in download


def test_installation_and_invocation_keep_code_and_archive_separate() -> None:
    workflow = yaml.load(TEMPLATE.read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["qualification"]["steps"]
    checkouts = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
    assert [(step["with"]["path"], step["with"]["ref"]) for step in checkouts] == [
        ("runtime-code", "${{ vars.REVIEWED_CODE_SHA }}"),
        ("public-data", "main"),
    ]
    assert all(step["with"]["persist-credentials"] == "false" for step in checkouts)
    setup = next(step for step in steps if "uv sync" in step.get("run", ""))
    assert setup["working-directory"] == "runtime-code"
    assert "--no-editable" in setup["run"] and "--frozen" in setup["run"]
    calls = [step for step in steps if " -m investo" in step.get("run", "")]
    assert len(calls) == 2
    assert all(step["working-directory"] == "public-data" for step in calls)
    assert all('python" -I -m investo.orchestrator.codex_runtime' in step["run"] for step in calls)
    assert "CODEX_AUTH_JSON" not in calls[0]["env"]
    assert calls[1]["env"]["CODEX_AUTH_JSON"] == "${{ secrets.CODEX_AUTH_JSON }}"
    assert calls[1]["env"]["CODEX_SECRET_WRITE_TOKEN"] == "${{ secrets.CODEX_SECRET_WRITE_TOKEN }}"


def test_public_preflight_still_runs_with_stdlib_python_outside_venv() -> None:
    env = {
        "PATH": os.defpath,
        "INVESTO_DRY_RUN": "1",
        "CLAUDE_CODE_OAUTH_TOKEN": "synthetic-claude",
        "SITE_URL_BASE": "https://example.com",
    }
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "scripts/check_daily_briefing_env.py")],
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
