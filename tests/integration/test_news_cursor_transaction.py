"""News cursor E11 transactions over real local Git and sealed producer output."""

from __future__ import annotations

import json
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from investo.models.news_window import NewsCursorLedger
from investo.orchestrator.event_publication import load_remote_event_baseline
from investo.orchestrator.news_window import load_committed_news_cursors
from investo.publisher.publication_receipts import PublicationReceiptError
from tests.integration.test_event_publication_boundary import _checked, _git
from tests.integration.test_news_window_pipeline import (
    _CURSOR_PATH,
    _PRICE_DATE,
    _RUN_START,
    NewsRepository,
    run_news_pipeline,
)
from tests.integration.test_news_window_pipeline import (
    _base_repository as _base_repository,
)
from tests.integration.test_news_window_pipeline import (
    news_repository as news_repository,
)


@pytest.mark.parametrize("advance_after_accept", [False, True])
async def test_news_cursor_lost_push_response_is_confirmed_by_remote_ancestry(
    news_repository: NewsRepository,
    monkeypatch: pytest.MonkeyPatch,
    advance_after_accept: bool,
) -> None:
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        result = _git(news_repository.work, *args[1:])
        if args[1] == "push":
            assert result.returncode == 0
            if advance_after_accept:
                news_repository.advance_remote()
            return subprocess.CompletedProcess(args, 1, "", "synthetic response loss")
        return result

    result, observed = await run_news_pipeline(monkeypatch, git_runner=runner)
    assert result.publication_committed is True
    assert sum(args[1] == "push" for args in calls) == 1
    assert not any(args[1] == "rebase" for args in calls)
    assert (news_repository.head() != news_repository.remote_head()) is advance_after_accept
    receipt = observed["publish"].data["publication_receipts"][-1]
    assert receipt.status == "remote_confirmed" and receipt.local_sha == news_repository.head()
    remote_ledger = news_repository.remote_ledger()
    assert all(cursor.end_utc == _RUN_START for cursor in remote_ledger.cursors)
    manifest_paths = tuple(Path("archive/_meta/news_windows").glob("*.json"))
    assert len(manifest_paths) == 1
    manifest_bytes = manifest_paths[0].read_bytes()
    assert news_repository.remote_bytes(manifest_paths[0]) == manifest_bytes
    assert receipt.local_sha.encode() not in manifest_bytes
    assert (
        news_repository.remote_bytes(Path(f"archive/us-equity/2026/09/{_PRICE_DATE}.md"))
        is not None
    )


