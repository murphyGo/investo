# NFR Requirements — `u1 sources`

**Date**: 2026-04-27
**Source**: u1-sources-nfr-requirements-plan.md (all recommended)

This document fixes measurable, testable acceptance criteria for the
NFRs that touch this unit. Anything not listed here is OUT of scope
for `u1` (typically owned by orchestrator or briefing).

---

## NFR-001 (share): Performance — per-adapter time budget

**Owner of overall budget**: u5 orchestrator (≤ 10 min total run)
**`u1` share**: ≤ 4 min for the collect stage

### Acceptance criteria
- AC-1.1 — `fetch_all(target_date)` returns within **70 s** wall-clock
  when every registered adapter completes within its 60-s ceiling.
  Concurrent execution means worst case ≈ slowest adapter + small
  gather/cancellation overhead.
- AC-1.2 — Each adapter respects the 60-s ceiling enforced by the
  shared retry helper (`sources/_retry.py`): per-call timeout 30 s,
  ≤ 2 retries with exp backoff (1 s, 2 s), so worst-case
  3 × 30 + 1 + 2 = ~93 s if all attempts use full timeout. The
  retry helper caps total wall-clock at 60 s (additional outer guard).
- AC-1.3 — A test (`tests/unit/sources/test_fetch_all_budget.py`)
  pins this: 1 mock adapter that simulates a 60-s call + 2 fast
  adapters → `fetch_all` returns ≤ 70 s.

---

## NFR-002: Cost — free APIs only

### Acceptance criteria
- AC-2.1 — No adapter requires an API key whose tier is metered or
  billed. Free-tier-with-billing-on-overage counts as PAID and is
  forbidden.
- AC-2.2 — A CI grep guard (`scripts/check_no_paid_apis.py`, executed
  by the lint job) fails the build if `src/investo/sources/**` matches
  a known-paid-API blocklist. The blocklist starts empty and is
  appended to as paid services are identified during reviews.
- AC-2.3 — The `/code-review` skill flags paid-API patterns in PR
  diffs (already enforced by the project rule "Reject attempts to
  register paid data-API keys").
- AC-2.4 — Every PR that adds an adapter must declare in its
  description: source URL, advertised free-tier rate limit, and an
  explicit "no paid tier required" sentence.

---

## NFR-003: Reliability — graceful degradation

### Acceptance criteria
- AC-3.1 — `fetch_all(target_date)` MUST NOT raise. It returns a
  `list[NormalizedItem]`, possibly empty.
- AC-3.2 — Per-adapter failure isolation per FD R6: `SourceFetchError`
  is caught and logged at WARNING; non-`SourceFetchError` exceptions
  propagate (programmer-error guard).
- AC-3.3 — A test (`tests/unit/sources/test_failure_isolation.py`)
  pins: with 3 adapters where 1 raises `SourceFetchError` and 2
  return data, `fetch_all` returns the 2 good lists' concatenation.
- AC-3.4 — A test pins: with all adapters raising `SourceFetchError`,
  `fetch_all` returns `[]` (not raise).
- AC-3.5 — The "all sources empty → pipeline FAILED" decision is the
  ORCHESTRATOR's, not `u1`'s. `u1` does not interpret an empty list
  as failure.
- AC-3.6 *(extension 2026-05-01)* — A source adapter requiring a
  secret (e.g., FRED via `FRED_API_KEY` per FD R13) raises
  `SourceFetchError(transient=False)` when the secret is unset or
  empty. The aggregator catches per R6 and logs WARNING; other
  adapters continue. Test pin: `tests/unit/sources/test_fred.py`
  asserts the missing-key path raises and that the aggregator-level
  isolation contract still holds.

---

## NFR-005: Maintainability — plugin extensibility

### Acceptance criteria
- AC-5.1 — Adding a new source = exactly one new file under
  `src/investo/sources/<name>.py` plus exactly one new import line in
  `src/investo/sources/__init__.py`. Verified by code review.
- AC-5.2 — A regression test (`tests/unit/sources/test_plugin_contract.py`)
  asserts:
  - `len(list_sources()) == EXPECTED_ADAPTER_COUNT` (drift guard;
    the constant lives in the test file alongside the expected name list)
  - Adding a stub adapter via `monkeypatch` increases the registry by
    exactly +1 and exposes the stub at the registered `name`.
- AC-5.3 — Re-registering a duplicate `name` raises `RuntimeError`
  at import time (FD R2). A test pins this.
- AC-5.4 — `CONTRIBUTING.md` (or a section in `README.md`) documents
  the four-line procedure: (a) create file, (b) define class, (c)
  apply `@register`, (d) add 1 import line. Wording must keep this
  count visible.
- AC-5.5 *(extension 2026-05-01)* — Adapters that expose
  user-configurable symbol/coin/series lists (per FD R12) follow the
  shared `INVESTO_<ADAPTER>_<NOUN>` env-var convention and resolve via
  the shared `sources/_config.py` parser. Tests pin (per adapter):
  - env var unset → defaults are used
  - env var set with valid comma list → exact override
  - env var set with whitespace and empty tokens → tokens stripped,
    empties dropped
  - env var set but yields zero non-empty tokens → defaults used
  (fail-safe; never raise on parse failure)

---

## NFR-006: Testing — PBT partial

### Acceptance criteria
- AC-6.1 — `FetchWindow.from_kst_date(date)` has a hypothesis-based
  property test asserting:
  - `window.start_utc` and `window.end_utc` are tz-aware
  - `window.start_utc < window.end_utc`
  - `window.end_utc - window.start_utc == 24 h`
- AC-6.2 — Window-membership filter has a hypothesis test asserting:
  - For any tz-aware datetime `dt`, membership is exactly
    `window.start_utc <= dt < window.end_utc`
  - Boundary inclusive at start, exclusive at end (half-open)
- AC-6.3 — The shared retry helper's backoff schedule (input: attempt
  N, optional `Retry-After` header; output: sleep seconds) is a pure
  function with a hypothesis test asserting:
  - Output is bounded `0 ≤ sleep ≤ 30`
  - `Retry-After` (if present and parseable) takes precedence, capped at 30
  - Otherwise, output equals the deterministic exponential schedule (1, 2)
