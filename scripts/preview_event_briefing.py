#!/usr/bin/env python3
"""Collect and seal one private event preview using the existing Claude budget."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Never, cast

from investo.briefing._core.classification import event_classification_diagnostics
from investo.briefing.claude_code import ClaudeRunner
from investo.briefing.codex_cli import CodexRunner
from investo.briefing.context import load_recent_briefings, resolve_recent_days
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.event_routing import share_official_event_candidates
from investo.briefing.generation_contract import GenerationInput
from investo.briefing.segments import segment_items
from investo.briefing.watchlist import DEFAULT_WATCHLIST_PATH, load_watchlist
from investo.models.segments import DOMESTIC_EQUITY, MarketSegment
from investo.orchestrator.domestic_anchor_quarantine import (
    load_previous_domestic_anchor_closes,
    project_domestic_public_items,
)
from investo.orchestrator.event_preview import preview_event_briefing
from investo.orchestrator.pipeline import SEGMENT_GENERATION_POLICIES, _reconcile_anchor_closes
from investo.orchestrator.stage_context import (
    SEGMENT_ORDER,
    _build_kr_anchors_from_verdicts,
    _load_market_anchors_for_run,
    _snapshot_close_by_ticker,
)
from investo.sources import collect_sources

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_MAX_MARKDOWN_BYTES = 256 * 1024
_MAX_MANIFEST_BYTES = 16 * 1024


class PreviewInputError(ValueError):
    """A fixed CLI error; never echo caller paths or private data."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        del message
        raise PreviewInputError


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = _Parser(description=__doc__)
    parser.add_argument("--target-date", required=True, type=date.fromisoformat)
    parser.add_argument("--segment", required=True, choices=SEGMENT_ORDER)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def _private_path(output_dir: Path, repository_root: Path) -> Path:
    """Require a new, untracked, ignored directory below the real repo .tmp."""
    root = repository_root.resolve(strict=True)
    output = output_dir if output_dir.is_absolute() else root / output_dir
    private_root = root / ".tmp"
    if ".." in output.parts or not output.is_relative_to(private_root) or output == private_root:
        raise PreviewInputError
    # Reject any alias into a tracked tree, including dangling symlinks.
    for part in (output, *output.parents):
        if part == root:
            break
        if part.is_symlink():
            raise PreviewInputError
    if output.exists():
        raise PreviewInputError
    for name in ("preview.md", "manifest.json"):
        relative = (output / name).relative_to(root).as_posix()
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", relative],
            cwd=root,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if ignored.returncode != 0:
            raise PreviewInputError
    tracked = subprocess.run(
        ["git", "--literal-pathspecs", "ls-files", "-z", "--", output.relative_to(root).as_posix()],
        cwd=root,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if tracked.returncode != 0 or tracked.stdout:
        raise PreviewInputError
    return output


def _write_private(output: Path, name: str, content: bytes) -> None:
    # A new directory and exclusive/no-follow files also reject existing
    # symlinks and hard links instead of overwriting their targets.
    with os.fdopen(
        os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600),
        "wb",
    ) as stream:
        stream.write(content)


def _failure_manifest(exc: Exception) -> dict[str, object]:
    manifest: dict[str, object] = {
        "status": "failed",
        "code": "preview.execution_failed",
        "error_type": "unexpected",
    }
    if isinstance(exc, BriefingGenerationError):
        manifest["error_type"] = "briefing_generation"
        manifest["stage"] = (
            exc.stage
            if exc.stage in {"classification", "synthesis", "post_validation", "budget"}
            else None
        )
        manifest["attempt_count"] = (
            exc.attempt_count
            if type(exc.attempt_count) is int and 0 <= exc.attempt_count <= 100
            else None
        )
        diagnostics = event_classification_diagnostics(exc.cause)
        if diagnostics:
            manifest["diagnostics"] = diagnostics
        known_causes = {
            "event_classification_unavailable: response_budget": "classification.response_budget",
            "event_classification_unavailable: invalid_schema_or_item": (
                "classification.invalid_schema_or_item"
            ),
            "event_classification_unavailable: invalid_evidence": "classification.invalid_evidence",
        }
        cause = str(exc.cause) if isinstance(exc.cause, ValueError) else ""
        if cause in known_causes:
            manifest["failure_code"] = known_causes[cause]
        elif re.fullmatch(
            r"Stage [12] subprocess returned rc=-?\d{1,3}, stdout_len=\d{1,8}", cause
        ):
            manifest["failure_code"] = "generation.subprocess_failed"
    elif isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)):
        manifest["error_type"] = "timeout"
    elif isinstance(exc, OSError):
        manifest["error_type"] = "io"
    elif isinstance(exc, ValueError):
        manifest["error_type"] = "validation"
    return manifest


