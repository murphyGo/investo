# Session Log: 2026-08-05 - u135 - Main Integration

## Overview

- **Date**: 2026-08-05
- **Unit**: `u135 watchpoint-current-value-and-deterministic-fallback`
- **Stage**: Main integration
- **Base**: `origin/main@b06b1ba`
- **Validated unit head**: `origin/codex/u135@64a54ef`

## Integration

Created an isolated integration worktree from the current remote main and
merged the complete validated u135 branch with a two-parent merge. Code and
test paths merged automatically. The append-only `aidlc-docs/audit.md` had one
content conflict where current-main u141/u146 records and u135 records shared
the same insertion point; the resolution retains both blocks without rewriting
their contents. The user's original dirty main worktree was not modified.

## Validation

| Gate | Result |
|------|--------|
| Lock / u135 fixture JSON / diff integrity | Passed |
| Ruff / format | Passed; 17 u135 Python files |
| mypy | Passed; 252 current-main source files |
| publisher + orchestrator | 1,468 passed |
| strict MkDocs | Not applicable; u135 changes no `site_docs` path |

## Main quality recovery

The merge commit `49018867aca154df3601a1924da280c072591e8a` was pushed to
the integration branch and `main`. Quality run `30994558625` failed twice on
the exact SHA: both attempts reported the same 18 downstream
`test_run_pipeline.py` failures, while Ruff, format, and mypy passed.

The common cause was a `us-equity` finalization failure. A synthesized u135
watchpoint card treated the protected, non-H2 quality-diagnostics block after
section ⑥ as section body and removed it. The resulting layout error carried
the region ID `diagnostics:quality`; forwarding that colon-bearing ID directly
to the bounded issue-code contract raised a second `ValueError`, turning the
intended segment trust block into a bundle-level failure.

The repair now stops all watchpoint parse/render paths before either collapsed
or expanded protected diagnostics, preserves the diagnostics and disclaimer
bytes in a dedicated regression, and normalizes layout region separators when
converting a layout failure to a bounded issue code. The finalization error also
exposes an allow-listed R13-safe `cause_code` without rendering raw causes.

## Recovery validation

| Gate | Result |
|------|--------|
| Root regression scope | 225 passed |
| Full pytest | 4,299 passed in 264.89s |
| Ruff / format | Passed; 567 Python files formatted |
| mypy | Passed; 252 source files |
| Diff integrity | Passed |

## Next step

Commit and push the bounded recovery, advance `main`, and verify a new exact-SHA
quality run before the final development-queue audit.
