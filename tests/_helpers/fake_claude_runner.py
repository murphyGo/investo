"""FakeClaudeRunner — recorded-fixture replay for u2 briefing tests.

References:
    Functional Design R9 (`u2-briefing/functional-design/business-rules.md`)
        — hash-of-prompt fixture mechanism with INVESTO_LIVE_LLM record
    NFR Requirements AC-6.5 — all LLM calls in tests go through this runner
    Tech Stack TS-8 — fixture file format
    Tech Stack TS-9 — in-house runner over pytest-subprocess

Fixture key
-----------

For each prompt, the fixture key is::

    sha256(prompt.encode("utf-8")).hexdigest()[:16]

The fixture file is at ``<fixture_dir>/<key>.json`` with shape::

    {
        "prompt": "<full prompt>",
        "stdout": "<recorded stdout>",
        "stderr": "<recorded stderr>",
        "returncode": 0,
        "elapsed_s": 12.34
    }

The full prompt is stored so a developer reading a stale fixture can
see the input that produced it without recomputing the hash.

Modes
-----

* **Replay** (default): look up by key. Found → return a
  ``CompletedProcess`` with the recorded fields. Not found →
  ``FixtureMissingError`` with a clear "set INVESTO_LIVE_LLM=1" hint.

* **Live record** (``INVESTO_LIVE_LLM=1``): dispatch ``subprocess.run``
  for real, write the result as a fresh fixture, and return.
  CI never sets this var; only developers refreshing fixtures.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final

# Default fixture directory parts under project root.
_DEFAULT_FIXTURE_DIR_PARTS: Final[tuple[str, ...]] = ("tests", "fixtures", "llm")

# Fixture key length in hex chars (= 64 bits of entropy; collision
# probability is vanishingly low at our scale of ~tens of fixtures).
_KEY_LENGTH: Final[int] = 16

# Env var that opts into live-recording mode.
_LIVE_MODE_ENV_VAR: Final[str] = "INVESTO_LIVE_LLM"

# Truncation for the prompt prefix attached to FixtureMissingError.
_PROMPT_PREVIEW_LIMIT: Final[int] = 200


class FixtureMissingError(Exception):
    """Raised when a fixture for a given prompt hash cannot be found.

    Carries enough context for the developer to find or record it:
    the truncated prompt prefix, the computed fixture key, and the
    expected on-disk path.
    """

    def __init__(self, *, prompt_prefix: str, key: str, expected_path: Path) -> None:
        self.prompt_prefix = prompt_prefix
        self.key = key
        self.expected_path = expected_path
        super().__init__(
            f"Missing LLM fixture for prompt hash {key!r} at {expected_path}. "
            f"To record, re-run with {_LIVE_MODE_ENV_VAR}=1. "
            f"Prompt (first {_PROMPT_PREVIEW_LIMIT} chars): {prompt_prefix!r}"
        )


def _compute_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:_KEY_LENGTH]


def _project_root() -> Path:
    # tests/_helpers/fake_claude_runner.py → parents[2] = project root
    return Path(__file__).resolve().parents[2]


# Type alias for the inner subprocess runner — matches subprocess.run's
# kwargs that we exercise.
_SubprocessRunner = Callable[..., "subprocess.CompletedProcess[str]"]


class FakeClaudeRunner:
    """Test-mode runner that replays recorded LLM fixtures.

    Implements the ``ClaudeRunner`` Protocol from
    ``investo.briefing.claude_code``. Inject into ``call_claude_code``
    via the ``runner=`` keyword argument.

    Live-mode subprocess invocation can be overridden via
    ``subprocess_runner`` for tests of the recording path itself
    (so the test does not actually spawn the real ``claude`` binary).
    """

    def __init__(
        self,
        *,
        fixture_dir: Path | None = None,
        subprocess_runner: _SubprocessRunner | None = None,
    ) -> None:
        if fixture_dir is None:
            fixture_dir = _project_root().joinpath(*_DEFAULT_FIXTURE_DIR_PARTS)
        self._fixture_dir = fixture_dir
        self._subprocess_runner: _SubprocessRunner = (
            subprocess_runner if subprocess_runner is not None else subprocess.run
        )

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        # The wrapper always invokes us with ``args = ["claude", "-p", prompt]``.
        # If a future caller breaks the contract (no ``-p``, or ``-p``
        # at the tail), ``args.index`` would raise a confusing
        # ValueError / IndexError — surface a clearer message instead.
        try:
            p_idx = args.index("-p")
            prompt = args[p_idx + 1]
        except (ValueError, IndexError) as exc:
            raise ValueError(
                "FakeClaudeRunner expects args of shape "
                "['claude', '-p', <prompt>, ...]; got: "
                f"{args!r}"
            ) from exc
        key = _compute_key(prompt)
        fixture_path = self._fixture_dir / f"{key}.json"

        if self._is_live_mode():
            return self._record(
                args,
                prompt,
                key,
                fixture_path,
                capture_output=capture_output,
                text=text,
                timeout=timeout,
            )
        return self._replay(args, prompt, key, fixture_path)

    @staticmethod
    def _is_live_mode() -> bool:
        return os.environ.get(_LIVE_MODE_ENV_VAR) == "1"

    def _replay(
        self,
        args: list[str],
        prompt: str,
        key: str,
        fixture_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        if not fixture_path.exists():
            raise FixtureMissingError(
                prompt_prefix=prompt[:_PROMPT_PREVIEW_LIMIT],
                key=key,
                expected_path=fixture_path,
            )
        with fixture_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        return subprocess.CompletedProcess(
            args=args,
            returncode=int(data["returncode"]),
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
        )

    def _record(
        self,
        args: list[str],
        prompt: str,
        key: str,
        fixture_path: Path,
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        start = time.monotonic()
        completed = self._subprocess_runner(
            args,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            check=False,
        )
        elapsed = time.monotonic() - start

        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "prompt": prompt,
            "stdout": completed.stdout if completed.stdout is not None else "",
            "stderr": completed.stderr if completed.stderr is not None else "",
            "returncode": int(completed.returncode),
            "elapsed_s": round(elapsed, 3),
        }
        # Atomic write: dump to a tmp sibling then ``os.replace`` so a
        # SIGINT mid-write cannot leave a half-written JSON that breaks
        # ``json.load`` on the next replay (Step 7 review M1).
        tmp_path = fixture_path.with_suffix(fixture_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2, sort_keys=True)
            fp.write("\n")
        os.replace(tmp_path, fixture_path)
        return completed


__all__ = ["FakeClaudeRunner", "FixtureMissingError"]
