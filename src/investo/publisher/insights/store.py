"""Bounded, recoverable multi-file preparation; Git receipt owns remote atomicity."""

from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from investo._internal.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO
from investo.models.insights import (
    MANIFEST_PATH,
    MAX_CURRENT_BYTES,
    MAX_HISTORY_BYTES,
    MAX_TOTAL_BYTES,
    InsightHistory,
    ManifestEntry,
    ModuleId,
    PublicInsightsManifest,
    ValidatedInsightModule,
    canonical_bytes,
    digest,
    read_insight_history,
)
from investo.models.publication import PublishReceipt
from investo.publisher.insights.calendar import render_calendar
from investo.publisher.insights.crypto import render_crypto
from investo.publisher.insights.macro import render_macro
from investo.publisher.verifier import verify_disclaimer


class InsightStoreError(ValueError):
    """Expected malformed bundle, dirty owned files or retained transaction."""


class InsightRecoveryUnknownError(InsightStoreError):
    """An unrecorded commit may exist; retain journal and never restore files."""


@dataclass(frozen=True, slots=True)
class PreparedInsights:
    files: tuple[tuple[Path, bytes], ...]
    manifest: PublicInsightsManifest


def module_paths(module: ModuleId) -> tuple[Path, Path, Path]:
    if module not in {"macro", "calendar", "crypto"}:
        raise InsightStoreError("unknown module path")
    data = Path("site_docs/insights/_data") / module
    return (
        data / "current.json",
        Path("site_docs/insights") / module / "index.md",
        data / "history.json",
    )


def render_module(module: ValidatedInsightModule) -> str:
    """Foundation fallback renderer. Product layouts belong to u181-u183."""
    lines = [
        f"<!-- insights-snapshot:{module.snapshot_id} -->",
        f"# {module.module}",
        "",
        f"기준 시점: {module.evaluated_at.isoformat()}",
        "",
        f"자료 상태: {module.availability}",
        "",
    ]
    lines += ['<div class="insights-data">']
    for row in module.metrics:
        clock = row.time.period or str(
            row.time.local_date or row.time.window_end or row.time.exact_at
        )
        lines += [
            f"<p>{escape(row.label)}: {row.value} {row.unit} · {row.freshness}"
            f" · {escape(clock)}<br>",
            f'<a href="{escape(row.source_href, quote=True)}">출처</a>'
            f" · {escape(row.attribution)}</p>",
        ]
    for event in module.events:
        clock = str(event.time.local_date or event.time.start_date or event.time.exact_at)
        lines += [
            f"<p>{escape(event.label)} · {escape(clock)} · {event.freshness}<br>",
            f'<a href="{escape(event.source_href, quote=True)}">출처</a>'
            f" · {escape(event.attribution)}</p>",
        ]
    lines += ["</div>", ""]
    lines += ["", DISCLAIMER_CRYPTO if module.module == "crypto" else DISCLAIMER, ""]
    return "\n".join(lines)


def prepare_bundle(
    modules: Sequence[ValidatedInsightModule],
    histories: Mapping[ModuleId, InsightHistory],
    *,
    baseline_manifest: PublicInsightsManifest | None = None,
    renderer: Callable[[ValidatedInsightModule], str] | None = None,
    macro_briefing_date: date | None = None,
) -> PreparedInsights:
    entries = {row.module: row for row in (baseline_manifest or PublicInsightsManifest()).modules}
    files: dict[Path, bytes] = {}
    if len({m.module for m in modules}) != len(modules):
        raise InsightStoreError("duplicate prepared module")
    for module in modules:
        # Frozen does not make model_copy/update or construct trustworthy.
        checked = ValidatedInsightModule.model_validate_json(canonical_bytes(module))
        current_path, index_path, history_path = module_paths(checked.module)
        current = canonical_bytes(checked)
        rendered = (
            renderer(checked)
            if renderer is not None
            else render_macro(checked, histories.get("macro"), briefing_date=macro_briefing_date)
            if checked.module == "macro"
            else render_calendar(checked)
            if checked.module == "calendar"
            else render_crypto(checked, histories.get("crypto"))
            if checked.module == "crypto"
            else render_module(checked)
        )
        if not verify_disclaimer(
            rendered, segment="crypto" if checked.module == "crypto" else None
        ):
            raise InsightStoreError("renderer disclaimer missing")
        index = rendered.encode("utf-8")
        if checked.module == "macro" and len(index) > 100 * 1024:
            raise InsightStoreError("macro initial HTML cap exceeded")
        if checked.module == "calendar" and len(index) > 120 * 1024:
            raise InsightStoreError("calendar initial HTML cap exceeded")
        if checked.module == "crypto" and len(index) > 100 * 1024:
            raise InsightStoreError("crypto initial HTML cap exceeded")
        if f"<!-- insights-snapshot:{checked.snapshot_id} -->".encode() not in index:
            raise InsightStoreError("renderer snapshot mismatch")
        if len(index) > MAX_CURRENT_BYTES:
            raise InsightStoreError("index cap exceeded")
        files[current_path] = current
        files[index_path] = index
        history_hash = None
        if checked.module != "calendar":
            history = histories.get(checked.module)
            if history is None or history.module != checked.module:
                raise InsightStoreError("missing matching history")
            history_bytes = canonical_bytes(InsightHistory.model_validate(history))
            files[history_path] = history_bytes
            history_hash = digest(history_bytes)
        entries[checked.module] = ManifestEntry(
            module=checked.module,
            snapshot_id=checked.snapshot_id,
            current_hash=digest(current),
            index_hash=digest(index),
            history_hash=history_hash,
        )
    manifest = PublicInsightsManifest(modules=tuple(entries[m] for m in sorted(entries)))
    files[Path(MANIFEST_PATH)] = canonical_bytes(manifest)
    if sum(len(value) for value in files.values()) > MAX_TOTAL_BYTES:
        raise InsightStoreError("bundle total cap exceeded")
    return PreparedInsights(tuple(sorted(files.items())), manifest)


