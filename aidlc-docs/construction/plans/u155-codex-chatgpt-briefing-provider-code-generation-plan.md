# Code Generation Plan — u155 codex-chatgpt-briefing-provider

**Date**: 2026-09-09 KST
**Status**: FD/NFR/Infrastructure approved — user “구현까지 진행시켜”,
2026-09-09. Local Code Generation Steps 1–7 complete; Steps 8/9 pending.
**Source**: 2026-09-09 user request; accepted Claude + Codex / ChatGPT login /
Actions Secrets / private automation direction.
**Baseline**: `f93def427be2d16365685102c7e9dcf1cad073e1`

## Stage Decision

- Functional Design: REQUIRED / APPROVED — user “진행시켜”, 2026-09-09;
  provider selection, session lifecycle and publication eligibility.
- NFR Requirements: REQUIRED / APPROVED — N155-01–16 cover
  rotating credentials, isolation, cost, serialization and bounded failure.
- NFR Design: SKIPPED as a separate stage — focused NFR contracts will map
  directly to runtime and infrastructure decisions; not a security waiver.
- Infrastructure Design: REQUIRED / APPROVED — two repositories,
  one proposed Environment-bound job, scoped tokens, reviewed code/latest
  data checkouts and schedule ownership.
- Code Generation / Build and Test: REQUIRED after the design stages.
- Requirements: FR-002/003/004/005/006/007; NFR-001/002/003/004/005/006/007;
  US-002/003/004/005/006/007/009. Scope is this unit's contribution only.

The user's new request explicitly expands the earlier Claude-only constraint.
Direct Anthropic SDK and additional paid LLM API calls remain outside scope.
Do not ask again whether Codex itself is allowed.

## Fixed contracts

R1–R14 in the Functional Design are the approved binding implementation
contracts. Claude remains the default, provider selection is immutable per run,
Codex auth is ChatGPT-only, and there is no automatic cross-provider fallback.
The existing parser/finalizer/publisher pipeline remains the only public path.
Partial-generation and authentication-persistence failures are separate outcomes.

## Implementation steps

- [x] Step 1 — Introduce neutral provider configuration and common CLI
  dispatch behind the existing Claude compatibility seam. Update
  `briefing/claude_code.py`, new `briefing/llm.py` / `codex_cli.py`,
  `_core/orchestration.py`, `generation_contract.py` and thin pipeline
  exports/callers as required. No new provider routing in data adapters.
- [x] Step 2 — Implement one provider-aware bootstrap/preflight policy shared
  by `__main__.py` and `scripts/check_daily_briefing_env.py`.
  Codex requires an explicit model and valid managed login; Claude mode
  requires only existing Claude credentials. Reject API-auth fallback.
  Dry-run must work without public publisher/Telegram credentials; keep
  production-mode requirements enforced.
- [x] Step 3 — Implement Codex session isolation, single-run call locking,
  remaining-budget accounting, clean child environment and timeout process
  cleanup. Qualify exact CLI flags on a pinned version. Prove tools and
  project/user instructions cannot turn market inputs into agent actions.
  Apply N155-02–07/16 deadlines, output limits and minimal child environment.
- [x] Step 4 — Add a secret-safe operations helper for validate/restore/
  persist/cleanup of auth files and Environment Secret encryption/write-back.
  Add an optional generation-complete/pre-publication checkpoint through the
  existing orchestrator boundary, plus failure/termination cleanup. A failed
  checkpoint blocks public side effects; no post-generation rerun is needed
  merely to publish the same result. Use bounded encrypted Environment API
  write-back and process quiescence from N155-08–11.
- [x] Step 5 — Add a non-active private runtime workflow template under
  `ops/private-runtime/`, install pinned dependencies before restoring auth,
  Environment binding, private-repository/event preflight, one fixed
  concurrency group, auth write-back, public checkout identity and least-
  privilege publication. Keep Codex auth out of public workflows. Initial
  private workflow is manual dry-run only. No untrusted PR execution.
  Qualify the proposed single Environment/job refinement, provider-aware
  no-send dry-run, non-editable approved-code installation and latest
  archive cwd. Check Environment metadata to reject repo-secret fallback.
- [x] Step 6 — Test immutable provider selection, unchanged Claude path,
  Codex output parsing, generated document quality and secret/failure cases.
  Add local two-repository Git integration coverage for reviewed-code/latest-
  archive separation, explicit staged-file publication and push failures.
- [x] Step 7 — Run scoped/full quality checks, independent fresh-eyes review
  and requirements cross-check; update requirements/story/architecture docs,
  runbook, session log and any applicable debt. Update the Claude-only wording
  in `CLAUDE.md`, `scripts/check_no_anthropic_sdk.py` diagnostics,
  u2 references and active review guidance to reflect the authorized CLI
  expansion without weakening SDK/shell guards. Recheck final diff/remote base.
- [ ] Step 8 — Operational provisioning and dry-run qualification, separately
  recorded: create/configure private runtime repository, register automation-
  only login through a local file-to-secret path, validate next-job refreshed
  auth, prove no public writes and measure runtime/usage. Never request raw
  credential contents in chat.
- [ ] Step 9 — Controlled activation: stop old public daily owner and await
  completion, verify approved destination/model/usage constraints, enable
  private schedule, run bounded acceptance, verify generated/archive/push/
  Telegram/Pages separately and record rollback procedure.

Step 8/9 remote effects are not implied by merely completing local tests.
Prepare their exact configuration/results for operator review first.

## Acceptance criteria

