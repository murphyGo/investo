from __future__ import annotations

import asyncio
import base64
import json
from datetime import date
from pathlib import Path
from typing import cast

import httpx
import pytest
from nacl.public import PrivateKey, SealedBox
from pydantic import HttpUrl, TypeAdapter

from investo import __main__ as entrypoint
from investo._internal.codex_auth import AuthDocument, read_auth, validate_auth, write_auth
from investo._internal.llm_config import LlmExecutionConfig
from investo.briefing.codex_cli import CodexRunner
from investo.notifier import BriefingPublisher, OperatorAlerter
from investo.orchestrator.codex_runtime import AuthLifecycle, validate_private_context
from investo.orchestrator.codex_secrets import (
    AuthPersistenceError,
    EnvironmentSecretStore,
    SecretTarget,
)
from investo.orchestrator.pipeline import run_pipeline
from investo.orchestrator.stages import Stage


def auth(suffix: str = "old") -> bytes:
    return json.dumps(
        {
            "auth_mode": "chatgpt",
            "tokens": {
                key: f"synthetic-{key}-{suffix}"
                for key in (
                    "id_token",
                    "access_token",
                    "refresh_token",
                )
            },
        }
    ).encode()


async def test_encrypted_environment_write_round_trip() -> None:
    private_key = PrivateKey.generate()
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer synthetic-writer"
        assert request.url.host == "api.github.com"
        assert "/environments/codex-runtime/secrets/" in request.url.path
        if request.url.path.endswith("public-key"):
            return httpx.Response(
                200,
                json={
                    "key_id": "public-key-id",
                    "key": base64.b64encode(bytes(private_key.public_key)).decode(),
                },
            )
        if request.method == "GET":
            return httpx.Response(200, json={"name": "CODEX_AUTH_JSON"})
        payload = json.loads(request.content)
        assert payload["key_id"] == "public-key-id"
        assert (
            SealedBox(private_key).decrypt(base64.b64decode(payload["encrypted_value"])) == auth()
        )
        assert b"synthetic-access_token" not in request.content
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        store = EnvironmentSecretStore(client, "synthetic-writer")
        await store.verify_environment_secret()
        await store.persist(validate_auth(auth()))
    assert [request.method for request in requests] == ["GET", "GET", "PUT"]


@pytest.mark.parametrize("status", [301, 401, 403, 404])
async def test_metadata_never_accepts_redirect_or_repository_fallback(status: int) -> None:
    seen: list[str] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            status,
            headers={"Location": "https://untrusted.example/"},
            text="synthetic-secret-in-error-body",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        store = EnvironmentSecretStore(client, "synthetic-writer")
        with pytest.raises(AuthPersistenceError) as exc:
            await store.verify_environment_secret()
        assert str(exc.value) == "codex_auth_persistence_failed"
    assert len(seen) == 1


