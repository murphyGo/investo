"""Public activation integration: real collector/metrics/renderer/store, synthetic HTTP only."""

from __future__ import annotations

import importlib.util
import json
import logging
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pytest
import yaml
from tests.unit.sector_dashboard.test_public_probe import _json, _transport

import investo.sector_dashboard.public_build as build
from investo.models.sector import SectorCoverageStatus
from investo.models.sector_public import PublicBuildIssueCode, PublicSectorBuildStatus
from investo.sector_dashboard.public_store import read_public_sector_projection

_ROOT = Path(__file__).resolve().parents[3]
_TARGET = date(2026, 9, 25)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    (tmp_path / "site_docs").mkdir()
    return tmp_path


async def _run(root: Path, **kwargs: object) -> build.PublicBuildReport:
    async with httpx.AsyncClient(transport=_transport([], body=_json(), **kwargs)) as client:
        return await build.build_public_sector(client, repository_root=root, target_date=_TARGET)


async def test_fresh_unchanged_partial_and_auth_failure_preserve_exact_pair(
    repository: Path,
) -> None:
    first = await _run(repository)
    assert first.status is PublicSectorBuildStatus.PROMOTED and first.exit_code == 0
    pair = read_public_sector_projection(repository)
    assert pair is not None
    files = list((repository / "site_docs/sectors").iterdir())
    assert {p.name for p in files} == {"index.md", "latest.json"}
    mtimes = {p: p.stat().st_mtime_ns for p in files}

    unchanged = await _run(repository)
    assert unchanged.status is PublicSectorBuildStatus.UNCHANGED and unchanged.exit_code == 0
    assert {p: p.stat().st_mtime_ns for p in files} == mtimes
    assert read_public_sector_projection(repository) == pair

    partial = await _run(repository, failure="XLK", status=503)
    assert partial.status is PublicSectorBuildStatus.PROMOTED and partial.exit_code == 2
    assert partial.coverage is SectorCoverageStatus.PARTIAL
    assert partial.available_sector_count == partial.comparable_sector_count == 10
    assert partial.request_count == 14 and partial.failed_request_count == 3
    assert partial.source_issue_codes
    assert not partial.failure_codes
    partial_pair = read_public_sector_projection(repository)
    assert partial_pair is not None and partial_pair != pair
    assert "생성 시점 신선도:" in partial_pair.markdown_bytes.decode()
    assert "secret-probe-sentinel" not in partial.model_dump_json()
    assert "secret-probe-sentinel" not in partial_pair.markdown_bytes.decode()

    unchanged_partial = await _run(repository, failure="XLK", status=404)
    # Different diagnostic codes can produce a different canonical pair; both stay partial/red.
    assert unchanged_partial.exit_code == 2
    retained = read_public_sector_projection(repository)
    failed = await _run(repository, failure="SPY", status=401)
    assert failed.status is PublicSectorBuildStatus.HELD_LAST_GOOD and failed.exit_code == 2
    assert failed.snapshot_id == unchanged_partial.snapshot_id and failed.as_of_date == _TARGET
    assert failed.request_count == failed.failed_request_count == 1
    assert "auth.rejected" in failed.model_dump_json()
    assert read_public_sector_projection(repository) == retained


async def test_first_publish_failure_creates_no_public_files(repository: Path) -> None:
    report = await _run(repository, failure="SPY", status=401)
    assert report.status is PublicSectorBuildStatus.BLOCKED and report.exit_code == 2
    assert report.snapshot_id is report.as_of_date is None
    assert not (repository / "site_docs/sectors").exists()


@pytest.mark.parametrize(("count", "end"), [(5, _TARGET), (64, date(2026, 9, 24))])
async def test_stale_or_short_history_holds_last_good(
    repository: Path, count: int, end: date
) -> None:
    await _run(repository)
    before = read_public_sector_projection(repository)
    async with httpx.AsyncClient(
        transport=_transport([], body=_json(count=count, end=end))
    ) as client:
        report = await build.build_public_sector(
            client, repository_root=repository, target_date=_TARGET
        )
    assert report.status is PublicSectorBuildStatus.HELD_LAST_GOOD and report.exit_code == 2
    assert read_public_sector_projection(repository) == before


