# Code Generation Plan: `u153 summary-sentence-boundary-extension`

**Date**: 2026-09-06
**Unit**: u153 summary-sentence-boundary-extension
**Stage**: Code Generation
**Status**: Complete — 7/7; follow-up cross-check APPROVE, production re-verification pending
**Source**: `briefing-review-20260906.md`; September 1–4 callouts/TL;DR
**Estimated Effort**: ~3–5 h
**Dependencies**:
- u71 snippet bounding; u131 sentence helper — complete.
- u61/u127 canonical summary validation/repair; u134 callout composition — complete.
- u144 final assembly/sealed summary — complete.
- u150/u151/u152 are not prerequisites; do not amend their policy.

## Problem Statement

Domestic September 4 conclusion ends `매수세가 본문 참고.`; its driver ends
`기관의 본문 참고.`. Crypto ends `이번 문서는 본문 참고.` and `반등하며
본문 참고.`. These are incomplete thoughts despite a syntactically complete
continuation suffix. `bound_summary_snippet` still uses word boundaries for
conclusion, driver and TL;DR. u131's implemented scope explicitly migrated
only meaning lines, caution and watchpoint titles.

## Goal

Bound the remaining summary surfaces at complete sentences when truncation is
necessary, with canonical fallback when no complete sentence fits. Final
published and notification summary text must satisfy the same rule.

## Existing Coverage / Deduplication

- Extend u131's existing `_internal/text.py::bound_at_sentence` and canonical
  decimal-safe terminator logic. No second sentence splitter.
- u134's heading/driver separator and full-sentence quality suffix remain.
- u61/u127 remain the single unsafe-summary predicate/repair owner.
- u153 owns text bounding only. u154 separately owns title/TL;DR block placement
  and cardinality; no layout reordering in this unit.

## Scope Boundary

In scope: conclusion, driver, three TL;DR item values, their existing short
malformed-continuation residue, and final assembly invocation ordering.
Out of scope: cautious/meaning-line policy changes, watchpoint titles,
new summaries, new token budgets, public diagnostics placement or KPI changes.

## Stage Decision

Functional Design: SKIP — a bounded algorithm extension using existing helpers,
caps and fallback strings; no new entity or public failure disposition.
NFR Requirements: SKIP — deterministic string processing, existing NFR-003/005/006,
no new dependency/I/O/source/secret/LLM/cost.

## Fixed Contracts

1. Keep `SNIPPET_MAX_CHARS = 90`. Count the stripped Markdown value with
   Python `len`, including emphasis/link syntax; prefix/list marker is outside
   the budget. Do not introduce a second visible-width counter.
2. A valid value already within budget and without a malformed continuation
   remains byte-identical, including a short noun-phrase driver heading.
   Overflow or a pre-existing unsafe `본문 참고.` continuation enters
   sentence bounding; do not merely append punctuation to a fragment.
3. Use the existing decimal-safe sentence terminator to retain the last
   complete sentence within `90 - len(" 본문 참고.")`. Add an optional
   `require_complete: bool = False` parameter to `bound_at_sentence` so
   callers can request sentence scanning even for short residue; default
   behavior and existing caution/meaning consumers remain unchanged.
   Candidate boundaries must pass the canonical summary safety predicate.
   If a boundary splits Markdown, step back to an earlier complete boundary.
4. Append ` 本문 참고.` only when some original text was omitted and the
   retained prefix ends at that complete boundary. Already-valid complete
   continuations remain byte-identical. Never emit `...본문 참고.`,
   `기관의 본문 참고.` or a duplicated continuation suffix.
5. No safe complete sentence fitting the budget means:
   conclusion -> `FALLBACK_BY_PREFIX[CONCLUSION_PREFIX]`;
   driver -> `FALLBACK_BY_PREFIX[DRIVER_PREFIX]`;
   TL;DR item -> existing `요약은 본문을 참고하세요.`.
   Caution keeps its existing dedicated fallback.
6. The first-viewport formatter must recognize both existing list items and
   the observed unbulleted TL;DR continuation lines inside the owned
   `한눈에 보기` block. Stop at the next H2; never scan macro tables,
   source diagnostics, body evidence or footer as TL;DR content.
