"""Private-runtime Claude isolation; the existing public Claude path is unchanged."""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from investo._internal.cli_process import CliProcessError, capture, stop_process


class PrivateClaudeRunner:
    def __init__(self, binary: str, node: str, token: str) -> None:
        self._binary = binary
        self._node = node
        self._token = token
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._cleanup_failed = False

    def close(self) -> None:
        self._cancelled.set()
        if not self._lock.acquire(timeout=11):
            self._cleanup_failed = True
            raise CliProcessError("claude_cleanup_failed")
        try:
            if self._cleanup_failed:
                raise CliProcessError("claude_cleanup_failed")
        finally:
            self._lock.release()

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del args, capture_output, text
        deadline = time.monotonic() + timeout
        if self._cancelled.is_set() or not self._lock.acquire(timeout=max(0, timeout)):
            return subprocess.CompletedProcess(["claude", "-p"], 124, "", "claude_timeout")
        try:
            if self._cancelled.is_set() or time.monotonic() >= deadline:
                raise CliProcessError("claude_timeout")
            return self._run(input or "", deadline)
        except (CliProcessError, OSError, ValueError, subprocess.SubprocessError):
            return subprocess.CompletedProcess(["claude", "-p"], 1, "", "claude_execution_failed")
        finally:
            self._lock.release()

    def _run(self, prompt: str, deadline: float) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="investo-claude-call-") as temporary:
            root = Path(temporary)
            home, work = root / "home", root / "work"
            home.mkdir(mode=0o700)
            work.mkdir(mode=0o700)
            env = {
                "PATH": os.pathsep.join(
                    (str(Path(self._binary).parent), str(Path(self._node).parent), os.defpath)
                ),
                "HOME": str(home),
                "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                "CLAUDE_CODE_OAUTH_TOKEN": self._token,
                "TMPDIR": str(root),
                "LANG": "C.UTF-8",
            }
            process = subprocess.Popen(
                [
                    self._binary,
                    "-p",
                    "--tools",
                    "",
                    "--disable-slash-commands",
                    "--setting-sources",
                    "",
                    "--strict-mcp-config",
                    "--mcp-config",
                    "{}",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=work,
                env=env,
                start_new_session=True,
            )
            try:
                stdout = capture(process, prompt.encode(), deadline, self._cancelled).decode()
            finally:
                try:
                    stop_process(process)
                except Exception:
                    self._cleanup_failed = True
                    self._cancelled.set()
                    raise CliProcessError("claude_cleanup_failed") from None
                finally:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream is not None:
                            stream.close()
            if process.returncode or (self._token and self._token in stdout):
                return subprocess.CompletedProcess(
                    ["claude", "-p"], 1, "", "claude_execution_failed"
                )
            return subprocess.CompletedProcess(["claude", "-p"], 0, stdout, "")
