# Session: u144 Code Generation Step 0.3

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 0, checklist 3 of 6 — pin pre-u144 failures
- **Outcome**: Complete; Step 0 checklist 4 is next

## Work Summary

Connected the watchpoint and body-evidence incident fixtures to their current
production producer and gate APIs. The truncation family is deliberately a
historical gate corpus: current `reflow_first_viewport()` already repairs those
three malformed shapes, so the tests preserve both the old blocking evidence
and the current safe producer output without claiming the producer still emits
the incident strings.

Five cases now pin:

- watchpoint rendering byte-equals the recorded card and reintroduces one
  `public_diagnostic.raw_label` issue after the earlier projection;
- each of the three historical first-viewport post-reflow shapes is rejected
  with `summary.truncated_mid_token`, while current reflow converts it to the
  exact safe `본문 참고.` output before the gate;
- body-evidence accounting reports `quality.body_evidence_untracked` before
  projection, then loses the parser signal after projection while the known
  evidence count stays one.

## Files Changed

- Added `tests/unit/publisher/test_public_document_incident_characterization_u144.py`.
- Marked Step 0 checklist 3 complete in the u144 code-generation plan.
- Updated AIDLC state/audit and added this session log.

No production module was changed. Unrelated dirty u140, generated archive/site,
settings, and worktree changes were not edited.

## Validation

- `uv run pytest -q tests/unit/publisher/test_public_document_incident_characterization_u144.py` — 5 passed
- Related watchpoint/surface/quality consistency regression scope — 79 passed
- `uv run ruff check tests/unit/publisher/test_public_document_incident_characterization_u144.py` — passed
- `uv run ruff format --check tests/unit/publisher/test_public_document_incident_characterization_u144.py` — passed after formatting
- `git diff --check` — passed

## Code Review Results

Fresh-eyes review found one High documentation/test-scope issue: the first
viewport cases were initially described as current producer output even though
the test only exercised the gate and current reflow already repairs all three.
The fixture and test now identify them as a historical gate corpus and also
assert the exact current repaired output. Re-review returned `APPROVE` with no
remaining findings.

## TECH-DEBT

No new TECH-DEBT item was introduced. The tests document defects already owned
by u144 and do not create a parallel gate or compatibility path.
