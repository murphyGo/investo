from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from investo._internal.codex_auth import CodexAuthError, read_auth, validate_auth, write_auth
from investo._internal.llm_config import LlmConfigError, LlmExecutionConfig, missing_environment
from investo.briefing.claude_code import call_claude_code
from investo.briefing.codex_cli import CodexRunner, _check_events
from investo.briefing.codex_policy import codex_arguments, model_catalog


def auth_bytes(suffix: str = "old") -> bytes:
    return json.dumps(
        {
            "auth_mode": "chatgpt",
            "OPENAI_API_KEY": None,
            "tokens": {
                key: f"synthetic-{key}-{suffix}"
                for key in ("access_token", "refresh_token", "id_token", "account_id")
            },
        }
    ).encode()


@pytest.mark.parametrize("provider", ["", " ", "claude"])
def test_claude_default_needs_no_codex(provider: str) -> None:
    env = {
        "INVESTO_LLM_PROVIDER": provider,
        "CLAUDE_CODE_OAUTH_TOKEN": "test",
        "INVESTO_DRY_RUN": "1",
        "SITE_URL_BASE": "https://example.com",
    }
    assert LlmExecutionConfig.from_env(env) == LlmExecutionConfig()
    assert missing_environment(env, LlmExecutionConfig.from_env(env)) == ()


@pytest.mark.parametrize("provider", ["Claude", "api", "openai", "codex --oss", "secret-input"])
def test_provider_error_never_echoes_input(provider: str) -> None:
    with pytest.raises(LlmConfigError) as exc:
        LlmExecutionConfig.from_env({"INVESTO_LLM_PROVIDER": provider})
    assert provider not in str(exc.value)


@given(st.text())
def test_unknown_provider_is_closed_set(value: str) -> None:
    if value.strip() in ("", "claude", "codex"):
        return
    with pytest.raises(LlmConfigError):
        LlmExecutionConfig.from_env({"INVESTO_LLM_PROVIDER": value})


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"{}",
        b"null",
        b"[]",
        b'{"auth_mode":"api"}',
        b"\xff",
        b'{"auth_mode":"chatgpt","auth_mode":"chatgpt"}',
        b"x" * (48 * 1024),
    ],
)
def test_invalid_auth_has_constant_error(payload: bytes) -> None:
    with pytest.raises(CodexAuthError, match=r"^codex_auth_invalid$"):
        validate_auth(payload)


def test_auth_rejects_api_key_and_missing_token() -> None:
    payload = json.loads(auth_bytes())
    payload["OPENAI_API_KEY"] = "synthetic-api"
    with pytest.raises(CodexAuthError):
        validate_auth(json.dumps(payload).encode())
    payload["OPENAI_API_KEY"] = None
    del payload["tokens"]["refresh_token"]
    with pytest.raises(CodexAuthError):
        validate_auth(json.dumps(payload).encode())


@given(st.text(min_size=1).filter(lambda text: bool(text.strip())))
def test_auth_round_trip(secret: str) -> None:
    payload = json.loads(auth_bytes())
    payload["tokens"]["refresh_token"] = secret
    raw = json.dumps(payload).encode()
    if len(raw) < 48 * 1024:
        document = validate_auth(raw)
        assert document.raw == raw
        assert secret in document.secrets
        assert repr(document) == "AuthDocument(<redacted>)"


def test_atomic_auth_preserves_previous_on_invalid_input(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    path = tmp_path / "auth.json"
    write_auth(path, auth_bytes())
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(CodexAuthError):
        write_auth(path, b"{}")
    assert read_auth(path).raw == auth_bytes()
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(CodexAuthError):
        read_auth(link)
    with pytest.raises(CodexAuthError):
        write_auth(link, auth_bytes("new"))
    path.chmod(0o644)
    with pytest.raises(CodexAuthError):
        read_auth(path)


def make_runner(tmp_path: Path, body: str = "") -> CodexRunner:
    home = tmp_path / "auth"
    home.mkdir(mode=0o700)
    write_auth(home / "auth.json", auth_bytes())
    binary = tmp_path / "codex"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import sys, os, json, time\n"
        "from pathlib import Path\n"
        "if '--version' in sys.argv:\n"
        " print('codex-cli 0.153.4'); sys.exit(0)\n"
        "prompt = sys.stdin.read()\n"
        "assert prompt not in sys.argv\n"
        "assert not any(key in os.environ for key in "
        "('GITHUB_TOKEN','CODEX_AUTH_JSON','CODEX_SECRET_WRITE_TOKEN',"
        "'INVESTO_PUBLIC_PUBLISH_TOKEN','TELEGRAM_BOT_TOKEN','OPENAI_API_KEY'))\n"
        "assert not list(Path.cwd().iterdir())\n"
        "output = 'market answer'\n" + body + "\n"
        "Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(output)\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':output}}))\n"
        "print(json.dumps({'type':'turn.completed'}))\n",
    )
    binary.chmod(0o700)
    return CodexRunner(
        LlmExecutionConfig("codex", "test-model"),
        home,
        deadline=time.monotonic() + 30,
        binary=str(binary),
    )


