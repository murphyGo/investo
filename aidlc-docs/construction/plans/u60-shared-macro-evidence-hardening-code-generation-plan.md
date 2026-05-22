# Code Generation Plan: `u60 shared-macro-evidence-hardening`

**Date**: 2026-05-23
**Unit**: u60 shared-macro-evidence-hardening
**Stage**: Code Generation
**Status**: Complete (6/6)
**Source**: 2026-05-23 user report: `미 국채 수익률 — Immunefi to absorb Code4rena bug bounty customers after shutdown decision`
**Estimated Effort**: ~3-5 h
**Dependencies**:
- u45 segment-routing-exclusivity: current source fan-out rules for `treasury-rates`.
- u55 numeric-freshness-and-market-fact-gates: source-backed numeric discipline.
- u57 segment-narrative-scope-and-time-reconciliation: `BundleContext`, shared macro detection, and `## ⓪ 오늘의 매크로` injection.
- u59 macro-actual-priority-and-lineage: broader macro actual lineage plan; do not duplicate that unit's actual-data scope.

---

## Problem Statement

The shared macro block can classify an unrelated crypto-security headline as U.S. Treasury yield evidence:

```markdown
- **미 국채 수익률** — Immunefi to absorb Code4rena bug bounty customers after shutdown decision
```

The local archive shows the same wrong line injected into all three 2026-05-13 segment briefings:

- `archive/domestic-equity/2026/05/2026-05-13.md`
- `archive/us-equity/2026/05/2026-05-13.md`
- `archive/crypto/2026/05/2026-05-13.md`

Root cause:

1. `src/investo/orchestrator/bundle_context.py::_SHARED_MACRO_PATTERNS["ust_yield"]` contains bare `UST` with `re.IGNORECASE`.
2. The substring `customers` contains `ust`, so an unrelated title matches.
3. `_detect_shared_macros()` stores the first matching title per segment with `setdefault()`.
4. The shared source `treasury-rates` can still provide real UST evidence later, but the earlier false positive can become the representative evidence title.
5. `publisher/shared_macro.py::inject_shared_macro_block()` then injects the already-wrong block into every segment.

This is not an LLM hallucination. It is deterministic pre-Stage-2 evidence selection drift.

---

## Goal

Make shared macro evidence source-backed and false-positive resistant so `## ⓪ 오늘의 매크로` never labels arbitrary title substrings as U.S. Treasury yield, oil, or FOMC evidence.

The detector must prefer canonical macro/calendar sources and must reject title-only substring accidents such as `customers`, `trust`, `custody`, or `dust`.

---

## Scope Boundary

In scope:
- Harden `_SHARED_MACRO_PATTERNS` and/or replace them with key-specific matcher functions.
- Add source/category-aware candidate scoring for shared macro evidence.
- Prefer canonical macro evidence over generic news evidence when both match.
- Preserve the current shared macro layout and injection site.
- Add deterministic tests for the reported `customers` false positive.
- Add regression coverage for real UST evidence from `treasury-rates` and `fred-macro`.
- Add required R13-safe diagnostics for accepted, rejected, suppressed, and selected shared macro candidates.

Out of scope:
- Backfilling already-published archive markdown.
- Changing Stage 1 or Stage 2 LLM prompts.
- Adding new macro actual sources or forecast/consensus data. That belongs to u59.
- Rewriting the whole shared macro system into a public lineage artifact.
- Making shared macro absence a hard publish failure.
- Changing `src/investo/briefing/segments.py` routing or adding new source fan-out.

---

## Implementation Map for a Fresh Agent

This section is intentionally concrete so an agent with no prior conversation context can start from the current repository state.

### Current chokepoints

