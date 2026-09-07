# u153 Code Generation Step 2 — Optional complete-boundary mode

**Date**: 2026-09-07 KST
**Status**: Step 2/6 complete; Step 3 summary-caller migration next
**Baseline**: `d5530353758b6475cf0852c69ea9b9b3cfd99e0b`

## Approved implementation plan

The user replied `진행시켜` after the Step 1 completion report identified
Step 2 as the next target. Continue in the existing isolated worktree
`/private/tmp/investo-briefing-review-20260906` and preserve all prior changes.
Plan-mode switching is unavailable in this session; research and this bounded
implementation plan precede source edits in Default mode.

1. Add keyword-only `require_complete: bool = False` to the existing
   `_internal/text.py::bound_at_sentence`. Only the fitting-input shortcut
   becomes conditional; reuse the existing decimal-safe terminator and scan.
2. With the option true, even a short input must have a complete terminator
   within the cap. Return the last matching prefix or `None`; trailing
   unfinished text and whitespace are omitted by the existing scan semantics.
   With the option false or omitted, preserve exact old behavior.
3. Extend `tests/unit/_internal/test_text.py` with short/empty/whitespace,
   exact-cap/non-positive-cap, multiple-sentence and decimal examples, plus
   seeded domain-specific properties for caps, last-boundary selection,
   prefix preservation, idempotence and default compatibility.
4. Run helper and existing publisher/summary regressions, Ruff/format and mypy;
   obtain separate fresh-eyes review before marking Step 2 complete.

## Ownership boundary

The helper recognizes the existing syntactic terminator; it does not certify
Korean grammar or Markdown validity. Canonical summary-safety checks, stepping
back from unsafe Markdown candidates, continuation suffixes and per-surface
fallbacks remain with the summary caller in Step 3 and scanner in Step 4.
No existing caller opts in during Step 2. Step 1's nine strict expected
failures stay in place; final-output acceptance criteria remain open.

## Traceability

u153 Fixed Contract 3; FR-002/004/009, NFR-003/005/006. The optional argument
preserves the existing caution/meaning consumers and module DAG. No new
dependency, external call, cost, secret, publication or historical rewrite.

## Implementation and verification

Only `src/investo/_internal/text.py` and `tests/unit/_internal/test_text.py`
are changed in the production/test slice of this step. The helper's only
behavioral change is conditioning the fitting-input shortcut on
`not require_complete`; no regex, scan, return sentinel or caller was replaced.

Twenty-nine new collected test cases cover seven default byte-preservation
cases, sixteen forced-boundary cases, four existing terminators and two
properties. The properties generate realistic finite two-place decimals with
plain/bold/link formatting and complete sentences; a generated-prefix oracle
checks the last fitting boundary independently of the production regex.

All commands ran in the isolated worktree, reusing the root virtualenv with
`PYTHONPATH=src` for test imports.

```sh
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/_internal/test_text.py -q --tb=short --hypothesis-seed=15320260907
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/_internal/test_text.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher/test_reader_format_reflow_u71.py tests/unit/publisher/test_reader_format_meaning_u76.py tests/unit/publisher/test_bounded_line_rendered_regression_u131.py tests/unit/publisher/test_summary_sentence_extension_u153.py -q --tb=short -r fX --hypothesis-seed=15320260907
/Users/user/Desktop/Projects/investo/.venv/bin/ruff check src/investo/_internal/text.py tests/unit/_internal/test_text.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff format --check src/investo/_internal/text.py tests/unit/_internal/test_text.py
/Users/user/Desktop/Projects/investo/.venv/bin/mypy src
/Users/user/Desktop/Projects/investo/.venv/bin/mypy --follow-imports=silent tests/unit/_internal/test_text.py
git diff --check
```

Results: helper **54 passed in 1.71s**; focused gate **165 passed, 9 xfailed
in 3.48s**; Ruff/check+format, all-source mypy (**254 files**), scoped test
mypy and diff check passed. The expected failures are the same pre-fix Step 1
targets; this step does not claim the summary-surface fix is complete.

## PBT compliance — Partial mode

| Rule | Status and evidence |
|---|---|
| PBT-02 | N/A: sentence bounding is lossy and has no inverse/serialization pair. |
| PBT-03 | Pass: generated-prefix selection, cap, prefix bytes, idempotence and default equivalence. |
| PBT-07 | Pass: reusable market-sentence strategy, bounded two-place decimals, safe Markdown and four terminators; cap range includes -1, 0 and fitting/overflow cases. |
| PBT-08 | Pass: seed `15320260907`, 100/60 examples, `print_blob=True`, shrinking enabled; normal pytest collection includes both properties. |
| PBT-09 | Pass: existing Hypothesis/pytest dependencies, no framework or CI change. |

There are no blocking PBT findings. Existing text and Step 1 preservation
properties also pass. No stateful behavior or new serialization was introduced.

## Review and handoff

Independent review approved Correctness, Safety, Reliability, Maintainability
and Test Coverage with no findings or debt candidates. It independently ran
54 helper tests and scoped Ruff/check+format. A read-only exploratory check
compared 37,459 inputs across 294,391 input/cap combinations with the HEAD
implementation for default/explicit-false equivalence and a non-regex oracle
for forced mode. Prefix, cap and idempotence checks passed, including Unicode
whitespace/digits, Markdown-shaped text and adjacent punctuation. A positional
third argument correctly raises `TypeError`.

The Performance protocol found no issue: production scanning remains linear
with one module-level regex and no accumulated collection; the test oracle's
nested prefix construction is bounded to four generated sentences. No other
protocol trigger applies to the changed scope.

Step 3 will migrate conclusion/driver/TL;DR
callers while retaining canonical summary-safety and malformed-link ownership.
Do not interpret `require_complete=True` alone as validation of complete Korean
thoughts or Markdown; it returns a syntactic candidate for the caller to check.
Archive, site, workflow and technical-debt paths remain unchanged. No full
repository suite, live publication, commit or push is claimed.