async def test_existing_seam_gets_codex_final_text_with_minimal_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "GITHUB_TOKEN",
        "CODEX_AUTH_JSON",
        "CODEX_SECRET_WRITE_TOKEN",
        "INVESTO_PUBLIC_PUBLISH_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "OPENAI_API_KEY",
    ):
        monkeypatch.setenv(key, "synthetic-parent-secret")
    runner = make_runner(tmp_path)
    outcome = await call_claude_code("evidence prompt", timeout_s=3, runner=runner)
    assert outcome.returncode == 0
    assert outcome.stdout == "market answer"
    assert outcome.stderr == ""
    runner.close()
    assert (await call_claude_code("again", runner=runner)).returncode != 0


@pytest.mark.parametrize(
    "body",
    [
        "sys.stderr.write('synthetic-sensitive-error'); sys.exit(2)",
        "print('x' * (4 * 1024 * 1024 + 1))",
        "sys.stderr.write('x' * (4 * 1024 * 1024 + 1))",
        "output = 'synthetic-access_token-old'",
        "print(json.dumps({'type':'item.completed','item':{'type':'command_execution'}}))",
    ],
)
async def test_failed_or_unsafe_output_never_reaches_parser(tmp_path: Path, body: str) -> None:
    runner = make_runner(tmp_path, body)
    outcome = await call_claude_code("test prompt", timeout_s=3, runner=runner)
    assert outcome.returncode != 0
    assert outcome.stdout == ""
    assert "synthetic" not in outcome.stderr
    runner.close()


async def test_rotated_token_output_is_blocked(tmp_path: Path) -> None:
    body = (
        "auth = Path(os.environ['CODEX_HOME']) / 'auth.json'\n"
        "payload = json.loads(auth.read_text())\n"
        "payload['tokens']['access_token'] = 'synthetic-new-access'\n"
        "auth.write_text(json.dumps(payload))\n"
        "output = 'synthetic-new-access'"
    )
    runner = make_runner(tmp_path, body)
    outcome = await call_claude_code("test", timeout_s=3, runner=runner)
    assert outcome.returncode != 0 and outcome.stdout == ""
    assert "synthetic-new-access" in read_auth(runner.auth_home / "auth.json").secrets
    runner.close()


@pytest.mark.parametrize(
    "body",
    [
        "time.sleep(20)",
        "os.close(0); os.close(1); os.close(2); time.sleep(20)",
    ],
)
def test_close_interrupts_running_process_before_return(tmp_path: Path, body: str) -> None:
    runner = make_runner(tmp_path, body)
    outcomes: list[subprocess.CompletedProcess[str]] = []
    thread = threading.Thread(
        target=lambda: outcomes.append(
            runner([], capture_output=True, text=True, timeout=25, input="test")
        )
    )
    thread.start()
    time.sleep(0.2)
    start = time.monotonic()
    runner.close()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert time.monotonic() - start < 2
    assert outcomes[0].returncode != 0


def test_metadata_removes_edit_tools_separately_from_shell() -> None:
    catalog = model_catalog("test-model")
    encoded = json.dumps(catalog)
    assert '"shell_type": "disabled"' in encoded
    assert '"apply_patch_tool_type": null' in encoded
    assert '"experimental_supported_tools": []' in encoded
    argv = codex_arguments("test-model", catalog=Path("/tmp/models"), work=Path("/tmp/work"))
    for flag in (
        "features.shell_tool=false",
        "features.multi_agent=false",
        'web_search="disabled"',
        'forced_login_method="chatgpt"',
    ):
        assert flag in argv


