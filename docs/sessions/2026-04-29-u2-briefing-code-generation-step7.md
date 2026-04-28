# Session Log: 2026-04-29 - u2 briefing - Code Generation Step 7

## Overview
- **Date**: 2026-04-29
- **Unit**: u2 briefing
- **Stage**: Code Generation
- **Step**: Step 7 — `FakeClaudeRunner` (recorded-fixture replay + INVESTO_LIVE_LLM record mode)

## Work Summary

Implemented the test-side LLM runner — the **R9 fixture mechanism** that
keeps CI fully offline while enabling local fixture refresh. Module
exposes `FakeClaudeRunner` (implementing the `ClaudeRunner` Protocol
from `claude_code.py`) and `FixtureMissingError`. Lookup key is
`sha256(prompt)[:16]`; fixture file format is JSON with prompt /
stdout / stderr / returncode / elapsed_s. Live-record mode kicks in
when `INVESTO_LIVE_LLM=1` (developer-only; CI never sets this).

The test file also pins **AC-6.5** via an AST-based grep that walks
all test files looking for `subprocess.run(["claude", ...])` call
patterns — false-positive-immune to mere mentions of the string
`"claude"` in arg-shape assertions.

16 new tests across one file (after Step 7 review applied 2 regression
pins — atomic write, args-shape guard).

## Files Changed

### Created
- `tests/_helpers/fake_claude_runner.py` (217 lines) — `FakeClaudeRunner`
  with `__call__` (extracts prompt, computes key, replay vs live-record
  switch) + `_replay` + `_record` (atomic write via tmp + `os.replace`)
  + args-shape guard (clear ValueError on malformed args) + module
  docstring documenting fixture format and modes.
- `tests/unit/briefing/test_fake_claude_runner.py` (333 lines) — 16
  tests covering replay round-trip (stdout/stderr/returncode/missing-
  field-defaults), missing-fixture diagnostic (key + prompt prefix +
  INVESTO_LIVE_LLM hint + 200-char prompt prefix truncation), live-
  recording mode with stubbed subprocess (records fixture, returns
  CompletedProcess, creates parent dirs, env-var must be exactly "1"),
  default fixture-dir resolution, public surface, args-shape guard
  (2 cases), atomic write (no .tmp leftover), and the AST-based AC-6.5
  grep.

### Modified
- `aidlc-docs/construction/plans/u2-briefing-code-generation-plan.md` —
  Step 7 sub-tasks `[x]` with detailed status notes
- `aidlc-docs/aidlc-state.md` — u2 CG progress 6/10 → 7/10
- `aidlc-docs/audit.md` — Step 7 entry prepended

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `tests/_helpers/` (underscore-prefix) over `tests/helpers/` | Avoids accidental pytest test collection from this support-only package. |
| Lazy env-var check on every `__call__` (not at construction) | Allows tests to monkeypatch `INVESTO_LIVE_LLM` without re-instantiating the runner. Pinned by `test_live_mode_then_replay_round_trip`. |
| `subprocess_runner` injection (default = `subprocess.run`) | Lets tests of the live-record path stub the inner subprocess without spawning real `claude`. Pinned by all live-mode tests. |
| Strict env-var match `== "1"` (not truthy) | Prevents accidental triggers from "true" / "yes" / arbitrary truthy strings. Tested by `test_live_mode_env_var_must_be_exactly_1`. |
| Atomic write via tmp + `os.replace` (Step 7 review M1) | A SIGINT mid-write would otherwise leave a half-written JSON that breaks `json.load` on the next replay. The fix is small and the cost of a corrupt fixture is high (CI breaks until manually fixed). |
| Args-shape guard at `__call__` entry (Step 7 review L1) | If a future caller breaks the `["claude", "-p", <prompt>]` contract, surface a clear `ValueError` instead of a raw `IndexError` from `args.index`. |
| AC-6.5 grep uses AST (not text match) | Mere mentions of the string `"claude"` in arg-shape assertions like `assert captured == ["claude", "-p", ...]` would false-positive a text grep. AST walk + check `subprocess.run/Popen` call sites with first arg = list literal containing `"claude"` is the precise contract. |

## Code Review Results

Sub-agent review (general-purpose): **APPROVE**.

| Category | Status |
|----------|--------|
| Correctness | ✅ |
| Safety | ✅ |
| Reliability | ⚠️ → ✅ (M1 atomic write applied) |
| Maintainability | ✅ |
| Test Coverage | ✅ |

Findings: 0 Critical / 0 High / 1 Medium / 4 Lows + 2 TECH-DEBT
candidates.
- **M1** Non-atomic fixture write — APPLIED (tmp + os.replace).
- **L1** Args-shape contract guard — APPLIED.
- **L2** `_KEY_LENGTH = 16` "64 bits" comment — sound.
- **L3** Aliased import `from subprocess import run` not covered —
  deferred (false-positive immunity > exhaustiveness).
- **L4** Test reads private `_fixture_dir` — acceptable for internal
  helper test.
- TD-fake-claude-runner-atomic-write — applied as M1 fix.
- TD-fake-claude-runner-args-shape-guard — applied as L1 fix.

## Quality Gate

- `ruff check .` ✅
- `ruff format --check .` ✅ (54 files already formatted)
- `mypy --strict src/` ✅ (21 source files; +0 — helper lives under
  `tests/`)
- `pytest -q` ✅ **369/369 passed in 3.56s**
  - +16 new tests in `test_fake_claude_runner.py`

## Potential Risks

- **R-Step7-1**: Live-record mode is gated only by `INVESTO_LIVE_LLM=1`.
  If a developer accidentally sets it in CI (via repo secret or
  workflow), CI would spawn the real `claude` CLI. Mitigation: the
  CI workflow (Step 10) does not set this var; the env var name is
  prefixed with `INVESTO_` to make accidental name collisions less
  likely.
- **R-Step7-2**: Fixture key collisions at 64-bit hash space are
  ~5e-15 for 1000 fixtures. Acceptable. If a real collision ever
  surfaces, the prompt content embedded in the fixture file lets
  the developer disambiguate.
- **R-Step7-3**: An aliased subprocess import (`from subprocess
  import run; run(["claude", ...])`) would slip past the AC-6.5
  AST grep (per agent L3). Mitigation: code review catches it; the
  pattern is unidiomatic and unusual.

## TECH-DEBT Items

None added to registry. Two agent-flagged candidates were resolved
inline (M1 + L1). Two more (L3 aliased imports, L4 private-attr
access) are explicitly accepted as design trade-offs.

## Next Step

**Step 8** — `pipeline.py`: the big one. `classify` + `synthesize` +
`generate_briefing` + R7 `serialize_items_for_prompt` + E3
`build_section_plan` + `parse_six_sections` + 2 PBTs (AC-6.2 / AC-6.3).
This step wires up everything from Steps 2-7.
