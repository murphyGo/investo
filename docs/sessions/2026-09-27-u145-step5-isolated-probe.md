# Session Log: 2026-09-27 — u145 Step 5 isolated production probe

## Scope and integration

The user requested `계속 진행해줘` after waiving actual viewport validation. This session
implements Step 5's manual production-adapter qualification workflow and its local gates.
The Step 4 waiver remains `WAIVED / NOT_EXECUTED`; Step 6 public activation is separate.

Work continues in `.tmp/u145-resume-20260922`, branch `codex/u145-resume-20260922`.
Fetched `origin/main` and fast-forwarded the worktree from `c286f500` to `04978d81` without
overlap conflicts. SHA-256 comparison confirmed all 45 existing u145 modified/untracked files
were preserved byte-for-byte at integration. The unrelated dirty root worktree was not changed.
Preservation manifest: `.tmp/step5-evidence/pre-integration.json`.

Live GitHub metadata confirms the existing `sector-dashboard-probe.yml` is registered and
active (workflow id `347821469`). Secret-name inventory contains `HF_DATA_API_KEY`, last
updated `2026-09-01T19:25:00Z`. No secret value was read or printed. Inventory presence is not
proof that the current key authenticates successfully.

## Step 5 changes

- Added `src/investo/sector_dashboard/public_probe.py`: production composition, strict aggregate
  evidence, complete-universe qualification, completed NYSE session resolution and resource gates.
- Added `scripts/build_sector_dashboard_public.py`: probe-only CLI, owned HTTP client, bounded
  safe output and GitHub Step Summary. No publish/store mode or runtime provider overrides.
- Added `scripts/benchmark_sector_dashboard_public.py`: synthetic maximum-shape resource gate.
- Updated `hf_data.py`: count fully accepted HTTP responses alongside attempted requests.
- Replaced the old Step 0 workflow command with locked production-adapter setup, synthetic
  benchmark, and secret-scoped live probe; read-only/manual/no-artifact boundaries remain.
- Added public-probe integration, failure, identity-screening and workflow tests; amended the
  existing private-workflow guard only for the two exact approved public entrypoint paths.
- Added `docs/sector-dashboard-probe-runbook.md` and Step 5 implementation summary.

## Review and corrections

The required independent reviewer reproduced two medium-severity correctness issues, both fixed:

1. A fixed 16:00 cutoff could qualify prior-session data after a 13:00 early close. Pinned the
   official 2026 early closes and tested before/at cutoff and stale prior-session rejection.
2. Async timeouts cannot preempt synchronous Parquet decoding. Measured collection >120 seconds
   and CPU >30 seconds now block qualification with `probe.resource` even if all inputs returned.

Projection-failure evidence now preserves actual completed symbol counts. Actual CLI integration
tests found legitimate snapshot/GitHub identities tripping generic credential heuristics. The
reviewed repair screens exact configured secrets before and after JSON decoding, exempts only
three exact typed identity fields/shapes, and preserves generic screening elsewhere. Tests cover
realistic run-id length, invalid metadata, malformed identities and JSON-escaped secret values.

The reviewer approved the final probe code, private-guard amendment and CLI screening correction
with no remaining blocking findings; independently ran 31 probe tests before the added CLI cases
and 15 CLI/security cases after the final correction.

## Validation

- Final focused public-probe suite: **46 passed**.
- Private-render plus then-current probe suite: **82 passed** after the integration-guard fix.
- Ruff check/format: passed, **609 files formatted**.
- Strict mypy: passed on **270 source files plus the CLI**.
- Locked dependencies: `uv lock --check --offline` passed (67 packages).
- No-paid API, no-Anthropic-SDK, curated asset and image-store guards: passed.
- Strict MkDocs build and both Material CSS/rendered-pair contracts: passed.
- Local synthetic resource gate: **11 x 10,000 rows**, **22 requests**, **2,304 ms CPU**,
  **2,426 ms wall**, **255,934,464 bytes peak RSS above baseline**, 326,233 bytes/response;
  passed all ceilings. This macOS result does not substitute for the Actions Ubuntu gate.
- Initial full run: 5,523 passed, one failure in the pre-existing private-workflow string guard.
  That guard was corrected narrowly and independently reviewed; this initial run is not the
  final gate because code review and CLI fixes followed it.
- Final full-suite result: **5,547 passed in 581.26 seconds** (exit 0); output
  `.tmp/step5-evidence/pytest-final.log`.
- All 29 code/configuration hashes match the manifest captured before the final test run;
  source/file manifest: `.tmp/step5-evidence/final-scope.json`. Final documentation changes
  are captured separately in `.tmp/step5-evidence/completed-scope.json`.

## Remaining operational gate

Five successful live production-adapter Actions runs are still required on the exact reviewed
commit. None has been counted yet. The historical Step 0 run `33578785358` is not Step 5 evidence.
The branch needs the reviewed Step 1–5 overlay committed and pushed before the registered
workflow can dispatch it. The `dev-investo` skill's explicit-approval commit rule is retained;
prepare all work and validation before requesting that final approval.

No live provider request, raw-data persistence, public-sector write, schedule/navigation
activation, Telegram send, deployment, commit or push has occurred in this Step 5 session.

## Commit and Actions execution approval

At 2026-09-27T03:22:44+09:00, the user replied `진행` to the explicit request to commit/push the reviewed
isolated branch and execute five sequential Actions probes. This authorizes those actions
and their operational evidence recording. Step 6 activation remains separate.
