# u155 shared runtime repository rename

## Stage decision and authorization

- User requested a shared runtime name after adding AI Trend Report and then
  explicitly requested continuing the remaining rename and Crypto Master work.
- Target: `murphyGo/automation-runtime`, existing private repository ID
  `1362684951`; same `codex-runtime` Environment, credentials and auth queue.
- Functional Design / NFR Requirements: existing u155 N155-01–16 contracts
  remain applicable; no model, prompt, output, provider, billing or auth policy change.
- Infrastructure design: bounded repository rename with workflow drain and
  independent validation before restoring normal scheduling.
- Preserve production base `056dd8a1...` with a name-only backport. Preview
  currently uses `269a15dc...`; apply the same source change on current main.
  Do not advance production to the preview implementation as part of this task.

## Steps

- [x] Update the fixed Secret destination, context fixtures, workflow templates
  and current runbook. Reject the retired name; never follow auth redirects.
- [x] Test encrypted write/read metadata against the exact new URL, rejection
  of the old repository context, and existing auth lifecycle regressions.
- [x] Independently review the changed implementation and private workflows.
- [x] Push reviewed main and production-backport revisions; record exact SHAs.
- [x] Snapshot existing private workflow/variable/Environment state, set both
  production gates to 0, disable auth consumers and drain running/queued work.
- [x] Update private workflow references and pinned code, rename the existing
  repository and update local remotes. Keep production schedules gated off.
- [x] Enable diagnostic and AI Report only; keep both production gates at 0.
  Run diagnostic plus AI Report dry-run under the new name and verify existing
  PAT/Environment access and unchanged publisher targets.
- [x] Only after qualification succeeds, restore the exact previous gates and
  previously active workflow states; leave formerly disabled workflows disabled.
- [x] Update current consumer docs and record remote/run evidence and rollback.

## Verification

Targeted u155 auth/runtime and workflow-contract tests; private AI Report
regressions; scoped Ruff/format/mypy; workflow/YAML validation; exact source
diff versus both reviewed bases. No production notification replay is needed
for a repository identity change.

Rollback: disable/drain private auth consumers, rename the same repository back,
restore its prior workflows/pins, gate values and previous enabled states. Do not
re-enable public Claude owners. Preserve existing billing-verification debt.

Review: main focused 60 passed; production backport 28 passed; private AI
Report 12 passed; scoped Ruff and mypy passed. Independent review found no
code blockers after moving schedule restoration after qualification.

## Operational evidence — 2026-10-09

- Renamed the existing repository to `murphyGo/automation-runtime`; ID
  `1362684951`, private visibility, Environment ID `21564346622` and all 15
  Secret names are unchanged. Local private clone remote uses the new URL.
- Public production source-only backport: `ca0ef610cdaafea7de188551f06d2107247e8472`.
  Preview source: `9ff1bcbc5be79d9e811676c56e4e5e7069ed41de`.
  Private workflow commit: `5cedf4e0c2ebea5d2bd41e40aa3cf787e4f59dae`.
  AI Report application pin remains `53037fc20e34a685f357c74c783e5dd4a39e47e4`.
- Both production gates were 0 and four auth consumers disabled while the
  existing preview drained. Preserved concurrent preview baseline-SHA wiring.
- New-name [diagnostic 37914320588](https://github.com/murphyGo/automation-runtime/actions/runs/37914320588)
  succeeded: native turn complete, no tools/errors, auth unchanged, exit 0.
- New-name [AI Report dry-run 37914423059](https://github.com/murphyGo/automation-runtime/actions/runs/37914423059)
  succeeded: 20 articles, Codex `gpt-6-astra`, auth unchanged, exit 0; publish and
  email steps skipped. Actual encrypted PUT URL is covered by regression tests;
  these live calls did not rotate tokens and therefore did not exercise a PUT.
- Restored both production gates to 1 and all eight previously active workflows
  to active only after these checks. Public Investo and AI Report Claude
  workflows remain `disabled_manually`. Existing publisher destinations and
  billing-verification debt are unchanged.
