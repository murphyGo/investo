#!/usr/bin/env python3
"""Run a non-publishing event preview inside the qualified private auth owner."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import ModuleType

from investo._internal.llm_config import LlmExecutionConfig
from investo.briefing.claude_code import ClaudeRunner
from investo.briefing.codex_cli import CodexRunner
from investo.orchestrator.codex_runtime import _supervised

PREVIEW_WORK_LIMIT_S = 100 * 60


def _reviewed_preview() -> ModuleType:
    # Only the sibling from the reviewed code checkout; never import the
    # current public-data checkout or add its source tree to sys.path.
    path = Path(__file__).resolve().with_name("preview_event_briefing.py")
    spec = importlib.util.spec_from_file_location("investo_reviewed_event_preview", path)
    if spec is None or spec.loader is None:
        raise ValueError("preview code unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    manifest: dict[str, object] = {"status": "failed", "code": "preview.runtime_failed"}
    try:
        preview = _reviewed_preview()
        args = preview._parse_args(argv)
        data_root = Path.cwd().resolve()
        # Reject a bad/reused output location before restoring auth.
        preview._private_path(args.output_dir, data_root)

        async def operation(
            *,
            llm_config: LlmExecutionConfig,
            llm_runner: ClaudeRunner,
            before_publication: Callable[[], Awaitable[None]] | None = None,
        ) -> int:
            nonlocal manifest
            del before_publication  # No public transaction exists in this operation.
            if llm_config.provider != "codex" or not isinstance(llm_runner, CodexRunner):
                return 1
            try:
                # Leave ten minutes inside the workflow step for the same
                # auth preservation and process cleanup as production.
                async with asyncio.timeout(PREVIEW_WORK_LIMIT_S):
                    manifest = await preview.run_preview(
                        target_date=args.target_date,
                        segment=args.segment,
                        output_dir=args.output_dir,
                        repository_root=data_root,
                        runner=llm_runner,
                        baseline_sha=args.baseline_sha,
                    )
                return 0 if manifest["status"] == "sealed" else 3
            except Exception as exc:
                manifest = preview._failure_manifest(exc)
                return 1

        rc = asyncio.run(_supervised(operation=operation))
        if rc == 1 and manifest.get("status") == "sealed":
            # The operation succeeded but the auth owner failed its final
            # checkpoint/cleanup. Never report that as a successful run.
            manifest = {"status": "failed", "code": "preview.runtime_failed"}
        print(json.dumps(manifest, ensure_ascii=True, sort_keys=True))
        return rc
    except Exception:
        print(json.dumps({"status": "failed", "code": "preview.runtime_input_invalid"}))
        return 2
    finally:
        logging.disable(previous_logging)


if __name__ == "__main__":
    raise SystemExit(main())