| Concern | File/function | Current behavior |
|---------|---------------|------------------|
| Shared macro detection | `src/investo/orchestrator/bundle_context.py::_detect_shared_macros` | Iterates routed segment items and stores first title match per `(macro_key, segment)`. |
| UST matcher | `src/investo/orchestrator/bundle_context.py::_SHARED_MACRO_PATTERNS["ust_yield"]` | Bare `UST` matches any substring under `re.IGNORECASE`, including `customers`. |
| Evidence rendering | `src/investo/orchestrator/bundle_context.py::_render_shared_macro_block` | Renders `- **{label}** — {evidence_title}` with no source/category validation. |
| Injection | `src/investo/publisher/shared_macro.py::inject_shared_macro_block` | Idempotently injects the rendered block after TL;DR or before `## ①`. Preserve this behavior. |
| Routing | `src/investo/briefing/segments.py` | `treasury-rates` is shared across `us-equity` and `crypto`; `fred-macro` is U.S. only. |
| Tests | `tests/unit/orchestrator/test_bundle_context.py` | Existing shared macro tests assert happy-path UST/oil/FOMC detection but do not test substring false positives or evidence priority. |

### Reported reproduction

Use this title as the must-not-match regression string:

```text
Immunefi to absorb Code4rena bug bounty customers after shutdown decision
```

Use these real-evidence examples as must-match strings:

```text
UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp
DGS10 4.46 (+0.0400 from prior)
미 국채 10년물 수익률 4.42%
10Y Treasury yield rises to 4.46%
```

---

## Decisions Closed Before Implementation

1. **UST canonical-source gate**: `ust_yield` may render in the reader-facing shared macro block only when the key has valid candidates in at least two routed segments and at least one candidate comes from a canonical U.S. rates source: `treasury-rates` or `fred-macro`. Strong non-canonical matches in two segments are suppressed, not published.
2. **`fred-macro` is not a shared fan-out source**: `fred-macro` is positive ranking evidence only. It must not cause crypto fan-out and must not change u45 routing. The existing shared trigger still requires valid candidates in at least two routed segments.
3. **`treasury-rates` fan-out is preserved**: `treasury-rates` already routes to both `us-equity` and `crypto`; that fan-out can satisfy the two-segment UST trigger.
4. **Reader-facing suppression policy**: suppressed shared macro keys are silent in the briefing. Suppression is operator/log-only and must never render a public "macro failed" line.
5. **`segments.py` routing is read-only for this unit**: canonical source names live in private constants inside `orchestrator/bundle_context.py`. If routing changes become necessary, create a separate unit.

---

## Design

### 1. Replace bare regex with key-specific predicate helpers

Keep the public behavior inside `compute_bundle_context()` unchanged, but make the internal matching explicit. Recommended private helpers:

```python
def _matches_ust_yield(title: str) -> bool: ...
def _matches_oil(title: str) -> bool: ...
def _matches_fomc(title: str) -> bool: ...
```

UST rules:

- Define "near" as the anchor and context regex matches in the same title with at most 40 characters between the end of the earlier match and the start of the later match. Prefer a helper such as `_has_near(text, anchor_re, context_re, max_gap=40)`.
- Accept Korean terms when the title has `미 국채`, `미국채`, or `미국 국채` near `10년`, `10년물`, `수익률`, or `금리`. Do not accept bare `국채` unless the source is canonical U.S. rates evidence.
- Accept `DGS10`, `DGS2`, `DGS30`, or `DGS3MO` as FRED rate-series evidence.
- Accept `UST` only with ASCII word boundaries: `(?<![A-Za-z])UST(?![A-Za-z])`.
- A bare `UST` token must be near at least one rate-context term: `yield`, `curve`, `10Y`, `2Y`, `30Y`, `Treasury`, `rate`, `금리`, `수익률`.
- Accept `Treasury` / `Treasuries` only near `yield`, `curve`, `rate`, or tenor terms.
- Reject substring-only hits in words such as `customers`, `trust`, `custody`, and `dust`.
- Reject semantic crypto-token false positives such as `UST stablecoin collapse`, `UST depeg`, and `UST custody product` unless the title also carries rate/yield/curve/tenor context.

