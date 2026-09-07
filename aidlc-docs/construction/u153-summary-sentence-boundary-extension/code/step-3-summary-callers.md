# u153 Code Generation Step 3 — Summary caller migration

**Date**: 2026-09-07 KST
**Status**: Step 3/6 complete; Step 4 canonical residue rejection next
**Baseline**: `d5530353758b6475cf0852c69ea9b9b3cfd99e0b`

## Approved bounded plan

The user replied `진행시켜` after the Step 2 report identified Step 3 as next.
Continue in `/private/tmp/investo-briefing-review-20260906`; preserve prior
planning and Steps 1–2. Plan-mode switching is unavailable, so this written
plan follows research in Default mode before implementation.

1. Replace word-boundary enumeration in `reader_format/reflow.py` with the
   Step 2 helper's complete mode. Check retained prefixes and candidates with
   `is_unsafe_summary_value`, stepping back to earlier canonical boundaries.
   Strip old continuation suffixes before scanning, never fabricate punctuation,
   and append one continuation only when original content was omitted.
2. Reuse the existing continuation predicate for short residue. Preserve valid
   short noun headings and complete continuations. Preserve original values
   with canonical `markdown.href_ellipsis` / `markdown.unmatched_link` findings
   verbatim for their existing repair owner, even if over the summary cap.
3. Use `FALLBACK_BY_PREFIX` for conclusion/driver and the existing TL;DR
   fallback. Leave caution's dedicated behavior untouched.
4. Replace the broad header bullet/residual scan with a single owned-line
   traversal: callouts in the preamble, list/plain TL;DR lines after its header,
   and stop at the next H2. Preserve tables, fenced code, diagnostics/details,
   metadata and all body/footer bytes. Reuse existing marker/fence helpers.
5. Convert the nine strict target failures to normal assertions after they pass
   without altering archived inputs or expected outputs. Update superseded u71
   word-boundary expectations and add safety/ownership/seeded PBT regressions.
6. Run scoped and publisher-wide tests, static checks, and independent review;
   record the outcome without publishing, committing or pushing.

## Remaining boundaries

Step 4 owns canonical scanner rejection of residual continuation defects.
Step 5 owns post-summary-repair finalizer ordering; Step 6 owns final Markdown
and notification acceptance. This step does not claim those contracts complete
or amend u150's link disposition. Traceability: u153 Contracts 1–6/8,
FR-002/004/009 and NFR-003/005/006; Partial PBT applies.

## Implementation

`bound_summary_snippet` now reserves the existing continuation budget, removes
old trailing continuation suffixes, and requests complete candidates from
`bound_at_sentence`. Candidates must pass the existing summary-safety predicate;
unsafe Markdown/ellipsis/particle endings roll back to earlier boundaries on
the original input. There is no new sentence splitter or grammar scanner.
Short valid headings and already-valid complete continuations remain unchanged.
No safe sentence returns the existing empty sentinel, interpreted at callers
as the canonical conclusion, driver or TL;DR fallback. Caution is unchanged.

The owned-line traversal handles preamble callouts and list/plain TL;DR values,
ending at the next H2 (including empty or repeated TL;DR headers). It preserves
the original line endings and unaffected body/footer bytes. Existing fence and
newline helpers are reused. Tables, metadata, nested details, indented code,
fenced code, images and reference definitions are not summary prose.

Original link defects take precedence over the local length cap: values with
`markdown.href_ellipsis` or `markdown.unmatched_link` are handed back unchanged.
The existing scanner runs in both bare and canonical-callout contexts so it
recognizes anchored reference definitions and pipe-leading callout/list values.
A synthetic section marker bounds this private scan to the entire value,
avoiding its unrelated 1,600-character no-anchor fallback. Neither the marker
nor the synthetic prefix is emitted. Actual reference-definition lines are
preserved as structure, including valid targets used by body reference links.

## Test changes and provenance

- Step 1's 14 inputs and literal expected outputs remain unchanged. Nine
  `pending` fields are now null and every target runs without xfail. The three
  archive extracts and baseline SHA are unchanged.