@pytest.mark.parametrize("resource", ["cpu", "wall"])
async def test_measured_resource_overrun_cannot_promote(
    repository: Path, monkeypatch: pytest.MonkeyPatch, resource: str
) -> None:
    await _run(repository)
    before = read_public_sector_projection(repository)
    cpu = iter([0, 31, 31] if resource == "cpu" else [0, 1, 1])
    wall = iter([0, 121, 121] if resource == "wall" else [0, 1, 1])
    monkeypatch.setattr(
        build, "time", SimpleNamespace(process_time=lambda: next(cpu), monotonic=lambda: next(wall))
    )
    report = await _run(repository)
    assert report.status is PublicSectorBuildStatus.HELD_LAST_GOOD
    assert PublicBuildIssueCode.RESOURCE in report.failure_codes
    assert read_public_sector_projection(repository) == before


async def test_corrupt_store_is_blocked_without_overwriting_it(repository: Path) -> None:
    await _run(repository)
    markdown = repository / "site_docs/sectors/index.md"
    markdown.write_text("damaged pair")
    report = await _run(repository)
    assert report.status is PublicSectorBuildStatus.BLOCKED and report.exit_code == 2
    assert PublicBuildIssueCode.STORE in report.failure_codes
    assert markdown.read_text() == "damaged pair"


async def test_internal_exception_is_closed_and_holds_last_good(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _run(repository)
    before = read_public_sector_projection(repository)

    def reject(*args: object, **kwargs: object) -> None:
        raise RuntimeError("provider-secret-should-never-escape")

    monkeypatch.setattr(build, "render_public_sector_projection", reject)
    report = await _run(repository)
    assert report.status is PublicSectorBuildStatus.HELD_LAST_GOOD
    assert report.failure_codes == (PublicBuildIssueCode.INTERNAL,)
    assert "provider-secret" not in report.model_dump_json()
    assert read_public_sector_projection(repository) == before


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "sector_publish_cli", _ROOT / "scripts/publish_sector_dashboard.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("failure", "code", "status"),
    [(None, 0, "promoted"), ("XLK", 2, "promoted"), ("SPY", 2, "blocked")],
)
def test_cli_real_pipeline_and_control_output(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str | None,
    code: int,
    status: str,
) -> None:
    module = _cli()
    client_class = httpx.AsyncClient
    calls: list[str] = []

    def client(**kwargs: object) -> httpx.AsyncClient:
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return client_class(transport=_transport(calls, body=_json(), failure=failure), **kwargs)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 9, 25, 22, tzinfo=UTC)

    monkeypatch.setattr(module, "_ROOT", repository)
    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    output, summary = repository / "output", repository / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    previous = logging.root.manager.disable
    try:
        assert module.main(["--write"]) == code
        captured = capsys.readouterr()
        assert captured.err == ""
        assert json.loads(captured.out)["status"] == status
        assert output.read_text() == f"build_status={status}\n"
        assert captured.out.strip() in summary.read_text()
        count = len(calls)
        assert module.main(["--verify-only"]) == (0 if status == "promoted" else 2)
        assert len(calls) == count
    finally:
        logging.disable(previous)


