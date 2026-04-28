"""Tests for ``tests._helpers.fake_claude_runner`` (FD R9; NFR AC-6.5)."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tests._helpers.fake_claude_runner import FakeClaudeRunner, FixtureMissingError


def _key_for(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


# --- Replay round-trip ------------------------------------------------------


def test_replay_returns_recorded_completed_process(tmp_path: Path) -> None:
    """Write a fixture, look it up via the runner, get the recorded
    fields back as a ``CompletedProcess``.
    """
    prompt = "test-prompt-A"
    key = _key_for(prompt)
    fixture = tmp_path / f"{key}.json"
    fixture.write_text(
        json.dumps(
            {
                "prompt": prompt,
                "stdout": "Hello",
                "stderr": "warn",
                "returncode": 0,
                "elapsed_s": 1.234,
            }
        ),
        encoding="utf-8",
    )

    runner = FakeClaudeRunner(fixture_dir=tmp_path)
    completed = runner(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120.0,
    )
    assert isinstance(completed, subprocess.CompletedProcess)
    assert completed.stdout == "Hello"
    assert completed.stderr == "warn"
    assert completed.returncode == 0


def test_replay_preserves_returncode_nonzero(tmp_path: Path) -> None:
    prompt = "test-prompt-fail"
    fixture = tmp_path / f"{_key_for(prompt)}.json"
    fixture.write_text(
        json.dumps(
            {
                "prompt": prompt,
                "stdout": "",
                "stderr": "broken",
                "returncode": 7,
                "elapsed_s": 0.5,
            }
        ),
        encoding="utf-8",
    )
    runner = FakeClaudeRunner(fixture_dir=tmp_path)
    completed = runner(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert completed.returncode == 7
    assert completed.stderr == "broken"


def test_missing_stdout_or_stderr_defaults_to_empty(tmp_path: Path) -> None:
    """Fixture with only ``returncode`` (no stdout/stderr keys) → safe."""
    prompt = "minimal"
    fixture = tmp_path / f"{_key_for(prompt)}.json"
    fixture.write_text(
        json.dumps({"prompt": prompt, "returncode": 0}),
        encoding="utf-8",
    )
    runner = FakeClaudeRunner(fixture_dir=tmp_path)
    completed = runner(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert completed.stdout == ""
    assert completed.stderr == ""


# --- Missing fixture --------------------------------------------------------


def test_missing_fixture_raises_with_diagnostic(tmp_path: Path) -> None:
    prompt = "this-fixture-was-never-recorded"
    expected_key = _key_for(prompt)
    runner = FakeClaudeRunner(fixture_dir=tmp_path)

    with pytest.raises(FixtureMissingError) as excinfo:
        runner(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=10.0,
        )

    err = excinfo.value
    assert err.key == expected_key
    assert err.prompt_prefix.startswith("this-fixture")
    assert err.expected_path == tmp_path / f"{expected_key}.json"
    # Error message hints at INVESTO_LIVE_LLM
    assert "INVESTO_LIVE_LLM=1" in str(err)


def test_missing_fixture_truncates_prompt_prefix(tmp_path: Path) -> None:
    """A 5000-char prompt yields a prefix capped at 200 chars."""
    prompt = "x" * 5000
    runner = FakeClaudeRunner(fixture_dir=tmp_path)
    with pytest.raises(FixtureMissingError) as excinfo:
        runner(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
    assert len(excinfo.value.prompt_prefix) == 200


# --- Live-record mode -------------------------------------------------------


def test_live_mode_records_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``INVESTO_LIVE_LLM=1`` set and a stubbed subprocess runner,
    invoking the FakeClaudeRunner writes a JSON fixture to disk.
    """
    monkeypatch.setenv("INVESTO_LIVE_LLM", "1")

    def stub_subprocess(
        args: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="recorded-stdout",
            stderr="",
        )

    runner = FakeClaudeRunner(fixture_dir=tmp_path, subprocess_runner=stub_subprocess)
    prompt = "fresh-prompt-for-recording"
    completed = runner(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120.0,
    )

    # Returned process matches what the stub gave us
    assert completed.stdout == "recorded-stdout"
    assert completed.returncode == 0

    # Fixture file landed
    fixture_path = tmp_path / f"{_key_for(prompt)}.json"
    assert fixture_path.exists()
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert data["prompt"] == prompt
    assert data["stdout"] == "recorded-stdout"
    assert data["stderr"] == ""
    assert data["returncode"] == 0
    assert isinstance(data["elapsed_s"], (int, float))
    assert data["elapsed_s"] >= 0.0


