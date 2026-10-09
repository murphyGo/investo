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
- [ ] Push reviewed main and production-backport revisions; record exact SHAs.
- [ ] Snapshot existing private workflow/variable/Environment state, set both
  production gates to 0, disable auth consumers and drain running/queued work.
- [ ] Update private workflow references and pinned code, rename the existing
  repository and update local remotes. Keep production schedules gated off.
- [ ] Enable diagnostic and AI Report only; keep both production gates at 0.
  Run diagnostic plus AI Report dry-run under the new name and verify existing
  PAT/Environment access and unchanged publisher targets.
- [ ] Only after qualification succeeds, restore the exact previous gates and
  previously active workflow states; leave formerly disabled workflows disabled.
- [ ] Update current consumer docs and record remote/run evidence and rollback.

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
