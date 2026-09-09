"""Real two-stage subprocesses and local Git publication, without live services."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.briefing.claude_code import ClaudeRunner
from investo.briefing.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO
from investo.briefing.pipeline import generate_briefing
from investo.briefing.private_claude import PrivateClaudeRunner
from investo.models import MarketSegment, NormalizedItem
from investo.publisher.errors import PublisherGitError
from investo.publisher.git_ops import commit_and_push
from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown
from tests.unit.briefing.test_codex_cli_u155 import make_runner


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("segment", [None, "domestic-equity", "us-equity", "crypto"])
async def test_both_providers_use_existing_two_stage_parser_and_assembly(
    tmp_path: Path, provider: str, segment: MarketSegment | None
) -> None:
    counter = tmp_path / "calls"
    outputs = [valid_classification_stdout(1), valid_stage2_markdown()]
    body = (
        f"counter=Path({str(counter)!r})\n"
        "n=int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(n+1))\n"
        f"output={outputs!r}[n]\n"
    )
    runner: ClaudeRunner
    if provider == "codex":
        runner = make_runner(tmp_path, body)
    else:
        binary = tmp_path / "claude"
        binary.write_text(
            f"#!{sys.executable}\nfrom pathlib import Path\nimport sys\n"
            "prompt=sys.stdin.read()\n" + body + "print(output)\n"
        )
        binary.chmod(0o700)
        runner = PrivateClaudeRunner(str(binary), sys.executable, "synthetic-claude")
    item = NormalizedItem(
        source_name="fixture-news",
        category="news",
        title="시장 흐름 점검",
        published_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
    )
    try:
        briefing = await generate_briefing(date(2026, 9, 8), [item], runner=runner, segment=segment)
    finally:
        runner.close()
    assert counter.read_text() == "2"
    expected = DISCLAIMER_CRYPTO if segment == "crypto" else DISCLAIMER
    assert expected.split("\n", 1)[1] in briefing.rendered_markdown
    assert "synthetic-" not in briefing.rendered_markdown
    assert all(
        getattr(briefing, field).strip()
        for field in (
            "market_summary",
            "key_issues",
            "sector_flow",
            "indicators_events",
            "notable_tickers",
            "today_watch",
        )
    )


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def initialize_repo(path: Path, *, bare: bool = False) -> None:
    path.mkdir()
    git(path, "init", "--initial-branch=main", *(["--bare"] if bare else []))
    if not bare:
        git(path, "config", "user.name", "Synthetic Test")
        git(path, "config", "user.email", "fixture@example.invalid")
        git(path, "config", "commit.gpgsign", "false")
        git(path, "config", "core.hooksPath", "/dev/null")


@pytest.mark.parametrize("reject", [False, True])
def test_private_code_and_latest_public_archive_have_separate_git_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reject: bool
) -> None:
    private, remote, public = (tmp_path / name for name in ("private", "public.git", "public"))
    initialize_repo(private)
    initialize_repo(remote, bare=True)
    initialize_repo(public)
    (private / "auth.json").write_text(json.dumps({"synthetic-secret": "private-only"}))
    (private / "workflow.yml").write_text("reviewed runtime fixture\n")
    git(private, "add", "workflow.yml")
    git(private, "commit", "-m", "private runtime")
    private_sha = git(private, "rev-parse", "HEAD")
    (public / "archive").mkdir()
    (public / "archive/previous.md").write_text("previous published briefing\n")
    git(public, "add", "archive/previous.md")
    git(public, "commit", "-m", "public archive")
    git(public, "remote", "add", "origin", str(remote))
    git(public, "push", "origin", "main")
    public_sha = git(public, "rev-parse", "HEAD")
    target = Path("archive/current.md")
    (public / target).write_text("finalized briefing\n")
    (public / "unrelated.txt").write_text("must not be published\n")
    if reject:
        git(remote, "config", "receive.denyNonFastForwards", "true")
        git(remote, "config", "receive.denyCurrentBranch", "refuse")
        # Deterministic server-side rejection, without an external Git host.
        hook = remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o700)
    monkeypatch.chdir(public)
    commit_and_push("dry run", [target], dry_run=True)
    assert git(public, "rev-parse", "HEAD") == public_sha
    if reject:
        with pytest.raises(PublisherGitError):
            commit_and_push("publish", [target], retries=0)
        assert git(remote, "rev-parse", "main") == public_sha
    else:
        commit_and_push("publish", [target], retries=0)
        published = git(remote, "rev-parse", "main")
        commit_and_push("publish same date", [target], retries=0)
        assert git(remote, "rev-parse", "main") == published
        assert git(remote, "show", "main:archive/previous.md") == "previous published briefing"
        assert git(remote, "ls-tree", "-r", "--name-only", "main").splitlines() == [
            "archive/current.md",
            "archive/previous.md",
        ]
        assert git(public, "rev-parse", "HEAD^") == public_sha
    assert git(private, "rev-parse", "HEAD") == private_sha
    assert (private / "auth.json").exists()