def test_live_mode_then_replay_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Record once with live mode, then replay returns the same payload."""
    prompt = "round-trip-prompt"

    def stub_subprocess(
        args: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="round-trip-stdout",
            stderr="round-trip-stderr",
        )

    # Record
    monkeypatch.setenv("INVESTO_LIVE_LLM", "1")
    recorder = FakeClaudeRunner(fixture_dir=tmp_path, subprocess_runner=stub_subprocess)
    recorder(["claude", "-p", prompt], capture_output=True, text=True, timeout=60.0)

    # Replay
    monkeypatch.delenv("INVESTO_LIVE_LLM", raising=False)
    replayer = FakeClaudeRunner(fixture_dir=tmp_path)
    completed = replayer(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=60.0,
    )
    assert completed.stdout == "round-trip-stdout"
    assert completed.stderr == "round-trip-stderr"
    assert completed.returncode == 0


def test_live_mode_creates_fixture_dir_if_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live mode writes through ``mkdir(parents=True, exist_ok=True)``."""
    monkeypatch.setenv("INVESTO_LIVE_LLM", "1")
    sub_dir = tmp_path / "nested" / "fixtures"

    def stub_subprocess(
        args: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="x", stderr="")

    runner = FakeClaudeRunner(fixture_dir=sub_dir, subprocess_runner=stub_subprocess)
    runner(["claude", "-p", "p"], capture_output=True, text=True, timeout=10.0)
    assert sub_dir.exists()
    assert any(sub_dir.iterdir())


# --- Live-mode env-var matching --------------------------------------------


def test_live_mode_env_var_must_be_exactly_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting INVESTO_LIVE_LLM to any value other than ``"1"`` keeps
    replay-mode active (no accidental triggers from "true" / "yes" /
    truthy strings).
    """
    monkeypatch.setenv("INVESTO_LIVE_LLM", "true")  # not "1"
    runner = FakeClaudeRunner(fixture_dir=tmp_path)
    with pytest.raises(FixtureMissingError):
        runner(["claude", "-p", "no-fixture"], capture_output=True, text=True, timeout=10.0)


def test_default_fixture_dir_resolves_to_project_path() -> None:
    """Without an explicit ``fixture_dir``, the runner resolves to
    ``<project_root>/tests/fixtures/llm/``.
    """
    runner = FakeClaudeRunner()
    expected_suffix = Path("tests") / "fixtures" / "llm"
    assert str(runner._fixture_dir).endswith(str(expected_suffix))


# --- AC-6.5: tests must use FakeClaudeRunner, not raw subprocess ------------


def _file_calls_claude_via_subprocess(text: str) -> bool:
    """AST-based check: True if the source contains a
    ``subprocess.run([..., "claude", ...])`` or
    ``subprocess.Popen([...])`` call where the first positional arg
    is a list literal containing the string ``"claude"``.

    Uses AST so that mere mentions of ``"claude"`` in unrelated
    assertions (e.g. ``assert captured == ["claude", "-p", ...]``)
    do NOT false-positive — only actual call sites count.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Detect ``subprocess.run`` / ``subprocess.Popen`` attribute calls.
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ("run", "Popen"):
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != "subprocess":
            continue
        # First positional arg must be a list literal with "claude" inside.
        if not node.args:
            continue
        first_arg = node.args[0]
        if not isinstance(first_arg, ast.List):
            continue
        for elt in first_arg.elts:
            if isinstance(elt, ast.Constant) and elt.value == "claude":
                return True
    return False


