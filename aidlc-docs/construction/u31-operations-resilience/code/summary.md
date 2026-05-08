# u31 Operations Resilience — Code Generation Summary

**Date**: 2026-05-09
**Unit**: u31 operations-resilience
**Status**: ✅ Complete (5/5 steps; 8/8 DoD)

---

## Goal

Strengthen the 1-person operator's 5-minute triage surface and reduce noise via retry/dedup/dry-run primitives. Persona evaluation 2026-05-07 (#5, P1 + wish-list).

## Steps

### Step 1 — GHA Step Summary source table + Telegram backoff
- `PipelineResult.source_outcomes: tuple[SourceOutcome, ...]` carries per-adapter outcomes through the result. The orchestrator threads `source_outcomes` into every `_build_result(...)` call (collect-empty, generate-fail, publish-fail, normal exit).
- `__main__._write_github_step_summary` renders a sorted source table (failed → zero → ok) when outcomes are present. Failure reasons are routed through the existing diagnostic redactor.
- `notifier/_telegram.send_message` now retries up to 3 attempts with 1s → 2s exponential backoff. HTTP 429 with the `Retry-After` header **or** the JSON body `parameters.retry_after` field is honoured (capped at 30s). 5xx and timeout/connection errors retry on the same exponential schedule. 4xx-other-than-429 and `ok: false` API responses do not retry.
- `sleep` is injectable so tests drive the loop without wall-clock waits.

### Step 2 — Boot-alert dedup + dry-run mode
- New module `orchestrator/boot_alert_dedup.py`. `should_alert` / `record_alert` consult a JSON ledger persisted at `archive/_meta/operator_state/boot_alerts.json` (path overridable via `INVESTO_OPERATOR_STATE_DIR`). Fingerprint = `error_type:sha256(message[:1024])`. Dedup window 14 days; out-of-window entries are pruned on every read. Corrupt ledger does not block alerting.
- `__main__._attempt_boot_alert` consults `should_alert` before constructing the alert text and calls `record_alert` only on successful delivery. Suppressed alerts log at INFO.
- `BriefingPublisher(dry_run=)` and `OperatorAlerter(dry_run=)` short-circuit `send/alert` to `SendResult(ok=True)` without I/O. `commit_and_push(dry_run=)` returns immediately, leaving the working tree dirty so the operator can inspect what *would* have been committed. `__main__` reads `INVESTO_DRY_RUN` once at boot and wires it into both Telegram dispatchers; orchestrator's `_is_dry_run()` reads the same env per publish-stage entry.

### Step 3 — Source health time series + auto-detect
- New module `orchestrator/source_health.py`. `append_daily_coverage(target_date, source_outcomes)` writes one JSON line per day to `archive/_meta/coverage.jsonl` (path overridable via `INVESTO_COVERAGE_LOG_PATH`). Each line lists `{source_name, category, status, item_count}` for every adapter.
- `detect_consecutive_failed(today, threshold)` walks the trailing `threshold` days; returns the alphabetical tuple of sources that were `failed` on every one of those days (intersection semantics — gaps and ok/zero days reset the counter).
- The orchestrator wires both at the very end of `run_pipeline`: appends the day's line, detects N-consecutive-failed sources, and emits a soft `_safe_alert(stage="orchestrator", ...)` listing the affected adapters. The block is wrapped in a best-effort try/except — coverage-log failures never change the pipeline's exit code.

### Step 4 — Weekly operator digest
- New module `orchestrator/weekly_ops_digest.py`. `build_weekly_digest_text(today)` reads the trailing 7 days of `coverage.jsonl` and renders a Korean Markdown block: observed runs, runs-with-failures, success rate (one decimal), top-5 failed sources by cumulative failure count, optional GHA-minute estimate.
- `INVESTO_WEEKLY_OPS_DIGEST=1` env opts in. `__main__` consumes the digest after `run_pipeline` returns and dispatches via `notifier/_telegram.send_message` directly to the operator chat (parse_mode=None). Dry-run skips the network dispatch.
- Workflow YAML: same Saturday 09:00 KST cron arm that already opts into the public `INVESTO_PUBLISH_WEEKLY` retrospective now also sets `INVESTO_WEEKLY_OPS_DIGEST=1`. The workflow also pins `INVESTO_OPERATOR_STATE_DIR=archive/_meta/operator_state` so future GHA caching can target the same path.

