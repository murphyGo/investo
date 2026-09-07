# u153 Code Generation Step 6 — Final-output acceptance

**Date**: 2026-09-07 KST
**Status**: Complete — Step 6/6; Code Generation complete, cross-check pending approval
**Baseline**: `d5530353758b6475cf0852c69ea9b9b3cfd99e0b`

## Approved bounded plan

The user's `진행시켜` approves Step 6 identified in the Step 5 handoff.
Continue in `/private/tmp/investo-briefing-review-20260906`, preserving all
earlier planning/implementation and the dirty original root. Plan switching
is unavailable; research and this written plan precede edits in Default mode.
There is no Critical/High/Medium debt escalation. Partial PBT applies.

1. Extend the existing u153 regression module with a typed synthetic
   three-segment context and complete seven-section documents. Exercise
   `finalize_public_bundle` without stubbing any production phase or gate.
   Reuse the fourteen original characterization cases and literal expectations.
2. Assert sealed Markdown values, the derived `PublicNotificationSummary`,
   SHA-256, repeated finalization and input immutability. Cover all three
   TL;DR positions, list/plain values, complete and generation-absent bundles,
   empty/no-boundary/overlong-first-sentence fallbacks and valid short headings.
3. Compare equivalent safe-control and target finalizations to isolate the
   summary change from existing reader-format transformations. Preserve
   caution/meaning/title, body evidence, diagnostics and disclaimer bytes.
   Check original link defects and other terminal hard gates with usable
   siblings; do not weaken gates to make synthetic fixtures publishable.
4. Add a bounded seeded property over finite decimals, safe Markdown styles,
   summary surfaces and segments. Assert final cap, complete sentence,
   notification derivation and byte/SHA repeatability. Exercise the existing
   notifier formatter in an integration acceptance test if needed; never send.
5. Run focused, broader and static checks, then a separate skill-mandated
   independent review. Resolve any in-scope acceptance defect with a regression
   before completion. Record all six ACs and PBT compliance with exact evidence.

## Independent-review correction plan

Real finalization exposed a second derived-text boundary: a 77-character
Markdown conclusion containing `price mi**ssing**` becomes 95 characters
when the existing notification cleanup removes emphasis and projects the
newly visible public label. The Markdown late pass cannot detect that raw
label, and the DTO previously had no cap after cleanup.

Reuse `bound_summary_snippet` on the cleaned conclusion **after** the existing
unsafe/public-label checks and before constructing `PublicNotificationSummary`.
Use the existing conclusion fallback when no complete sentence fits. Preserve
the raw valid Markdown bytes, all original hard checks and the watchlist policy.
This is bounded derived-text construction, not a second Markdown writer or a
post-seal rewrite. No generic label-masking policy or public disposition changes.
Add literal three-segment and seeded masked-label regression tests plus an
actual notifier-consumer assertion before marking Step 6 complete.

Traceability: AC-153.1–6; US-002/003/004, FR-002/004/009,
NFR-003/005/006. No new cap, layout, generator, scanner, public disposition,
dependency, I/O or live publication. No commit/push, next-unit implementation
or automatic cross-check/global Build and Test approval is inferred.

## Implementation and acceptance evidence

The only Step 6 production change is in
`publisher/public_document.py::_derive_public_notification_summary`. Existing
cleaned-value safety/public-label rejection still runs first. Only a safe
cleaned conclusion longer than the existing `SNIPPET_MAX_CHARS` enters the
existing sentence helper; no fitting sentence uses the canonical conclusion
fallback. Watchlist extraction, validation witnesses, seal factory and every
Markdown producer remain unchanged in this step.

For ordinary values, the DTO remains exactly the canonical cleaned Markdown
conclusion. When cleanup expands a masked label beyond 90 characters, the DTO
is a complete bounded prefix of that cleaned text, or the existing fallback.
The original valid in-cap Markdown is not rewritten to match the shorter DTO.
The literal 77-to-95-character case now emits an **82-character** DTO while
preserving all 77 original Markdown characters. This is distinct from Step 5's
repair-exposed Markdown projection regression.

Added **72 cases**: 66 in the existing u153 unit module and 6 in the existing
reader-format integration module. Two of the unit tests are seeded 60-example
properties; Hypothesis examples are not counted as additional pytest cases.
No original incident input/expectation, historical fixture or old assertion
was changed to accept a failure.

| Acceptance | Evidence |
|---|---|
| AC-153.1 | Real finalizer caps conclusion/driver/TL;DR and derived DTO; all three segments and all three list/plain TL;DR positions; masked-label expansion regression. |
| AC-153.2 | Four-surface overflow, literal complete-prefix/one-continuation and canonical fallback assertions; seeded decimal and masked-label properties. |
| AC-153.3 | Fourteen original incident/boundary fixtures pass through the real finalizer; short driver heading retained; actual notifier message and plain-text fallback exclude all incident tails and the generated-field sentinel. |
| AC-153.4 | Decimal/plain/bold/link controls and generated cases; a spy delegates to the real surface-repair owner and proves original link findings reach it after reflow. |
| AC-153.5 | Empty owned values, no terminator and overlong first sentence use literal fallbacks; complete/partial bundles and derived DTOs repeat with identical Markdown/SHA bytes. |
| AC-153.6 | Safe-control and target finalizations agree on all other bytes; existing u131 caution/meaning/title gates remain in regression; actual trace/numeric/unsafe-cleaned-summary failures preserve usable siblings. |

### Existing policy distinctions

- Empty unbulleted whitespace is a separator, not an owned TL;DR value.
  It does not create a new summary; u154 retains cardinality ownership.
