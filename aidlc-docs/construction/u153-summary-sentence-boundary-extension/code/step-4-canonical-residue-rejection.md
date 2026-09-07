# u153 Code Generation Step 4 — Canonical residue rejection

**Date**: 2026-09-07 KST
**Status**: Step 4/6 complete; Step 5 post-repair finalizer ordering next
**Baseline**: `d5530353758b6475cf0852c69ea9b9b3cfd99e0b`

## Approved bounded plan

The user's `진행시켜` approves the Step 4 announced after Step 3. Research
and this written plan run in Default mode because Plan-mode switching is
unavailable. Preserve the isolated worktree's earlier planning and Steps 1–3.

1. Opt the existing continuation predicate into the existing decimal-safe
   complete-boundary helper. Keep its default caution behavior unchanged.
   Reject missing retained sentences, ellipsis, duplicate continuation and
   the archived incomplete-clause tails; do not add a grammar validator.
2. Apply this predicate in the existing surface scanner only to preamble
   conclusion/driver and owned first-TL;DR list/plain values. Track ownership
   within that scanner, preserving body, structural and protected regions
   and every existing unrelated issue check/code.
3. Apply the same predicate directly in the canonical summary-value gate,
   retaining the existing surface-quality error contract. Caution's typed
   validation/repair keeps its old behavior. Canonical repair must not erase
   terminal punctuation to make a rejected continuation pass accidentally.
   Review traced the shared predicate into `briefing/_assembly/summary_extraction.py`:
   a keyword-only compatibility flag must also be passed by its caution caller
   to retain pre-u153 extraction behavior. This is a necessary compatibility
   adapter, not a new caution algorithm or finalizer-ordering change.
4. Test incident shapes, valid short headings/complete decimal/Markdown
   sentences, protected/body ownership, original link findings and repair
   stability; add seeded domain-specific properties with shrinking.
5. Run focused/broad regression and static gates, then the skill-mandated
   separate fresh-eyes review. Record exact results and update only Step 4.

Traceability: u153 Contracts 4/6/7/8, AC-153.2–6; FR-002/004/009 and
NFR-003/005/006. Partial PBT remains active. No finalizer ordering change
(Step 5), final-output acceptance (Step 6), new dependency/I/O, publication,
commit or push is authorized in this step.

## Implementation and compatibility

The existing `looks_truncated_caution_continuation` accepts an optional
`require_complete=False`; strict summary calls reuse `bound_at_sentence` and
reject empty retained text, ellipsis, repeated suffixes and incomplete tails.
No new sentence splitter, grammar rules, issue code or exception was added.
Canonical summary validation maps the new predicate to its existing
surface-quality error. Typed caution validation and the caution producer
explicitly retain the legacy predicate; non-caution callers default strict.

The existing scanner now carries a small ownership state across its existing
viewport/body passes. Only preamble conclusion/driver and first-TL;DR values
enter the new check. Whitespace-compatible callouts/H2s, code fences, indented
code, nested details, references, metadata and protected phrases follow the
existing formatter's boundaries. Legacy unrelated issue checks and their
scan-window behavior are unchanged. At an artificial 1,600-character split,
only the new predicate receives the full crossing line once, with original
evidence. New summary-only findings retain `segment_first_viewport` so E3's
existing region ownership filter cannot mistake them for bounded body rules.

For newly rejected continuation residue, canonical repair uses the existing
per-surface fallback instead of stripping the terminal dot into an apparently
valid fragment. If the value also carries another canonical blocking finding,
it stays verbatim for its existing owner. Bare and full anchored-callout scans
preserve reference-link, pipe-leading, long-link and trace evidence. This
branch does not change ordinary legacy repair or any disposition table.

## Review corrections

The independent review and local repros identified and corrected:

- Protected disclaimer/diagnostic phrases being treated as summary prose.
- Tab/NBSP H2 boundaries, malformed backtick info strings and whitespace
  callout spellings diverging from formatter ownership.
