# Step 5.6 Workflow Pages Sequencing

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

`PipelineResult.publication_committed` is now owned by the successful publish
transaction and defaults to false. It becomes true only after segmented or
legacy publish completes outside dry-run mode; publish failures and rollback
paths cannot set it.

`__main__` appends only bounded controller outputs to `$GITHUB_OUTPUT`:
pipeline status, content completeness, publication-commit boolean, and
expected/finalized/published integer counts. The daily workflow's pipeline
step has `id: pipeline`, captures rc 0/1/2, writes `process_exit_code`, and
returns 0 so subsequent control flow can inspect the result.

Pages dispatch is conditioned solely on
`steps.pipeline.outputs.publication_committed == 'true'`. A final
`if: always()` step runs after Pages and re-emits rc 1 or 2. Missing,
non-numeric, or out-of-set rc values fail closed as 1.

## Regression evidence

- Complete and content-partial successful publishes set the commit flag.
- Dry-run and staged-write rollback failures keep the flag false.
- Controller outputs contain no Markdown, URL, exception, token, or chat ID.
- Workflow tests pin step IDs/order, Pages gating, delayed rc re-emission, and
  fail-closed invalid-rc handling.

## Validation

- focused result/CLI/workflow/publish scenarios: 116 passed;
- result, CLI, workflow, weekly flags, env contract, and full orchestrator
  regressions: 229 passed;
- Ruff check/format and strict mypy over 244 source files: passed;
- no dependency, source, secret, or additional workflow/job introduced.