- The short KOSPI 1.20% fixture supplies a typed synthetic `^KOSPI` anchor
  (3,036 versus 3,000). With no anchor, the real numeric gate correctly
  limits that claim. No terminal gate is stubbed to force a text expectation.
- Existing surface repair handles recoverable unmatched-link syntax;
  canonical summary repair can clean callout links. A remaining required
  TL;DR ellipsis target keeps `trust_blocked` / `document.fallback_exhausted`.
  u150's planned residual-code/disposition policy is not implemented here.
- The unsafe-cleaned negative case (86-character Markdown, 100-character
  cleaned value with a hidden matcher fragment) proves **zero** calls to
  DTO bounding, `summary.invalid_conclusion`, and a usable sibling.

## Partial PBT compliance

| Rule | Result and evidence |
|---|---|
| PBT-02 | N/A: lossy bounding and display cleanup have no inverse or new serialization pair. |
| PBT-03 | Pass: final caps, complete retained prefixes, safe canonical fallback, exact ordinary DTO derivation and repeated Markdown/SHA/DTO identity. |
| PBT-07 | Pass: finite two-place decimals, safe Markdown styles, fixed segment/surface domains, bounded sentence/prelude counts and real masked public-label variants. |
| PBT-08 | Pass: seed `15320260907`, shrinking enabled, `print_blob=True`, two 60-example finalizer properties in normal pytest collection; deadline disabled only for the composed real finalizer. |
| PBT-09 | Pass: existing Hypothesis/pytest configuration; no dependency or CI change. |

No blocking PBT finding. Advisory idempotence and complementary literal
regressions are also implemented; there is no state machine change.

## Validation commands and scope

All commands run from the isolated worktree, using its source via
`PYTHONPATH=src` and the existing root virtualenv. No dependency installation,
network, live pipeline, archive write or Telegram send is needed.

```sh
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests/unit/publisher/test_summary_sentence_extension_u153.py tests/integration/test_briefing_reader_format.py -q --tb=short --hypothesis-seed=15320260907
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest tests -q --tb=short --hypothesis-seed=15320260907
/Users/user/Desktop/Projects/investo/.venv/bin/mypy src
/Users/user/Desktop/Projects/investo/.venv/bin/mypy --follow-imports=silent tests/unit/publisher/test_summary_sentence_extension_u153.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff check src/investo/publisher/public_document.py tests/unit/publisher/test_summary_sentence_extension_u153.py tests/integration/test_briefing_reader_format.py
/Users/user/Desktop/Projects/investo/.venv/bin/ruff format --check src/investo/publisher/public_document.py tests/unit/publisher/test_summary_sentence_extension_u153.py tests/integration/test_briefing_reader_format.py
/Users/user/Desktop/Projects/investo/.venv/bin/python -B scripts/check_no_paid_apis.py
git diff --check
```

Exact final focused gate: **202 passed in 6.20s**. Source mypy: **254 files**;
scoped u153 test mypy: **1 file**. Scoped Ruff/check+format, all fifteen u153
Python-file format checks, no-paid guard and diff checks pass.

The existing integration module is not globally mypy-clean: direct scoped
checking reports 20 diagnostics (one private-export `attr-defined`, nineteen
`unused-ignore`). The exact same 20 diagnostics were reproduced from the
unchanged HEAD version in
`/private/tmp/investo-u153-typecheck.iePq6s/test_briefing_reader_format.py`.
These are not new Step 6 regressions or a claimed passing integration type
gate; its new test code adds no diagnostic. No unrelated typing cleanup.

An earlier full run passed **4,776 tests in 468.43s**, but began before the
DTO correction and is only intermediate evidence. A broad publisher/briefing/
internal/_internal/notifier + reader integration run passed **2,733 tests in
107.58s** with the final production code, before the last added negative test.
Counts overlap and are not additive. The exact final full repository run
completed with **4,787 passed in 464.71s (7m44s)**, no failures or xfails.
All production/test edits preceded that run; only closeout documentation
changed afterward. This is a local test gate, not live production acceptance
or an automatic transition of the global Build and Test stage.

## Independent final review

The separate reviewer read the changed files and relevant complete production
paths, reproduced the High notification-expansion defect, and re-reviewed its
fix plus the persistent unsafe-cleaned negative regression.

| Category | Result |
|---|---|
| Correctness | Pass |
| Safety | Pass |
| Reliability | Pass |
| Maintainability | Pass |
| Test Coverage | Pass |

Final reviewer gate: **372 passed in 9.90s** across eight related modules.
Independent exploration covered **216 real-finalizer combinations**, each
run twice, including three segments, six masked-label variants and twelve
lengths. Caps, canonical safety, exact Markdown/SHA bytes and DTO repeatability
passed. The original 77-to-95 case preserves Markdown and emits the exact
82-character conclusion. The 86-to-100 unsafe case invokes bounding zero times
and preserves its blocked status plus the valid sibling.

Error Contract, Security Boundary, Performance and Memory protocols passed.
The source fix runs only for over-cap derived text, has no I/O or accumulated
state and reuses the existing helper/constants/fallback. Final source mypy,
scoped unit mypy, Ruff/check+format and diff checks passed independently.
No remaining finding, new TECH-DEBT candidate or architectural ADR is needed.
The main agent's separate exact-final-tree full suite also passed as above.
All six implementation steps are now complete. Cross-check awaits explicit
approval; do not start another unit or clear u154's integration gates. Original
root/prior work remain preserved; no commit/push/deployment/send occurred.