7. Apply one authoritative bounding pass after summary repair in u144 phase-one
   presentation assembly and before body-used accounting/layout reindex.
   Reuse the same publisher helper at older call sites; do not import publisher
   code into `_internal` or mutate any validated/sealed bytes.
   Final summary validation must reject unsafe continuation residue through
   the existing `summary.truncated_mid_token`/summary-safety path.
   Notification cleanup can expand Markdown-hidden public labels; bound that
   derived conclusion with the same helper/cap/fallback after its original
   safety checks and before DTO creation. Preserve valid Markdown bytes;
   ordinary DTOs remain the exact cleaned conclusion, expanded ones retain
   a complete bounded cleaned prefix or the canonical fallback.
8. u150's invalid-link repair and non-presentation hard-gate policy are unchanged.
   This unit must not discard malformed link evidence merely to fit a length
   budget; link findings remain with the existing canonical scanner/owner.

## Implementation Steps

- [x] Step 1 — Add the three archived fragment shapes and synthetic long
  complete sentences, decimal values and emphasized/linked sentences as
  characterization fixtures.
- [x] Step 2 — Extend `_internal/text.py::bound_at_sentence` with the optional
  complete-boundary behavior, preserving the default byte-identity contract.
- [x] Step 3 — Replace word-boundary truncation in
  `publisher/reader_format/reflow.py::bound_summary_snippet`; use fixed
  per-surface fallback at callers and contain unbulleted TL;DR scanning to
  its H2 block.
- [x] Step 4 — Extend the existing summary continuation check in
  `_internal/surface_quality.py` and `_internal/summary_quality.py` only
  to reject this exact residue family. Reuse the existing code;
  do not add a parallel scanner or broad Korean grammar validator.
- [x] Step 5 — Invoke the helper after `repair_first_viewport_summary` in
  `public_document.py::_assemble_phase_one_presentation_briefing`.
  Assert no later writer regenerates an over-budget callout before sealing.
- [x] Step 6 — Validate finalized Markdown and `PublicNotificationSummary`,
  repeated assembly, decimal safety and unrelated-region byte stability.
- [x] Step 7 — Repair the 2026-09-07 US production false-positive path:
  remove generic Korean terminal-syllable inference, classify meaning lines and
  watchpoint titles with owner-specific structural issue codes, contain those
  presentation defects in their indexed region, and prove complete noun endings
  plus genuine truncation through the real finalizer.

## Acceptance Criteria

1. AC-153.1: Conclusion/driver/TL;DR values are at most 90 characters after the
   final assembly path, including emphasis and continuation syntax.
2. AC-153.2: Overflow keeps a complete safe sentence plus one continuation, or
   the specified fallback; no word-boundary fragment is presented as complete.
3. AC-153.3: The three incident tails are absent from both final Markdown and
   notification summaries; short valid driver headings remain unchanged.
4. AC-153.4: Decimal points, links and bold delimiters are not split; preexisting
   link defects still reach their original scanner and disposition.
5. AC-153.5: Empty/no-terminator/first-sentence-too-long inputs produce exactly
   the surface fallback, and repeated repair/bounding is byte-stable.
6. AC-153.6: Caution/meaning/title behavior, non-summary evidence, diagnostics,
   disclaimer and existing terminal hard gates remain unchanged.

## Tests / Validation

Step 1 evidence (2026-09-07 KST): `tests/fixtures/u153/summary-sentence-boundary.json`
contains three verbatim archived callout values and eleven synthetic cases.
`test_summary_sentence_extension_u153.py` pins literal target outputs with
nine strict expected failures until the implementation steps land; five target
controls, fourteen non-summary/idempotence cases and one 60-example decimal
PBT pass. Related u71/u131/text suite: **73 passed, 9 xfailed**. Running only
the target cases with `--runxfail` confirms **9 failed, 5 passed**; this is
pre-fix evidence, not a completed production fix.

Fresh-eyes review found no blocking defect; its Low next-H2 macro-paragraph
coverage request was implemented and re-reviewed with no remaining findings.
Detailed evidence: `aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-1-characterization.md`.
Session: `docs/sessions/2026-09-07-u153-code-generation-step1.md`.

