# Step 8 post-implementation review corrections

## Outcome

The five approved review gaps are closed without changing the U-144 product,
infrastructure, persistence, or post-git recovery boundaries. The production
path still has one generated-to-sealed finalizer, but its terminal checks,
repair ownership, partial visibility, rollback behavior, and producer planning
now match the existing design contracts.

## Corrections

| Contract | Correction | Evidence |
|---|---|---|
| AC-144.23 | Terminal validation now calls the canonical reader-visible public-label traversal and one canonical full-document surface scan. Owned-region findings remain available for attribution; the union fails closed before notifier DTO derivation. | Reader-visible table leakage and injected cross-region blocker regressions in `test_public_projection_u144.py`. |
| AC-144.24 | Production assembly disables its legacy whole-document surface repair. The repair phase begins from owned findings only, records one `PublicBlockOutcome` per region action, re-projects, and blocks on residual non-warning findings. Balanced inline-code spans are preserved because the scanner also excludes them. | Owned repair/outcome, inline-code preservation, first-viewport internal-heading, and residual-fallback regressions. |
| AC-144.25 | Segmented notification consumes the complete canonical `SegmentFinalizationOutcome` tuple. Public copy distinguishes generation absence from pre-publication trust failure without codes; every trust-blocked outcome emits a bounded private publish-stage alert. | Notifier typed-outcome tests, PublishStage entity-gate test, and end-to-end pipeline alert assertion. |
| AC-144.26 | Pre-git rollback restores old bytes through `write_atomic_bytes`, attempts every snapshot after an individual failure, and raises `PublisherIOError` for the first failed path. New-file unlink errors are no longer suppressed. | `test_rollback_u144.py` atomic restore, unlink-failure, and restore-failure tests. |
| AC-144.27 | Each active fixed-point pass prebuilds one immutable per-segment producer plan. The plan owns rendered anchor table, shared macro, crypto indicator, channel anchor, cause map, and daily thesis payloads; both `PublicRegionExpectation` and assembly consume those exact values. Builder/context exceptions are converted to bounded finalization errors. | Full-finalizer call-count spy, anchor eligibility assertion, cached-plan identity, and producer/context error-normalization regressions. |

Contract 9 diagnostics were synchronized at the same boundary: every
replacement/omission emits one redacted
`public_document.block_degraded segment=<...> block=<...> disposition=<...> codes=<...>`
record. No rejected prose, generated Markdown, source payload, or secret is
logged.

## Fresh-eyes review

The required independent review covered correctness, data integrity, error
contracts, performance, resource lifecycle, and privacy. It found and drove
four additional corrections before closeout:

- inline-code spans ignored by the scanner were being mutated by repair;
- daily thesis and anchor-table producers still had duplicate computation
  paths outside the active producer plan;
- newly moved producer-plan construction could leak raw `ValueError` or
  unexpected exceptions;
- the documented bounded block-degradation log had not been wired.

After those repairs and focused revalidation, the reviewer reported no
remaining blocking code findings.

## Validation

- U-144/owner-focused scope: **529 passed**.
- Full orchestrator pipeline module: **99 passed**.
- Full repository pytest: **4,083 passed**.
- Module-boundary/shared-domain scope: **19 passed**.
- Ruff check and format check: passed.
- Strict mypy: passed across **246 source files**.
- No-paid-API guard: passed.
- Strict MkDocs: passed after removing test-generated archive/site projections.
- `git diff --check`: passed.

All tests ran in the isolated `codex/u144-review-fixes` worktree. Generated
archive, site, OG-card, coverage, and fact-snapshot artifacts were restored or
removed before the final diff. The user subsequently requested commit/push, so
the corrective slice is published from that isolated branch after rebasing and
overlap validation.