@pytest.mark.parametrize("phase", ["pre_commit", "post_commit"])
async def test_news_cursor_failure_restores_before_commit_and_retains_pending_after(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    baseline = news_repository.remote_head()
    before = _CURSOR_PATH.read_bytes()
    before_index = (news_repository.work / ".git/index").read_bytes()
    pushing = False

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal pushing
        if phase == "pre_commit" and args[1] == "add":
            assert _git(news_repository.work, *args[1:]).returncode == 0
            return subprocess.CompletedProcess(args, 1, "", "synthetic add failure")
        if phase == "post_commit" and args[1] == "push":
            pushing = True
            return subprocess.CompletedProcess(args, 1, "", "synthetic disconnected push")
        if pushing and args[1] == "fetch":
            return subprocess.CompletedProcess(args, 1, "", "synthetic unavailable remote")
        return _git(news_repository.work, *args[1:])

    result, observed = await run_news_pipeline(monkeypatch, git_runner=runner)
    assert not result.publication_committed
    error = observed["publish"].error
    assert isinstance(error, PublicationReceiptError) and error.phase == phase
    assert news_repository.remote_head() == baseline
    assert news_repository.remote_bytes(_CURSOR_PATH) == before
    observed["publisher"].send.assert_not_awaited()
    if phase == "pre_commit":
        assert news_repository.head() == baseline
        assert _CURSOR_PATH.read_bytes() == before
        assert (news_repository.work / ".git/index").read_bytes() == before_index
        assert not list(Path("archive/_meta/news_windows").glob("*.json"))
        assert not Path(f"archive/us-equity/2026/09/{_PRICE_DATE}.md").exists()
    else:
        assert news_repository.head() != baseline
        assert _CURSOR_PATH.read_bytes() != before
        assert Path(f"archive/us-equity/2026/09/{_PRICE_DATE}.md").exists()
        private = [
            json.loads(path.read_bytes())
            for path in Path(".tmp/publication-receipts").glob("*.json")
        ]
        assert {row["status"] for row in private} >= {"pending", "outcome_unknown"}
        assert any(row["local_sha"] == news_repository.head() for row in private)
        remote = load_remote_event_baseline(observed_at=_RUN_START)
        next_baseline = load_committed_news_cursors(remote.baseline_sha, run_id="next-run")
        assert next_baseline.baseline_sha == baseline
        assert all(
            row.end_utc == _RUN_START - timedelta(days=3) for row in next_baseline.ledger.cursors
        )


async def test_notification_failure_preserves_confirmed_cursor_and_manifest(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, observed = await run_news_pipeline(monkeypatch, fail_notification=True)
    assert result.publication_committed is True
    assert result.stages["notify_briefing"].startswith("failed:")
    assert news_repository.head() == news_repository.remote_head()
    ledger = news_repository.remote_ledger()
    assert all(cursor.end_utc == _RUN_START for cursor in ledger.cursors)
    assert observed["publish"].data["publication_receipts"][-1].status == "remote_confirmed"
    assert len(tuple(Path("archive/_meta/news_windows").glob("*.json"))) == 1


@pytest.mark.parametrize("change_after_rebase", [False, True])
async def test_cursor_cas_rejects_concurrent_remote_change_without_max_merge(
    news_repository: NewsRepository,
    monkeypatch: pytest.MonkeyPatch,
    change_after_rebase: bool,
) -> None:
    ledger = NewsCursorLedger.model_validate_json(_CURSOR_PATH.read_bytes())
    concurrent = (
        ledger.model_copy(
            update={
                "cursors": tuple(
                    cursor.model_copy(update={"end_utc": cursor.end_utc + timedelta(hours=1)})
                    for cursor in ledger.cursors
                )
            }
        )
        .model_dump_json()
        .encode()
    )
    advanced = False
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal advanced
        calls.append(args)
        if args[1] == "push" and not advanced:
            advanced = True
            news_repository.advance_remote(cursor_bytes=None if change_after_rebase else concurrent)
        if change_after_rebase and args[1:3] == ["rebase", "--onto"]:
            result = _git(news_repository.work, *args[1:])
            assert result.returncode == 0
            news_repository.advance_remote(cursor_bytes=concurrent)
            _checked(news_repository.work, "fetch", "origin")
            return result
        return _git(news_repository.work, *args[1:])

    result, observed = await run_news_pipeline(monkeypatch, git_runner=runner)
    assert not result.publication_committed
    error = observed["publish"].error
    assert isinstance(error, PublicationReceiptError) and error.phase == "post_commit"
    # A completed rebase creates a new pending successor SHA. A stale CAS
    # must stop it before repush; it does not pretend that successor published.
    assert error.receipt.status == ("pending" if change_after_rebase else "definitely_unpublished")
    assert sum(args[1] == "push" for args in calls) == 1
    assert any(args[1:3] == ["rebase", "--onto"] for args in calls) is change_after_rebase
    assert news_repository.remote_bytes(_CURSOR_PATH) == concurrent
    assert _CURSOR_PATH.read_bytes() != concurrent
    assert not (news_repository.work / ".git/rebase-merge").exists()
    observed["publisher"].send.assert_not_awaited()
    remote = load_remote_event_baseline(observed_at=_RUN_START)
    next_baseline = load_committed_news_cursors(remote.baseline_sha, run_id="next-run")
    assert next_baseline.baseline_sha == news_repository.remote_head()
    assert next_baseline.ledger == NewsCursorLedger.model_validate_json(concurrent)
