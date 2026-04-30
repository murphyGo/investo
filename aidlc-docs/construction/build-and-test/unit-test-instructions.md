# Unit Test Execution

**Project**: Investo
**Test runner**: `pytest` (with `pytest-asyncio` for async coroutines + `hypothesis` for PBT)
**Date**: 2026-05-01
**Total tests**: **705 unit + 15 integration = 720 tests** across 6 units

---

## Run unit tests

### 1. Execute all tests

```bash
uv run pytest
```

Expected output (clean repo, `uv sync --extra dev`):

```
========================= 720 passed in ~5.5s =========================
```

The runtime is dominated by:
- u2 briefing PBT (hypothesis examples — ~1.5s)
- u3 publisher git_ops integration (subprocess fakes — ~0.5s)
- u5 orchestrator integration test (4-mock end-to-end with real `generate_briefing` + `write_briefing` — ~0.3s)

### 2. Execute a single unit's tests

```bash
# models foundation
uv run pytest tests/unit/models/ -q

# u1 sources
uv run pytest tests/unit/sources/ -q

# u2 briefing
uv run pytest tests/unit/briefing/ -q

# u3 publisher
uv run pytest tests/unit/publisher/ -q

# u4 notifier
uv run pytest tests/unit/notifier/ -q

# u5 orchestrator
uv run pytest tests/unit/orchestrator/ -q

# Integration suite (covers cross-unit flows)
uv run pytest tests/integration/ -q
```

### 3. Run only fast tests (skip PBTs)

```bash
uv run pytest -m 'not slow'
```

(No `slow` marker is currently used; PBTs run in the default `pytest` invocation. Reserved for future benchmarks.)

### 4. Run with verbose output

```bash
uv run pytest -v
```

---

## Test inventory by unit

| Unit | Test files | Tests | Test types |
|------|-----------|------:|------------|
| **models** | 5 (`test_briefing.py` / `test_init.py` / `test_items.py` / `test_results.py` / `test_roundtrip.py`) | **101** | Validators, frozen-pydantic, cross-field invariants, hypothesis round-trip |
| **u1 sources** | 8 | **252** | Per-adapter (FOMC RSS), aggregator failure isolation, FetchWindow PBT, retry backoff, sanitization, plugin registry |
| **u2 briefing** | 8 | **178** | Two-stage prompt + parsing PBTs, RetryBudget, leak guard, FakeClaudeRunner record/replay, append_disclaimer idempotence, NFC normalization, no-prompt-strings AST grep |
| **u3 publisher** | 5 | **70** | Atomic write, verify-disclaimer hard block (NFR-004), commit_and_push retry exhaustion, idempotent-noop detector, paths boundary |
| **u4 notifier** | 4 + 1 smoke | **56** | UTF-16 truncation, bot-token redaction (URL + shape regex), kwargs-only ctors, MockTransport happy/failure, chat-ID-separation invariant |
| **u5 orchestrator** | 7 + 1 integration | **149** | 4 stage runners, run_pipeline Q9=B router (11 ACs), 3 AST-grep deny tests (no asyncio.wait_for / no stage-level gather / no orchestrator retry), main entrypoint env validation, INVESTO_TARGET_DATE override |
| **u6 infra/CI** | (extension to test_main.py) | **+15** (in u5 count) | INVESTO_TARGET_DATE override side-quest tests |
| **Integration** | 4 (`test_briefing_pipeline_poc.py` / `test_publisher_smoke.py` / `test_notifier_smoke.py` / `test_pipeline.py`) | **15** (subset of above) | Cross-unit smoke; u5's `test_pipeline.py` wires all 4 mock patterns simultaneously |
| **Total** | 35+ files | **720** | |

---

## Test categories

### Property-based tests (Hypothesis)

PBT exercises pure functions + serialization round-trips per NFR-006. Locations:

