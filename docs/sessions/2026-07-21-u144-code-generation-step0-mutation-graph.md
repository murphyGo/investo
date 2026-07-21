# Session: u144 Code Generation Step 0.1

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 0, checklist 1 of 6 — freeze the mutation graph
- **Outcome**: Complete; Step 0 checklist 2 is next

## Work Summary

Enumerated the default segmented production call graph from generated
`Briefing` construction through archive write. Recorded all nine executable
post-generation `rendered_markdown` replacement sites, the internal ordering of
`apply_reader_format_to_segments()`, read-only gates around each mutation, and
the file-producing visual/chart operations that currently occur before terminal
validation. The baseline also records that publish-local late mutations are not
returned to pipeline accumulation, so notification currently reads an earlier
Markdown version than archive/index/quality consumers.

## Files Changed

- Created `aidlc-docs/construction/u144-public-document-finalization-contract/code/mutation-graph-baseline.md`.
- Marked the first Step 0 checklist item complete in the u144 code-generation plan.
- Added this session log and the matching AIDLC audit entry.

Unrelated dirty u140, generated archive/site, settings, and worktree changes were
not edited.

## Key Decisions

| Decision | Rationale |
|---|---|
| Separate generated construction from post-generation replacement sites | U144 must preserve the u118 generation boundary while sealing only publisher-finalized bytes. |
| Count only executable direct `Briefing` replacements | The `publisher/charts.py` match is a docstring example and would otherwise create a false architecture baseline. |
| Record read-only gates beside mutations | The production defect is ordering: several real producers run after the apparent terminal gate. |
| Treat each Step 0 checkbox as one `dev-investo` execution unit | The skill requires one next unchecked plan item per invocation. |

## Code Review Results

The required fresh-eyes review found two documentation-accuracy issues:

- Medium: the baseline said four direct replacements run after the surface gate;
  the correct count is five when partial-bundle navigation is included.
- Low: the orchestrator registry was described as the last validator without
  mentioning `write_briefing()`'s write-time disclaimer verification.

Both were corrected. The reviewer otherwise confirmed the nine executable
direct replacement sites, production call order, docstring/construction
exclusions, and AC-144.4 bounded scope. No application code changed, so the
Python-specific deep-review protocols were not applicable.

## Potential Risks

- Line numbers are a frozen pre-u144 baseline and will move during later steps;
  the named functions and direct-site count are the durable contract.
- Helper-internal string transforms are grouped under their production caller;
  later AST coverage remains intentionally bounded as required by AC-144.4.

## TECH-DEBT

No new TECH-DEBT item was introduced. The ordering and ownership gaps recorded
here are the planned scope of u144 rather than deferred shortcuts.