Oil and FOMC rules stay close to the current behavior, but must use boundary/context guards:

- Oil: `WTI`, `Brent`, `브렌트`, `국제 유가`, `원유`; ASCII `WTI` / `Brent` require word boundaries so titles such as `Brentwood office lease` do not match.
- FOMC/Fed: `FOMC`, `연준`, `Fed meeting`, `Federal Reserve` near `meeting`, `rate`, `decision`, `minutes`, `statement`, or `기준금리`; ASCII acronym terms require boundaries.

### 2. Add candidate scoring before choosing representative evidence

Do not let the first matching title automatically become the representative line. Build candidates and choose by deterministic priority.

Recommended private dataclass:

```python
@dataclass(frozen=True, slots=True)
class _SharedMacroCandidate:
    key: str
    segment: MarketSegment
    title: str
    source_name: str
    category: Category
    source_rank: int
    title_rank: int
```

Required priority:

1. Canonical source rank:
   - UST: `treasury-rates` rank 0, `fred-macro` rank 1, other sources rank 9.
   - FOMC: `fomc-calendar`, `fomc-rss`, `fred-economic-calendar`.
   - Oil: source-specific canonical source if one exists; otherwise macro/news allowed but title must match strongly.
2. Category rank:
   - `macro` rank 0, `calendar` rank 1, `news` rank 2, unknown category rank 9.
3. Title specificity:
   - numeric/rate-bearing title before generic macro headline.
   - `DGS10`, `UST curve`, `10Y`, `수익률`, `금리` before generic `Treasury`.
4. Deterministic tie-break:
   - Use `(source_rank, category_rank, title_rank, source_name, title, segment)` for representative evidence selection. Segment participates only as the final tie-break; segment membership is for shared-trigger counting, not evidence priority.

This keeps output stable while making canonical macro sources win over earlier generic news.
Unknown `source_name` or `category` must degrade to the lowest rank and log a bounded diagnostic; it must not raise or break publishing.

### 3. Preserve shared trigger semantics

The shared block should still appear only when the same macro key has evidence in at least two segments.
For `ust_yield`, an additional gate applies: among those valid candidates, at least one must be canonical U.S. rates evidence (`treasury-rates` or `fred-macro`). Non-canonical-only UST candidates are suppressed with diagnostics.

Important nuance:

- `treasury-rates` is intentionally routed to both `us-equity` and `crypto`.
- That fan-out is enough to make a UST macro shared.
- `fred-macro` is U.S.-only and must not be fan-out by this unit. It can satisfy the canonical-evidence gate only when another routed segment also has a valid UST candidate.
- The representative evidence must be the canonical title, for example `UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp`, not a crypto news headline.

### 4. Keep reader output unchanged except for corrected evidence

Do not change `publisher/shared_macro.py` unless needed for tests. The target output shape remains:

```markdown
## ⓪ 오늘의 매크로

- **미 국채 수익률** — UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp
```

If the only UST-like strings are false positives, `shared_macro_block` must be `None`.

---

## Implementation Steps

### Step 1 — Pin the false positive

- [x] Add a focused unit test in `tests/unit/orchestrator/test_bundle_context.py`.
- [x] Scenario: `us-equity` and `crypto` each contain unrelated news titles with `customers`/`trust`/`custody`; `compute_bundle_context(...).shared_macro_block is None`.
- [x] Scenario: one segment has false-positive news and another has real UST evidence, but fewer than two valid UST segments exist; no UST shared macro.
- [x] Scenario: false-positive news appears before real `treasury-rates` items in the same segment; representative evidence still chooses the real macro title.
- [x] Scenario: two strong non-canonical UST-ish news titles exist across two segments, but no `treasury-rates` / `fred-macro` candidate exists; `ust_yield` is suppressed and logged, not rendered.

### Step 2 — Harden UST matching

