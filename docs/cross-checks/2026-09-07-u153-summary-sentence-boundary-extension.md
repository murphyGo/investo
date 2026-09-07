# Cross-Check: u153 summary-sentence-boundary-extension

**Date**: 2026-09-07 KST

**Checked by**: Codex, `cross-check` skill

**Verdict**: APPROVE — all six u153 acceptance criteria complete; no new gap/debt.

**Approval**: User replied `진행시켜` after the Step 6 handoff proposed this cross-check.

**Validated workspace**: `/private/tmp/investo-briefing-review-20260906`, branch
`codex/briefing-review-20260906`, uncommitted implementation over baseline
`d5530353758b6475cf0852c69ea9b9b3cfd99e0b`.

## Scope and compliance summary

This report checks the u153 conclusion/driver/TL;DR sentence-boundary extension
and its final Markdown/notification contract. It does not certify the entire
project, current remote main, live Telegram delivery, Pages or production output.
No implementation/test changes were made during this cross-check.

| Status | Count | Percentage |
|---|---:|---:|
| Complete | 6 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| Total u153 acceptance criteria | 6 | 100% |

The denominator is AC-153.1–6, not every AC of the parent FRs/NFRs. The mappings
below describe bounded contributions and preserved contracts, not a new claim
that all parent requirements or operational stages have been revalidated.

## Requirements and design traceability

Primary requirements: `docs/requirements.md:45`, `:66`, `:99`, `:319`, `:328`,
`:334`; the inception requirements document remains a reference to that SoT.
Unit scope, fixed contracts, stage decision and ACs are in
`aidlc-docs/construction/plans/u153-summary-sentence-boundary-extension-code-generation-plan.md`.

| Requirement | u153 contribution | Status within scope | Evidence |
|---|---|---|---|
| FR-002 — Korean briefing | Preserve readable summary text, canonical fallback and existing rejection of unsafe output | Complete | `summary_quality.py:57`, `reflow.py:170`; AC-153.1–3/5 |
| FR-004 — public notification | Derive bounded safe summary from finalized Markdown; preserve the existing message limit | Complete | `public_document.py:2659`; integration test at line 401 checks actual Markdown/plain formatter output and ≤4,096 UTF-16 units |
| FR-009 — reader format | Bound existing owned conclusion/driver/TL;DR values; preserve safe Markdown and unrelated regions | Complete | `reflow.py:296`; AC-153.1/4/6. Block order and cardinality repair belong to u154 |
| NFR-003 — reliability | Exact fallbacks, stable repeated finalization, unchanged trust/link policy and usable siblings | Complete | Finalizer tests at lines 562, 594, 633, 679 and 774 |
| NFR-005 — maintainability | Reuse existing helper, 90-character constant, safety predicate and fallbacks; no reverse publisher dependency | Complete | `text.py:22`, `summary_quality.py:57`, `reflow.py:170`; source mypy and all 15 scoped Ruff/check+format files pass |
| NFR-006 — testing | Literal incident fixtures plus unit, real-finalizer, notifier integration and seeded pure-transform properties | Complete | Fresh 2,734-test gate; property tests at lines 708 and 818; no pending fixture cases |

Path shorthand in tables: `text.py` and `summary_quality.py` are under
`src/investo/_internal/`; `reflow.py` is under
`src/investo/publisher/reader_format/`; `public_document.py` is under
`src/investo/publisher/`. Unqualified finalizer test lines refer to
`tests/unit/publisher/test_summary_sentence_extension_u153.py`; the integration
test is `tests/integration/test_briefing_reader_format.py`.

US-002, US-003 and US-004 are traced through briefing summary safety, publisher
assembly and notifier consumption (`stories.md:42`, `:61`, `:80`). C2/C3/C4
component responsibilities remain unchanged (`components.md:47`, `:66`, `:88`).
The early story checklists and execution-plan preview are historical artifacts;
this check does not bulk-close their unrelated criteria. Current per-unit
decisions in the u153 plan and `aidlc-state.md` govern this extension.