Step 2 implementation evidence (2026-09-07 KST): added keyword-only
`require_complete=False` without changing the existing terminator or callers.
Twenty-nine new test cases (including two seeded properties) bring the helper
module to 54 passing tests. The focused helper/summary/u71/u76/u131/u153 gate
passes **165 tests with 9 expected failures** still owned by Step 3. Ruff/check
and format pass; `mypy src` passes all 254 source files and scoped test mypy
also passes. Independent review approved all five categories with no findings;
294,391 input/cap combinations matched the legacy default and an independent
complete-mode boundary oracle. No production caller opts in yet.
Evidence: `aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-2-sentence-helper.md`.
Session: `docs/sessions/2026-09-07-u153-code-generation-step2.md`.

Step 3 evidence (2026-09-07 KST): conclusion/driver/list and plain TL;DR callers
now use complete safe sentences or the canonical per-surface fallback. All nine
Step 1 target gaps pass as normal assertions with original expected values;
94 additional cases cover safety, ownership and generated decimal/Markdown
invariants. Original link findings and reference definitions remain with their
existing owner, including pipe-leading values and scanner-window crossings.
Final focused gate **268 passed**; publisher-wide gate **1,169 passed**;
Ruff/check+format, all-source mypy (254 files), scoped test mypy and JSON/diff
checks passed. Independent re-review approved all five categories with no
remaining findings after context/ownership corrections. Steps 4–6 and final
Markdown/notification acceptance remain open; no commit/push or live publication.
Evidence: `aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-3-summary-callers.md`.
Session: `docs/sessions/2026-09-07-u153-code-generation-step3.md`.

Step 4 evidence (2026-09-07 KST): the existing continuation predicate and
canonical scanner/summary gate reject incomplete, empty, ellipsis and repeated
continuation residue on owned non-caution summary surfaces. Existing caution
validation and producer behavior are preserved through an explicit compatibility
flag. New fallback preserves simultaneous link/trace findings for their owner;
new summary findings retain E3 viewport ownership across scanner-window splits.
Added **154 cases**, including two seeded properties and actual E3 body controls.
Final focused gate **492 passed**; broad publisher/briefing/internal gate
**2,439 passed** (overlapping suites); mypy 254 source/3 test files, Ruff/check+
format and diff checks passed. Independent final review approved all five
categories with no remaining findings, 346 related tests and exact legacy
scanner parity over 840 non-target documents. No finalizer production change;
Steps 5–6 and final-output AC remain open. No commit/push or live publication.
Evidence: `aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-4-canonical-residue-rejection.md`.
Session: `docs/sessions/2026-09-07-u153-code-generation-step4.md`.

Step 5 evidence (2026-09-07 KST): the shared owned-line helper now runs after
canonical summary repair and before evidence accounting/reindex. Explicit
final-assembly mode preserves caution and other hard/link findings; it reuses
canonical public-label projection before bounding so later projection cannot
expand repair-exposed fragments beyond the cap. Original reflow defaults and
block layout are unchanged. Added **54 cases** including two seeded properties;
real finalizer tests pin accounting-through-seal ordering and the 83-to-96-char
expansion regression. Exact final focused gate **186 passed**; broad gate
**2,493 passed** (overlapping suites). Mypy 254 source/1 test files, scoped
Ruff/check+format and diff checks passed. Independent final review approved
all five categories with no remaining findings, 238 related tests and 216
real-finalizer combinations. Step 6 remains open; no commit/push/publication.
Evidence: `aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-5-final-assembly-ordering.md`.
Session: `docs/sessions/2026-09-07-u153-code-generation-step5.md`.

Step 6 evidence (2026-09-07 KST): **72 new cases** (66 unit, 6 integration)
cover all six ACs through the real finalizer and notifier formatter. Independent
review exposed a 77-character Markdown conclusion becoming a 95-character DTO
after cleanup. The existing helper now bounds safe over-cap derived conclusions
before DTO creation, after all original safety checks; the literal case keeps
Markdown unchanged and emits an 82-character complete summary. An unsafe
86-to-100-character negative case proves zero bounding calls, existing
`summary.invalid_conclusion`, and usable-sibling preservation.
Exact final focused gate **202 passed**; exact full repository gate
**4,787 passed in 464.71s** (overlapping suites). Mypy 254 source/1 unit test
files, scoped Ruff/check+format, all fifteen u153 Python-file format checks,
no-paid guard and diff checks passed. The integration module's 20 scoped mypy
diagnostics are baseline-identical and not a passing gate claim. Independent
final review approved all five categories, 372 related tests and 216 twice-run
finalizer combinations, no remaining findings or new debt. Code Generation
is complete; cross-check awaits approval. No commit/push/live publication.
Evidence: `aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-6-final-output-acceptance.md`.
Session: `docs/sessions/2026-09-07-u153-code-generation-step6.md`.

