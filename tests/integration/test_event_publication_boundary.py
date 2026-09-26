"""E11 archive/metadata transactions over real local Git and thread draining.

Presentation sidecars are stubbed; archive writes, index snapshots, receipt
persistence, publisher reconciliation and cancellation use production code.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.models.publication import PublicationRequest, PublishReceipt
from investo.models.segments import US_EQUITY, MarketSegment
from investo.orchestrator import pipeline
from investo.orchestrator.event_receipts import EVENT_RECEIPT_PATH
from investo.publisher.git_ops import GitRunner
from investo.publisher.paths import archive_path
from investo.publisher.publication_receipts import PublicationReceiptError, metadata_hash_at

_TARGET = date(2026, 9, 26)
_INDEX = Path("site_docs/index.md")
_STATIC = Path("site_docs/unchanged.md")
_NEW_METADATA = b'{"schema_version":1,"receipts":[]}\n'


def _briefing() -> Briefing:
    return Briefing(
        target_date=_TARGET,
        market_summary="시장 요약",
        key_issues="전일 사건",
        sector_flow="섹터 동향",
        indicators_events="지표 일정",
        notable_tickers="주요 종목",
        today_watch="다음 확인 사항",
        disclaimer=DISCLAIMER,
        rendered_markdown=f"# 합성 시황\n\n새로운 사건을 확인했습니다.\n\n{DISCLAIMER}",
    )


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _checked(directory: Path, *args: str) -> str:
    result = _git(directory, *args)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@dataclass(frozen=True)
class Repository:
    work: Path
    remote: Path
    baseline: str
    request: PublicationRequest
    original_files: dict[Path, bytes]
    original_index: bytes

    def head(self) -> str:
        return _checked(self.work, "rev-parse", "HEAD")

    def remote_head(self) -> str:
        return _checked(self.remote, "rev-parse", "refs/heads/main")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repository:
    work, remote = tmp_path / "work", tmp_path / "remote.git"
    work.mkdir()
    remote.mkdir()
    _checked(remote, "init", "--bare")
    _checked(work, "init", "-b", "main")
    _checked(work, "config", "user.name", "Publication Boundary Test")
    _checked(work, "config", "user.email", "publication@example.invalid")
    monkeypatch.chdir(work)
    monkeypatch.delenv("INVESTO_DRY_RUN", raising=False)
    monkeypatch.delenv("INVESTO_PUBLISH_WEEKLY", raising=False)
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", Path("archive"))
    monkeypatch.setattr("investo.publisher.publication_receipts.time.sleep", lambda _: None)

    original = {
        archive_path(_TARGET, segment=US_EQUITY): b"previous archive\n",
        EVENT_RECEIPT_PATH: b'{"schema_version":1,"receipts":[]}',
        _INDEX: b"previous index page\n",
        _STATIC: b"unchanged sidecar\n",
    }
    for path, content in original.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    _checked(work, "add", ".")
    _checked(work, "commit", "-m", "baseline")
    _checked(work, "remote", "add", "origin", str(remote))
    _checked(work, "push", "-u", "origin", "main")
    baseline = _checked(work, "rev-parse", "HEAD")
    request = PublicationRequest(
        run_id="boundary-test",
        baseline_metadata_hash=metadata_hash_at(baseline, (EVENT_RECEIPT_PATH,)),
    )

    def update_index(*args: object, **kwargs: object) -> tuple[Path, ...]:
        _INDEX.write_bytes(b"new index page\n")
        return (_INDEX,)

    monkeypatch.setattr(pipeline, "SITE_INDEX_PATH", _INDEX)
    monkeypatch.setattr(pipeline, "_build_publish_heatmap_svg", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "update_latest_index_pages", update_index)
    monkeypatch.setattr(pipeline, "write_og_card", lambda *_a, **_k: ())
    monkeypatch.setattr(pipeline, "_build_quality_snapshot", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "append_quality_snapshot", lambda *_a, **_k: _STATIC)
    monkeypatch.setattr(pipeline, "update_quality_page", lambda *_a, **_k: _STATIC)
    monkeypatch.setattr(pipeline, "_enforce_quality_consistency_gate", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "append_forecast_entries", lambda *_a, **_k: _STATIC)
    monkeypatch.setattr(pipeline, "update_accuracy_page", lambda *_a, **_k: _STATIC)
    monkeypatch.setattr(pipeline, "_maybe_publish_monthly_retrospective", lambda *_a, **_k: ())
    monkeypatch.setattr(
        "investo.publisher.watchlist_pages.update_watchlist_pages", lambda *_a, **_k: ()
    )
    monkeypatch.setattr(
        "investo.publisher.watchlist_pages.write_daily_impact_page", lambda *_a, **_k: _STATIC
    )
    return Repository(work, remote, baseline, request, original, (work / ".git/index").read_bytes())


async def _publish(
    repository: Repository,
    *,
    runner: GitRunner | None = None,
    receipts: list[PublishReceipt] | None = None,
) -> dict[MarketSegment, Path]:
    return await pipeline._stage_publish_segments(
        {US_EQUITY: _briefing()},
        _TARGET,
        phase_one_complete=True,
        git_runner=runner,
        publication_request=repository.request,
        transactional_metadata={EVENT_RECEIPT_PATH: _NEW_METADATA},
        publication_receipts=receipts,
    )


@pytest.mark.asyncio
async def test_archive_and_metadata_share_confirmed_remote_commit(repository: Repository) -> None:
    observed: list[PublishReceipt] = []
    paths = await _publish(repository, receipts=observed)
    assert repository.head() == repository.remote_head() != repository.baseline
    assert observed[0].status == "pending"
    assert observed[-1].status == "remote_confirmed"
    for path in (paths[US_EQUITY], EVENT_RECEIPT_PATH, _INDEX):
        remote_bytes = _git(repository.remote, "show", f"refs/heads/main:{path}").stdout.encode()
        assert remote_bytes == path.read_bytes()
    private = list(Path(".tmp/publication-receipts").glob("*.json"))
    assert private
    assert {json.loads(path.read_bytes())["status"] for path in private} >= {
        "pending",
        "remote_confirmed",
    }
    assert ".tmp/" not in _checked(repository.remote, "ls-tree", "-r", "--name-only", "main")


class FailingRunner:
    def __init__(self, repository: Repository, phase: str, *, block: bool) -> None:
        self.repository = repository
        self.phase = phase
        self.block = block
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls: list[list[str]] = []

    def __call__(
        self, args: list[str], *, capture_output: bool, text: bool, check: bool
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        command = args[1]
        fail_here = command == ("add" if self.phase == "pre_commit" else "push")
        if fail_here:
            if command == "add":
                # Simulate add partially succeeding before its error is observed.
                assert _git(self.repository.work, *args[1:]).returncode == 0
            self.entered.set()
            if self.block:
                assert self.release.wait(10), "test did not release the Git worker"
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="injected failure")
        if self.phase == "post_commit" and command == "fetch":
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="remote unavailable")
        return _git(self.repository.work, *args[1:])


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["pre_commit", "post_commit"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_publish_failure_or_cancellation_respects_commit_boundary(
    repository: Repository, phase: str, cancel: bool
) -> None:
    runner = FailingRunner(repository, phase, block=cancel)
    task = asyncio.create_task(_publish(repository, runner=runner))
    if cancel:
        try:
            assert await asyncio.to_thread(runner.entered.wait, 10)
            task.cancel()
        finally:
            runner.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=10)
    else:
        with pytest.raises(PublicationReceiptError) as caught:
            await task
        assert caught.value.phase == phase
    assert repository.remote_head() == repository.baseline
    if phase == "pre_commit":
        assert repository.head() == repository.baseline
        assert (repository.work / ".git/index").read_bytes() == repository.original_index
        for path, previous in repository.original_files.items():
            assert path.read_bytes() == previous
        assert not list(Path(".tmp/publication-receipts").glob("*.json"))
    else:
        assert repository.head() != repository.baseline
        assert EVENT_RECEIPT_PATH.read_bytes() == _NEW_METADATA
        assert _INDEX.read_bytes() == b"new index page\n"
        article = archive_path(_TARGET, segment=US_EQUITY)
        assert article.read_text() == _briefing().rendered_markdown
        observed = [
            json.loads(path.read_bytes())
            for path in Path(".tmp/publication-receipts").glob("*.json")
        ]
        assert any(
            r["local_sha"] == repository.head() and r["status"] == "pending" for r in observed
        )
        assert any(r["status"] == "outcome_unknown" for r in observed)


@pytest.mark.asyncio
async def test_precommit_rejection_preserves_unrelated_staged_work(repository: Repository) -> None:
    Path("unrelated.txt").write_text("already staged work\n")
    _checked(repository.work, "add", "unrelated.txt")
    original_index = (repository.work / ".git/index").read_bytes()
    with pytest.raises(PublicationReceiptError) as caught:
        await _publish(repository)
    assert caught.value.phase == "pre_commit"
    assert repository.head() == repository.remote_head() == repository.baseline
    assert (repository.work / ".git/index").read_bytes() == original_index
    assert _checked(repository.work, "diff", "--cached", "--name-only") == "unrelated.txt"
    for path, previous in repository.original_files.items():
        assert path.read_bytes() == previous