def test_events_reject_unknown_hosted_tools() -> None:
    with pytest.raises(RuntimeError, match="codex_unexpected_event"):
        _check_events(b'{"type":"item.started","item":{"type":"mcp_tool_call"}}')


async def test_cleanup_failure_permanently_blocks_calls_and_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import cast

    from investo.briefing import codex_cli
    from investo.orchestrator.codex_runtime import AuthLifecycle
    from investo.orchestrator.codex_secrets import AuthPersistenceError, EnvironmentSecretStore

    runner = make_runner(tmp_path)
    stop = codex_cli._stop_process
    cleanups = 0

    def fail_cleanup(process: subprocess.Popen[bytes]) -> None:
        nonlocal cleanups
        cleanups += 1
        stop(process)  # no real child left by this injected failure
        raise OSError("synthetic-cleanup-error")

    monkeypatch.setattr(codex_cli, "_stop_process", fail_cleanup)
    assert (await call_claude_code("one", runner=runner)).returncode != 0
    assert (await call_claude_code("two", runner=runner)).returncode != 0
    assert cleanups == 1
    lifecycle = AuthLifecycle(
        runner, cast(EnvironmentSecretStore, object()), read_auth(runner.auth_home / "auth.json")
    )
    with pytest.raises(AuthPersistenceError):
        await lifecycle.checkpoint()
    with pytest.raises(RuntimeError, match="codex_cleanup_failed"):
        runner.close()


def test_private_claude_cannot_discover_latest_checkout_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investo.briefing.private_claude import PrivateClaudeRunner

    (tmp_path / "CLAUDE.md").write_text("unreviewed instructions")
    monkeypatch.chdir(tmp_path)
    binary = tmp_path / "fake-claude"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\nfrom pathlib import Path\n"
        "assert not list(Path.cwd().iterdir())\n"
        "assert not (Path(os.environ['HOME']) / '.claude.json').exists()\n"
        "assert os.environ['CLAUDE_CODE_OAUTH_TOKEN']=='synthetic-claude'\n"
        "assert 'CODEX_AUTH_JSON' not in os.environ\n"
        "assert sys.argv[sys.argv.index('--tools')+1]==''\n"
        "assert sys.argv[sys.argv.index('--setting-sources')+1]==''\n"
        "assert sys.stdin.read()=='prompt'\nprint('claude answer')\n"
    )
    binary.chmod(0o700)
    runner = PrivateClaudeRunner(str(binary), sys.executable, "synthetic-claude")
    result = runner([], capture_output=True, text=True, timeout=2, input="prompt")
    assert result.returncode == 0 and result.stdout == "claude answer\n"


async def test_concurrent_requests_serialize_and_charge_lock_wait(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="investo.briefing.codex_cli")
    runner = make_runner(
        tmp_path,
        (
            "marker = Path(os.environ['CODEX_HOME']) / 'busy'\n"
            "assert not marker.exists()\n"
            "marker.write_text('busy')\n"
            "time.sleep(0.2)\n"
            "marker.unlink()"
        ),
    )
    one, two = await asyncio.gather(
        call_claude_code("one", runner=runner, timeout_s=3),
        call_claude_code("two", runner=runner, timeout_s=3),
    )
    assert one.returncode == two.returncode == 0
    assert max(one.elapsed_s, two.elapsed_s) >= 0.4
    timings = [
        json.loads(record.message.removeprefix("codex_call "))
        for record in caplog.records
        if record.message.startswith("codex_call ")
    ]
    assert len(timings) == 2
    assert max(item["lock_wait_s"] for item in timings) >= 0.1
    assert all(set(item) == {"lock_wait_s", "execution_s"} for item in timings)
    runner.close()


async def test_lock_wait_expires_without_second_launch(tmp_path: Path) -> None:
    runner = make_runner(tmp_path, "time.sleep(0.3)")
    first = asyncio.create_task(call_claude_code("one", runner=runner, timeout_s=3))
    await asyncio.sleep(0.05)
    second = await call_claude_code("two", runner=runner, timeout_s=0.05)
    assert second.returncode == 124 and second.elapsed_s >= 0.05
    assert (await first).returncode == 0
    runner.close()
