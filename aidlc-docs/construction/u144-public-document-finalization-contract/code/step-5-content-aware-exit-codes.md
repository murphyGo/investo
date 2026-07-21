# Step 5.5 Content-Aware Exit Codes

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The CLI now maps typed public-content disposition through one
`_pipeline_exit_code()` owner instead of treating every legacy
`PipelineStatus.PARTIAL` as successful:

- complete content, including notifier-only or visual-only partial: exit 0;
- no public content or a legacy `FAILED` result: exit 1;
- a committed one/two-segment content-partial bundle: exit 2.

Content-partial is evaluated first, so its exit-2 severity remains visible if
notification also fails. The legacy `FAILED` check remains as a
backward-compatibility guard for callers that have not populated the new
content field.

## Regression evidence

- success plus complete content exits 0;
- delivery-only `PARTIAL` plus complete content exits 0;
- content-partial exits 2 for both `PARTIAL` and a defensive conflicting
  `FAILED` fixture;
- `none` and legacy `FAILED` results exit 1;
- configuration and unexpected-exception paths remain exit 1.

## Validation

- CLI contract tests: 61 passed;
- CLI plus full orchestrator regressions: 159 passed;
- Ruff check/format and strict mypy over 244 source files: passed;
- no workflow sequencing change yet; that is the next checklist item.