- `tests/unit/models/test_roundtrip.py` — every model survives `model_dump → model_validate` (including `FailureContext`, `PipelineResult`, `Briefing`, `BriefingNotification`).
- `tests/unit/sources/test_window_pbt.py` — `FetchWindow.contains` + `from_kst_date` invariants.
- `tests/unit/sources/test_retry.py` — backoff schedule monotonicity.
- `tests/unit/briefing/test_disclaimer.py` — `append_disclaimer` is idempotent + leaves disclaimer at last.
- `tests/unit/briefing/test_pipeline_*.py` — `parse_six_sections` round-trip.
- `tests/unit/orchestrator/test_date_resolution.py` — 2 PBTs (default-flag post-condition + flag-False post-condition), 100 examples each.

### AST-grep deny tests (NFR enforcement)

Static checks on source files that grep would miss:

- `scripts/check_no_anthropic_sdk.py` — repo-wide ban on `anthropic` SDK + `subprocess shell=True` + string-form subprocess (NFR-002 / NFR-007 / U2 AC-2.2 / AC-2.3 / AC-7.1 / AC-7.6). Exercised by `tests/unit/briefing/test_no_anthropic_sdk.py`.
- `tests/unit/briefing/test_pipeline_no_prompt_strings.py` — prompts are constants in `prompts.py`, not embedded in `pipeline.py`.
- `tests/unit/orchestrator/test_run_pipeline.py` — 3 AST-grep deny tests:
  - AC-001-3: no `asyncio.wait_for(_stage_*)` (Q1=A — trust unit timeouts).
  - AC-001-5: no stage-level `asyncio.gather` (Q5 — sequential stages).
  - AC-003-11: no orchestrator-level retry loops wrapping `await _stage_*` (Q4=A — trust unit retries).

### Record/replay LLM fixtures (NFR-002 / NFR-006)

- `tests/_helpers/fake_claude_runner.py` — implements the `ClaudeRunner` Protocol; replays recorded JSON fixtures keyed by `sha256(prompt)[:16]`.
- `tests/fixtures/llm/` — recorded fixtures (committed to git so CI doesn't need `claude` binary).
- Live recording mode via `INVESTO_LIVE_LLM=1` env var (requires `claude` CLI access; for fixture refresh only, not CI).

### Mocked HTTP (NFR-006)

- `httpx.MockTransport` for u1 source adapters + u4 notifier dispatch.
- u3's `GitRunner` Protocol with fake implementations for git lifecycle.

---

## Test coverage

Coverage is not measured automatically (pytest-cov not in dev deps). Manual sampling shows ~95% line coverage for the orchestrator + notifier paths; PBT explores ~10× the example space of unit tests.

The project's quality gate prioritizes **AC pinning** (each NFR acceptance criterion has at least one test asserting it) over coverage percentage. Per-unit summary docs (`aidlc-docs/construction/{unit}/code/summary.md`) trace every AC to its pinning test.

---

## Fix failing tests

If `uv run pytest` reports failures:

1. **Identify the failing test**: `pytest -v` shows file + test name.
2. **Reproduce in isolation**: `uv run pytest path/to/test_file.py::test_name -v`.
3. **Inspect the assertion**: per-test docstrings explain which AC the test pins (e.g., `# Pins AC-007-2 chat-ID disjointness`).
4. **Fix or update**: if the test's AC is wrong, update the AC in the relevant `nfr-requirements.md` and update the test in lockstep. If the code is wrong, fix the code. Tests are the contract.
5. **Re-run quality gate**: `uv run ruff check . && uv run mypy --strict src/ && uv run pytest`.

Test failures block the merge — no `--no-verify` shortcuts (per CONTRIBUTING.md).

---

## Tests NOT covered by automated suite (operational verification only)

These verify only in production (the runbook in `CONTRIBUTING.md` walks through them):

- **First production cron fire**: end-to-end live `claude` CLI subprocess + real httpx + real git push + real Telegram delivery. Verifiable only by triggering the workflow.
- **GitHub Pages first deploy**: `pages.yml` workflow. Verifiable only after the first push to `main`.
- **Operator's manual Q3=A holiday-recovery flow**: documented in CONTRIBUTING.md; exercises `workflow_dispatch + target_date` input.
