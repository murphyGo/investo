# Session Log: 2026-09-07 — u153 Code Generation Step 3

## Overview

- **Unit / Stage**: u153 summary-sentence-boundary-extension / Code Generation
- **Step**: 3/6 complete — summary caller migration
- **Workspace**: `/private/tmp/investo-briefing-review-20260906`
- **Baseline**: `d5530353758b6475cf0852c69ea9b9b3cfd99e0b`
- **Approval**: User replied `진행시켜` to the Step 3 next-action proposal.

## Changes

- `src/investo/publisher/reader_format/reflow.py`: sentence-only candidate
  selection with canonical safety/rollback, per-surface fallbacks, and owned
  TL;DR traversal. Existing malformed-link findings and reference definitions
  remain with their original owner; caution/default text-helper behavior is unchanged.
- `tests/unit/publisher/test_summary_sentence_extension_u153.py` and
  `tests/fixtures/u153/summary-sentence-boundary.json`: all nine former expected
  failures now pass normally; 94 new cases added without altering original
  incident inputs or expected outputs.
- `tests/unit/publisher/test_reader_format_reflow_u71.py`: superseded legacy
  word-boundary expectations updated and exact issue types annotated.
- `tests/fixtures/u144/first-viewport-truncation-family.json`: two current-output
  expectations updated; historical incident fields and caution output preserved.
- Created Step 3 construction evidence and this session log; updated the plan,
  state, unit-of-work, story-map and append-only audit.

## Decisions and review

The dev-investo single-step scope was retained. The existing helper and canonical
summary/scanner predicates remain authoritative. The caller preserves original
link defects even over budget, because fitting text must not conceal an error.
The private guard keeps full bare/prefixed scan contexts; reference definitions
are structure, not prose. H2 traversal excludes code and tracks active details.

Independent review initially identified context/ownership defects and follow-up
boundary cases. All were corrected, including pipe-leading values, anchored
reference links, scanner-window crossings and indented code/details endings.

| Review category | Final result |
|---|---|
| Correctness | Pass |
| Safety | Pass |
| Reliability | Pass |
| Maintainability | Pass |
| Test Coverage | Pass |

Re-review: 273 related tests and 250 targeted variants passed, no remaining
finding or debt candidate. Security Boundary, Performance, Memory and Error
Contract protocols applied. No new architectural decision required an ADR.

## Validation

- Exact final focused gate: **268 passed**, no xfails.
- Exact final publisher-wide gate: **1,169 passed**, no xfails; overlaps the above.
- All-source mypy: **254 files**; scoped test mypy: **2 files**; Ruff/check+format,
  JSON parsing and diff whitespace checks passed.
- Supplemental briefing/notifier/orchestrator/integration run: **1,569 passed**;
  it began before the last review corrections and is not an exact-final-tree claim.
- Partial PBT: PBT-02 N/A for lossy no-inverse bounding; PBT-03/07/08/09 compliant.
  Seed `15320260907`, realistic decimal/Markdown cases, shrinking enabled.

Exact commands and review evidence:
`aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-3-summary-callers.md`.

## Risks and next target

Step 4 still needs to teach the existing canonical scanner to reject the exact
residual continuation family. Steps 5–6 still own finalizer ordering and final
Markdown/notification proof. This is not unit completion or a live production
fix. No historical archive, site, workflow or debt file changed; no commit,
push, publication or Telegram action occurred. Original dirty work and other
worktrees remain untouched.
