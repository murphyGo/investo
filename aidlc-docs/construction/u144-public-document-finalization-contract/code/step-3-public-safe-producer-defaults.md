# Step 3.2 Public-Safe Producer Defaults

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The Stage-2 prompt and watchpoint producer now consume the neutral shared
public-language map rather than emitting raw operator diagnostics as public
defaults.

- `SEGMENT_DATA_LIMITED_NOTE` and the watchpoint prompt contract prescribe the
  exact shared reader-safe limitation sentence and no longer ask the model to
  emit a raw coverage label.
- `WatchpointRow.data_limited()`, partial structured-row fallbacks, source
  promotion, confidence labels, trigger defaults, implication defaults, and
  the collapsed watchpoint note all use shared public-safe values.
- Direct `render_matrix_table()` output for limited and partially populated
  rows has zero findings from the existing u108 public-evidence predicate.
- The shared source fallback is deliberately classified as unusable by the
  parser. It cannot make an incomplete row appear source-backed.

## Legacy-input boundary

Raw diagnostic spellings remain only in the watchpoint parser's legacy input
recognizers and invalid-source sentinel set. They are accepted as historical
or malformed input evidence but are never selected as an output default. The
run-29707052598 fixture remains unchanged as incident evidence; its
characterization now proves that the same input produces safe current output
while the captured pre-u144 output still reproduces the original block.

## Review and validation

Fresh-eyes review confirmed the prompt/default boundary, direct-render
non-leakage, fallback-source rejection, structured-row behavior, idempotence,
and the unchanged historical corpus. No correction was requested.

- focused prompt/watchpoint/incident suite: 112 passed;
- broad briefing/publisher/surface/integration suite: 1,545 passed locally and
  1,583 passed in the independent review scope;
- Ruff check and format check: passed;
- strict mypy for the changed source modules: passed;
- scoped diff check: passed.

The workspace-wide diff check remains outside this slice because an unrelated
generated watchlist page already has trailing whitespace. No such finding is
present in the Step 3.2 files.
