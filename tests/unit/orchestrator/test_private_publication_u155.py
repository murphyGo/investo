from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "ops/private-runtime/git-credential-investo.sh"
PRODUCTION = ROOT / "ops/private-runtime/production-briefing.yml"


@pytest.mark.parametrize(
    ("page_state", "should_dispatch"),
    [
        ("queued", False),
        ("in_progress", False),
        ("waiting", False),
        ("pending", False),
        ("requested", False),
        ("success", False),
        ("failure", True),
        ("cancelled", True),
        ("timed_out", True),
        ("skipped", True),
        ("missing", True),
    ],
)
def test_pages_retries_failed_deployment_without_duplicate_active_run(
    page_state: str, should_dispatch: bool, tmp_path: Path
) -> None:
    workflow = yaml.load(PRODUCTION.read_text(), Loader=yaml.BaseLoader)
    pages = next(
        step
        for step in workflow["jobs"]["briefing"]["steps"]
        if step["name"] == "Ensure Pages deployment"
    )
    gh = tmp_path / "gh"
    gh.write_text(
        '#!/bin/sh\ncase "$1 $2" in\n'
        '  "run list") printf "%s\\n" "$TEST_PAGE_STATE" ;;\n'
        '  "workflow run") printf "%s\\n" "$*" > "$TEST_DISPATCH" ;;\n'
        "  *) exit 1 ;;\nesac\n"
    )
    gh.chmod(0o700)
    dispatch = tmp_path / "dispatch"
    result = subprocess.run(
        ["bash", "-c", pages["run"]],
        text=True,
        capture_output=True,
        env={
            "PATH": f"{tmp_path}:{os.defpath}",
            "TEST_PAGE_STATE": page_state,
            "TEST_DISPATCH": str(dispatch),
            "PUBLISHED_SHA": "a" * 40,
            "PIPELINE_STARTED_AT": str(int(time.time())),
        },
    )
    assert result.returncode == 0, result.stderr
    assert dispatch.exists() == should_dispatch
    if should_dispatch:
        assert dispatch.read_text().strip() == (
            "workflow run pages.yml --repo murphyGo/investo --ref main"
        )


@pytest.mark.parametrize("path", ["murphyGo/investo", "murphyGo/investo.git"])
def test_git_gets_publisher_token_only_for_public_destination(path: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"credential.helper=!sh {HELPER}",
            "-c",
            "credential.useHttpPath=true",
            "credential",
            "fill",
        ],
        input=f"protocol=https\nhost=github.com\npath={path}\n\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env={
            "PATH": os.defpath,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "INVESTO_PUBLIC_PUBLISH_TOKEN": "synthetic-publish",
        },
    )
    assert result.returncode == 0
    assert "password=synthetic-publish" in result.stdout
    assert "synthetic-publish" not in result.stderr


@pytest.mark.parametrize(
    "credential_request",
    [
        "protocol=https\nhost=evil.invalid\npath=murphyGo/investo\n\n",
        "protocol=http\nhost=github.com\npath=murphyGo/investo\n\n",
        "protocol=https\nhost=github.com\npath=murphyGo/investo-runtime\n\n",
        "protocol=https\nhost=github.com\n\n",
    ],
)
def test_helper_rejects_other_destinations(credential_request: str) -> None:
    result = subprocess.run(
        ["sh", str(HELPER), "get"],
        input=credential_request,
        text=True,
        capture_output=True,
        env={"PATH": os.defpath, "INVESTO_PUBLIC_PUBLISH_TOKEN": "synthetic-publish"},
    )
    assert result.stdout == "" and result.stderr == ""


def test_production_is_gated_and_preserves_publication_boundaries() -> None:
    raw = PRODUCTION.read_text()
    workflow = yaml.load(raw, Loader=yaml.BaseLoader)
    job = workflow["jobs"]["briefing"]
    assert "vars.CODEX_PRODUCTION_ENABLED == '1'" in job["if"]
    assert "github.event.repository.private == true" in job["if"]
    assert workflow["concurrency"]["group"] == "investo-codex-auth-v1"
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    assert job["environment"] == "codex-runtime"
    assert job["env"]["INVESTO_LLM_PROVIDER"] == "codex"
    assert job["env"]["INVESTO_CODEX_MODEL"] == "gpt-6-astra"
    assert job["env"]["INVESTO_DRY_RUN"] == "0"
    assert "CODEX_AUTH_JSON" not in job["env"]
    steps = job["steps"]
    pipeline = next(step for step in steps if step.get("id") == "pipeline")
    assert pipeline["working-directory"] == "public-data"
    assert 'python" -I -m investo.orchestrator.codex_runtime' in pipeline["run"]
    assert (
        pipeline["env"]["INVESTO_PUBLIC_PUBLISH_TOKEN"]
        == "${{ secrets.INVESTO_PUBLIC_PUBLISH_TOKEN }}"
    )
    assert all(
        step["with"]["persist-credentials"] == "false"
        for step in steps
        if step.get("uses", "").startswith("actions/checkout@")
    )
    pages = next(step for step in steps if step["name"] == "Ensure Pages deployment")
    assert pages["if"] == "steps.pipeline.outputs.publication_committed == 'true'"
    assert "--repo murphyGo/investo" in pages["run"]
    assert "--commit" in pages["run"]
    assert steps[-1]["if"] == "always()"
    assert "upload-artifact" not in raw
    for step in steps:
        if "run" in step:
            result = subprocess.run(
                ["bash", "-n"], input=step["run"], text=True, capture_output=True
            )
            assert result.returncode == 0, result.stderr
            assert "${{ inputs." not in step["run"]
