# Step 6.4 Active-Survivor Thesis Isolation

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The fixed-point lifecycle regression now records both typed thesis state and
rendered thesis wording on every assembly attempt. After crypto is trust
blocked, the next pass proves it is absent from:

- `daily_thesis_signals`;
- `supporting_segments`;
- `per_segment_lines` keys; and
- the combined reader-facing decision and per-segment wording.

The first pass still contains the crypto support label, proving the assertion
observes redecision rather than a fixture that never included the removed
segment. A direct neutral-owner test also rejects `가상자산`, `BTC`, and `ETH`
in the surviving domestic/US wording while preserving the immutable base
context. The architecture AST guard continues to prove
`publisher.public_document` imports no `investo.orchestrator` module.

## Validation

- lifecycle plus neutral-owner tests: 47 passed;
- scoped Ruff and format check: passed.
