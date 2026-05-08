# Cross-Check: u31 operations-resilience

**Scope**: u31 operations-resilience (Steps 1–5)
**Date**: 2026-05-09
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 8 | 100% |
| ⚠️ Partial | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ❌ Gap | 0 | 0% |
| **Total** | **8** | **100%** |

**Overall Compliance**: 100% (all eight DoD items closed).

---

## Plan / Goal

- **Plan**: `aidlc-docs/construction/plans/u31-operations-resilience-code-generation-plan.md`
- **Goal**: Strengthen the 1-person operator's 5-minute triage surface and reduce noise via retry / dedup / dry-run primitives. Persona evaluation 2026-05-07 (#5, P1 + wish-list).

---

## Definition-of-Done Mapping

| DoD Item | Status | Evidence |
|----------|--------|----------|
| GHA Step Summary `source_outcomes` table | ✅ | `__main__._write_github_step_summary` consumes `PipelineResult.source_outcomes`; renders sorted (failed → zero → ok) Markdown table with redacted reason column. `models/results.py::PipelineResult.source_outcomes`. |
| Telegram retry with backoff + `Retry-After` | ✅ | `notifier/_telegram.send_message` retries up to 3 attempts; honours HTTP `Retry-After` and JSON `parameters.retry_after`; cap 30s; 4xx-non-429 + `ok: false` no-retry. Tests `test_send_message_retries_on_429_and_honors_retry_after_header`, `…_json_body`, `…_5xx`, `…_does_not_retry_on_non_transient_4xx`, `…_retry_after_is_capped`. |
| Boot-alert 14-day dedup | ✅ | `orchestrator/boot_alert_dedup.py` JSON ledger; sha256 fingerprint over (type, message[:1024]); auto-prune on read; 8 unit tests. `__main__._attempt_boot_alert` consults `should_alert` before construction and `record_alert` after delivery. |
| `INVESTO_DRY_RUN=1` skip git push + Telegram | ✅ | `BriefingPublisher(dry_run=)` and `OperatorAlerter(dry_run=)` short-circuit `send/alert` to `SendResult(ok=True)` without I/O. `commit_and_push(dry_run=)` returns immediately, leaving the working tree dirty. Orchestrator `_is_dry_run()` reads env per stage. `__main__` reads env once at boot and threads to both dispatchers. Test `test_briefing_publisher_dry_run_returns_ok_without_dispatch`. |
| Per-source health time series → `archive/_meta/coverage.jsonl` | ✅ | `orchestrator/source_health.append_daily_coverage(target_date, source_outcomes)` writes one JSON line per run. Path overridable via `INVESTO_COVERAGE_LOG_PATH`. The orchestrator hook in `run_pipeline` writes after the notify stage. 8 unit tests. |
| Sunday weekly digest → operator chat | ✅ | `orchestrator/weekly_ops_digest.build_weekly_digest_text(today)`. Korean Markdown block: observed runs / failures / success rate / top-5 failed sources / optional GHA-minute estimate. `INVESTO_WEEKLY_OPS_DIGEST=1` opt-in arm wired on the existing Saturday 09:00 KST cron. `__main__` dispatches via `_telegram_send` directly. 5 unit tests. |
| N-day FAILED auto-detect | ✅ | `orchestrator/source_health.detect_consecutive_failed(today, threshold=3)` walks the trailing N days and returns the alphabetical tuple of sources `failed` on every one. Orchestrator emits a `_safe_alert(stage="orchestrator", ...)` listing the affected sources. Coverage hook is wrapped in best-effort try/except so observability failures never change the pipeline's exit code. |
| Per-run retry budget cap | ✅ | `_internal/retry_budget.py` process-singleton counter (default 30; `INVESTO_RETRY_BUDGET` override). Telegram retry loop consults `allow_retry()` before each backoff. 8 unit tests + 1 telegram-side gate test (`test_send_message_respects_global_retry_budget`). |

---

## Scope Mapping

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-007 operator alerts | ✅ | Boot-alert dedup; soft "N-day FAILED" alert; weekly digest | All operator-chat additions respect the public/operator chat-id disjointness invariant — the new digest dispatch uses the operator chat id directly. |
| NFR-002 cost / no paid APIs | ✅ | All u31 surfaces are local I/O + the existing free Telegram Bot API | No new external endpoints. The retry budget actively reduces unnecessary GHA minute consumption. |
| NFR-003 graceful degradation | ✅ | Best-effort try/except around the source_health hook; corrupt ledger does not block alerts; dry-run is reversible by env-var unset; budget exhaustion fails through the existing failure branch | Operator misconfiguration of the new env vars fails safe to defaults (logged warning, no alert silence). |
| NFR-004 compliance / disclaimer boundary | ✅ | Publisher `verify_disclaimer` unchanged; the digest is operator-only and bypasses neither the disclaimer gate nor the chat-id disjointness invariant | The digest text is plain-text (parse_mode=None) so Telegram cannot mis-render the operator surface as the public format. |
| NFR-005 consistency / DRY | ✅ | Single retry-budget chokepoint shared across surfaces; single boot-alert ledger; single coverage log; module-boundary respected (retry_budget under `_internal/`) | The notifier imports `_internal/retry_budget`, not orchestrator — keeps the notifier↔orchestrator boundary intact. |
| NFR-006 testing | ✅ | +36 targeted tests (1383 → 1419) | 8 retry budget + 8 boot-alert dedup + 8 source health + 5 weekly digest + 6 telegram retry + 1 dry-run = 36 net adds (excluding the autouse-fixture refactors). |
| NFR-007 secret hygiene (R13) | ✅ | New env vars (`INVESTO_DRY_RUN`, `INVESTO_OPERATOR_STATE_DIR`, `INVESTO_COVERAGE_LOG_PATH`, `INVESTO_WEEKLY_OPS_DIGEST`, `INVESTO_RETRY_BUDGET`) carry no secret values; all five accept safe non-secret strings | The boot-alert ledger fingerprint hashes the error message to a sha256 prefix — secret-shaped substrings in the message can no longer be reconstructed from the ledger. |

---

## Architectural / Module-Boundary Notes

- `_internal/retry_budget.py` lives outside `orchestrator/` so the `notifier` can consume it without violating the boundary rule (only `orchestrator` may import sources/briefing/publisher/notifier).
- `weekly_ops_digest.py` and `source_health.py` are orchestrator-only consumers and therefore live under `orchestrator/`.
- The Saturday workflow arm was extended with two env-var lines; no separate cron entry was added. Operators wanting a different day for the digest can flip the env on a different cron firing without code change.

## Quality Gate

- `uv run ruff check .` — ✅
- `uv run ruff format --check .` — ✅ (211 files)
- `uv run mypy --strict src/` — ✅ (83 source files)
- `uv run pytest -q` — ✅ (1419 passed)
- `uv run mkdocs build --strict` — ✅

## TECH-DEBT Delta

No new TECH-DEBT items. No DEBT-* resolved.

## Status

u31 operations-resilience construction and cross-check **complete**.