Cross-check follow-up (2026-09-07 KST): approved by the user's `진행시켜` after
the Step 6 handoff; **APPROVE, 6/6 ACs complete**, no new gap/task/debt. Fresh
publisher/briefing/internal/notifier/integration gate **2,734 passed in 102.06s**;
source/scoped-unit mypy, all fifteen scoped Ruff/check+format files, no-paid and
diff checks pass. The integration module's 20 type diagnostics again match the
byte-verified HEAD baseline; that type gate is not claimed as passing. All three
archive fixture inputs match the baseline source lines. No implementation/test
change, main integration or production action in this cross-check.
Report: `docs/cross-checks/2026-09-07-u153-summary-sentence-boundary-extension.md`.
Session: `docs/sessions/2026-09-07-u153-cross-check.md`.

Step 7 evidence (2026-09-09 KST): removed generic Korean terminal-syllable
inference and assigned structural meaning/watchpoint defects distinct closed
policy codes with indexed regional fallback. Hard numeric/entity/compliance
findings are snapshotted before a mutating surface action can erase evidence;
all actionable codes survive fail-closed aggregation. Link-plus-visible-clipping
is grouped once, while incomplete link punctuation cannot impersonate body
truncation. Real finalizer/sibling/repeatability regressions and an 80-example
seeded property cover safe `기관`/`미 국채` endings and genuine structural defects.
Final related gate **571 passed**; exact full repository gate **5,229 passed in
299.25s**; Ruff 581 files, mypy 254 source files, policy/assets/docs/diff gates
and the final independent review pass. No remaining finding or new debt. The
2026-09-07 cross-check remains evidence for Steps 1–6; a fresh Step 7 follow-up
cross-check and production re-verification remained pending at construction
handoff. The later explicit
delivery request produced implementation commit `c5cdfa48b637f07f4c95afa75c6c992b74251453`
and pushed branch `codex/u153-operational-fix-20260909`; no live publication.
The later explicit main-integration request merged source
`f55e3a446a05b67a36b482e060f8c4286c997308` into current main
`a63f863f44fb62ce81993bcda7ed7d351737273e` without conflict as
`64747390541a7cd5d4eab6ab16651e7c351a9d8b`. The combined tree passes 5,229
full and 571 focused tests plus all workflow/static/docs guards. Production
re-verification and the Step 7 follow-up cross-check remained pending at
integration handoff.
Evidence:
`aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-7-production-incident-followup.md`.
Session: `docs/sessions/2026-09-09-u153-production-incident-followup-step7.md`.
Integration: `docs/sessions/2026-09-09-u153-main-integration-step7.md`.

Step 7 follow-up cross-check (2026-09-09 KST): **APPROVE, 6/6 fixed contracts
Complete**. Current main `71c1db17fab62dde0caf981b909e51c2d6564c4c`
passes a fresh 571-test related gate in 16.69s, full 5,229-test gate in 316.94s,
lock/Ruff/581-file format/source mypy 254/policy/assets/strict-doc checks, and
GitHub Quality run `34309893210` for the same SHA. No new gap, task or debt.
The unpersisted rejected US draft prevents exact-byte incident replay, so live
production re-verification remains pending as a separate operational closeout.
Report:
`docs/cross-checks/2026-09-09-u153-step7-production-incident-followup.md`.
Session: `docs/sessions/2026-09-09-u153-step7-cross-check.md`.

PBT partial mode: Step 1 adds seeded domain-specific decimal/surface preservation
coverage (PBT-03/07/08/09). There is no new production serialization pair
(PBT-02 N/A); existing text-helper PBT remains in the regression gates. Steps 2–6
extend Hypothesis coverage for complete-boundary selection, cap, canonical
safety and idempotence, including final assembly/projection ordering and
comprehensive final Markdown/notification acceptance. Partial enforcement
is compliant with no blocking finding.