- Missing continuation evidence at a 1,600-character split, and later
  summary findings being misclassified as E3 bounded-body findings.
- New fallback erasing simultaneous pipe-leading link/trace findings.
- Shared strict validation changing the caution producer's historical output.

Corrections are covered by direct scanner/summary tests and the existing
u144 containment test harness. No finalizer production code changed.
The reviewer independently compared 840 non-target documents with the
baseline scanner and found exact `(code, severity, evidence, region)` parity.

## Validation plan and PBT

Final focused gate includes the previous u153 helper/caller gates plus
summary extraction/fidelity and actual E3 containment. The broad gate covers
all publisher, briefing, internal and `_internal` unit tests. Static gates
cover all 254 source files and three changed test modules; no fixture rewrite,
dependency, workflow, archive, site or debt change is needed.

Two new 80-example seeded properties generate realistic finite two-decimal
values, plain/bold/link sentences, archived fragment families and TL;DR
markers. They assert strict safe/unsafe classification, canonical fallback
stability and non-summary scope. Seed `15320260907`, shrinking enabled,
`print_blob=True`, ordinary pytest collection. PBT-03/07/08/09 apply and
PBT-02 is N/A (no inverse/serialization pair). Existing Steps 1–3 properties
remain in the gates.

## Final validation and sign-off

- Added **154 tests**, including two 80-example seeded properties, across
  the existing surface, summary and u144 containment modules. No xfails.
- Final focused gate: **492 passed in 9.93s**.
- Final publisher/briefing/internal/_internal gate: **2,439 passed in 61.50s**.
  The focused and broad suites overlap; their counts are not additive.
- All-source mypy: **254 files**; scoped test mypy: **3 files**.
- Ruff/check+format: **6 changed Python files**; `git diff --check` passed.
- Independent final review: Correctness, Safety, Reliability, Maintainability
  and Test Coverage all **Pass**, no remaining finding or debt candidate.
  Reviewer ran **346 related tests**, repeated the **840-document** legacy
  oracle and tested E3 body ownership at **7 lengths**. Security Boundary,
  Error Contract, Performance and Memory protocols applied.

Commands ran from the isolated worktree using the existing root virtualenv:

```sh
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/_internal/test_text.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher/test_reader_format_reflow_u71.py tests/unit/publisher/test_reader_format_meaning_u76.py tests/unit/publisher/test_bounded_line_rendered_regression_u131.py tests/unit/publisher/test_summary_sentence_extension_u153.py tests/unit/publisher/test_public_document_containment_u144.py tests/unit/briefing/test_summary_extraction_surface_quality.py tests/unit/briefing/test_summary_fidelity.py -q --tb=short --hypothesis-seed=15320260907
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/publisher tests/unit/briefing tests/unit/internal tests/unit/_internal -q --tb=short --hypothesis-seed=15320260907
/Users/user/Desktop/Projects/investo/.venv/bin/mypy src
/Users/user/Desktop/Projects/investo/.venv/bin/mypy --follow-imports=silent tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher/test_public_document_containment_u144.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff check src/investo/_internal/surface_quality.py src/investo/_internal/summary_quality.py src/investo/briefing/_assembly/summary_extraction.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher/test_public_document_containment_u144.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff format --check src/investo/_internal/surface_quality.py src/investo/_internal/summary_quality.py src/investo/briefing/_assembly/summary_extraction.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher/test_public_document_containment_u144.py
git diff --check
git diff --exit-code -- src/investo/publisher/public_document.py
```

No full repository suite or live pipeline was run. Step 5 ordering and Step 6
final Markdown/notification acceptance remain open. No ADR is warranted for
this existing-contract compatibility extension. Original dirty root status
was rechecked unchanged; earlier planning/Steps 1–3 and independent worktrees
are preserved. No fixture, archive, site, workflow or debt file was changed
in Step 4. All work remains uncommitted; no push, deployment or send occurred.
