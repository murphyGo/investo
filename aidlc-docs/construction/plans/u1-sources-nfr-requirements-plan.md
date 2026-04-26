# NFR Requirements Plan: `u1 sources`

**Date**: 2026-04-27
**Unit**: u1 sources — Source Adapters
**Stage**: NFR Requirements
**Source artifacts**:
- `aidlc-docs/construction/u1-sources/functional-design/` — entities, rules, business-logic-model
- `docs/requirements.md` — NFR-002, NFR-003, NFR-005, NFR-006, NFR-007 acceptance criteria

---

## Unit Context

NFRs that touch this unit (per `unit-of-work-story-map.md` cross-cutting NFR table):

- **NFR-002** Cost ($0/월)
- **NFR-003** Reliability (graceful degradation)
- **NFR-005** Maintainability (plugin extensibility)
- **NFR-006** Testing (PBT partial)
- **NFR-007** Security baseline

NFR-001 (≤10 min wall-clock) is owned by orchestrator; this unit only
contributes its share of the budget. NFR-004 (disclaimer) is briefing
unit's concern — not relevant here.

---

## Execution Checklist

### Part 1 — Planning (you are here)
- [x] Q1~Q8 모두 [Answer]: 채움 (2026-04-27, "all recommended")
- [x] Ambiguity 분석: 없음 (option letters explicit)
- [x] Plan 명시적 승인

### Part 2 — Generation (after approval)
- [x] `aidlc-docs/construction/u1-sources/nfr-requirements/nfr-requirements.md`
- [x] `aidlc-docs/construction/u1-sources/nfr-requirements/tech-stack-decisions.md`
- [x] aidlc-state.md / audit.md 업데이트
- [x] NFR Requirements 명시적 승인 (2026-04-27, "Continue to Next Stage")

---

## Embedded Questions

### Q1: Per-adapter time budget (Performance — NFR-001 share)

`u1` shares the 4-min collect budget. Each adapter has the 60-s
per-adapter ceiling baked into the retry policy (FD R4). What's the
acceptance gate for this?

A) **권장**: `fetch_all` returns within **70 s** for any input where every
adapter completes within its 60-s ceiling, even if all adapters are
slow simultaneously (concurrent execution, so worst case ≈ slowest
adapter + small overhead). Test: 1 adapter that simulates a 60-s call,
2 fast adapters → total ≤ 70 s.
B) Stricter: 60-s wall-clock total — implies any single slow adapter
hits the ceiling and we still meet budget. Hard to guarantee under
concurrent gather + cancellation cost.
C) Looser: 90-s — pads for unforeseen overhead; risks bumping up
against the orchestrator's 4-min collect budget when 4+ slow adapters
land.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q2: Failure budget (Reliability — NFR-003)

What fraction of registered sources may fail before the run is
considered degraded vs failed?

A) **권장**: `fetch_all` always succeeds (returns a list, possibly empty)
regardless of how many adapters fail. The orchestrator's `_stage_collect`
guard converts an empty result list to a pipeline FAILURE. So at this
unit's level: 0% failure means everything OK; 100% failure means an
empty list — orchestrator decides what to do. No "degraded" state
inside `u1`.
B) `u1` itself raises `AggregatorError` when ≥80% of adapters fail.
Pushes the FAIL/PARTIAL decision into `u1` instead of the orchestrator.
Couples this unit to a higher-level concern.
C) `u1` raises when ALL adapters fail (and all transient). Same intent
as A but at the wrong layer.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q3: Cost guards (Cost — NFR-002)

How is "free APIs only" enforced concretely?

A) **권장**: Two-layer guard:
   1. Code-review skill rule (already in place) blocks paid-API
      patterns in PR review.
   2. CI runs a lightweight grep that fails the build if any
      adapter file imports/configures a known paid-tier client
      library (initial blocklist: empty — populated as adapters land).
B) Code review only — no CI guard. Lighter, but humans miss things.
C) Code review + a per-adapter `requires_paid_key: bool = False`
attribute that the registry refuses unless `INVESTO_ALLOW_PAID=1`.
Already rejected in FD Q8=A (YAGNI).

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q4: Plugin extensibility (Maintainability — NFR-005, US-008)

How does the unit prove "1 file + 1 import line" is achievable?

A) **권장**: A regression test (`tests/unit/sources/test_plugin_contract.py`)
asserts:
   - `len(list_sources()) == len(<expected adapter modules>)` (drift guard)
   - Adding a stub adapter via `monkeypatch` changes the list by exactly
     +1 (proves the registry mechanism)
   - A minimal `CONTRIBUTING.md` snippet (or section in README) documents
     the 4-line procedure: create file, define class, decorate, add 1
     import line.
