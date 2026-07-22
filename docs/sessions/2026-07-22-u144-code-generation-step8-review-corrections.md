# Session: u144 Code Generation Step 8 review corrections

## Context

- **Date**: 2026-07-22
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation Step 8
- **User direction**: "위 개선 안건들을 u144에 반영하고 작업 진행하자"
- **Isolation**: `codex/u144-review-fixes` at `/private/tmp/investo-u144-fixes.SgsPK0/repo`

The user's main worktree already contained unrelated changes. Work therefore
continued in a clean isolated worktree from `origin/main`; none of the original
dirty files were overwritten, staged, committed, or pushed.

## Delivered

1. Added terminal canonical reader-visible leakage traversal and full-document
   surface scanning.
2. Removed production's unowned whole-document surface repair and made each
   owned action auditable through typed outcomes and bounded degradation logs.
3. Propagated typed segment outcomes to notifier copy and private publish-stage
   alerts.
4. Made pre-git snapshot rollback atomic, best-effort across the complete set,
   and observable on failure.
5. Added one active-pass producer plan shared by rendered payload assembly and
   region eligibility, including anchor tables and daily thesis.
6. Preserved scanner-exempt inline code and normalized producer/context errors
   at the finalization boundary after independent review.

## Validation

- 529 U-144/owner tests passed.
- 99 full `test_run_pipeline.py` tests passed.
- 4,083 full repository tests passed.
- 19 module-boundary/shared-domain tests passed.
- Ruff, Ruff format, strict mypy (246 source files), no-paid guard, strict
  MkDocs, and `git diff --check` passed.
- Independent fresh-eyes review finished with no blocking findings.

## State

U-144 Code Generation Step 8 is complete. After the implementation stage, the
user explicitly requested commit/push; the isolated branch is therefore
rebased, overlap-validated, committed, and pushed without touching the original
dirty main worktree.
