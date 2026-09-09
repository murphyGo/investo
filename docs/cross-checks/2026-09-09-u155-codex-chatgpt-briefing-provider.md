# u155 requirements cross-check

**Date**: 2026-09-09 KST
**Scope**: local Steps 1–7, optional CLI provider and private auth runtime.
**Decision**: local implementation review PASS; production acceptance deferred
to the already planned Steps 8/9. This does not mark the whole unit activated.

FR-002/003/004/005/006/007, NFR-001–007 and
US-002/003/004/005/006/007/009 are evaluated only for this extension.
Existing finalizer/publisher/notifier ownership and SDK/paid-API guards remain.

## Acceptance matrix

| AC | Status | Evidence / remaining condition |
|---|---|---|
| 155.1 | Complete locally | Closed immutable config, shared preflight, existing Claude/default regression tests |
| 155.2 | Complete locally | Eight real synthetic CLI integrations: Claude/Codex × unsegmented/domestic/us/crypto, each exactly two calls through existing parser/assembly |
| 155.3 | Complete locally | Managed-auth schema, API-key rejection, clean environment/config, explicit model and official provider; no fallback |
| 155.4 | Complete locally | Atomic secure restore, encrypted round-trip, rotated auth preserved after failure/cancel/timeout, invalid current file cannot overwrite seed |
| 155.5 | Partial: operational | Workflow/job and runner serialization tested; Environment metadata rejects repo fallback. Actual queued next-job refreshed auth requires Step 8 |
| 155.6 | Complete locally | Checkpoint failure before real pipeline publish-stage sentinel; failed checkpoint remains failed after later preservation; manual workflow has no send credentials |
| 155.7 | Partial: operational | Synthetic old/new token rejection, minimal env, empty cwd, bounded private events, fixed local catalog and denied tool events. Full Linux request tool inventory must be qualified before real credentials |
| 155.8 | Complete locally | Global/call deadlines, charged lock/backoff, bounded pipes and EOF, process-group cleanup, poisoned failed cleanup, explicit 120s cleanup reserve; runtime duration qualification remains Step 8 |
| 155.9 | Complete locally | Shared parsers/disclaimer and finalization path; full legacy trust/numeric/link/seal/sibling regression gate; both providers use existing assembly |
| 155.10 | Partial: operational | Reviewed non-editable install under Python -I verified against malicious cwd modules; separate archive read and two-repo local Git lineage/allowed paths/rejected push/duplicate date proven. Live fixed-public-repo credentials are Step 9 |
| 155.11 | Partial: operational | Manual-only dry-run, boot no-send, no publisher/Telegram credentials/cron/Pages; local dry-run and duplicate-date Git behavior verified. One schedule owner/real notification rollback is Step 9 |
| 155.12 | Deferred: operational | Account plan, dedicated login/model, Linux behavior, refresh-next-job and usage/time measurements are Step 8; activation closeout is Step 9 |

Seven criteria have complete local evidence; four include outstanding live
acceptance and one is entirely operational. These are explicit planned gates,
not hidden implementation debt or claims of production readiness.

## NFR traceability

| NFR | Implementation and verification |
|---|---|
| N155-01 | llm_config, main/preflight and existing Claude regression tests |
| N155-02 | Frozen config, segment concurrency=1, runner lock and concurrent synthetic process test |
| N155-03 | Existing RetryBudget, Codex backoff accounting, wrapper elapsed includes lock/call/cleanup; numeric-only separate timing |
| N155-04 | Codex absolute 210m cutoff, work timeout 225m−120s, process reaping before preservation; private Claude deadline/cancel test |
| N155-05 | ChatGPT-only validation, official provider/file store, explicit model, isolated HOME/config; actual model access pending |
| N155-06 | Pinned source/model metadata and no-tool event tests; full effective Linux tool surface pending before live credential use |
| N155-07 | Constructed child environment, separate private paths; writer/publisher/Telegram/source secrets excluded; final text only |
| N155-08 | Secure-auth tests: regular non-symlink file, owner/mode, size, duplicate/missing/API auth, atomic replace |
| N155-09 | AuthLifecycle: close before read/persist; valid changes survive failure, no stale overwrite; same Environment slot |
| N155-10 | Fixed GitHub target, sealed-box round-trip, HTTP deadline/retry/denial/redirect tests |
| N155-11 | Real pipeline publication sentinel blocked by checkpoint; failed latch and unconditional failure receipt |
| N155-12 | Existing finalizer/seals plus two-provider assembly and isolated local Git publication tests |
| N155-13 | Existing pipeline stage/segment/publication summary plus auth receipt, validated run/code/date identifiers and auth/call timing. Live Pages outcome is deferred with activation |
| N155-14 | Manual template, fixed concurrency, no active cron; cutover/rollback checklist in runbook |
| N155-15 | Explicit Step 8 prerequisites in runbook/state; no account upgrade/API fallback performed |
| N155-16 | 4MiB bounded pipe/final-output capture, overflow stops CLI and suppresses payload |

## Review and checks

- Independent fresh-eyes reviewer passed the final implementation and added
  telemetry. All reported high/medium issues were fixed; no new debt deferred.
- Full/focused pytest, Ruff/format, mypy, lock, SDK/paid guards and diff evidence
  is recorded in `docs/sessions/2026-09-09-u155-implementation.md`.
- Official actionlint 1.7.12 workflow schema/context validation passes after
  moving the runner-temp environment setting to the first step.
  Workflow parsing, shell/Python syntax extraction and contract tests pass;
  no actual GitHub Actions run is claimed.
- Package install/provenance rehearsal passed in an independent temporary venv.
- No rendered site changes were made, so a strict MkDocs build is not applicable.

## Operational actions already tracked

1. Confirm private Environment eligibility and provision the proposed private
   repository/Environment using the reviewed final code SHA.
2. Qualify Linux effective tools without real credentials, then register a
   dedicated ChatGPT login via the documented local file-to-secret flow.
3. Run serialized manual dry-runs, observe genuine refresh into the next job,
   verify no public effects and measure runtime/usage.
4. Prepare/review the concrete public publisher credential/Pages/schedule
   activation change, stop the old owner, then verify every publication outcome.

No new unit or TECH-DEBT entry is required: these actions are already Steps 8/9.
Root dirty work and unrelated units remain outside this implementation scope.

## Latest-main integration evidence

The combined `fc373277` + `27a6c42c` tree passed 5,305 tests in 344.97s,
Ruff/format594, mypy263, lock/policy/assets and strict MkDocs/Material checks.
The source/test/template/dependency slice is byte-identical to the reviewed
feature; current u151/u153 state and archive outputs are preserved. This adds
integration evidence without changing any of the Step 8/9 acceptance statuses.
Record: `docs/sessions/2026-09-09-u155-main-integration.md`.
