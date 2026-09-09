# Cross-Check: u153 Step 7 production incident follow-up

**Date**: 2026-09-09 KST

**Checked by**: Codex, `cross-check` skill

**Verdict**: APPROVE — all six Step 7 fixed contracts are complete; no new
gap, development task or technical debt.

**Operational status**: Closed — exact-incident-date and current-date live
re-verification both completed all three segments, publication, Telegram,
exit-code and Pages checks successfully.

**Validated main**: `71c1db17fab62dde0caf981b909e51c2d6564c4c`, equal to
`origin/main` at validation start. GitHub Quality run
[`34309893210`](https://github.com/murphyGo/investo/actions/runs/34309893210)
completed successfully for the same SHA.

## Scope and compliance summary

The requirements cross-check checks only the six contracts introduced by u153
Code Generation Step 7 after production run `34172164168` rejected US equity
with `summary.truncated_mid_token`. The original Steps 1–6 cross-check remains
the historical evidence for AC-153.1–6. A later user-authorized operational
closeout, recorded below, adds live replay, publication, Pages and Telegram
evidence without changing the six-contract denominator.

| Status | Count | Percentage |
|---|---:|---:|
| Complete | 6 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| Total Step 7 fixed contracts | 6 | 100% |

The denominator is Step 7 contracts S7.1–S7.6, not every acceptance criterion
of the parent requirements. Production re-verification is a separate
operational acceptance axis, now closed, and is not reclassified as a code gap.

## Requirements and design traceability

Primary requirements are `docs/requirements.md:45`, `:99`, `:319`, `:328` and
`:334`. The bounded Step 7 decision and contracts are in
`aidlc-docs/construction/plans/u153-summary-sentence-boundary-extension-code-generation-plan.md`.

| Requirement | Step 7 contribution | Status within scope | Evidence |
|---|---|---|---|
| FR-002 — Korean briefing | Complete Korean nouns such as `기관` and `미 국채` are no longer rejected through a last-syllable heuristic; genuine clipping still fails safely | Complete | `surface_quality.py:1025`; safe-ending tests at `test_surface_quality.py:1124`, `:1139`; real finalizer at `test_summary_sentence_extension_u153.py:625` |
| FR-009 — reader-facing format | Summary, meaning and watchpoint surfaces retain distinct owners and one indexed regional disposition | Complete | `surface_quality.py:506`; `public_document.py:2074`; policy table at `_public_document_policy.py:70`, `:182` |
| NFR-003 — reliability | Presentation containment cannot erase numeric/entity/compliance evidence; a valid sibling survives a blocked segment | Complete | pre-mutation gate at `public_document.py:2548`; exhaustive terminal snapshot at `:2830`; finalizer regression at `test_summary_sentence_extension_u153.py:702` |
| NFR-005 — maintainability | One canonical scanner, two explicit owner codes and a closed code/block disposition matrix replace implicit owner reuse | Complete | `_find_owned_surface_quality_issues` at `public_document.py:2074`; `SURFACE_ISSUE_CODES` and table at `_public_document_policy.py:70`, `:201` |
| NFR-006 — testing | Literal incident controls, real finalizer regressions, policy exhaustiveness and a seeded 80-example property cover the correction | Complete | `test_surface_quality.py:1102`, `:1124`, `:1139`; containment tests at `test_public_document_containment_u144.py:426`, `:467`, `:498`, `:534`; fresh gates below |

FR-004 notification and sealed DTO behavior is preserved compatibility, not a
new Step 7 denominator item. It is covered by the full repository gate and the
existing u153 final-output tests. US-002, US-003 and US-004 continue to map the
briefing, publisher and notification flow (`stories.md:42`, `:61`, `:80`), and
C2/C3/C4 ownership remains unchanged (`components.md:47`, `:66`, `:88`). The
selective-design allowance remains `execution-plan.md:113`; Step 7 introduces
no new entity, I/O, source, secret, dependency, retry or cost contract, so the
existing Functional Design and NFR Requirements SKIP decisions remain valid.

## Step 7 contract evidence

| Contract | Status | Implementation and named test evidence |
|---|---|---|
| S7.1 — no terminal Korean-syllable inference | Complete | `looks_truncated_mid_token` at `surface_quality.py:1025` uses structural residue, not a Korean terminal family. `test_body_owned_complete_korean_noun_endings_are_not_inferred_as_truncation:1124` and seeded `test_body_owner_terminal_syllable_never_implies_truncation_property:1139` cover `채/확/민/관`; `test_finalized_complete_body_noun_endings_do_not_block_us_segment:625` proves the real finalizer path. |
| S7.2 — summary/meaning/watchpoint owner separation | Complete | Scanner ownership at `surface_quality.py:506`; actual viewport filtering at `public_document.py:2074`; registered codes and fail-closed matrix at `_public_document_policy.py:70`, `:182`. `test_body_owned_structural_truncation_uses_owner_specific_code:1102` and policy exhaustiveness tests at `test_public_document_policy_u144.py:47`, `:54`, `:146`. |
| S7.3 — indexed regional fallback and deterministic seal | Complete | Meaning maps only to `section_body`, watchpoint title only to `watchpoints` at `_public_document_policy.py:184`; `test_finalized_body_structural_truncation_is_locally_contained:671` verifies the real finalizer, regional replacement and repeated bytes/SHA. |
| S7.4 — canonical summary-marker fallback without hiding link evidence | Complete | `_repair_summary_value` at `summary_quality.py:164` retains the existing summary owner. `test_u153_structural_summary_truncation_uses_owner_fallback:145`, `test_u153_continuation_fallback_does_not_erase_other_blockers:221` and `test_finalized_original_link_policy_keeps_good_siblings:739` cover fallback and harder link ownership. |
| S7.5 — non-surface hard gates precede mutation and aggregate | Complete | `_repair_projected_draft` snapshots numeric/entity/compliance codes before mutation at `public_document.py:2548`; `_collect_terminal_hard_gates` and `_collect_non_surface_hard_gate_codes` remain exhaustive at `:2830`, `:2882`. `test_non_surface_hard_gate_blocks_before_body_fallback:498`, `test_early_hard_gate_snapshot_keeps_every_actionable_surface_code:534` and real-finalizer sibling test at `test_summary_sentence_extension_u153.py:702`. |
| S7.6 — link and body classification coexist in one pass | Complete | Canonical regional scan at `surface_quality.py:506` evaluates safe visible residue while retaining link findings; public finalization consumes the grouped findings once at `public_document.py:2560`. `test_link_and_body_truncation_are_grouped_into_one_local_containment:426` and `test_incomplete_link_does_not_impersonate_body_truncation:467` prove both sides. |

No requirement deviation, owner leak, unsupported disposition or missing test
case was found. The rejected US Markdown from the original incident was not
persisted, so byte-for-byte replay of that rejected draft is impossible. This
known evidence limit does not invalidate the reproducible policy-path and
literal safe-ending controls. Exact-date and current-date live runs provide the
available post-fix production evidence instead of an unavailable rejected-byte
replay.

## Fresh validation in this cross-check

All commands below ran in the clean isolated main worktree at the validated SHA.
Past construction or integration counts are not reused as fresh evidence.

```sh
uv run python -m pytest \
  tests/unit/internal/test_surface_quality.py \
  tests/unit/briefing/test_summary_quality.py \
  tests/unit/publisher/test_public_document_policy_u144.py \
  tests/unit/publisher/test_public_document_containment_u144.py \
  tests/unit/publisher/test_numeric_degradation_containment_u149.py \
  tests/unit/publisher/test_summary_sentence_extension_u153.py \
  tests/unit/orchestrator/test_terminal_entity_validation_u144.py \
  -q --tb=short --hypothesis-seed=15320260909
```

- Related Step 7 gate: **571 passed in 16.69s**.
- Full repository gate with the same seed: **5,229 passed in 316.94s**.
- `uv lock --check`: 65 locked packages resolve; pass.
- Ruff check: pass. Ruff format: **581 files already formatted**.
- Mypy: **254 source files**, no issues.
- No-Anthropic-SDK and no-paid-API guards: pass.
- Curated assets: **19 filed, 0 deferred**; image store: **0 binaries, 0 sidecars**.
- Strict MkDocs build and Material light/dark rendered-pair contracts: pass.
- `git diff --check`: pass before documentation closeout; the report/session
  updates receive a second strict-doc and diff check.
- Current remote Quality run `34309893210`: success for exact SHA
  `71c1db17fab62dde0caf981b909e51c2d6564c4c`.

The fixed-seed property is finite, shrinking-enabled and collected by normal
pytest. PBT-03/07/08/09 apply; PBT-02 remains N/A for this lossy presentation
repair with no inverse serialization contract.

## Production re-verification

The user subsequently authorized the remaining work with `진행시켜`. Following
the incident procedure, the failing target date and a no-input current-date run
were checked separately, and generation, finalization, publication,
notification, exit status and Pages were classified independently.

| Target | Daily run | Finalization | Publish / notify / exit | Bot commit | Pages |
|---|---|---|---|---|---|
| `2026-09-07` exact incident date | [`34328379033`](https://github.com/murphyGo/investo/actions/runs/34328379033), success, `847.442s` | domestic `finalized_degraded` with only `numeric.anchor_assertion`; US and crypto `finalized`; no u153 surface code | three archives written and pushed; Telegram HTTP 200, message `124`; rc 0 | `978d37ed49039f20aeca60e67836f7a0f7713f64` | [`34329717519`](https://github.com/murphyGo/investo/actions/runs/34329717519), success |
| `2026-09-08` resolved current date | [`34330763708`](https://github.com/murphyGo/investo/actions/runs/34330763708), success, `1083.996s` | domestic `finalized_degraded` with only `numeric.anchor_assertion`; US and crypto `finalized`; no u153 surface code | three archives written and pushed; Telegram HTTP 200, message `125`; rc 0 | `eb137d788209917bd972e6790169e0b02b37fe97` | [`34332491487`](https://github.com/murphyGo/investo/actions/runs/34332491487), success |

Both runs reported `[generate] ... ok=3 failed=0`. The US segment that the
original incident rejected survived finalization and publication in both runs,
with none of `summary.truncated_mid_token`, `meaning.truncated_surface` or
`watchpoint.title_truncated_surface`. Domestic `numeric.anchor_assertion` is the
expected u149 local containment state, not a u153 regression or partial
pipeline. All six published URLs (three segments for each target date) returned
HTTP 200 after the matching Pages deployments.

Both pipeline durations exceed NFR-001's ten-minute target. This is additional
evidence for existing `DEBT-090`, not a new u153 correctness gap or duplicate
debt item.

## Gaps, actions and boundary

**Cross-check result**: 6 Complete, 0 Partial, 0 Gap, 0 Deferred, 0 In Progress.
No code/test repair was needed during this cross-check. No ADR or TECH-DEBT
entry is warranted, and there are **0 new development tasks**.

**Remaining operational action**: none for u153 Step 7. The implementation is
requirements-approved, main-integrated and operationally closed by two post-fix
live runs. `DEBT-090` remains an independent performance follow-up.

The initial cross-check was documentation-only. The later operational closeout
performed the authorized live pipeline, archive/site publication, Pages
deployment and Telegram send from the isolated main worktree. The original
dirty root remained outside that worktree and untouched.