- Extend `tests/unit/_internal/test_text.py`,
  `tests/unit/internal/test_surface_quality.py`,
  `tests/unit/briefing/test_summary_quality.py`, and
  `tests/unit/publisher/test_reader_format_reflow_u71.py`.
- Add `tests/unit/publisher/test_summary_sentence_extension_u153.py` using
  u144 finalizer fixtures, three-segment callouts, complete and partial
  bundles, parsed notification summaries and newline/byte-idempotence checks.
- Regress `tests/unit/publisher/test_reader_format_meaning_u76.py` to prove
  default helper compatibility.
- Local gate: `uv run --extra dev pytest tests/unit/_internal/test_text.py tests/unit/internal/test_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher/test_reader_format_reflow_u71.py tests/unit/publisher/test_reader_format_meaning_u76.py tests/unit/publisher/test_summary_sentence_extension_u153.py -q`;
  scoped Ruff/check+format and `uv run --extra dev mypy src`.

## Main Integration Follow-up — 2026-09-08

Source commit `65a1246` is merged with fetched main `6b76fab`, including the
completed u150 contract. Combined full gate **4,950 passed in 494.85s**; focused
u150/u153 gate **709 passed in 19.08s**. Earlier counts remain historical baseline
evidence. Integration preserves u150's shaped link policy and fixes cosmetic
blank/newline removal exposed by u153's repeated-byte tests. Recoverable targets
are repaired and sentence-bounded; residual unmatched syntax retains owned-region
replacement. All quality workflow gates pass locally; exact remote commit/CI
confirmation belongs to the integration handoff. No manual production replay or
notification send. Integration record: `docs/sessions/2026-09-08-u153-main-integration.md`.

## Production Incident Follow-up — 2026-09-09

Scheduled run `34172164168` generated all three segments but trust-blocked US
equity with `summary.truncated_mid_token`; domestic and crypto published in
partial commit `f93def42`, Telegram succeeded, and Pages run `34172964321`
completed. The rejected US bytes were not persisted, but the exact policy path
is reproducible: `_TRUNCATED_DENYLIST_RE = [채확민관]$` classifies complete body
labels such as `미 국채` and `기관` as `segment_body`, while the shared summary
code maps every non-first-viewport owner to `block_segment`.

The user's `개발 진행해줘` approves this bounded follow-up after reviewing the
root solution. Functional Design and NFR Requirements remain skipped: this is
a deterministic owner/policy correction under existing FR-002/FR-009 and
NFR-003/005/006, with no new entity, I/O, source, secret, dependency or cost.

### Step 7 fixed contracts

1. Terminal quality checks must not infer truncation from the last Korean
   syllable. Complete nouns and labels ending in `채`, `확`, `민` or `관` are
   ordinary text unless an explicit structural defect is present.
2. `summary.truncated_mid_token` remains owned by the actual first viewport.
   Meaning callouts and watchpoint titles use distinct machine-readable issue
   codes and retain `segment_body` scanner ownership.
3. Body-owner truncation is limited to observable structural evidence already
   supported by the scanner: ASCII/Unicode ellipsis and unmatched Markdown
   delimiters. An ellipsis attached to content is a clipping marker; a spaced
   standalone `...` retains the existing cosmetic repair path. No Korean
   grammar classifier or replacement suffix heuristic.
4. A meaning defect replaces only its indexed `section_body`; a watchpoint-title
   defect replaces only `watchpoints`. Unexpected owner/code combinations stay
   fail-closed. Numeric, entity, compliance, disclaimer, link and structure
   gates remain unchanged.
5. Finalizer regressions must prove `미 국채` and `기관` do not block a segment,
   genuine ellipsis/unmatched syntax is locally contained, usable siblings and
   sealed-output determinism remain intact, and every issue code is present in
   the closed disposition matrix.
6. Record only bounded code/owner/action metadata. Do not persist rejected
   Markdown or expand logs with evidence text.

## Non-Goals

No general Korean grammar correction, punctuation fabrication, driver-topic
ranking, watchpoint semantic change, layout redesign, historical rewrite,
new quality metric or live publish/send.
