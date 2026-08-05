# u135 Step 1 — Current-value trace

## Outcome

- Traced the live segmented publish path from the orchestrator's frozen E1
  context through u144 phase-one assembly into the u72/u98/u110 watchpoint
  renderer.
- Confirmed that reconciled anchors and routed source items already cross the
  publisher boundary as plain model data; u135 can extend that existing call
  without a publisher-to-orchestrator import.
- Located the source-label leak at the row-building/rendering seam: the card
  shape stays unchanged, but its renderer faithfully emits an unresolved row
  value. The compliance scanner is not the value-resolution owner.

## Active call path

1. `orchestrator.pipeline::_build_public_document_context` freezes reconciled
   `anchors_by_segment` and routed `items_by_segment`.
2. `publisher.public_document::_assemble_phase_one_reader_draft` passes those
   payloads into `apply_reader_format_to_segments` before projection and seal.
3. `publisher.segment_reader_format::apply_reader_format_to_segments` performs
   the first raw-prose compliance scan, calls
   `render_watchpoint_matrix_result`, then performs the second compliance scan
   over the rendered §⑥ surface.
4. `publisher.watchpoint_matrix::_build_row` and `render_matrix_table` construct
   and render the u98 card.

## Root cause

u110's `_promote_source` searches the source/current/trigger/implication fields
and returns a value for `출처`. It does not mutate or replace `row.current`.
`render_matrix_table` subsequently normalizes the original current text and
renders it unchanged. `_renderable_row` counts a generic current as only one
soft invalid, and the current generic-value matcher does not reject every
multi-token source label. Consequently, a populated row can render
`출처: CoinGecko BTC` and `현재: CoinGecko BTC` even though the reconciled BTC
anchor and routed crypto price item contain numeric values.

## Step 2 boundary

- Add one explicit plain-data payload parameter at the existing call boundary.
- Resolve only exact ticker/canonical-label/indicator keys; no fuzzy matching.
- Substitute a deterministic numeric value after u110 source promotion.
- Hard-fail any surviving LLM row whose final `현재` lacks a digit or supported
  resolved value token.
- Preserve u131 title bounding, u110 trigger/source rules, both compliance
  scans, and u144 pre-seal ownership.

## Validation

- Existing watchpoint matrix suite: passed.
- Scoped Ruff and format: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved after four documentation-precision findings were
  corrected; no remaining findings.