Functional Design and NFR Requirements are explicitly SKIP: existing-helper,
deterministic text processing with no new entity, I/O, source, secret, LLM call,
cost or disposition. All six Code Generation steps and their scoped build/test
gates are complete. The general execution plan allows selective per-unit design
(`execution-plan.md:113`); its initial-unit preview is not a missing u153 stage.

## Acceptance criteria evidence

| Criterion | Status | Implementation and named test evidence |
|---|---|---|
| AC-153.1 — final values ≤90 characters | Complete | `reflow.py:170` bounds the stripped Markdown value including syntax; `public_document.py:365` applies it after repair and `:2659` bounds a cleanup-expanded DTO. `test_finalized_all_three_tldr_positions:530`, `test_finalized_notification_cleanup_expansion_keeps_markdown_bytes:739`, `test_finalized_notification_projection_cap_property:818` |
| AC-153.2 — complete safe sentence and one continuation, or fallback | Complete | `text.py:22` reuses the decimal-safe terminator with opt-in complete scanning; `reflow.py:170` reserves the suffix budget and rolls back unsafe candidates. `test_candidate_rolls_back_to_safe_sentence:144`, `test_continuation_is_complete_and_not_repeated:168`, `test_finalized_incident_and_boundary_contract:486` |
| AC-153.3 — incident tails absent; valid short driver preserved | Complete | Canonical continuation rejection uses `summary_quality.py:57` and `surface_quality.py:476`. `test_finalized_incident_and_boundary_contract:486` checks literal fixture outputs, including the short noun driver; integration `test_u153_sealed_summary_reaches_notification_without_fragment_or_regrowth:401` verifies real outgoing message text |
| AC-153.4 — decimal/Markdown integrity and original link ownership | Complete | `text.py:22` keeps the existing terminator rule; `reflow.py:170` preserves original link findings before bounding. `test_finalized_decimal_markdown_and_notification_property:708`, `test_finalized_original_link_policy_keeps_good_siblings:633`; the link spy delegates to the real repair owner |
| AC-153.5 — exact fallbacks and byte-stable repeats | Complete | Canonical per-surface fallbacks in `reflow.py:296`; no safe complete prefix means fallback. `test_finalized_fallbacks_and_unrelated_regions:562`, `test_finalized_complete_and_partial_bundle_repeatability:594` assert exact output and repeated Markdown/SHA/DTO |
| AC-153.6 — unaffected surfaces/regions and terminal gates | Complete | Owned traversal is bounded by H2/protected-region state; strict caution opt-out preserves legacy behavior; `_seal_document` at `public_document.py:3446` copies validated bytes. `test_finalized_non_summary_hard_gates_survive_bounding:679`, `test_finalized_unsafe_cleaned_summary_is_rejected_before_bounding:774`, plus compatibility tests below |

Additional compatibility/ordering evidence:

- `tests/unit/_internal/test_text.py:81::test_bound_at_sentence_default_keeps_all_fitting_bytes`
  preserves default helper behavior; `:51` covers decimal safety.
- `tests/unit/briefing/test_summary_quality.py:175::test_u153_typed_caution_gate_and_repair_remain_unchanged`
  and `:182::test_u153_caution_extraction_retains_legacy_predicate` preserve caution consumers.
- `tests/unit/publisher/test_public_document_assembly_u144.py:385::test_u153_real_finalizer_keeps_repair_output_bounded_until_seal`
  checks the actual repair → bounding → accounting/reindex → validation → seal chain;
  `:470` covers the late public-label expansion regression.
- `tests/unit/publisher/test_public_document_containment_u144.py:276::test_u153_region_local_scan_keeps_body_callout_continuations_unowned`
  preserves body ownership; `:288` still recognizes actual viewport residue.
- The fresh publisher-wide gate includes u131 rendered caution/meaning/title
  regressions and public-document architecture, policy, disclaimer and immutability tests.

