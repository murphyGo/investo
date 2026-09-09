"""Private/manual supervisor: restore, generate, checkpoint, preserve, clean.

Run using the reviewed installation with the latest public checkout as cwd.
Dedicated auth arrives from CODEX_AUTH_JSON, never a personal auth file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import signal
import tempfile
import time
from pathlib import Path

import httpx

from investo._internal.codex_auth import AuthDocument, read_auth, validate_auth, write_auth
from investo._internal.llm_config import LlmExecutionConfig
from investo.briefing.codex_cli import CodexRunner
from investo.briefing.private_claude import PrivateClaudeRunner
from investo.orchestrator.codex_secrets import (
    RUNTIME_REPOSITORY,
    AuthPersistenceError,
    EnvironmentSecretStore,
)

GENERATION_LIMIT_S = 210 * 60
RUNTIME_LIMIT_S = 225 * 60
# Included in the 225-minute allowance: quiesce <=11s, persist <=60s,
# final close <=11s plus startup/receipt margin. The work timeout is earlier.
CLEANUP_RESERVE_S = 120
_logger = logging.getLogger(__name__)


class AuthLifecycle:
    def __init__(
        self, runner: CodexRunner, store: EnvironmentSecretStore, seed: AuthDocument
    ) -> None:
        self.runner = runner
        self.store = store
        self._persisted = seed.raw
        self.status = "restored"
        self.failed_checkpoint = False
        self.elapsed_s = 0.0

    async def preserve(self) -> None:
        started = time.monotonic()
        try:
            self.runner.close()
            document = read_auth(self.runner.auth_home / "auth.json")
            if document.raw != self._persisted:
                await self.store.persist(document)
                self._persisted = document.raw
                self.status = "persisted"
            elif self.status != "persisted":
                self.status = "unchanged"
        finally:
            self.elapsed_s += time.monotonic() - started

    async def checkpoint(self) -> None:
        try:
            await self.preserve()
        except Exception:
            self.failed_checkpoint = True
            self.status = "failed"
            raise AuthPersistenceError() from None


def validate_private_context(env: dict[str, str]) -> None:
    """No rotating ChatGPT credentials in public or untrusted-event jobs."""
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != RUNTIME_REPOSITORY
        or env.get("INVESTO_RUNTIME_VISIBILITY") != "private"
        or env.get("GITHUB_EVENT_NAME") not in ("workflow_dispatch", "schedule")
        or env.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise AuthPersistenceError()


def _receipt_provenance(env: dict[str, str]) -> dict[str, str | None]:
    # Only validated identifiers; malformed values never become diagnostics.
    return {
        label: value if re.fullmatch(pattern, value := env.get(variable, "")) else None
        for label, variable, pattern in (
            ("run_id", "GITHUB_RUN_ID", r"[0-9]{1,30}"),
            ("code_sha", "REVIEWED_CODE_SHA", r"[0-9a-f]{40}"),
            ("target_date_override", "INVESTO_TARGET_DATE", r"[0-9]{4}-[0-9]{2}-[0-9]{2}"),
        )
    }


async def run() -> int:
    from investo.__main__ import _async_main

    env = dict(os.environ)
    config = LlmExecutionConfig.from_env(env)
    validate_private_context(env)
    if config.provider == "claude":
        claude, node = shutil.which("claude"), shutil.which("node")
        if claude is None or node is None:
            raise AuthPersistenceError()
        claude_runner = PrivateClaudeRunner(claude, node, env.get("CLAUDE_CODE_OAUTH_TOKEN", ""))
        try:
            async with asyncio.timeout(RUNTIME_LIMIT_S - CLEANUP_RESERVE_S):
                return await _async_main(llm_config=config, llm_runner=claude_runner)
        finally:
            claude_runner.close()
    binary = shutil.which("codex")
    if binary is None:
        raise AuthPersistenceError()
    seed = validate_auth(env.pop("CODEX_AUTH_JSON", "").encode("utf-8"))
    token = env.pop("CODEX_SECRET_WRITE_TOKEN", "")
    os.environ.pop("CODEX_AUTH_JSON", None)
    os.environ.pop("CODEX_SECRET_WRITE_TOKEN", None)
    start = time.monotonic()
    rc = 1
    lifecycle: AuthLifecycle | None = None
    old_auth_home = os.environ.get("INVESTO_CODEX_HOME")
    old_concurrency = os.environ.get("INVESTO_SEGMENT_GENERATION_CONCURRENCY")
    with tempfile.TemporaryDirectory(prefix="investo-codex-auth-") as temporary:
        home = Path(temporary)
        write_auth(home / "auth.json", seed.raw)
        os.environ["INVESTO_CODEX_HOME"] = str(home)
        os.environ["INVESTO_SEGMENT_GENERATION_CONCURRENCY"] = "1"
        runner = CodexRunner(config, home, deadline=start + GENERATION_LIMIT_S, binary=binary)
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                store = EnvironmentSecretStore(client, token)
                lifecycle = AuthLifecycle(runner, store, seed)
                try:
                    async with asyncio.timeout(
                        max(0.001, RUNTIME_LIMIT_S - CLEANUP_RESERVE_S - (time.monotonic() - start))
                    ):
                        await store.verify_environment_secret()
                        rc = await _async_main(
                            llm_config=config,
                            llm_runner=runner,
                            before_publication=lifecycle.checkpoint,
                        )
                finally:
                    try:
                        await lifecycle.preserve()
                    except Exception:
                        lifecycle.status = "failed"
                        rc = 1
                        _logger.error("codex_auth_preservation_failed")
        finally:
            try:
                runner.close()
            except Exception:
                rc = 1
                if lifecycle is not None:
                    lifecycle.status = "failed"
                _logger.error("codex_process_cleanup_failed")
            for name, previous in (
                ("INVESTO_CODEX_HOME", old_auth_home),
                ("INVESTO_SEGMENT_GENERATION_CONCURRENCY", old_concurrency),
            ):
                if previous is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = previous
            if lifecycle is not None:
                if lifecycle.failed_checkpoint:
                    rc = 1
                _logger.info(
                    "codex_runtime %s",
                    json.dumps(
                        {
                            **_receipt_provenance(env),
                            "provider": "codex",
                            "model": config.model,
                            "auth": lifecycle.status,
                            "exit_code": rc,
                            "duration_s": round(time.monotonic() - start, 3),
                            "auth_duration_s": round(lifecycle.elapsed_s, 3),
                        }
                    ),
                )
    return rc


async def _supervised() -> int:
    task = asyncio.current_task()
    assert task is not None
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, task.cancel)
    try:
        return await run()
    except (Exception, asyncio.CancelledError):
        _logger.error("codex_runtime_failed")
        return 1
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return asyncio.run(_supervised())


if __name__ == "__main__":
    raise SystemExit(main())