- [x] Replace bare `UST` pattern with a key-specific matcher or stricter pattern.
- [x] Add tests for:
  - `customers` rejected.
	  - `trust` rejected.
	  - `custody` rejected.
	  - `dust` rejected.
	  - `UST stablecoin collapse` rejected.
	  - `UST depeg` rejected.
	  - `UST custody product` rejected.
	  - `UST curve ... 10Y ...` accepted.
	  - `DGS10 ...` accepted.
	  - `10Y Treasury yield ...` accepted.
	  - `미 국채 10년물 수익률 ...` accepted.
	  - `한국 국채 10년물 금리 ...` rejected unless emitted by canonical U.S. rates source.
	- [x] Keep matching pure and deterministic. No external calls.
	- [x] Add boundary tests for oil/FOMC: `Brentwood office lease` rejected, real `Brent crude` accepted, real `FOMC statement` / `Federal Reserve issues FOMC statement` accepted.

### Step 3 — Add evidence ranking

- [x] Replace `hits_by_key: dict[str, dict[MarketSegment, str]]` with candidate collection.
- [x] Rank candidates by source/category/title specificity.
- [x] Implement the representative sort key as `(source_rank, category_rank, title_rank, source_name, title, segment)`.
- [x] Treat unknown `source_name` / `category` as lowest rank and non-fatal.
- [x] Preserve the current return shape from `_detect_shared_macros()` unless a private richer shape is clearly simpler.
- [x] Ensure `shared.sort(key=lambda pair: pair[0])` or equivalent keeps macro-key ordering deterministic.
- [x] Add tests proving canonical macro source wins over earlier generic news with explicit `category="macro"` / `category="calendar"` fixtures.

### Step 4 — Add safe diagnostics

- [x] Add structured logging for `shared_macro.candidate_accepted`, `shared_macro.candidate_rejected`, `shared_macro.key_suppressed`, and `shared_macro.representative_selected`.
- [x] Do not log `raw_metadata`.
- [x] If logging a title, truncate to a safe preview length such as 120 chars.
- [x] Allowed extra keys: `key`, `segment`, `source_name`, `category`, `reason`, `title_preview`, `title_hash`.
- [x] Use `caplog` tests to assert raw metadata and secret-shaped strings are not emitted.

### Step 5 — Regression test the injection surface

- [x] Extend `tests/integration/test_bundle_reconciliation.py` or add a focused integration test that runs `NormalizedItem` fixtures -> `compute_bundle_context()` -> `_apply_reader_format_to_segments()`. Do not satisfy this step with a precomputed `BundleContext(shared_macro_block=...)`.
- [x] Fixture order must put the Immunefi `customers` false-positive before the canonical `treasury-rates` UST evidence.
- [x] Assert the final markdown contains `미 국채 수익률`.
- [x] Assert the final markdown does not contain `Immunefi to absorb Code4rena`.
- [x] Assert the macro block appears exactly once.
- [x] Run the reader-format application twice on already-injected markdown and assert the macro header/body remains single and unchanged.

### Step 6 — Closeout docs and summary

- [x] Update this plan checkboxes.
- [x] Add `aidlc-docs/construction/u60-shared-macro-evidence-hardening/code/summary.md`.
- [x] Update `aidlc-docs/aidlc-state.md` from planned to complete.
- [x] Update `aidlc-docs/inception/application-design/unit-of-work.md` u60 DoD checkboxes and `docs/requirements.md` FR-015 AC checkboxes.
- [x] Add cross-check report under `docs/cross-checks/`.
- [x] Cross-check and summary include a `known_affected_archives` section listing the 2026-05-13 domestic/us/crypto archives and explicitly stating that automatic backfill was not performed unless separately requested.
- [x] No archive backfill unless separately requested.

---

## Acceptance Criteria

