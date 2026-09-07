# Generated Briefing Review — 2026-09-06

**Mode**: Planning/docs only; local review, no subagents, no production execution.
**Review completed**: 2026-09-07 KST (started September 6; original filenames retain the review-start date).
**Baseline**: fetched `origin/main` = `d553035` (`briefing: 2026-09-04 segmented`).
**Workspace**: `/private/tmp/investo-briefing-review-20260906`, branch `codex/briefing-review-20260906`.

## Evidence and limits

The latest committed target date is 2026-09-04. Read all three September 4
briefings, compared recurring shapes across September 1–4, and inspected
`archive/_meta/quality_history.jsonl`, `archive/_meta/coverage.jsonl`,
`site_docs/quality.md`, and `site_docs/watchlist/daily.md`. There are ten
published segment documents in this four-date corpus: domestic and crypto on
all four dates, US only on September 3–4. Quality history records published
segment counts `2, 2, 3, 3`; missing US documents were not reconstructed.

All ten documents contain two top-level H1 titles. September 4 examples:

| Finding | Exact artifact evidence | Code evidence / consequence |
| --- | --- | --- |
| CFTC contract count promoted to oil macro | All three `2026-09-04.md` files, `⓪ 오늘의 매크로`: `국제 유가 — CFTC WTI crude oil managed_money net +94281 contracts`; following cause-map asserts an oil/geopolitics connection | `orchestrator/bundle_context.py::_matches_oil` accepts the title on `WTI` alone; `publisher/cross_market_cause_map.py::_candidate_types` reads the rendered Korean label |
| Trigger prices mistaken for observed current values | Crypto September 3 lines 147–154: ETH current repeats the 24h high/low conditions; September 4 lines 124–130: CFTC ETH current repeats the full conditional paragraph; domestic September 4 lines 116–122 repeats a paragraph across title/current/conditions | `_build_row` falls back to the whole bullet; `resolve_watchpoint_currents` preserves any numeric current before checking payload candidates |
| Sentence fragments in summary callouts | Domestic September 4 lines 16–17 ends `매수세가 본문 참고.` / `기관의 본문 참고.`; crypto lines 15–16 ends `이번 문서는 본문 참고.` / `반등하며 본문 참고.` | `reader_format/reflow.py::bound_summary_snippet` still uses word boundaries for conclusion, driver and TL;DR; u131 only migrated caution/meaning/title surfaces |
| Canonical preamble not assembled as one structure | September 4 documents lines 1 and 3 repeat H1; hero precedes TL;DR; `한눈에 보기` contains three unbulleted lines | Presentation assembly only normalizes line zero; layout indexing validates that first line but not H1 uniqueness; `ensure_tldr_block` returns early when the H2 already exists |

Read-only probes against this worktree's `src` with the existing Python
environment confirmed: `_matches_oil(CFTC WTI ... contracts)` is `True`; an
ETH conditional price survives `resolve_watchpoint_currents` with an empty
payload; `bound_summary_snippet` emits a mid-clause continuation. These are
characterization results, not passing fix tests. Market figures above are
quoted artifact content, not independently verified investment information.

## Deduplication and priority

| Candidate | Disposition | Owner / narrow extension |
| --- | --- | --- |
| Positioning misclassified as shared oil evidence | P1 improvement **u151** | u57/u60/u74/u107/u124; exclude structured CFTC positioning before shared classification and carry typed selected keys; addresses DEBT-076 without a second macro detector |
| Conditional numbers passing as current observations | P1 improvement **u152** | u98/u110/u135; remove numeric passthrough, resolve supported observations from the existing payload, keep existing fallback and card layout |
| Conclusion/driver/TL;DR sentence fragments | P2 improvement **u153** | u71/u131/u134; extend existing sentence bounding to the three omitted surfaces; no new summary generator |
| Duplicate title and late hero/TL;DR assembly | P2 improvement **u154** | u51/u61/u71/u141/u144; canonicalize known preamble blocks during assembly and validate final structure; no CSS/chart redesign |
| Missing US September 1–2 / malformed links | Existing work; no new unit | u150 owns link containment. Published counts alone do not establish each missing segment's failure cause |
| Domestic numeric quarantine and source outages | Existing work; no generic numeric/source unit | u109/u130/u138/u148/u149; keep source health, content degradation, and publication outcome distinct |
| Quality page `100.0%` verified KPI versus September 4 history `0.666667` | Existing-owner follow-up, not a new generic KPI | u54/u62/u65/u69/u96/u123; denominator and historical-versus-current semantics require a separate exact KPI calculation audit before asserting a new defect |
| Watchlist daily direct hits versus segment coverage-hold copy | Existing-owner follow-up, not a new matcher | u64/u73/u111/u133; daily cross-segment impact and segment coverage hold have different inputs; preserve that distinction |
| Weekly CFTC used as same-day explanation in free prose | Existing u107 AC4 recheck; not claimed fixed by u151 | US September 4 §② and crypto §② juxtapose weekly positions with session moves. u151 removes deterministic shared-macro overpromotion only; arbitrary narrative causality remains outside its acceptance claim |
| Price-table 52w distances and chart 52w levels differ | Metric-contract audit deferred | u49/u50/u70; current model uses trailing 252 closes, chart uses supplied OHLC highs/lows. Different bases are observed; this review does not infer bad source prices or create a generic chart redesign |
| Funding precision, wording, table ticker labels | Existing presentation-owner follow-up | u66/u70/u74/u108/u125/u134; do not bundle these into the four units |

## Readiness and integration order

- u153 is backlog with FD/NFR skipped under its fixed algorithm; it can start independently.
- u151 and u152 are backlog ready for Functional Design. Their proposed contracts below are reviewable defaults, not recorded user design approvals.
- u154 is ready for Functional Design; code integration is blocked until u150 is integrated and u153's bounding contract is available.
- The live local u150 worktree reports Steps 1–4/6 complete, Step 5 next, which is ahead of the fetched main registration. This review leaves that worktree and u150's main row untouched; it does not roll back or claim completion of the ongoing work.
- u151/u152 can be developed independently after their design gates; serialize final integration with other edits to the shared registrations.

## Review and validation

Local review covered contextless implementability, owner deduplication,
closed data/ordering rules, negative fixtures, and final generated-byte
assertions. Subagent review count: **0** (not requested).

The review narrowed u151 away from a general causality validator, explicitly
excluded unsupported current-value families in u152, kept full diagnostics at
the current footer in u154, and required bounded complete sentences after
summary repair in u153. The path cross-check corrected the text-helper test
target to `tests/unit/_internal/test_text.py`. None of the plans treats
hypothetical source data or unintegrated u150 code as already available.

Validation for this docs-only change: `git diff --check` on tracked changes,
no-index diff checks for new plans, unresolved-placeholder scan, and a
registration/path cross-check. MkDocs is not required: these files are under
`aidlc-docs/`, while `mkdocs.yml` publishes `site_docs/` and its archive symlink.
No runtime code, generated archive, site output, source configuration, or
TECH-DEBT status is changed. No commit or push is part of this review.
