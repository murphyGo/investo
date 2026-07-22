# Step 7 production replay: watchpoint supplement preservation

## Production evidence

Exact-date retry `29895552891` at head `f918982` collected 119 items and
generated all three segment drafts for `target_date=2026-07-17`
(`ok=3 failed=0`). All three then entered the same typed structure block and
the fixed point ended with:

```text
phase=bundle codes=bundle.zero_survivors,structure.supplement_expectation
```

No public commit was made, Pages was skipped, the operator notification
succeeded, and the workflow re-emitted pipeline exit code 1 as designed.

## Root cause

Every visual preparation includes a `watchlist-relevance` supplement placed
inside the owned `## ⑥ 오늘의 관전 포인트` section. Phase-one assembly then
called `render_watchpoint_matrix_result()`, whose bounded rewrite replaced the
entire section body. The rewrite retained the H2 and rendered cards but erased
the marker-backed visual supplement. The next canonical layout reindex
correctly rejected the missing declared supplement.

This was a producer-composition gap, not invalid LLM content and not a reason
to omit all visual supplements or weaken `structure.supplement_expectation`.

## Repair

- `publisher.public_document` remains the sole owner that renders typed E1
  supplements into exact marker-backed fragments.
- The finalization boundary supplies those exact fragments to its internal
  segment reader collaborator.
- The watchpoint renderer accepts caller-owned fragments only as opaque byte
  strings. It removes any fragments located inside §⑥ before interpreting
  bullets and reinserts them byte-for-byte ahead of the rewritten cards or
  limitation note.
- The watchpoint module does not parse, reconstruct, or duplicate the U-144
  marker grammar.
- Duplicate or empty preservation inputs fail closed. Repeated rendering is
  byte-idempotent.

## Validation

- Focused watchpoint/public-document/architecture scope: 125 passed.
- Ruff check passed for all touched files.
- Ruff format passed after formatting the segment collaborator.
- Strict mypy passed for the three touched source files.
- Regressions cover rendered and limited watchpoint outcomes plus the real
  phase-one public-document assembly call with a typed visual supplement.

The exact-date replay must be rerun at the repair commit before Step 7 can be
closed.
