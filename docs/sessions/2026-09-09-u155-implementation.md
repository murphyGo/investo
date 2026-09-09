# u155 local implementation — 2026-09-09

**User authorization**: “구현까지 진행시켜”. FD/NFR/Infrastructure approved;
continue local Steps 1–7 through implementation, tests and review. The normal
one-step pause does not apply to this explicit scope. No remote provisioning,
activation, personal auth handling, commit or push was authorized here.

**Worktree**: `/Users/user/Desktop/Projects/investo/.tmp/codex-provider-20260909`
**Branch**: `codex/codex-provider-20260909`
**Base**: `f93def427be2d16365685102c7e9dcf1cad073e1`

## Delivered behavior

Claude is the default. Explicit Codex/model configuration uses a pinned native
CLI and managed ChatGPT session in a separate private runtime. Both generation
stages reuse the current parser/assembly/finalizer. Child CLI processes have
isolated cwd/HOME/config and minimal credentials; process cancellation,
bounded output, auth-call serialization and deadline cleanup are implemented.

The supervisor validates/restores Environment auth, persists valid rotations
with encrypted bounded GitHub requests before public publication, and preserves
again on failure/cancellation when needed. Failed checkpoint or cleanup cannot
permit publishing or another model call. The private template is manual-only
and dry-run without public sender/publisher credentials.

## Validation record

- Existing Claude/main/preflight focused regression: 103 passed earlier.
- First complete pytest: 5,024 passed / 1 failed, because the exact expected
  redaction secret-name set omitted the three new names. Updated that test;
  redaction suite 55 passed.
- Second full gate: 5,025 passed in 357.01s before the final provenance/timing
  addition was included in the collected suite.
- Final provenance/timing and auth/CLI focused gate: 62 passed in 8.43s.
- Final full gate: **5,026 passed in 326.68s**.
- Ruff check and format: all passed, 590 files formatted.
- mypy: 263 source files passed.
- `uv lock --check`, no-Anthropic-SDK and no-paid-API guards: passed.
- Workflow contract tests: 4 passed; embedded Bash/Python syntax verified.
- Official actionlint 1.7.12, release checksum verified: schema/context passed
  with shellcheck/pyflakes disabled (syntax is covered by the contract tests).
- Two-provider × four-market staged subprocess integration plus two local
  Git cases: 10 passed. Real local Git push rejection/dry-run/idempotence and
  private/public lineage tested; no network Git publication.
- Non-editable frozen operations installation in a separate `/private/tmp`
  venv: passed. Absolute `python -I` imports reviewed installed code even with
  adversarial same-name modules/sitecustomize/PYTHONPATH in a different cwd;
  reads that cwd's current archive.
- Independent fresh-eyes review: PASS after all fixes, plus final timing and
  Actions-context delta reviews. No unresolved local blocker or new debt.
- Requirements cross-check: local PASS; full operational acceptance remains
  the explicit Step 8/9 gate. See the linked cross-check for each AC/NFR.
- No rendered site changes: strict MkDocs build not applicable.
- Final diff/root/remote audit: passed; final diff is scoped, root dirty entries preserved, newer remote recorded below.

## CLI qualification boundary

Pinned upstream schema, model manager and tool registration source inspected
for Codex 0.153.4. Actual macOS native `debug models` accepted the restricted
catalog without auth. The official Linux native release/digest is pinned.
The npm registry lookup did not provide that version.

A mock endpoint probe with invalid synthetic credentials did not intercept the
model websocket request and received authentication failures. It is not evidence
of a complete tool-free request or a successful model invocation. No personal
login was read/changed and no real account model generation was performed.
Effective Linux tool inventory must be qualified before dedicated live auth.

## Remaining operational work

Steps 8/9: confirm private Environment eligibility, provision
`murphyGo/investo-runtime` / `codex-runtime`, register dedicated login using the
local file-to-secret runbook, verify actual model/Linux execution and refreshed
auth in the next serialized job, measure usage/runtime. Then separately prepare
and review publisher token/Git/Pages wiring and one-owner schedule cutover.
No public workflow, schedule, repository Secret or Telegram send was changed.

## Repository state

`origin/main` advanced during work to
`a63f863f44fb62ce81993bcda7ed7d351737273e`, containing u151 and the next daily
archive. No changed application-code file overlaps this implementation.
Shared AIDLC documents must preserve the newer u151 state when integrating;
this uncommitted branch is not yet merged with main.
The root dirty entries are unchanged: `.claude/settings.local.json`,
`.claude/worktrees/`, `archive/_meta/fact_snapshots.jsonl`.

References:
- `aidlc-docs/construction/u155-codex-chatgpt-briefing-provider/code/summary.md`
- `aidlc-docs/construction/u155-codex-chatgpt-briefing-provider/code/code-review.md`
- `docs/cross-checks/2026-09-09-u155-codex-chatgpt-briefing-provider.md`
- `ops/private-runtime/README.md`

## Follow-up — feature-branch commit/push authorized

The user subsequently requested “커밋·푸시해줘”. Commit and push the validated
u155 slice to `codex/codex-provider-20260909`. Preserve the root dirty work;
main integration and Steps 8/9 private provisioning/activation remain separate.
The 5,026-test implementation has no subsequent application-code changes;
this follow-up updates only delivery status documentation. Verify the staged
scope and remote branch SHA and report the exact commit in the delivery reply.

At commit/push preflight, refreshed `origin/main` is
`71c1db17fab62dde0caf981b909e51c2d6564c4c`. Overlap is limited to the four
shared AIDLC state/audit/unit/story documents; no application-code overlap.
The feature branch does not include those concurrent main updates.