def validate_bundle(
    files: Mapping[Path, bytes],
) -> tuple[
    PublicInsightsManifest, dict[ModuleId, ValidatedInsightModule], dict[ModuleId, InsightHistory]
]:
    try:
        manifest = PublicInsightsManifest.model_validate_json(files[Path(MANIFEST_PATH)])
        modules: dict[ModuleId, ValidatedInsightModule] = {}
        histories: dict[ModuleId, InsightHistory] = {}
        if sum(map(len, files.values())) > MAX_TOTAL_BYTES:
            raise InsightStoreError("bundle total cap exceeded")
        for entry in manifest.modules:
            current_path, index_path, history_path = module_paths(entry.module)
            current, index = files[current_path], files[index_path]
            if (
                len(current) > MAX_CURRENT_BYTES
                or len(index) > MAX_CURRENT_BYTES
                or digest(current) != entry.current_hash
                or digest(index) != entry.index_hash
            ):
                raise InsightStoreError("current/index hash mismatch")
            module = ValidatedInsightModule.model_validate_json(current)
            if (
                module.module != entry.module
                or module.snapshot_id != entry.snapshot_id
                or f"<!-- insights-snapshot:{entry.snapshot_id} -->".encode() not in index
            ):
                raise InsightStoreError("module identity mismatch")
            modules[entry.module] = module
            if entry.module == "calendar":
                if entry.history_hash is not None:
                    raise InsightStoreError("calendar history forbidden")
            else:
                data = files[history_path]
                if len(data) > MAX_HISTORY_BYTES or digest(data) != entry.history_hash:
                    raise InsightStoreError("history hash mismatch")
                history = read_insight_history(data)
                if history.module != entry.module:
                    raise InsightStoreError("history module mismatch")
                histories[entry.module] = history
        return manifest, modules, histories
    except (KeyError, ValidationError, ValueError) as exc:
        raise InsightStoreError("invalid insight bundle") from exc


def _safe_owned_path(root: Path, relative: Path) -> Path:
    module_ids: tuple[ModuleId, ...] = ("macro", "calendar", "crypto")
    allowed = {Path(MANIFEST_PATH)} | {p for module in module_ids for p in module_paths(module)}
    if relative not in allowed:
        raise InsightStoreError("unowned transaction path")
    target = root / relative
    current = target
    while current != root:
        if current.is_symlink():
            raise InsightStoreError("symlink in owned path")
        current = current.parent
    return target


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_directory(path: Path) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        _fsync_directory(directory.parent)
        _fsync_directory(directory)


def _atomic_write(path: Path, data: bytes) -> None:
    _ensure_directory(path.parent)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".insights-", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        _fsync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


