# u155 main integration — 2026-09-09

**Authorization**: The user selected “1번 진행해줘” after the next-step list
specified latest-main reconciliation, integration tests, PR checks and merge.
This authorizes the complete main-integration task, not private runtime
provisioning or activation (Steps 8/9).

**Integration base**: `fc373277125e5455dc4e4292bcd7a098e877fbe8`
**Feature**: `27a6c42c14c93672b5b7458394f551220c68cfe4`
**Branch**: `codex/u155-main-integration-20260909`
**Worktree**: `/Users/user/Desktop/Projects/investo/.tmp/u155-main-integration-20260909`

## Merge review

Created the isolated integration worktree from refreshed `origin/main` and
merged the validated provider feature without changing application logic.
The only textual conflict was the append-only `aidlc-docs/audit.md` tail.
Both parent histories were retained in order, verified as complete line
subsequences; the u151 implementation and u153 production closeout are preserved.
The other three shared unit/state/story surfaces merged cleanly.

All 24 feature-owned implementation/test/template/dependency files match the
reviewed feature commit byte for byte. The first-parent diff has no active
`.github/workflows/`, `archive/` or `site_docs/` change. The latest public
archive and production-closeout state are retained. Private credentials,
repository provisioning and Codex schedule activation remain unperformed.
The existing Pages workflow may rebuild automatically on main because the
feature changes pyproject.toml; that is separate from Codex runtime activation.

## Integration validation

- Full repository pytest: **5,305 passed in 344.97s** on the combined tree.
- Ruff check passed; format check passed for 594 files.
- Source mypy passed for 263 files; frozen lock check passed (66 packages).
- No-SDK, no-paid, curated-assets (19 filed / 0 deferred) and image-store
  (empty store) guards passed.
- Strict MkDocs build and both Material stylesheet/rendered-pair guards passed.
- Private template actionlint 1.7.12 passed; its four contract tests are included
  in the full suite along with both-provider, auth lifecycle and local Git cases.
- Audit-history subsequence checks, resolved-merge checks and diff checks passed.
- Refreshed main remained the integration first parent before final commit.

The application/test/template/dependency bytes were unchanged after the full
gate; final integration edits record evidence and update unit delivery state.
PR and main Quality checks verify the delivery commits on GitHub.

No existing root changes were staged: `.claude/settings.local.json`,
`.claude/worktrees/`, `archive/_meta/fact_snapshots.jsonl` remain untouched.
The original feature worktree stays clean and preserves the delivered feature
commit. Main delivery uses a PR from the integration branch; check its status
and exact merged commit/Quality run for remote completion evidence.

## Operational boundary

Local implementation and main integration do not qualify the live private
runtime. Account Environment support, effective Linux tool inventory, dedicated
ChatGPT login/model access, next-job refresh reuse and usage/runtime remain
Step 8. Public publication credentials, Pages dispatch and one-owner schedule
cutover/rollback remain Step 9. Existing Claude remains the default.