- AC-6.4 — At least 100 examples per PBT (matches existing
  `models/test_roundtrip.py` setting).

Adapter-specific parsing functions (e.g. FOMC RSS date extraction)
are NOT in PBT scope at this stage; example-based tests cover them.

---

## NFR-007: Security — baseline (extension SKIP, but trust-boundary still applies)

### Acceptance criteria
- AC-7.1 — The shared retry helper rejects any HTTP response whose
  body length exceeds **5 MB**. Reject path raises
  `SourceFetchError(transient=False)`. RSS/news feeds fit easily.
- AC-7.2 — Adapters MUST sanitize feed-derived HTML in titles and
  summaries before constructing `NormalizedItem`. Sanitization library:
  `bleach>=6` configured to strip ALL tags (we want plain text).
- AC-7.3 — Adapters MUST validate that any URL extracted from
  responses uses scheme `http` or `https`. Items with other schemes
  (`file://`, `javascript:`, etc.) are dropped, not stored.
- AC-7.4 — XML parsing uses `defusedxml.ElementTree`, never
  stdlib `xml.etree.ElementTree`. JSON parsing uses stdlib `json`
  (already safe — no XXE equivalent).
- AC-7.5 — No `eval`, no `pickle.loads`, no `exec` on response data.
  This is implicit in NFR-007 baseline but worth pinning at the unit
  level.
- AC-7.6 — A test asserts `defusedxml` is the import used by every
  XML-parsing adapter (grep at test time over `src/investo/sources/`).
  *Scope clarification (extension 2026-05-01)*: this AC applies only
  to adapters that parse XML/RSS/Atom payloads. JSON-based adapters
  (yfinance, CoinGecko, FRED) are out of scope — their parsing path
  uses stdlib `json` (TS-4) which has no XXE-equivalent vulnerability.
  The grep test continues to assert no `xml.{etree,dom,sax,parsers}`
  imports anywhere under `src/investo/sources/**` regardless of the
  adapter's payload format.

---

## NFR drift / monitoring

### Acceptance criteria
- AC-D.1 — All PBT and regression tests above run in CI on every PR
  via `pytest`.
- AC-D.2 — The cost-grep guard (AC-2.2) runs in CI.
- AC-D.3 — Functional changes that touch `u1`'s public surface
  (`SourceAdapter` Protocol, registry, `fetch_all` signature) trigger
  a fresh `/code-review git` per the standard `/dev-investo` flow.
- AC-D.4 — Runtime metrics (per-source success/fail counts, p50/p95
  fetch latency emitted to logs) are NOT required at v1 — deferred
  to a future ADR if/when operations evidence demands them.

---

## Trace map

| NFR | Stories tied | Acceptance count |
|-----|--------------|------------------|
| NFR-001 (share) | US-005 | 3 |
| NFR-002 | US-001, US-008, US-009 | 4 |
| NFR-003 | US-001 | 6 *(+AC-3.6 in extension)* |
| NFR-005 | US-008 | 5 *(+AC-5.5 in extension)* |
| NFR-006 | (cross-cutting) | 4 |
| NFR-007 | (cross-cutting) | 6 |
| Drift | (cross-cutting) | 4 |

*Extension 2026-05-01*: total ACs go from 30 to 32 (+AC-3.6, +AC-5.5).
AC-7.6's wording was clarified (scope limited to XML adapters) but
not split into a new AC.