def test_output_screen_failure_never_emits_publishable_control(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _cli()

    async def unsafe() -> tuple[str, int]:
        return '{"status":"promoted","provider":"secret-output-sentinel"}', 0

    monkeypatch.setattr(module, "_build", unsafe)
    monkeypatch.setenv("HF_DATA_API_KEY", "secret-output-sentinel")
    output = repository / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    previous = logging.root.manager.disable
    try:
        assert module.main(["--write"]) == 2
    finally:
        logging.disable(previous)
    assert output.read_text() == "build_status=blocked\n"
    assert "secret-output-sentinel" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "args", [[], ["--write", "--date", "2026-09-25"], ["--url", "https://example.com"]]
)
def test_cli_rejects_overrides(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli().main(args) == 2
    assert "build.arguments" in capsys.readouterr().out


def test_activation_workflow_bounds_publication_and_preserves_partial_failure() -> None:
    text = (_ROOT / ".github/workflows/sector-dashboard.yml").read_text()
    workflow = yaml.safe_load(text)
    trigger = workflow.get("on", workflow.get(True))
    assert trigger == {"workflow_dispatch": None, "schedule": [{"cron": "35 21 * * 1-5"}]}
    assert workflow["permissions"] == {"contents": "write", "actions": "write"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["refresh"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    steps = job["steps"]
    build_step = next(s for s in steps if s.get("id") == "build")
    assert "process_exit_code=$result" in build_step["run"] and "exit 0" in build_step["run"]
    publish = next(s for s in steps if "git push" in s.get("run", ""))
    assert "git add -- site_docs/sectors/index.md site_docs/sectors/latest.json" in publish["run"]
    assert "git push origin HEAD:main" in publish["run"]
    assert "--force" not in text and "git rebase" not in text
    validate = next(s for s in steps if "mkdocs build --strict" in s.get("run", ""))
    deploy = next(s for s in steps if "gh workflow run pages.yml --ref main" in s.get("run", ""))
    assert validate["if"] == publish["if"] == deploy["if"]
    assert "promoted" in publish["if"] and "unchanged" in publish["if"]
    assert steps.index(validate) < steps.index(publish) < steps.index(deploy)
    assert steps[-1]["if"] == "always()" and "exit 2" in steps[-1]["run"]
    assert "secrets." not in text and "HF_DATA_API_KEY" not in text
    assert "telegram" not in text.lower() and "daily-briefing" not in text.lower()
    pages = (_ROOT / ".github/workflows/pages.yml").read_text()
    assert pages.index("publish_sector_dashboard.py --verify-only") < pages.index(
        "run: uv run mkdocs build --strict"
    )


@pytest.mark.parametrize("concurrent_push", [False, True])
def test_actual_workflow_git_step_stages_only_pair_and_never_overwrites_main(
    tmp_path: Path, concurrent_push: bool
) -> None:
    remote, checkout, other = (tmp_path / name for name in ("remote.git", "checkout", "other"))

    def git(*args: str, cwd: Path = tmp_path) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
        ).stdout.strip()

    git("init", "--bare", str(remote))
    git("init", "-b", "main", str(checkout))
    git("config", "user.name", "Test", cwd=checkout)
    git("config", "user.email", "test@example.com", cwd=checkout)
    (checkout / "unrelated.txt").write_text("keep this committed content")
    git("add", "unrelated.txt", cwd=checkout)
    git("commit", "-m", "seed", cwd=checkout)
    git("remote", "add", "origin", str(remote), cwd=checkout)
    git("push", "origin", "main", cwd=checkout)
    if concurrent_push:
        git("clone", "--branch", "main", str(remote), str(other))
        git("config", "user.name", "Test", cwd=other)
        git("config", "user.email", "test@example.com", cwd=other)
        (other / "concurrent.txt").write_text("new main content")
        git("add", "concurrent.txt", cwd=other)
        git("commit", "-m", "advance main", cwd=other)
        git("push", "origin", "main", cwd=other)
    remote_before = git("rev-parse", "refs/heads/main", cwd=remote)
    pair = checkout / "site_docs/sectors"
    pair.mkdir(parents=True)
    (pair / "index.md").write_text("validated markdown fixture")
    (pair / "latest.json").write_text('{"validated":"fixture"}')
    (checkout / "unrelated.txt").write_text("dirty content must not be committed")
    workflow = yaml.safe_load((_ROOT / ".github/workflows/sector-dashboard.yml").read_text())
    script = next(
        s["run"] for s in workflow["jobs"]["refresh"]["steps"] if "git push" in s.get("run", "")
    )
    result = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", script], cwd=checkout, text=True, capture_output=True
    )
    assert (result.returncode != 0) is concurrent_push
    remote_after = git("rev-parse", "refs/heads/main", cwd=remote)
    if concurrent_push:
        assert remote_after == remote_before
        assert git("show", "main:concurrent.txt", cwd=remote) == "new main content"
    else:
        assert remote_after != remote_before
        assert set(
            git("diff-tree", "--no-commit-id", "--name-only", "-r", "main", cwd=remote).splitlines()
        ) == {"site_docs/sectors/index.md", "site_docs/sectors/latest.json"}
        subprocess.run(["bash", "-eo", "pipefail", "-c", script], cwd=checkout, check=True)
        assert git("rev-parse", "refs/heads/main", cwd=remote) == remote_after
    assert git("show", "main:unrelated.txt", cwd=remote) == "keep this committed content"
