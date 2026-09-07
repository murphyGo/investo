# u153 Code Generation Step 5 — Final assembly ordering

**Date**: 2026-09-07 KST
**Status**: Step 5/6 complete; Step 6 final Markdown/notification acceptance next
**Baseline**: `d5530353758b6475cf0852c69ea9b9b3cfd99e0b`

## Approved bounded plan

The user's `진행시켜` approves Step 5 announced after Step 4. Continue in
`/private/tmp/investo-briefing-review-20260906`, preserving earlier work and
the dirty original root. Plan-mode switching is unavailable; research and
this written plan precede implementation in Default mode. Debt dashboard
has no Critical/High/Medium escalation. Partial PBT remains enabled.

1. Expose the existing owned summary-line traversal as a publisher helper;
   reuse it from the original reflow call and the phase-one presentation
   assembler. Do not invoke the full reflow/layout-reordering pipeline again.
2. Invoke it immediately after `repair_first_viewport_summary`, before
   evidence accounting and layout reindex. The late pass targets only
   conclusion/driver/TL;DR; explicit final-assembly mode preserves the old
   reflow default while leaving caution unchanged at this new call site.
3. Add regressions proving repair-generated overflow is bounded, both list
   and plain TL;DR values are covered, short/decimal/Markdown values remain
   safe, and caution/body/diagnostics are unchanged by the late pass.
4. Trace the real downstream accounting/projection/containment/validation
   path and test that it cannot regrow an over-budget callout before seal.
   Preserve simultaneous original link findings and every existing hard gate.
   A composition repro showed the new late pass could erase a trace finding
   deliberately retained by Step 4 repair. Opt this call into preserving all
   non-summary blockers in the existing snippet guard; leave the original
   reflow default unchanged. Reuse the guard's bare/prefixed full-value scans,
   not a new scanner or disposition rule.
   Independent live-path review also reproduced an 83-character original
   summary becoming 96 characters when repair exposed `price missing` and
   later canonical projection expanded it. Final-assembly mode applies the
   existing public-label projector to owned non-caution values before bounding,
   only when no simultaneous hard/link blocker is present. The later canonical
   projection is then idempotent on those values. No second post-validation
   pass, new label grammar, global projection order or policy is introduced.
5. Run example-based and seeded property tests, scoped and broad gates,
   independent skill-mandated review, then update only Step 5 records.

Traceability: u153 Contract 7 and AC-153.1/2/4/6; FR-002/004/009,
NFR-003/005/006. No new summary generator, cap, disposition, dependency,
external I/O, layout order, sealed-byte mutation, commit/push or publication.
Step 6 still owns comprehensive final Markdown/notification acceptance and
unit closeout; this step proves the bounded invocation ordering only.

## Implementation and ordering

`reader_format/reflow.py::bound_first_viewport_summary_lines` exposes the
existing owned-line traversal and is re-exported by `reader_format`. Original
reflow uses its unchanged default. Only phase-one presentation opts into
`final_assembly=True`, immediately after canonical summary repair and before
evidence accounting/layout reindex. This mode skips caution and leaves
layout, body, protected diagnostics and footer handling with their owners.

The existing snippet guard still preserves malformed links. Final-assembly
mode additionally preserves other non-summary blockers before any local
transformation. It resolves eligible public labels using the existing
`first_forbidden_public_evidence` / `project_public_quality_language` pair,
then applies the same sentence/cap/fallback algorithm. The canonical predicate
is important: a scanner-protected phrase can coexist with a raw public label,
and the later projector still recognizes that label. No alternative regex,
projector, issue family or disposition table was added.

The real finalizer ordering regression wraps, but does not replace, accounting,
projection, containment, terminal validation and sealing. It injects a long
summary-repair result and asserts the bounded value remains unchanged through
each later phase and that sealing copies the validated bytes exactly.
Separate real-input regressions cover repair unmasking a public label that
would otherwise expand after the authoritative bound. Other later writers
still exist (including canonical fixed fallbacks and secondary summary repair);
the claim is that these tested successfully prepared values do not regrow,
not that the lifecycle contains no subsequent text writers.