### Step 5 — Retry budget + verification
- New module `_internal/retry_budget.py`. Process-singleton counter; `allow_retry()` charges one slot and returns False when exhausted. Default budget 30; env override via `INVESTO_RETRY_BUDGET` (negative or non-numeric values fall back to default with a warning log). Lives under `_internal/` so multiple consumers (notifier, future briefing/publisher retries) can share without crossing the orchestrator-only-imports module boundary.
- The Telegram retry loop now consults `retry_budget.allow_retry()` before each backoff sleep. When the budget is exhausted, the loop breaks immediately and returns the last failure unchanged.

## New / Modified Files

### New source
- `src/investo/_internal/retry_budget.py`
- `src/investo/orchestrator/boot_alert_dedup.py`
- `src/investo/orchestrator/source_health.py`
- `src/investo/orchestrator/weekly_ops_digest.py`

### New tests
- `tests/unit/_internal/test_retry_budget.py` (8)
- `tests/unit/orchestrator/test_boot_alert_dedup.py` (8)
- `tests/unit/orchestrator/test_source_health.py` (8)
- `tests/unit/orchestrator/test_weekly_ops_digest.py` (5)

### Modified source
- `src/investo/__main__.py` — dry-run env read at boot, dedup-aware boot alert, weekly digest dispatch.
- `src/investo/models/results.py` — `PipelineResult.source_outcomes`.
- `src/investo/notifier/_telegram.py` — retry loop with backoff + `Retry-After` honor + retry budget gate.
- `src/investo/notifier/briefing_publisher.py` — `dry_run` kwarg.
- `src/investo/notifier/operator_alerter.py` — `dry_run` kwarg.
- `src/investo/orchestrator/pipeline.py` — `_is_dry_run`, `_DRY_RUN_ENV`, source_health hook, source_outcomes threading on every `_build_result`.
- `src/investo/publisher/git_ops.py` — `commit_and_push(dry_run=)` short-circuit.

### Modified tests
- `tests/unit/notifier/test_telegram.py` — 6 retry tests (Retry-After header, JSON body, 5xx, non-transient 4xx, cap, budget gate).
- `tests/unit/notifier/test_briefing_publisher.py` — dry-run test.
- `tests/unit/orchestrator/test_main.py` — autouse fixture isolates the boot-alert ledger.
- `tests/unit/orchestrator/conftest.py` — autouse fixture isolates operator-state dir + coverage path.
- `tests/unit/orchestrator/test_stage_publish.py` — spy now accepts `dry_run` kwarg.

### Modified workflow
- `.github/workflows/daily-briefing.yml` — Saturday cron arm now also opts into `INVESTO_WEEKLY_OPS_DIGEST=1` and pins `INVESTO_OPERATOR_STATE_DIR`.

## Test Delta

- 1383 → 1419 (+36 tests).

## Quality Gate

- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ (211 files)
- `uv run mypy --strict src/` ✅ (83 source files)
- `uv run pytest -q` ✅ (1419 passed)
- `uv run mkdocs build --strict` ✅

## TECH-DEBT

No new TECH-DEBT items raised by u31. The five new env vars (`INVESTO_DRY_RUN`, `INVESTO_OPERATOR_STATE_DIR`, `INVESTO_COVERAGE_LOG_PATH`, `INVESTO_WEEKLY_OPS_DIGEST`, `INVESTO_RETRY_BUDGET`) all follow the project's `INVESTO_<SCOPE>_<NOUN>` convention and carry safe defaults.

## Source

Persona evaluation 2026-05-07: persona #5 (P1 + wish-list).
