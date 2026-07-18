"""Tests for ``investo.orchestrator.pipeline._run_image_candidate_stage``.

Pins u137 Contract #5 / R9 / I16 (AC-137.4) for the failure-isolated
image-candidate stage: the post-routing ledger → index → cleared-fetch
sequence, existence-checked staging paths, the run-trace note format,
and — the core acceptance — that ANY exception degrades to one WARNING
plus a ``"failed: <Type>"`` note without raising.

All roots are injected ``tmp_path`` dirs; no live HTTP (the fetch path
stays env-gated off — the store test stubs the library function).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.models import NormalizedItem
from investo.orchestrator.pipeline import _run_image_candidate_stage
from investo.visuals.image_library import (
    FetchReport,
    ImageCandidateRecord,
    RecurrenceIndexEntry,
)

_TARGET = date(2026, 7, 16)
_PUBLISHED = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def _item(
    *,
    source_name: str = "yonhap-market",
    title: str = "이미지 기사",
    image_url: str | None = "https://img.yna.co.kr/photo/reuters/a.jpg",
) -> NormalizedItem:
    raw_metadata: dict[str, str] = {}
    if image_url is not None:
        raw_metadata["image_url"] = image_url
    return NormalizedItem(
        source_name=source_name,
        category="news",
        title=title,
        url="https://www.yna.co.kr/view/x",
        published_at=_PUBLISHED,
        raw_metadata=raw_metadata,
    )


def test_success_path_writes_ledger_and_index_and_reports_counts(tmp_path: Path) -> None:
    ledger_root = tmp_path / "image_candidates"
    paths, note = _run_image_candidate_stage(
        _TARGET,
        [_item()],
        ledger_root=ledger_root,
        store_root=tmp_path / "store",
    )

    assert note == "ok: candidates=1 indexed=1 stored=0"
    ledger_path = ledger_root / "2026" / "2026-07-16.jsonl"
    index_path = ledger_root / "index.json"
    assert set(paths) == {ledger_path, index_path}
    row = ImageCandidateRecord.model_validate_json(
        ledger_path.read_text(encoding="utf-8").splitlines()[0]
    )
    assert row.source_name == "yonhap-market"
    assert row.collected_on == _TARGET  # I3 — target date, no wall clock


def test_imageless_run_writes_nothing_and_reports_zero(tmp_path: Path) -> None:
    ledger_root = tmp_path / "image_candidates"
    paths, note = _run_image_candidate_stage(
        _TARGET,
        [_item(image_url=None)],
        ledger_root=ledger_root,
        store_root=tmp_path / "store",
    )

    assert note == "ok: candidates=0 indexed=0 stored=0"
    assert paths == ()  # only-existing-paths rule: nothing was written
    assert not ledger_root.exists()


def test_any_exception_is_isolated_to_warn_and_failed_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # I16 / AC-137.4 — the isolation proof at the stage-helper level:
    # a crash inside the library never propagates.
    def _boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("ledger disk on fire")

    monkeypatch.setattr("investo.visuals.image_library.append_candidates", _boom)

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.pipeline"):
        paths, note = _run_image_candidate_stage(
            _TARGET,
            [_item()],
            ledger_root=tmp_path / "image_candidates",
            store_root=tmp_path / "store",
        )

    assert paths == ()
    assert note == "failed: RuntimeError"
    assert "[image_candidates] stage failed" in caplog.text
    assert "never blocks briefing/publish" in caplog.text


def test_stored_paths_from_fetch_report_join_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # R9 — newly stored binaries + sidecars join the staging list. The
    # fetch itself is stubbed (quadruple gate + HTTP behavior is pinned
    # in tests/unit/visuals/test_image_library.py).
    binary = tmp_path / "store" / "ab" / ("a" * 64 + ".png")
    sidecar = binary.with_name(binary.name + ".provenance.json")
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(b"png")
    sidecar.write_text("{}", encoding="utf-8")

    def _fake_fetch(index: dict[str, RecurrenceIndexEntry], **kwargs: object) -> FetchReport:
        return FetchReport(
            store_root=tmp_path / "store",
            scraping_enabled=True,
            candidates_considered=len(index),
            cleared=1,
            invalid_clearances=0,
            gate_blocked=0,
            skipped_existing=0,
            attempted=1,
            fetch_failed=0,
            stored=1,
            stored_paths=(binary, sidecar),
        )

    monkeypatch.setattr("investo.visuals.image_library.fetch_cleared_candidates", _fake_fetch)

    ledger_root = tmp_path / "image_candidates"
    paths, note = _run_image_candidate_stage(
        _TARGET,
        [_item()],
        ledger_root=ledger_root,
        store_root=tmp_path / "store",
    )

    assert note == "ok: candidates=1 indexed=1 stored=1"
    assert binary in paths
    assert sidecar in paths
    assert ledger_root / "2026" / "2026-07-16.jsonl" in paths
    assert ledger_root / "index.json" in paths