## Regression evidence and review corrections

- Before implementation, new ordering/cap tests produced **14 failures and
  1 pass**. Those target assertions are now ordinary passing tests.
- A new late pass initially erased the trace in
  `| input_hash=redacted 기관의 본문 참고.` that canonical repair retained.
  The final-assembly guard now preserves simultaneous trace, matcher, numeric
  emphasis and link findings, including pipe-leading and long values.
- Independent review reproduced an actual **83-character input sealing as
  a 96-character conclusion**: balanced Markdown hid `price missing` until
  summary cleanup, then later public projection expanded it. The existing
  projector now runs before late bounding on eligible owned values.
- Protected-phrase variants showed why the projection trigger must use the
  projector's canonical predicate instead of scanner issue membership.
  Six real finalizer cases and a seeded property pin this ordering correction.

## Partial PBT compliance

Two new 60-example properties use seed `15320260907`, shrinking enabled and
`print_blob=True`. The first generates realistic finite two-decimal values,
four summary surfaces and bounded overflow tails, checking cap, complete
retained sentence and repeated assembly identity. The second generates
Markdown-hidden public-label fragments, sentence counts and protected-phrase
variants, checking that subsequent canonical projection is a no-op on the
bounded output and repeated assembly stays stable.

PBT-03/07/08/09: compliant. PBT-02: N/A for lossy projection/bounding; no new
inverse or serialization pair. Existing helper/formatter PBT remains in the
gates. No dependency or CI change.

## Final validation and review

- **54 new test cases** (including two seeded properties) added to the
  existing assembly test module; no xfails or historical fixture rewrites.
- Exact final focused gate: **186 passed in 3.61s**.
- Exact final publisher/briefing/internal/_internal gate:
  **2,493 passed in 57.32s**. Suites overlap; counts are not additive.
- Mypy: **254 source files**, **1 changed test module**; Ruff/check+format:
  **4 changed Python files**; `git diff --check` passed.
- Independent review: Correctness, Safety, Reliability, Maintainability and
  Test Coverage all **Pass**, no remaining finding or debt candidate.
  Reviewer ran **238 related tests** and **216 real-finalizer combinations**
  (two callouts, three masked public fragments, three protected-text variants,
  twelve lengths), checking cap, projection idempotence and sealed SHA equality.
  Error Contract, Security Boundary, Performance and Memory protocols applied.

Commands ran in the isolated worktree with the existing root virtualenv:

```sh
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/publisher/test_public_document_assembly_u144.py tests/unit/publisher/test_summary_sentence_extension_u153.py tests/unit/publisher/test_bounded_line_rendered_regression_u131.py -q --tb=short --hypothesis-seed=15320260907
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/publisher tests/unit/briefing tests/unit/internal tests/unit/_internal -q --tb=short --hypothesis-seed=15320260907
/Users/user/Desktop/Projects/investo/.venv/bin/mypy src
/Users/user/Desktop/Projects/investo/.venv/bin/mypy --follow-imports=silent tests/unit/publisher/test_public_document_assembly_u144.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff check src/investo/publisher/public_document.py src/investo/publisher/reader_format/reflow.py src/investo/publisher/reader_format/__init__.py tests/unit/publisher/test_public_document_assembly_u144.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff format --check src/investo/publisher/public_document.py src/investo/publisher/reader_format/reflow.py src/investo/publisher/reader_format/__init__.py tests/unit/publisher/test_public_document_assembly_u144.py
git diff --check
```

Earlier intermediate broad results (2,462/2,478) preceded review corrections;
only the final 2,493-test gate is the exact final-tree claim. No full repository
or live pipeline run. Step 6 comprehensive final-output acceptance remains
open. No ADR is needed for this same-owner ordering correction. Original dirty
root and earlier work were rechecked preserved. No archive/site/workflow/debt
edit, commit, push, deployment or notification; changes remain uncommitted.