async def test_write_denial_is_not_success() -> None:
    key = PrivateKey.generate()

    async def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "key_id": "key",
                    "key": base64.b64encode(bytes(key.public_key)).decode(),
                },
            )
        return httpx.Response(403, text="synthetic-writer-secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(AuthPersistenceError):
            await EnvironmentSecretStore(client, "writer").persist(validate_auth(auth()))


async def test_retry_after_beyond_budget_does_not_sleep_or_retry() -> None:
    count = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(429, headers={"Retry-After": "120"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(AuthPersistenceError):
            await EnvironmentSecretStore(client, "writer").verify_environment_secret()
    assert count == 1


def test_fixed_secret_target_cannot_be_overridden() -> None:
    with pytest.raises(AuthPersistenceError):
        SecretTarget(repository="attacker/elsewhere")


class FakeRunner:
    def __init__(self, home: Path) -> None:
        self.auth_home = home
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeStore:
    def __init__(self) -> None:
        self.documents: list[bytes] = []
        self.fail = False

    async def persist(self, document: AuthDocument) -> None:
        if self.fail:
            raise RuntimeError("synthetic-store-error")
        self.documents.append(document.raw)


def lifecycle(tmp_path: Path) -> tuple[AuthLifecycle, FakeRunner, FakeStore]:
    tmp_path.chmod(0o700)
    seed = write_auth(tmp_path / "auth.json", auth())
    runner, store = FakeRunner(tmp_path), FakeStore()
    return (
        AuthLifecycle(cast(CodexRunner, runner), cast(EnvironmentSecretStore, store), seed),
        runner,
        store,
    )


async def test_refresh_survives_generation_failure_and_is_not_written_twice(tmp_path: Path) -> None:
    owner, runner, store = lifecycle(tmp_path)
    write_auth(tmp_path / "auth.json", auth("new"))
    await owner.preserve()  # finally path, even when generation produced no documents
    await owner.preserve()
    assert runner.closed
    assert store.documents == [auth("new")]
    assert owner.status == "persisted"


async def test_failed_checkpoint_remains_failed_even_if_finally_preserves(tmp_path: Path) -> None:
    owner, _, store = lifecycle(tmp_path)
    write_auth(tmp_path / "auth.json", auth("new"))
    store.fail = True
    with pytest.raises(AuthPersistenceError):
        await owner.checkpoint()
    store.fail = False
    await owner.preserve()
    assert owner.failed_checkpoint
    assert store.documents == [auth("new")]


async def test_invalid_latest_file_does_not_overwrite_secret_with_seed(tmp_path: Path) -> None:
    owner, _, store = lifecycle(tmp_path)
    (tmp_path / "auth.json").write_text("{}")
    with pytest.raises(AuthPersistenceError):
        await owner.checkpoint()
    assert store.documents == []


async def test_valid_unchanged_auth_requires_no_update(tmp_path: Path) -> None:
    owner, _, store = lifecycle(tmp_path)
    await owner.checkpoint()
    assert store.documents == [] and owner.status == "unchanged"
    assert read_auth(tmp_path / "auth.json").raw == auth()


@pytest.mark.parametrize(
    "changed",
    [
        {"GITHUB_REPOSITORY": "murphyGo/investo"},
        {"INVESTO_RUNTIME_VISIBILITY": "public"},
        {"GITHUB_EVENT_NAME": "pull_request_target"},
        {"GITHUB_REF": "refs/heads/unreviewed"},
        {"GITHUB_ACTIONS": "false"},
    ],
)
def test_private_runtime_rejects_untrusted_context(changed: dict[str, str]) -> None:
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "murphyGo/investo-runtime",
        "INVESTO_RUNTIME_VISIBILITY": "private",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        **changed,
    }
    with pytest.raises(AuthPersistenceError):
        validate_private_context(env)


async def test_auth_failure_prevents_publication_stage() -> None:
    calls: list[str] = []

    class WouldPublish:
        name = "publish"

        async def execute(self, *args: object) -> None:
            calls.append("publish")
            raise AssertionError("Public stage must never run")

    async def checkpoint() -> None:
        calls.append("checkpoint")
        raise AuthPersistenceError()

    with pytest.raises(AuthPersistenceError):
        await run_pipeline(
            date(2026, 9, 8),
            publisher=cast(BriefingPublisher, object()),
            alerter=cast(OperatorAlerter, object()),
            site_url_base=TypeAdapter(HttpUrl).validate_python("https://example.com"),
            stages=(cast(Stage, WouldPublish()),),
            before_publication=checkpoint,
        )
    assert calls == ["checkpoint"]


async def test_dry_run_boot_failure_never_sends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_DRY_RUN", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "synthetic-bot")
    monkeypatch.setenv("TELEGRAM_OPERATOR_CHAT_ID", "synthetic-chat")

    def no_client(*args: object, **kwargs: object) -> None:
        raise AssertionError("no Telegram client")

    monkeypatch.setattr(entrypoint.httpx, "AsyncClient", no_client)
    await entrypoint._attempt_boot_alert(ValueError("failed"))


def test_codex_dry_run_preflight_needs_no_claude_or_send_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in entrypoint._REQUIRED_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("INVESTO_LLM_PROVIDER", "codex")
    monkeypatch.setenv("INVESTO_CODEX_MODEL", "test-model")
    monkeypatch.setenv("INVESTO_CODEX_HOME", "/dedicated-test-home")
    monkeypatch.setenv("INVESTO_DRY_RUN", "1")
    monkeypatch.setenv("SITE_URL_BASE", "https://example.com")
    _, _, public, operator, _ = entrypoint._validate_env(LlmExecutionConfig("codex", "test-model"))
    assert public != operator


@pytest.mark.parametrize("failure", ["cancel", "timeout", "generation"])
async def test_supervisor_always_preserves_rotation_and_emits_failure_receipt(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: str,
) -> None:
    import logging
    import sys

    from investo.orchestrator import codex_runtime as runtime

    env = {
        "INVESTO_LLM_PROVIDER": "codex",
        "INVESTO_CODEX_MODEL": "test-model",
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "murphyGo/investo-runtime",
        "INVESTO_RUNTIME_VISIBILITY": "private",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "CODEX_AUTH_JSON": auth().decode(),
        "CODEX_SECRET_WRITE_TOKEN": "synthetic-writer",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    saved: list[bytes] = []

    class Store:
        def __init__(self, *args: object) -> None:
            pass

        async def verify_environment_secret(self) -> None:
            pass

        async def persist(self, document: AuthDocument) -> None:
            saved.append(document.raw)

    async def failed_pipeline(**kwargs: object) -> int:
        import os

        write_auth(Path(os.environ["INVESTO_CODEX_HOME"]) / "auth.json", auth("new"))
        if failure == "cancel":
            raise asyncio.CancelledError()
        if failure == "timeout":
            raise TimeoutError()
        raise RuntimeError("synthetic-generation-failure")

    monkeypatch.setattr(runtime, "EnvironmentSecretStore", Store)
    monkeypatch.setattr(runtime.shutil, "which", lambda _: sys.executable)
    monkeypatch.setattr(entrypoint, "_async_main", failed_pipeline)
    caplog.set_level(logging.INFO)
    with pytest.raises((RuntimeError, TimeoutError, asyncio.CancelledError)):
        await runtime.run()
    assert saved == [auth("new")]
    receipt = next(
        record.message for record in caplog.records if record.message.startswith("codex_runtime ")
    )
    assert '"auth": "persisted"' in receipt and '"exit_code": 1' in receipt
    assert "synthetic" not in receipt


def test_work_deadline_reserves_bounded_cleanup_time() -> None:
    from investo.orchestrator.codex_runtime import (
        CLEANUP_RESERVE_S,
        GENERATION_LIMIT_S,
        RUNTIME_LIMIT_S,
    )

    assert CLEANUP_RESERVE_S > 11 + 60 + 11
    assert GENERATION_LIMIT_S < RUNTIME_LIMIT_S - CLEANUP_RESERVE_S


def test_receipt_provenance_drops_untrusted_values() -> None:
    from investo.orchestrator.codex_runtime import _receipt_provenance

    assert _receipt_provenance({"GITHUB_RUN_ID": "synthetic-secret"}) == {
        "run_id": None,
        "code_sha": None,
        "target_date_override": None,
    }
    assert _receipt_provenance({"REVIEWED_CODE_SHA": "a" * 40})["code_sha"] == "a" * 40


@pytest.mark.parametrize("failure", ["cancel", "deadline"])
async def test_private_claude_supervisor_reaps_running_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import os
    import sys
    import time

    from investo.briefing.claude_code import call_claude_code
    from investo.orchestrator import codex_runtime as runtime

    pidfile = tmp_path / "child.pid"
    binary = tmp_path / "claude"
    binary.write_text(
        f"#!{sys.executable}\nimport os,time\nfrom pathlib import Path\n"
        f"Path({str(pidfile)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n"
    )
    binary.chmod(0o700)
    for key, value in {
        "INVESTO_LLM_PROVIDER": "claude",
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "murphyGo/investo-runtime",
        "INVESTO_RUNTIME_VISIBILITY": "private",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        runtime.shutil, "which", lambda name: str(binary) if name == "claude" else sys.executable
    )

    async def pipeline(**kwargs: object) -> int:
        await call_claude_code("evidence", runner=kwargs["llm_runner"], timeout_s=30)
        return 0

    monkeypatch.setattr(entrypoint, "_async_main", pipeline)
    if failure == "deadline":
        monkeypatch.setattr(runtime, "RUNTIME_LIMIT_S", runtime.CLEANUP_RESERVE_S + 2)
    task = asyncio.create_task(runtime.run())
    for _ in range(250):
        if pidfile.exists():
            break
        await asyncio.sleep(0.02)
    if not pidfile.exists():
        await task
    assert pidfile.exists()
    start = time.monotonic()
    if failure == "cancel":
        task.cancel()
    with pytest.raises((asyncio.CancelledError, TimeoutError)):
        await task
    assert time.monotonic() - start < 3
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)