B) Manual checklist in CONTRIBUTING only, no test. Cheaper, weaker.
C) Full integration test that spawns a temp module on disk and verifies.
Heavier than payoff at this scale.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q5: PBT scope (Testing — NFR-006, partial)

Per project-wide policy, PBT applies to "pure functions and
serialization round-trips". What pure functions in `u1` are PBT
candidates?

A) **권장**:
   - `FetchWindow.from_kst_date(date)` — output bounds invariant
     (`start_utc < end_utc`, both tz-aware, 24-h span)
   - Window-membership filter: `lambda item, window: in_window(item, window)`
     — given any tz-aware datetime + window, the membership decision
     equals the strict comparison
   - The shared `_retry` helper's backoff schedule pure-function
     (input: attempt N, header value → output: sleep seconds; cap
     applied)
B) Just `FetchWindow.from_kst_date`. Skip the rest as low-value.
C) All of A plus the FOMC RSS parser's date-extraction sub-function.
Adapter-specific PBT, expensive maintenance.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q6: Source response trust boundary (Security — NFR-007)

External feed bytes are untrusted input. How strict do we get?

A) **권장**:
   - **Bound payload size**: reject responses > 5 MB at the retry-helper
     level (raises `SourceFetchError(transient=False)`). RSS/news feeds
     fit easily.
   - **No HTML rendering trust**: titles/summaries from feeds may contain
     HTML. Adapters strip tags via `bleach`-or-equivalent before storing
     in `NormalizedItem`. (Adds 1 dep — `bleach` is small + audited.)
   - **No file:// or non-HTTP URLs in extracted item URLs**: validate
     scheme is http/https; otherwise drop the item.
   - **No code execution from response**: never `eval`, never `pickle.loads`,
     no XML XXE — use `defusedxml` for any XML parsing (`bleach` and
     `defusedxml` are both small + Python standard ecosystem).
B) Lighter: just payload size + no XXE. Skip HTML stripping (done in
briefing/publisher anyway? — not currently planned, so the title hits
the published markdown raw → risky).
C) Heavier: A plus content-security checks (URL reputation lookup,
domain allowlist). Massive scope creep for a $0 personal tool.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q7: Tech stack decisions for this unit

Anything to choose beyond what's already locked? Confirm or override:

| Component | Locked / Suggested | Decision |
|-----------|---------------------|----------|
| async HTTP | `httpx>=0.27` (project core) | A |
| XML parser | `defusedxml.ElementTree` (NEW dep) | A |
| HTML sanitizer | `bleach>=6` (NEW dep, only if Q6=A) | A |
| RSS/Atom feed parser | `defusedxml` direct (NOT `feedparser` — adds many deps and is loose-mode) | A |
| Logging | stdlib `logging` (no structlog) | A |

A) **All recommended above** (권장)
B) Override one or more (please specify which and why)

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q8: NFR drift / monitoring

Once `u1` ships, what stops NFRs from drifting?

A) **권장**:
   - PBT round-trips (Q5) live forever in CI
   - Plugin contract test (Q4) lives forever in CI
   - Cost grep guard (Q3) runs in CI on every PR
   - Functional changes that touch `u1`'s public surface require a fresh
     `/code-review git` (already standard in `/dev-investo` flow)
B) A plus a per-quarter manual NFR review checkpoint. Adds a calendar
ritual; useful for a real team but heavyweight for solo.
C) A plus runtime metrics (count of source failures per run, p50/p95
fetch latency) emitted to logs for trend-watching. Useful but
implementation adds non-trivial code; defer to future ADR.

[Answer]: A (per "all recommended" 2026-04-27)

---

## Plan Summary Reference

| Aspect | Recommendation |
|--------|----------------|
| Q1 Time budget | A — `fetch_all` ≤ 70 s with one slow adapter at 60 s |
| Q2 Failure budget | A — never raise from `fetch_all`; orchestrator owns FAIL/PARTIAL |
| Q3 Cost guard | A — review rule + CI grep blocklist |
| Q4 Plugin extensibility | A — regression test + CONTRIBUTING snippet |
| Q5 PBT scope | A — FetchWindow + window-filter + retry backoff |
| Q6 Security boundary | A — payload cap + HTML strip + URL scheme guard + defusedxml |
| Q7 Tech stack | A — httpx + defusedxml + bleach + stdlib logging |
| Q8 NFR drift | A — CI tests + grep + standard code-review |

---

## How to Fill Answers

Each Q1~Q8 `[Answer]:` accepts a letter (A/B/C/...) or free text. **"all recommended"** accepts every option marked A above.