| ID | Required evidence |
|---|---|
| AC-155.1 | Unset/blank/claude configuration invokes unchanged Claude; Codex binary/auth not required; unknown providers fail before generation |
| AC-155.2 | Explicit Codex/model runs both stages with original input/parser contracts, and all selected markets use the same provider |
| AC-155.3 | Codex requires managed ChatGPT auth; API key/custom provider/ambient profile cannot silently take over; no extra paid LLM calls |
| AC-155.4 | Restored/rotated valid auth survives successful and failed generation; malformed/empty/symlink/oversized files never overwrite Secret |
| AC-155.5 | Environment Secret is loaded after serialized job admission; next queued run uses the rotated version; internal CLI calls never share the session concurrently |
| AC-155.6 | Auth persistence fails before public publication: zero push/public Telegram/Pages; final workflow status cannot mask the failure |
| AC-155.7 | Synthetic old/new token leaves absent from stdout/stderr/errors/summary/artifacts/fixtures/public files; LLM child lacks unrelated credentials/tools |
| AC-155.8 | Existing budgets/retries remain bounded including lock waits and timeout descendants; fake clock/process tests verify no unbounded queue or hidden retry layer |
| AC-155.9 | Existing trust/numeric/link/disclaimer/partial-sibling/seal contracts pass for both providers; no new finalizer or model-specific bypass |
| AC-155.10 | Code uses approved SHA; publish checkout retains current archive lineage; only finalized allowed paths reach the fixed public destination |
| AC-155.11 | Initial private dry-run cannot send/push/deploy; activated schedule has one owner; rollback and duplicate-date behavior verified |
| AC-155.12 | CLI/model availability, private environment features, runtime and included usage limits measured before activation; production closeout evidence recorded separately |

## Focused NFR stage inputs

The approved assessment is recorded in
[NFR requirements](../u155-codex-chatgpt-briefing-provider/nfr-requirements/nfr-requirements.md),
[tech decisions](../u155-codex-chatgpt-briefing-provider/nfr-requirements/tech-stack-decisions.md)
and [infrastructure](../u155-codex-chatgpt-briefing-provider/infrastructure-design/infrastructure-design.md).
These artifacts were approved by “구현까지 진행시켜”; live qualification
gates remain. Step 3 local evidence is pinned upstream source, effective
macOS model catalog and synthetic event/process tests; the complete Linux
request tool surface is an explicit Step 8 pre-credential gate. Step 5 is the
approved manual qualification template; live publication credentials/Pages
wiring and ownership cutover remain Step 9.

- Preserve caller-specific GenerationPolicy ceilings. Check the current
  runtime overrides rather than claiming every production run uses defaults:
  at baseline, per-call 1,800s; US shared 3,900s; domestic/crypto shared 5,700s;
  Actions job 240 minutes. Serial Codex calls must fit the chosen operational
  budget; local default 120/300s is not a production performance measurement.
- Private Actions minute allowance and Environment support must be established
  for the account. No auto-purchase/paid API fallback and no zero-cost promise
  based only on public-repository pricing. GitHub account API returned
  `plan: null`; the private Environment Secret prerequisite remains pending.
- Restrict auth payload to a regular non-symlink file below GitHub's 48 KB
  Secret limit; use atomic restricted-permission writes and exact credential
  schema checks without printing values.
- Write-back HTTP: bounded timeouts and attempts; success only on expected
  response status. Validation errors and response bodies remain private.
- Test forced generation failure after synthetic token rotation; checkpoint
  failure; corrupt final auth; token revocation; missing secret write rights;
  queued jobs; mid-run cancellation; cleanup errors and process descendants.
- Masking is supplemental. Never stream raw CLI events. Validate synthetic
  individual token leaves, not just the full JSON string or known key prefixes.

## Test targets

Extend `tests/unit/briefing/test_claude_code.py`,
`tests/unit/orchestrator/test_main.py`,
`tests/unit/orchestrator/test_daily_briefing_env_script.py`,
`tests/unit/orchestrator/test_daily_workflow_contract_u144.py` and existing
redaction/generation/finalizer integration tests. Add focused provider,
auth-lifecycle and private-workflow modules under their existing test owners.
No real secrets in fixtures, live account calls or external sends in unit tests.

Partial PBT applies to pure config/auth-shape transforms and serialization;
external CLI/API calls use explicit recorded/synthetic outcomes.

Validation during implementation: scoped Ruff/format, `mypy src`, targeted
pytest followed by full appropriate repository gate, no-paid and no-Anthropic
SDK guards, workflow YAML/schema validation, template setup rehearsal and
`git diff --check`. Run strict docs build if rendered documentation changes.
Independent review is required after implementation by the dev-investo skill.

## Out of scope

Responses API integration, automatic paid fallback, model quality claims
without comparison, market-source changes, archive backfill, sector-radar
activation, public remote agent endpoints, automatic repository visibility
changes or modifying a personal interactive Codex login.

## Local completion evidence — 2026-09-09

Final full pytest: **5,026 passed in 326.68s**. Ruff/check+format (590 files),
mypy (263 source files), lock, SDK/paid guards, actionlint 1.7.12, workflow
contract tests and independent review passed. No new implementation debt.
Code summary, review, cross-check and session log document exact scope and
remaining effective-Linux-tool/account/next-job/usage/activation gates.
The validated branch is authorized for commit/push by the subsequent user
request “커밋·푸시해줘”; newer origin/main
`a63f863f44fb62ce81993bcda7ed7d351737273e` must be preserved at integration.
