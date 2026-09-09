# u155 implementation summary

**Date**: 2026-09-09 KST
**Status**: Local implementation complete; full pytest 5,026 passed in 326.68s.
**Scope**: Approved local Code Generation Steps 1–7; private provisioning and
activation are Steps 8/9. No production-complete claim.
**Branch**: `codex/codex-provider-20260909`
**Implementation base**: `f93def427be2d16365685102c7e9dcf1cad073e1`

## Result

`INVESTO_LLM_PROVIDER` defaults to Claude; `codex` requires an explicit
`INVESTO_CODEX_MODEL` and the managed private supervisor. The existing
ClaudeRunner compatibility seam carries both classification and synthesis
through the same parsers, assembly and public finalization pipeline.
There is no provider fallback, direct SDK/API call or change to source adapters.

- `_internal/llm_config.py` owns immutable provider-aware bootstrap/preflight.
  Dry-run needs no Telegram credentials and boot failure cannot send an alert.
- `briefing/codex_cli.py` and `codex_policy.py` pin native Codex 0.153.4,
  isolate HOME/cwd/config/environment, disable tool registration through fixed
  model metadata and feature configuration, serialize calls, enforce deadlines,
  bound event/final output, reject tool events and old/new auth leaves.
- `_internal/cli_process.py` drains bounded pipes and terminates process groups.
  Private Claude uses the same lifecycle boundary with its own isolated OAuth
  environment. The public default Claude path remains compatible.
- `_internal/codex_auth.py` validates ChatGPT-only JSON, rejects duplicate keys,
  missing/API credentials, oversized or symlink files; restricted atomic restore
  never reads a personal login.
- `orchestrator/codex_runtime.py` owns restore, invocation, pre-publication
  checkpoint, failure/cancellation preservation and cleanup. A failed cleanup
  poisons further calls; a failed checkpoint cannot later permit publication.
- `orchestrator/codex_secrets.py` encrypts rotated auth to the fixed private
  Environment Secret. Metadata rejects repository-secret fallback, HTTP is
  bounded with no redirects and fixed error messages.
- `ops/private-runtime/daily-briefing.yml` is an inactive, manual dry-run
  template. Reviewed code is installed non-editably; latest public data has a
  separate checkout. No public publisher/Telegram credentials, cron, Pages
  dispatch, auth cache or artifact upload is configured.

New logging is numeric timing and validated run/code/date identifiers only.
Existing pipeline summaries retain generation/finalization/publication/notification
status; the private auth receipt is separate. A failure after rotation can be
`auth=persisted` while generation/runtime still fails. Lock waits are reported
separately and charged only once through the existing wrapper elapsed time.

## Validation

Final results are recorded in
`docs/sessions/2026-09-09-u155-implementation.md` and
`docs/cross-checks/2026-09-09-u155-codex-chatgpt-briefing-provider.md`.
Coverage includes pure-config/auth PBT; child isolation and synthetic token
redaction; timeout/cancellation/EOF/process cleanup; serialization and budget;
encrypted write-back round-trip/denial; finally after rotated-auth failure;
checkpoint-before-publish; no-send preflight; eight provider/market two-stage
subprocess integrations and two local Git publication cases.

A separate `uv sync --frozen --no-dev --extra operations --no-editable`
installation in `/private/tmp` imported the installed implementation under
`python -I` from a different public-data cwd. Malicious same-name module and
sitecustomize fixtures in that cwd were not loaded; the current archive was read.
This is package isolation evidence, not a live Linux Actions execution.

## CLI evidence and limits

Official rust-v0.153.4 source at
`042fb41b7c813ac7999105e886b2b7aa715b5081` supplies the config/model schema,
static model-manager behavior and tool registration rules. An actual macOS
native `debug models` invocation parsed the custom model catalog without
creating auth. The official Linux release digest is pinned in the template.
The npm registry lookup for that version returned 404, so installation uses
the native release. The full request tool inventory has not been established:
a synthetic HTTP mock probe failed to intercept the model websocket route.
It used only invalid synthetic credentials, with no successful model generation;
it is not qualification evidence. Linux effective-tool validation remains a
Step 8 gate before real credentials are used.

## Operational handoff

Account Environment support, private repo creation, dedicated login registration,
actual model access, refresh into the next serialized job, runtime/usage and
schedule cutover remain unperformed. The runbook gives the concrete proposed
repository, Environment, secret names, permissions, pinned setup and rollback.
Public Git credentials/Pages wiring belong to the later activation change.
No credentials were registered and no public workflow was changed or run.

During local work origin/main advanced to
`a63f863f44fb62ce81993bcda7ed7d351737273e` (u151 plus the next archive run).
There is no overlapping application-code change, but shared AIDLC documents
need integration against that newer state before a merge. The implementation was validated
on its recorded base; root dirty work is preserved. After local completion,
the user authorized committing and pushing this feature branch. Main
integration and private operational activation remain separate.
