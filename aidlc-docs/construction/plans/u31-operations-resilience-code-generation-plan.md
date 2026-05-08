# Code Generation Plan: `u31 operations-resilience`

**Date**: 2026-05-08
**Unit**: u31 operations-resilience
**Stage**: Code Generation

---

## Goal

Strengthen the 1-person operator's 5-minute triage surface and reduce noise via retry/dedup/dry-run primitives.

---

## Definition of Done

- [x] GHA Step Summary includes a `source_outcomes` table so a failed adapter is visible at a glance. — `__main__._write_github_step_summary` renders a sorted table (failed → zero → ok) consuming `PipelineResult.source_outcomes`.
- [x] Telegram retry path applies 1-2s backoff and honors the `Retry-After` header. — `notifier/_telegram.send_message` retries up to 3 attempts with 1s → 2s exponential backoff; honors HTTP `Retry-After` and `parameters.retry_after` JSON, capped at 30s.
- [x] Boot-alert dedup suppresses identical `ConfigError` notifications within a 14-day window. — `orchestrator/boot_alert_dedup.py` persists `(error_type, sha256(message))` fingerprints under `archive/_meta/operator_state/boot_alerts.json`.
- [x] `INVESTO_DRY_RUN=1` mode skips git push and Telegram send while still writing local archive files. — `publisher/git_ops.commit_and_push(dry_run=)`, `BriefingPublisher(dry_run=)`, `OperatorAlerter(dry_run=)`; orchestrator threads `_is_dry_run()` per stage.
- [x] Per-source health time series appended to `archive/_meta/coverage.jsonl` (one line per day, append-only). — `orchestrator/source_health.append_daily_coverage`.
- [x] Sunday weekly digest cron sends an operator-chat summary covering 7-day success rate, failed sources, and GHA minutes used. — `orchestrator/weekly_ops_digest.build_weekly_digest_text` + `INVESTO_WEEKLY_OPS_DIGEST=1` opt-in arm on the existing Saturday cron.
- [x] N-consecutive-day FAILED source is auto-detected and surfaced to the operator chat. — `orchestrator/source_health.detect_consecutive_failed` (default threshold = 3 days); the orchestrator emits a soft alert via `_safe_alert("orchestrator", ...)` after each successful pipeline run.
- [x] Retry budget caps total retries per cron run. — `_internal/retry_budget.py` (default 30, env-overridable via `INVESTO_RETRY_BUDGET`); the Telegram retry loop respects the global counter.

---

## Steps

### Step 1 — Step Summary Source Table and Telegram Backoff

- [x] Extend GHA Step Summary writer with the `source_outcomes` table.
- [x] Add 1-2s backoff + `Retry-After` handling to the Telegram client.

### Step 2 — Boot-Alert Dedup and Dry-Run

- [x] Persist boot-alert fingerprints with a 14-day TTL.
- [x] Wire `INVESTO_DRY_RUN=1` through publisher / notifier.

### Step 3 — Source Health Time Series and Auto-Detect

- [x] Append daily coverage line to `archive/_meta/coverage.jsonl`.
- [x] Detect N-day-consecutive FAILED source and emit operator alert.

### Step 4 — Weekly Digest Cron

- [x] Add Sunday cron + digest renderer to operator chat. — opted in on the existing Saturday 09:00 KST cron via `INVESTO_WEEKLY_OPS_DIGEST=1`; operators wanting a different day can flip the env on a different cron entry without code change.

### Step 5 — Retry Budget and Verification

- [x] Enforce a per-run retry budget across HTTP retry sites.
- [x] Run targeted ops tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #5 (P1 + wish-list).