- The u153 test module now has 123 cases: the previous 29 plus 94 new cases,
  including a 100-example seeded long-summary property. Existing short-value
  PBT and all 14 non-summary/idempotence checks remain in place.
- Eight u71 word-boundary expectations were superseded by complete-sentence
  or fallback expectations; the numeric-emphasis regression now supplies a
  complete sentence before the unsafe emphasized tail. Helper return annotations
  now use `SurfaceQualityIssue`, fixing the pre-existing scoped mypy mismatch.
- In `tests/fixtures/u144/first-viewport-truncation-family.json`, only two
  `current_reflow_output` fields changed to the canonical conclusion fallback.
  Historical before/after inputs, expected issue codes and pre-u144 evidence
  remain unchanged. The caution current-output expectation is unchanged.

## Independent review and corrections

Initial review found a High link-preservation issue caused by stripping the
original line context, and a Medium ownership issue where indented code headings
ended TL;DR early. Follow-up review exposed related anchored-reference,
1,600-character scan-window and indented-details-close cases. All were fixed
within Step 3; no global scanner or finalizer policy was changed.

Final independent re-review: Correctness, Safety, Reliability, Maintainability
and Test Coverage all Pass, no remaining findings or debt candidates. The
reviewer ran 273 related tests and 250 input/newline/list variants of the exact
boundary repros. Security Boundary, Performance, Memory and Error Contract
protocols were applied. The empty sentinel still leads to the canonical caller
fallback, original link evidence remains visible, and no I/O or import boundary
was introduced. Candidate rollback is bounded by the existing snippet cap;
the reviewer measured a deliberately extreme 10,000-continuation input without
finding an actionable performance issue.

## Final validation

All commands ran in the isolated worktree with the existing root virtualenv.

```sh
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/_internal/test_text.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher/test_reader_format_reflow_u71.py tests/unit/publisher/test_reader_format_meaning_u76.py tests/unit/publisher/test_bounded_line_rendered_regression_u131.py tests/unit/publisher/test_summary_sentence_extension_u153.py -q --tb=short --hypothesis-seed=15320260907
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/publisher -q --tb=short --hypothesis-seed=15320260907
/Users/user/Desktop/Projects/investo/.venv/bin/mypy src
/Users/user/Desktop/Projects/investo/.venv/bin/mypy --follow-imports=silent tests/unit/publisher/test_summary_sentence_extension_u153.py tests/unit/publisher/test_reader_format_reflow_u71.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff check src/investo/publisher/reader_format/reflow.py tests/unit/publisher/test_summary_sentence_extension_u153.py tests/unit/publisher/test_reader_format_reflow_u71.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff format --check src/investo/publisher/reader_format/reflow.py tests/unit/publisher/test_summary_sentence_extension_u153.py tests/unit/publisher/test_reader_format_reflow_u71.py
git diff --check
```

Final tree: **268 focused tests passed in 6.46s**, **1,169 publisher tests passed
in 31.14s**, no xfails. These suites overlap and their counts are not additive.
Mypy passed all 254 source files and both scoped test files; Ruff/check+format,
fixture JSON and diff integrity passed. A supplemental briefing/notifier/
orchestrator/integration run passed 1,569 tests in 308.54s; it started before
the final link-context/definition corrections, so it is not cited as an
exact-final-tree gate. A full repository suite and live publication were not run.

## PBT compliance — Partial mode

| Rule | Evidence |
|---|---|
| PBT-02 | N/A: lossy bounding has no inverse/serialization pair. |
| PBT-03 | Pass: output cap, complete retained prefix, one continuation, canonical safety, idempotence and unaffected-region bytes. |
| PBT-07 | Pass: finite two-place decimal values, plain/bold/link sentences, four summary surfaces, bounded overflow tails. |
| PBT-08 | Pass: seed `15320260907`, 100-example long and 60-example short properties, shrinking enabled, `print_blob=True`, normal pytest collection. |
| PBT-09 | Pass: existing Hypothesis/pytest; no dependency or CI change. |

No blocking PBT finding, ADR or new technical-debt item. The original dirty
workspace, independent worktrees, archive/site/workflow/debt paths and prior
planning/Step 1–2 changes are preserved. All work remains uncommitted.
