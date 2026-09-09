# 2026-09-09 — u155 NFR and Infrastructure Design

## Authorization and workspace

The user replied “진행시켜” to the Functional Design approval and
NFR/Infrastructure handoff. Approval recorded at 2026-09-08T18:06:59Z.
Functional Design R1–R14 is approved. The new NFR/Infrastructure artifacts
are prepared for review; code implementation is not started.

Continue isolated `.tmp/codex-provider-20260909`,
branch `codex/codex-provider-20260909`,
HEAD/refreshed origin/main `f93def427be2d16365685102c7e9dcf1cad073e1`.
Preserve the original dirty root and independent worktrees.
Applied the previously announced `dev-investo` and `openai-docs` skills.

## Outcome

Created six NFR/Infrastructure plan/design files. Sixteen NFRs map to all
twelve ACs; retain nine unchecked implementation steps. Proposals specify
one private Environment-bound job, scoped writer/publisher tokens, exact
reviewed-code installation plus current public archive cwd, serialized
Codex, bounded outputs/deadlines, auth persistence before public effects
and separate qualification/cutover/rollback.

The one-Environment placement refines the FD table's suggested private
publishing environment; the approval request must disclose this decision.
Parent process privilege is trusted; minimum child environment and disabled
model tools are explicit boundaries, not an assertion of OS-user isolation.

## Evidence and open prerequisites

- Local `codex --version`: 0.153.4. Help/features support further adapter
  qualification, not a proven tool-free Linux model invocation.
- Actual caller limits: per-call 1,800s, US 3,900s shared, domestic/crypto
  5,700s shared; all three ceilings total 255 minutes. Proposed outer job
  240 minutes, supervisor 225, generation cutoff 210.
- Existing segment concurrency defaults to one; private Codex template will
  pin it explicitly and retain the session lock for other callers.
- `ARCHIVE_ROOT = Path("archive")` supports current-public-cwd separation;
  installed-code import provenance and Git identity require integration tests.
- `gh api user` returned no plan; `investo-runtime` lookup returned 404.
  Asked GitHub tier asynchronously. Private Environment Secrets eligibility
  is unresolved; no automatic upgrade or repository-secret fallback.
- Primary references are linked in the design artifacts; credential contents
  were not accessed and no LLM login/model call was performed.

## Validation

Final scoped document validation passed: 20 changed Markdown files (14 new,
including prior FD work), 24 added relative links, balanced fences and clean
changed whitespace; 14 approved rules, 12 ACs, 16 NFRs, preparation checklists
7/6/6 and nine unchecked code steps. `git diff --check` passed.
The first broad link scan encountered an unchanged historical `(url)`
placeholder in the global state file; validation was correctly scoped to new
documents and added links rather than modifying unrelated history.

The isolated diff contains no source/test/workflow/site/archive changes.
Original root still shows only its prior `.claude/settings.local.json`,
`.claude/worktrees/` and `archive/_meta/fact_snapshots.jsonl` dirt.
Runtime tests and a public-site build are not appropriate for this
design-only change outside `site_docs`; none were claimed or executed.

## Handoff

Review the prepared NFR/Infrastructure decisions, then explicitly approve
Code Generation or request changes. Account/model/tool/usage qualification
and remote provisioning/activation remain separate from local implementation.
No source/test/workflow/site/archive/debt edits, secret registrations, live
generation, external writes, commit/push, notifications or Pages dispatch.
