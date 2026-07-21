# Step 4.5 Terminal Numeric-Anchor Scan

## Landed boundary

Assembly now calls the existing `gate_body_assertions()` result directly. It
keeps deterministic prose repair and raises the existing
`NumericAnchorReconciliationError` only when a structural claim cannot be
rewritten. The default segmented reader path no longer calls
`enforce_anchor_assertions()`.

`anchor_assertion_gate.scan_anchor_assertions()` is the exact read-only
terminal API. It returns frozen `AnchorAssertionFinding` values from the input
Markdown without returning or applying rewritten text. It shares the existing
core-symbol, alias, move, magnitude, protected market-anchor, traceability-row,
structural-line, list, and blockquote semantics.

The legacy `enforce_anchor_assertions()` remains a compatibility wrapper. It
runs assembly repair, scans the repaired bytes for residual findings, raises on
the first residual, and otherwise returns the repaired Markdown. There are zero
default segmented call sites outside that definition.

## Finalizer adapter

`publisher.public_document._scan_terminal_anchor_assertions()` reads only:

- `draft.layout.markdown`, the final active layout bytes;
- `draft.segment` and `draft.target_date` identity; and
- ticker symbols from E1 `PublicDocumentContext.anchors_by_segment`.

It does not read history, refetch data, mutate the layout, or call an assembly
repair helper. The concrete terminal validator will compose this adapter with
the other read-only trust gates in the following slices.

## Regression evidence

- Read-only tests prove an isolated unsupported claim is reported while the
  exact input string remains unchanged.
- Assembly/terminal composition proves the deterministic replacement leaves no
  terminal finding, while structural claims remain blocking.
- AST regression tests prove `segment_reader_format` and `pipeline` have no
  compatibility-wrapper call.
- Finalizer tests prove only final layout bytes and E1 anchor symbols determine
  the result.
- Focused and integration review scope passed 105 tests; the full publisher and
  orchestrator unit scope passed 1,057. Strict mypy passed all 242 source files;
  Ruff check/format and scoped diff checks passed. Fresh-eyes review approved
  with no blocker.