class _Backup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str
    backup: str | None = Field(default=None, pattern=r"^[0-9]{1,2}$")
    new_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    old_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class _Journal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    records: tuple[_Backup, ...] = Field(max_length=10)
    receipt: PublishReceipt | None = None
    initial_head: str | None = Field(default=None, pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")


class InsightTransaction:
    """Private journal is retained after commit ambiguity; never a public baseline.

    Pre-commit rollback touches only owned files and refuses changed bytes.
    The orchestrator restores only owned index entries, preserving other staging.
    """

    def __init__(self, root: Path = Path(".")) -> None:
        self.root = root.resolve()
        self._lease: BinaryIO | None = None
        self.directory = self.root / ".tmp/insights-publication"
        if self.directory.is_symlink() or self.directory.parent.is_symlink():
            raise InsightStoreError("unsafe private journal path")

    def acquire(self) -> None:
        _ensure_directory(self.directory.parent)
        path = self.directory.parent / "insights-publication.lock"
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        stream = os.fdopen(fd, "a+b")
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise InsightStoreError("insights publication already running") from exc
        self._lease = stream

    def release(self) -> None:
        if self._lease is not None:
            fcntl.flock(self._lease, fcntl.LOCK_UN)
            self._lease.close()
            self._lease = None

    def retained_receipt(self) -> PublishReceipt | None:
        return self._journal().receipt if self.directory.exists() else None

    def recover(
        self,
        *,
        current_head: str | None = None,
        restore_index: Callable[[tuple[tuple[Path, str, str | None], ...]], None] | None = None,
    ) -> None:
        if not self.directory.exists():
            return
        data = self._journal()
        if data.receipt is not None:
            receipt = data.receipt
            if receipt.status == "remote_confirmed":
                self.finish()
                return
            raise InsightStoreError("retained publication requires remote reconciliation")
        if data.initial_head != current_head:
            raise InsightRecoveryUnknownError("initial HEAD changed before receipt persistence")
        if data.initial_head is not None and restore_index is None:
            raise InsightStoreError("Git journal recovery requires owned index restoration")
        self.rollback(partial=True, restore_index=restore_index)

    def _journal(self) -> _Journal:
        path = self.directory / "journal.json"
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 32 * 1024:
            raise InsightStoreError("invalid private journal")
        return _Journal.model_validate_json(path.read_bytes())

    def stage(self, prepared: PreparedInsights, *, initial_head: str | None = None) -> None:
        _ensure_directory(self.directory.parent)
        try:
            self.directory.mkdir()
            _fsync_directory(self.directory.parent)
        except FileExistsError as exc:
            raise InsightStoreError("publication already staged") from exc
        records: list[_Backup] = []
        try:
            for ordinal, (relative, content) in enumerate(prepared.files):
                target = _safe_owned_path(self.root, relative)
                old = target.read_bytes() if target.exists() else None
                if old is not None and len(old) > MAX_HISTORY_BYTES:
                    raise InsightStoreError("owned baseline cap exceeded")
                backup = str(ordinal)
                if old is not None:
                    _atomic_write(self.directory / backup, old)
                records.append(
                    _Backup(
                        path=str(relative),
                        backup=backup if old is not None else None,
                        new_hash=digest(content),
                        old_hash=digest(old) if old is not None else None,
                    )
                )
            _atomic_write(
                self.directory / "journal.json",
                canonical_bytes(_Journal(records=tuple(records), initial_head=initial_head)),
            )
            for relative, content in prepared.files:
                _atomic_write(_safe_owned_path(self.root, relative), content)
        except BaseException:
            if (self.directory / "journal.json").exists():
                self.rollback(partial=True)
            else:
                self.finish()
            raise

    def verify(self, prepared: PreparedInsights) -> None:
        for path, expected in prepared.files:
            target = _safe_owned_path(self.root, path)
            if not target.is_file() or target.stat().st_size != len(expected):
                raise InsightStoreError("staged insight content changed")
            if digest(target.read_bytes()) != digest(expected):
                raise InsightStoreError("staged insight content changed")

    def record_receipt(self, receipt: PublishReceipt) -> None:
        data = self._journal().model_copy(update={"receipt": receipt})
        _atomic_write(self.directory / "journal.json", canonical_bytes(data))

    def rollback(
        self,
        *,
        partial: bool = False,
        restore_index: Callable[[tuple[tuple[Path, str, str | None], ...]], None] | None = None,
    ) -> None:
        data = self._journal()
        if data.receipt is not None:
            raise InsightStoreError("committed transaction cannot be rolled back")
        restoration: list[tuple[Path, bytes | None]] = []
        for record in data.records:
            target = _safe_owned_path(self.root, Path(record.path))
            backup = self.directory / record.backup if record.backup is not None else None
            if backup is not None and backup.is_symlink():
                raise InsightStoreError("unsafe backup path")
            if backup is not None and (
                not backup.is_file() or backup.stat().st_size > MAX_HISTORY_BYTES
            ):
                raise InsightStoreError("backup kind/size rejected")
            old = backup.read_bytes() if backup is not None else None
            if old is not None and digest(old) != record.old_hash:
                raise InsightStoreError("backup identity mismatch")
            current = target.read_bytes() if target.exists() else None
            if current is not None and digest(current) != record.new_hash:
                if partial and current == old:
                    continue
                raise InsightStoreError("owned file changed during rollback")
            if current is None and old is None:
                continue
            if current is None and old is not None:
                raise InsightStoreError("owned file removed during rollback")
            restoration.append((target, old))
        # Validate all paths/hashes before restoring the first file.
        if restore_index is not None:
            restore_index(tuple((Path(r.path), r.new_hash, r.old_hash) for r in data.records))
        for target, old in restoration:
            if old is None:
                target.unlink(missing_ok=True)
                _fsync_directory(target.parent)
            else:
                _atomic_write(target, old)
        self.finish()

    def finish(self) -> None:
        shutil.rmtree(self.directory)
        _fsync_directory(self.directory.parent)