All five unit DoDs are satisfied: final cap/fallback (AC-153.1/2/5), single
complete continuation (AC-153.2/3), short/decimal/Markdown preservation
(AC-153.3/4), post-repair/pre-seal ordering and DTO agreement (AC-153.1/6), and
generated-byte/idempotence/link/unaffected-region tests (AC-153.4/5/6).

## Fresh validation in this cross-check

```sh
PYTHONPATH=src /Users/user/Desktop/Projects/investo/.venv/bin/python -B -m pytest \
  tests/unit/publisher tests/unit/briefing tests/unit/internal tests/unit/_internal \
  tests/unit/notifier tests/integration/test_briefing_reader_format.py \
  -q --tb=short --hypothesis-seed=15320260907
```

- **2,734 passed in 102.06s**; no failures, skips or xfails in this gate.
- Source mypy: **254 files pass**. Scoped u153 test mypy: **1 file passes**.
- Ruff check and format check: **all 15 u153 Python files pass**.
- `scripts/check_no_paid_apis.py` and `git diff --check`: pass.
- Rechecked the 14-case JSON fixture: no pending cases. The three incident
  inputs match the exact recorded lines in the baseline archives: domestic
  September 4 lines 16/17 and crypto September 4 line 15. Synthetic URLs are
  fixture text, not fetched sources.
- Rechecked integration scoped mypy against the saved, byte-verified HEAD
  version: **20 identical diagnostics on each**, both exit 1 (one private-export
  `attr-defined`, nineteen `unused-ignore`). No new diagnostic; this is **not**
  a passing integration mypy gate. No unrelated typing repair is included.

The Step 6 record separately documents an exact-final-tree full repository run:
**4,787 passed in 464.71s**, focused **202 passed**, and the independent final
review's five-category Pass. These are prior Step 6 evidence, not fresh full-suite
or new independent-review runs in this cross-check. Counts overlap and must not
be added. See
`aidlc-docs/construction/u153-summary-sentence-boundary-extension/code/step-6-final-output-acceptance.md`.

Partial PBT evidence uses the existing Hypothesis collection, seed `15320260907`,
literal expected outputs and domain-specific decimal/Markdown/continuation
properties. The six construction records document PBT-03/07/08/09 compliance;
PBT-02 is N/A for these lossy text transforms without an inverse. No framework,
serialization contract or new performance target is introduced here.

## Important boundaries and recommendations

- The 90-character cap counts the stripped Markdown **value** with Python `len`,
  including link/emphasis syntax, excluding the callout/list marker. It is not
  the notifier's separate whole-message UTF-16 limit.
- Short valid noun headings need no invented terminal punctuation. Complete
  boundaries use the existing conservative terminator, not general Korean grammar.
- Empty unbulleted whitespace is a separator, not an owned TL;DR item. u153 does
  not synthesize missing items or repair TL;DR cardinality/layout; u154 owns that.
- Ordinary DTO conclusions equal the canonical cleaned Markdown conclusion.
  Cleanup-expanded safe conclusions retain a complete bounded cleaned prefix or
  fallback; original Markdown remains unchanged. Unsafe cleaned values are
  rejected **before** bounding, so length repair cannot hide a safety finding.
- Malformed links may deliberately remain over-cap in an intermediate helper
  result so the original owner can repair/block them. The final published-output
  contract does not authorize erasing link evidence or adopting u150's new policy.
- Existing non-summary numeric/entity/compliance/link gates, disclaimers and
  diagnostic placement remain in force. No new paid API, I/O, secret wiring,
  source or cross-layer dependency was introduced.

**Actions**: report and current u153 AIDLC status updated; **0 new development
tasks**, **0 new TECH-DEBT entries**. No blocking gap within the approved scope.
Existing integration typing diagnostics remain baseline context, not hidden
passing evidence or a newly authorized cleanup task.

**Handoff**: Code Generation 6/6 and u153 requirements cross-check are complete.
Main integration, commit/push, production replay, deployment and notification
send are not performed or implied. Preserve the original dirty root and other
worktrees; u154 integration still requires its original completed/integrated
u150 and u153 prerequisites. Any integration or next-unit work needs its own
approved scope.