async def run_preview(
    *,
    target_date: date,
    segment: MarketSegment,
    output_dir: Path,
    repository_root: Path = _REPOSITORY_ROOT,
    runner: ClaudeRunner | None = None,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    """No run_pipeline, publisher, notifier, receipt or cursor writer is called."""
    if segment not in SEGMENT_ORDER:
        raise PreviewInputError
    clock = observed_at or datetime.now(UTC)
    if clock.utcoffset() is None:
        raise PreviewInputError
    clock = clock.astimezone(UTC)
    output = _private_path(output_dir, repository_root)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    report = await collect_sources(target_date, evidence_received_at=clock)
    anchors, _history = await _load_market_anchors_for_run(target_date)
    archive = repository_root.resolve() / "archive"
    projection = project_domestic_public_items(
        report.items,
        target_date=target_date,
        source_outcomes=report.outcomes,
        previous_closes=load_previous_domestic_anchor_closes(archive, target_date),
    )
    domestic = _build_kr_anchors_from_verdicts(
        tuple(verdict for _, verdict in projection.item_verdicts)
    )
    if domestic:
        anchors[DOMESTIC_EQUITY] = domestic
    anchors = _reconcile_anchor_closes(anchors, _snapshot_close_by_ticker(projection.public_items))
    routed = segment_items(projection.public_items)
    candidates = share_official_event_candidates(
        projection.public_items,
        {market: routed.for_segment(market) for market in SEGMENT_ORDER},
    )
    days = resolve_recent_days()
    result = await preview_event_briefing(
        GenerationInput(
            target_date=target_date,
            items=candidates[segment],
            segment=segment,
            runner=runner,
            watchlist_config=load_watchlist(repository_root / DEFAULT_WATCHLIST_PATH),
            source_outcomes=report.outcomes,
            market_anchors=anchors.get(segment, ()),
            data_limited=routed.is_data_limited(segment),
            generation_policy=SEGMENT_GENERATION_POLICIES[segment],
            recent_context=load_recent_briefings(archive, target_date, days=days) if days else None,
            event_observed_at=clock,
            event_baseline=(),
            event_baseline_available=False,
            event_collection_items=projection.public_items,
        )
    )
    documents = result.finalized.documents
    if len(documents) > 1:
        raise ValueError("preview returned multiple documents")
    document = documents[0] if documents else None
    markdown = document.briefing.rendered_markdown.encode("utf-8") if document else b""
    if len(markdown) > _MAX_MARKDOWN_BYTES:
        raise ValueError("preview exceeds output limit")
    if document and hashlib.sha256(markdown).hexdigest() != document.markdown_sha256:
        raise ValueError("preview seal mismatch")
    manifest: dict[str, object] = {
        "schema_version": 1,
        "mode": "preview",
        "provider": "codex" if isinstance(runner, CodexRunner) else "claude",
        "target_date": target_date.isoformat(),
        "segment": segment,
        "observed_at": clock.isoformat(),
        "status": "sealed" if document else "blocked",
        "collected_item_count": len(report.items),
        "routed_item_count": len(candidates[segment]),
        "source_status_counts": {
            status: sum(row.status == status for row in report.outcomes)
            for status in ("ok", "zero", "failed")
        },
        "finalized_document_count": len(documents),
        "markdown_sha256": document.markdown_sha256 if document else None,
        "markdown_bytes": len(markdown),
        "event_coverage": result.event_coverage.model_dump(mode="json")
        if result.event_coverage is not None
        else None,
        "event_baseline_available": False,
        "human_semantic_review": "pending",
        "publication_committed": False,
        "notification_sent": False,
        "production_cursor_written": False,
        "production_receipt_written": False,
    }
    encoded = (json.dumps(manifest, ensure_ascii=True, sort_keys=True) + "\n").encode()
    if len(encoded) > _MAX_MANIFEST_BYTES:
        raise ValueError("preview manifest exceeds output limit")
    # Recheck every path component after the awaited network/model work.
    if any(part.is_symlink() for part in (output, *output.parents)):
        raise PreviewInputError
    if document:
        _write_private(output, "preview.md", markdown)
    _write_private(output, "manifest.json", encoded)
    return manifest


def main(argv: list[str] | None = None) -> int:
    # Library diagnostics may contain source text; the CLI emits only this
    # bounded manifest or a fixed error. Credentials remain owned by Claude.
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        args = _parse_args(argv)
        manifest = asyncio.run(
            run_preview(
                target_date=args.target_date,
                segment=cast(MarketSegment, args.segment),
                output_dir=args.output_dir,
            )
        )
        print(json.dumps(manifest, ensure_ascii=True, sort_keys=True))
        return 0 if manifest["status"] == "sealed" else 3
    except PreviewInputError:
        print('{"status":"rejected","code":"preview.input_invalid"}')
        return 2
    except Exception as exc:
        print(json.dumps(_failure_manifest(exc), ensure_ascii=True, sort_keys=True))
        return 1
    finally:
        logging.disable(previous_logging)


if __name__ == "__main__":
    raise SystemExit(main())
