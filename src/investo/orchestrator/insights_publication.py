"""FR-026 bounded pre-LLM phase using the existing scoped receipt/CAS owner."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from investo.models.insights import (
    MANIFEST_PATH,
    MAX_HISTORY_BYTES,
    MAX_TOTAL_BYTES,
    InsightHistory,
    InsightRunOutcome,
    ModuleId,
    PublicInsightsManifest,
    ValidatedInsightModule,
    digest,
)
from investo.models.publication import PublicationRequest, PublishReceipt
from investo.orchestrator.insights import (
    InsightCapture,
    InsightQualificationError,
    InsightsConfig,
    load_qualifications,
)
from investo.orchestrator.insights_projection import (
    project_module,
    retention_allowed,
    rights_reason,
    update_history,
)
from investo.publisher.errors import PublisherGitError
from investo.publisher.git_ops import GitRunner, commit_and_push
from investo.publisher.insights.store import (
    InsightRecoveryUnknownError,
    InsightStoreError,
    InsightTransaction,
    module_paths,
    prepare_bundle,
    validate_bundle,
)
from investo.publisher.publication_receipts import (
    PublicationReceiptError,
    metadata_hash_at,
    reconcile_publication,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InsightsBaseline:
    sha: str
    metadata_hash: str
    manifest: PublicInsightsManifest
    modules: dict[ModuleId, ValidatedInsightModule]
    histories: dict[ModuleId, InsightHistory]


class _GitRead:
    def __init__(self, runner: GitRunner | None, deadline: float) -> None:
        self.runner = runner
        self.deadline = deadline

    def run(self, *args: str) -> str:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("insights deadline exhausted")
        command = ["git", *args]
        result = (
            subprocess.run(command, capture_output=True, text=True, check=False, timeout=remaining)
            if self.runner is None
            else self.runner(command, capture_output=True, text=True, check=False)
        )
        if result.returncode:
            raise InsightStoreError("insights Git operation failed")
        return result.stdout

    def file(self, sha: str, path: Path) -> bytes | None:
        info = self.run("ls-tree", "-l", sha, "--", str(path)).strip()
        if not info:
            return None
        fields = info.split("\t", 1)[0].split()
        if len(fields) != 4 or fields[1] != "blob" or int(fields[3]) > MAX_HISTORY_BYTES:
            raise InsightStoreError("remote file kind/size rejected")
        return self._show(f"{sha}:{path}")

    def index_file(self, path: Path) -> bytes | None:
        entry = self.run("ls-files", "--stage", "-z", "--", str(path)).strip("\0")
        if not entry:
            return None
        fields = entry.split("\t", 1)[0].split()
        if len(fields) != 3 or fields[0] != "100644" or fields[2] != "0":
            raise InsightStoreError("owned index entry kind/stage rejected")
        if int(self.run("cat-file", "-s", fields[1])) > MAX_HISTORY_BYTES:
            raise InsightStoreError("owned index blob cap exceeded")
        return self._show(f":{path}")

    def _show(self, revision: str) -> bytes:
        if self.runner is not None:
            return self.run("show", revision).encode("utf-8")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("insights deadline exhausted")
        # Preserve bytes: Korean labels must not widen a multi-MiB blob to UTF-16.
        result = subprocess.run(
            ["git", "show", revision], capture_output=True, check=False, timeout=remaining
        )
        if result.returncode:
            raise InsightStoreError("insights Git blob read failed")
        return result.stdout


def _restore_owned_index(
    git: _GitRead, records: tuple[tuple[Path, str, str | None], ...], *, initial_head: str
) -> None:
    """Reset only journal-owned staged bytes after proving the same initial HEAD."""
    if git.run("rev-parse", "--verify", "HEAD^{commit}").strip() != initial_head:
        raise InsightRecoveryUnknownError("HEAD changed during index recovery")
    by_path = {str(path): (path, new_hash, old_hash) for path, new_hash, old_hash in records}
    staged = git.run("diff", "--cached", "--name-only", "-z", "--", *by_path).strip("\0")
    paths = staged.split("\0") if staged else []
    for name in paths:
        if name not in by_path:
            raise InsightStoreError("unowned staged recovery path")
        path, expected, old_hash = by_path[name]
        content = git.index_file(path)
        old = git.file(initial_head, path)
        if content is None or digest(content) != expected:
            raise InsightStoreError("owned index changed during recovery")
        if (digest(old) if old is not None else None) != old_hash:
            raise InsightStoreError("owned HEAD differs from journal baseline")
    if git.run("rev-parse", "--verify", "HEAD^{commit}").strip() != initial_head:
        raise InsightRecoveryUnknownError("HEAD changed during index recovery")
    if paths:
        git.run("reset", "--quiet", initial_head, "--", *paths)


def load_remote_baseline(
    *, runner: GitRunner | None = None, deadline: float | None = None
) -> InsightsBaseline:
    deadline = deadline or time.monotonic() + 10
    git = _GitRead(runner, deadline)
    git.run("fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
    sha = git.run("rev-parse", "--verify", "refs/remotes/origin/main^{commit}").strip()
    manifest_path = Path(MANIFEST_PATH)
    data = git.file(sha, manifest_path)
    modules: dict[ModuleId, ValidatedInsightModule]
    histories: dict[ModuleId, InsightHistory]
    if data is None:
        manifest, modules, histories = PublicInsightsManifest(), {}, {}
    else:
        manifest = PublicInsightsManifest.model_validate_json(data)
        files = {manifest_path: data}
        for entry in manifest.modules:
            paths = module_paths(entry.module)
            for path in paths[:2] if entry.module == "calendar" else paths:
                value = git.file(sha, path)
                if value is None:
                    raise InsightStoreError("remote module file missing")
                files[path] = value
                if sum(map(len, files.values())) > MAX_TOTAL_BYTES:
                    raise InsightStoreError("remote bundle cap exceeded")
        manifest, modules, histories = validate_bundle(files)
    metadata = metadata_hash_at(
        sha, (manifest_path,), runner=runner, total_budget_s=max(0.001, deadline - time.monotonic())
    )
    return InsightsBaseline(sha, metadata, manifest, modules, histories)


def verified_macro_briefing_date(
    git: _GitRead, sha: str, module: ValidatedInsightModule
) -> date | None:
    """Only link archived documents proven to exist in the confirmed remote tree."""
    today = module.evaluated_at.astimezone(ZoneInfo("Asia/Seoul")).date()
    listing = git.run(
        "ls-tree",
        "-r",
        "--name-only",
        sha,
        "--",
        f"site_docs/archive/us-equity/{today.year}",
        f"site_docs/archive/us-equity/{today.year - 1}",
    )
    candidates = set()
    for name in listing.splitlines():
        match = re.fullmatch(
            r"site_docs/archive/us-equity/(\d{4})/(\d{2})/(\d{4}-\d{2}-\d{2})\.md", name
        )
        if match is None:
            continue
        try:
            day = date.fromisoformat(match[3])
        except ValueError:
            continue
        if day <= today and day.year == int(match[1]) and day.month == int(match[2]):
            candidates.add(day)
    target = max(
        (row.time.local_date for row in module.metrics if row.time.local_date), default=today
    )
    return target if target in candidates else max(candidates, default=None)


def _phase(
    config: InsightsConfig,
    capture: InsightCapture,
    *,
    run_started_at: datetime,
    collection_completed_at: datetime,
    evaluated_at: datetime,
    write_allowed: bool,
    runner: GitRunner | None,
) -> InsightRunOutcome:
    started = time.monotonic()
    deadline = started + 60
    transaction = InsightTransaction()
    baseline: InsightsBaseline | None = None
    remote_spent = 0.0
    try:
        qualifications = load_qualifications()
        if config.mode == "active" and write_allowed:
            transaction.acquire()
            remote_start = time.monotonic()
            retained = transaction.retained_receipt()
            if retained is not None and retained.status != "remote_confirmed":
                reconciled = reconcile_publication(
                    retained, runner=runner, total_budget_s=min(10, deadline - time.monotonic() - 5)
                )
                transaction.record_receipt(reconciled)
            recovery_git = _GitRead(runner, min(deadline - 5, time.monotonic() + 10))
            recovery_head = recovery_git.run("rev-parse", "--verify", "HEAD^{commit}").strip()
            transaction.recover(
                current_head=recovery_head,
                restore_index=lambda records: _restore_owned_index(
                    recovery_git, records, initial_head=recovery_head
                ),
            )
            baseline = load_remote_baseline(
                runner=runner, deadline=min(deadline - 5, time.monotonic() + 10)
            )
            remote_spent = time.monotonic() - remote_start
        local_start = time.monotonic()
        modules = tuple(
            project_module(
                module,
                capture,
                qualifications,
                run_started_at=run_started_at,
                collection_completed_at=collection_completed_at,
                evaluated_at=evaluated_at,
                previous=baseline.modules.get(module) if baseline else None,
            )
            for module in config.modules
        )
        if baseline is not None:
            sanitized = []
            for module_id, previous in baseline.modules.items():
                if module_id in config.modules:
                    continue
                revoked = any(
                    rights_reason(row, qualifications) for row in previous.metrics
                ) or any(rights_reason(row, qualifications) for row in previous.events)
                old_history = baseline.histories.get(module_id)
                retention_changed = old_history is not None and any(
                    not retention_allowed(d.metric, qualifications) for d in old_history.definitions
                )
                if revoked or retention_changed:
                    sanitized.append(
                        project_module(
                            module_id,
                            InsightCapture((), capture.outcomes),
                            qualifications,
                            run_started_at=run_started_at,
                            collection_completed_at=collection_completed_at,
                            evaluated_at=evaluated_at,
                            previous=previous,
                            retain_previous_schedule=True,
                        )
                    )
            modules += tuple(sanitized)
        if time.monotonic() - local_start > 10:
            raise TimeoutError("insights local budget exhausted")
        if config.mode == "shadow" or not write_allowed:
            return InsightRunOutcome(
                mode=config.mode,
                modules=config.modules,
                status="shadow" if config.mode == "shadow" else "skipped",
                projected_modules=modules,
            )
        assert baseline is not None
        histories: dict[ModuleId, InsightHistory] = {
            module.module: update_history(
                module, baseline.histories.get(module.module), qualifications
            )
            for module in modules
            if module.module != "calendar"
        }
        macro = next((m for m in modules if m.module == "macro"), None)
        link_date = (
            verified_macro_briefing_date(
                _GitRead(runner, min(deadline - 5, time.monotonic() + 3)), baseline.sha, macro
            )
            if macro is not None
            else None
        )
        prepared = prepare_bundle(
            modules, histories, baseline_manifest=baseline.manifest, macro_briefing_date=link_date
        )
        files = tuple(path for path, _ in prepared.files)
        git = _GitRead(runner, min(deadline - 5, time.monotonic() + 5))
        if git.run("status", "--porcelain", "-z", "--", *(str(p) for p in files)):
            raise InsightStoreError("owned insight files are dirty")
        if git.run("diff", "--cached", "--name-only", "-z"):
            raise InsightStoreError("publication index contains pre-existing staging")
        if time.monotonic() - local_start > 10:
            raise TimeoutError("insights local budget exhausted")
        initial_head = git.run("rev-parse", "--verify", "HEAD^{commit}").strip()
        transaction.stage(prepared, initial_head=initial_head)
        transaction.verify(prepared)
        request = PublicationRequest(
            run_id="insights-" + uuid4().hex,
            baseline_metadata_hash=baseline.metadata_hash,
            metadata_paths=(Path(MANIFEST_PATH),),
            total_budget_s=min(45 - remote_spent, deadline - time.monotonic() - 5),
        )
        verified_shas: set[str] = set()

        def record_and_verify(receipt: PublishReceipt) -> None:
            transaction.record_receipt(receipt)
            if receipt.local_sha is None or receipt.local_sha in verified_shas:
                return
            reader = _GitRead(runner, deadline - 5)
            for path, expected in prepared.files:
                committed = reader.file(receipt.local_sha, path)
                if committed is None or digest(committed) != digest(expected):
                    raise InsightStoreError("committed insight content differs from projection")
            verified_shas.add(receipt.local_sha)

        try:
            receipt = commit_and_push(
                "Publish public insights",
                files,
                publication=request,
                runner=runner,
                receipt_sink=record_and_verify,
            )
        except PublicationReceiptError as exc:
            if exc.phase == "pre_commit":
                transaction.rollback(
                    restore_index=lambda records: _restore_owned_index(
                        _GitRead(runner, deadline), records, initial_head=initial_head
                    )
                )
            # Preserve every ambiguous/post-commit transaction for reconciliation.
            return InsightRunOutcome(
                mode="active",
                modules=config.modules,
                status="outcome_unknown"
                if exc.receipt.status in {"pending", "outcome_unknown"}
                else "failed",
                projected_modules=modules,
                receipt=exc.receipt,
            )
        assert receipt is not None
        # Receipt validates exact committed file content and remote ancestry.
        try:
            transaction.finish()
        except OSError:
            _logger.warning("[insights] confirmed publication private cleanup degraded")
        return InsightRunOutcome(
            mode="active",
            modules=config.modules,
            status="remote_confirmed",
            projected_modules=modules,
            receipt=receipt,
        )
    except InsightRecoveryUnknownError:
        return InsightRunOutcome(mode=config.mode, modules=config.modules, status="outcome_unknown")
    except (
        InsightStoreError,
        PublisherGitError,
        OSError,
        TimeoutError,
        InsightQualificationError,
        ValidationError,
    ):
        # Closed failure result: no body, URL, exception text or secret is exposed.
        return InsightRunOutcome(mode=config.mode, modules=config.modules, status="failed")
    finally:
        transaction.release()


async def run_insights_phase(
    config: InsightsConfig,
    capture: InsightCapture,
    *,
    run_started_at: datetime,
    collection_completed_at: datetime,
    evaluated_at: datetime,
    write_allowed: bool,
    runner: GitRunner | None = None,
) -> InsightRunOutcome:
    if config.mode == "off":
        raise ValueError("off mode must bypass the phase")
    task = asyncio.create_task(
        asyncio.to_thread(
            _phase,
            config,
            capture,
            run_started_at=run_started_at,
            collection_completed_at=collection_completed_at,
            evaluated_at=evaluated_at,
            write_allowed=write_allowed,
            runner=runner,
        )
    )
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Drain the bounded worker so rollback/receipt persistence cannot race cleanup.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        with contextlib.suppress(BaseException):
            task.result()
        raise
