# Step 5.7 GitHub Summary Diagnostics

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The GitHub step summary now shows public-content completeness,
`publication_committed`, and expected/finalized/published segment counts next
to the existing pipeline status and duration. A dedicated Public Documents
table renders every typed segment outcome in canonical order with its terminal
state and machine-readable issue codes.

Finalization codes remain deterministic and operator-safe: the shared model
accepts only bounded code syntax and canonicalizes ordering; the summary passes
codes through the existing strict diagnostic redactor and displays at most
eight per segment with an omitted-count suffix.

## Regression evidence

- A two-survivor committed result renders `2/3` finalized and `2` published.
- The trust-blocked segment shows its typed state and
  `entity.fact_contradiction` code while finalized siblings show no code.
- A ten-code fixture displays eight codes and a `... (+2)` suffix.
- Existing stage/source timing diagnostics and secret/chat redaction remain
  unchanged.
- The same shared count helper feeds both Markdown summary and bounded workflow
  outputs, preventing count drift.

## Validation

- CLI summary contract tests: 65 passed;
- CLI, workflow, full orchestrator, and finalizer type regressions: 206 passed;
- Ruff check/format and strict mypy over 244 source files: passed;
- no dependency, source, secret, network, or workflow control-flow change.