- [x] `customers` does not match `ust_yield`.
- [x] `trust`, `custody`, and `dust` do not match `ust_yield`.
- [x] `UST stablecoin collapse`, `UST depeg`, and `UST custody product` do not match `ust_yield` unless rate/yield/curve/tenor context is also present.
- [x] `UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp` matches `ust_yield`.
- [x] `DGS10 4.46 (+0.0400 from prior)` matches `ust_yield`.
- [x] `10Y Treasury yield rises to 4.46%` matches `ust_yield`.
- [x] `미 국채 10년물 수익률 4.42%` matches `ust_yield`.
- [x] `한국 국채 10년물 금리` does not render as `미 국채 수익률`.
- [x] `ust_yield` shared macro requires valid UST candidates in at least two routed segments and at least one canonical source candidate (`treasury-rates` or `fred-macro`).
- [x] `fred-macro` alone never creates a shared macro block or changes crypto routing.
- [x] When false-positive news appears before real UST evidence, the shared macro line uses the real UST evidence.
- [x] When only false-positive news appears across two segments, no `미 국채 수익률` shared macro block is emitted.
- [x] Existing oil and FOMC shared macro happy paths still pass, and boundary false positives such as `Brentwood` are rejected.
- [x] Shared macro block injection remains idempotent and appears once.
- [x] Reader-facing output shape is unchanged except for corrected evidence.
- [x] Suppressed macro keys are silent in reader-facing markdown and visible only through R13-safe diagnostics.
- [x] No new paid source, secret, network dependency, or LLM call is introduced.

---

## Test Plan

Run at minimum:

```bash
uv run pytest tests/unit/orchestrator/test_bundle_context.py -q
uv run pytest tests/unit/publisher/test_shared_macro_block.py tests/integration/test_bundle_reconciliation.py -q
uv run ruff check src/investo/orchestrator/bundle_context.py tests/unit/orchestrator/test_bundle_context.py
uv run mypy --strict src/
```

Before closing the unit, run the normal repo gate if time allows:

```bash
uv run ruff check .
uv run pytest -q
uv run mkdocs build --strict
```

If full format check is attempted, preserve known out-of-scope formatting drift and report it rather than reformatting unrelated files.

---

## Files Expected to Change

| File | Change |
|------|--------|
| `src/investo/orchestrator/bundle_context.py` | Harden matchers, add candidate scoring, preserve public `compute_bundle_context()` behavior. |
| `tests/unit/orchestrator/test_bundle_context.py` | Add false-positive, real-positive, and priority-selection regression tests. |
| `tests/integration/test_bundle_reconciliation.py` | Add or extend end-to-end shared macro injection regression. |
| `aidlc-docs/construction/u60-shared-macro-evidence-hardening/code/summary.md` | Add when implementation closes. |
| `docs/cross-checks/2026-05-23-u60-shared-macro-evidence-hardening.md` | Add when implementation closes. |

---

## Non-Goals and Guardrails

- Do not remove the shared macro feature.
- Do not rely on LLM reasoning to decide whether a title is macro evidence.
- Do not add a network fetch or live source check to this detector.
- Do not backfill published archives in the implementation commit.
- Do not weaken `treasury-rates` fan-out; it is legitimate shared macro input for U.S. equities and crypto.
- Do not fan out `fred-macro`; it remains US-only routing evidence.
- Do not edit `src/investo/briefing/segments.py` for this unit.
- Do not broaden UST matching to generic words like `rate` without Treasury/UST/DGS context.
- Do not change `NormalizedItem.raw_metadata` shape.

---

## Deferred Questions

1. Should domestic-equity receive the shared macro block when the overlap is only U.S. + crypto? Current behavior injects the same `BundleContext.shared_macro_block` into every segment; preserve for this unit and revisit separately only if reader feedback says it is confusing.
2. Should suppressed shared macro diagnostics later be promoted into an operator-only run trace artifact? This unit uses structured logs only; u59 owns broader lineage artifacts.