def test_no_test_invokes_claude_via_raw_subprocess() -> None:
    """AC-6.5 — no test file under ``tests/`` directly calls
    ``subprocess.run(["claude", ...])``.

    All LLM calls in tests must go through ``FakeClaudeRunner``
    (FD R9). The only authorized direct-subprocess invocation of
    ``claude`` lives in ``tests/_helpers/fake_claude_runner.py``'s
    live-recording path.

    The check uses AST analysis (not text grep) so that legitimate
    references to the string ``"claude"`` in non-subprocess contexts
    (e.g. arg-shape assertions, attribute checks) do not trigger
    false positives.
    """
    project_root = Path(__file__).resolve().parents[3]
    tests_dir = project_root / "tests"

    offenders: list[Path] = []
    for py_file in tests_dir.rglob("*.py"):
        # Skip the helper module — its live-recording path legitimately
        # spawns ``claude`` (and only when INVESTO_LIVE_LLM=1; CI never
        # sets this).
        if py_file.name == "fake_claude_runner.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        if _file_calls_claude_via_subprocess(text):
            offenders.append(py_file)

    assert not offenders, (
        "AC-6.5 violation — these test files spawn ``claude`` directly "
        f"via subprocess: {offenders}. Use FakeClaudeRunner instead."
    )


# --- Public surface ---------------------------------------------------------


def test_module_exports_runner_and_error() -> None:
    from tests._helpers import fake_claude_runner as fcr

    assert "FakeClaudeRunner" in fcr.__all__
    assert "FixtureMissingError" in fcr.__all__


def test_fixture_missing_error_is_exception_subclass() -> None:
    assert issubclass(FixtureMissingError, Exception)


# --- Args-shape contract guard (Step 7 review L1) ---------------------------


def test_runner_rejects_args_without_dash_p(tmp_path: Path) -> None:
    """The runner expects ``["claude", "-p", <prompt>, ...]``; if the
    contract is broken, surface a clear ValueError rather than a raw
    ``args.index`` exception.
    """
    runner = FakeClaudeRunner(fixture_dir=tmp_path)
    with pytest.raises(ValueError, match=r"shape \['claude', '-p'"):
        runner(["claude", "no-dash-p"], capture_output=True, text=True, timeout=10.0)


def test_runner_rejects_args_with_dash_p_at_tail(tmp_path: Path) -> None:
    """If ``-p`` is present but at the tail (no prompt follows),
    surface the same ValueError.
    """
    runner = FakeClaudeRunner(fixture_dir=tmp_path)
    with pytest.raises(ValueError, match=r"shape \['claude', '-p'"):
        runner(["claude", "-p"], capture_output=True, text=True, timeout=10.0)


# --- Atomic write (Step 7 review M1) ----------------------------------------


def test_live_mode_uses_atomic_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fixture write path uses tmp-file + os.replace so a SIGINT
    mid-write cannot leave a corrupt fixture. We can't easily inject
    a SIGINT in a unit test, but we CAN verify that no ``.tmp`` file
    is left behind after a successful write.
    """
    monkeypatch.setenv("INVESTO_LIVE_LLM", "1")

    def stub_subprocess(
        args: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="x", stderr="")

    runner = FakeClaudeRunner(fixture_dir=tmp_path, subprocess_runner=stub_subprocess)
    runner(["claude", "-p", "atomic-test"], capture_output=True, text=True, timeout=10.0)

    # Final file exists; no leftover .tmp
    files = list(tmp_path.iterdir())
    assert any(f.suffix == ".json" for f in files)
    assert not any(f.suffix == ".tmp" for f in files)
