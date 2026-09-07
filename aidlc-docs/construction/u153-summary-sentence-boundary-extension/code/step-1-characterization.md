# u153 Code Generation Step 1 — Sentence-boundary characterization

**Date**: 2026-09-07 KST
**Status**: Step 1/6 complete; production behavior is not fixed
**Baseline**: `d5530353758b6475cf0852c69ea9b9b3cfd99e0b`
**Worktree**: `/private/tmp/investo-briefing-review-20260906`
**Branch**: `codex/briefing-review-20260906`

## Authorization and scope

The user replied `진행시켜` to the proposal to execute u153 Code Generation
Step 1. This step adds fixtures and characterization tests only. Steps 2–6,
production changes, historical output rewrites, publishing, and commit/push
are not part of this execution.

The existing u151–u154 planning changes remain in this isolated worktree.
The original dirty workspace and the separate u145/u150 worktrees are untouched.

## Fixture and test contract

`tests/fixtures/u153/summary-sentence-boundary.json` records the baseline SHA,
source date and exact source path/line. Its three archived values were checked
verbatim against the baseline archives:

- Domestic September 4 conclusion, line 16: `매수세가 본문 참고.` residue.
- Domestic September 4 driver, line 17: `기관의 본문 참고.` residue.
- Crypto September 4 conclusion, line 15: `이번 문서는 본문 참고.` residue.

Eleven synthetic cases cover short valid sentences, a short noun-phrase driver,
a valid continuation, decimal/bold/link preservation, long complete sentences,
unbulleted TL;DR, missing sentence boundaries and an overlong first sentence.
Synthetic links use `example.invalid` and are never fetched. Expected outputs
are literal target contracts, not snapshots that bless the defective output.

`tests/unit/publisher/test_summary_sentence_extension_u153.py` exercises the
existing `reflow_first_viewport` boundary:

- Five target controls pass. Nine target assertions have explicit owning-step
  reasons and `xfail(strict=True, raises=AssertionError)`; an unexpected pass
  fails the suite and missing-target/setup errors are not accepted as xfails.
- All fourteen cases independently assert byte preservation of the next-H2
  macro block, table, body evidence and disclaimer, plus reflow idempotence.
  These assertions are not marked xfail.
- One seeded, 60-example Hypothesis property generates finite two-place
  decimals on conclusion, driver, bulleted TL;DR and plain TL;DR surfaces.
  It checks short-value identity, the existing cap, idempotence and tail bytes.

No acceptance criterion for implemented production behavior is marked complete.
Finalizer/notification and complete/partial-bundle coverage belongs to Steps 5–6.

## Property-based testing compliance

The repository's Partial PBT mode applies to this step.

| Rule | Step 1 evidence |
|---|---|
| PBT-02 | No new production serializer/deserializer pair; not applicable. |
| PBT-03 | Finite, two-place market-like decimal values and four owned summary surfaces. |
| PBT-07 | The new preservation invariant has Hypothesis coverage; the existing text-helper PBT also runs. |
| PBT-08 | Hypothesis shrinking remains enabled; `print_blob=True` preserves replay guidance. |
| PBT-09 | Fixed seed `15320260907`, 60 examples, no wall clock, network or external state. |

Steps 2–3 must extend properties for complete-boundary selection, length caps
and idempotence as production behavior is added.

## Validation

Commands ran from the isolated worktree using the existing root virtualenv;
`PYTHONPATH=src` was verified to import this worktree's source.

```sh
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/publisher/test_summary_sentence_extension_u153.py tests/unit/publisher/test_reader_format_reflow_u71.py tests/unit/publisher/test_bounded_line_rendered_regression_u131.py tests/unit/_internal/test_text.py -q --tb=short -r fX --hypothesis-seed=15320260907
```

Final result after review correction: **73 passed, 9 xfailed in 1.82s**, exit 0.

```sh
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/publisher/test_summary_sentence_extension_u153.py -k target_contract --runxfail -q --tb=no -r f --hypothesis-seed=15320260907
```

Diagnostic result: **9 failed, 5 passed, 15 deselected in 0.78s**, exit 1 as
expected. The nine failures exactly match the cases with pending Step 3
reasons. This demonstrates the pre-fix gaps; it is not a failed release gate
or evidence of a completed fix.

Scoped Ruff check, Ruff format check and mypy with `--follow-imports=silent`
passed for the new Python module. The fixture parses as JSON. No source,
archive, site, workflow or technical-debt file changed. A full repository
gate and live publication were not run for this test-only step.

## Fresh-eyes review

An independent reviewer found no blocking correctness, safety, reliability or
maintainability defect. One Low coverage finding requested a long non-list
macro paragraph between the next `## ⓪` H2 and `## ①` to catch TL;DR processing
that crosses its owning block. The paragraph now exceeds 90 characters and
is included in the exact tail-preservation assertions. Independent re-review
confirmed the finding resolved with no additional findings.

## Handoff

Next: Step 2, extend `_internal/text.py::bound_at_sentence` with optional
`require_complete=False` while preserving default behavior. Remove each strict
xfail only when its owning implementation makes the target assertion pass;
do not change expected values merely to match the old word-boundary output.
No ADR or technical-debt entry is needed: the known failures are already
tracked by the approved u153 implementation plan.
