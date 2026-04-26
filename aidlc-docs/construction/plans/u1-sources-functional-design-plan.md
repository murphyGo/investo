# Functional Design Plan: `u1 sources`

**Date**: 2026-04-27
**Unit**: u1 sources — Source Adapters (plugin layer)
**Stage**: Functional Design
**Source artifacts**:
- `aidlc-docs/inception/application-design/components.md` — sources component description
- `aidlc-docs/inception/application-design/component-methods.md` — `SourceAdapter` Protocol + `register` + `fetch_all` signatures
- `aidlc-docs/inception/application-design/component-dependency.md` — depends only on `models` + `httpx`
- `aidlc-docs/inception/application-design/unit-of-work.md` — Definition of Done
- `aidlc-docs/inception/application-design/unit-of-work-story-map.md` — US-001, US-008
- `docs/requirements.md` — FR-001 acceptance criteria + NFR-002/003/005

---

## Unit Context

### Stories
- **US-001 매일 시장 데이터를 자동 수집한다** — adapters fetch from free APIs/RSS; categories include news, prices, macro, calendar, earnings
- **US-008 새 데이터 소스를 단일 모듈 추가로 통합한다** — plugin extensibility: 1 file + 1 registration line

### Cross-cutting NFRs
- **NFR-002** Cost — free APIs only; no paid keys
- **NFR-003** Reliability — graceful degradation: single-source failure ≠ pipeline failure
- **NFR-005** Maintainability — plugin structure, common timeout/retry base

### What Functional Design covers
This stage defines **business logic, domain rules, and contracts**, technology-agnostic except where the contract IS the technology (e.g. async Protocol). Concrete library choices that are already locked (httpx, pydantic) are inputs, not decisions.

What it does NOT cover (deferred):
- NFR Requirements (next stage) — measurable acceptance criteria for NFR-002/003/005
- Code Generation — actual implementation
- Specific source adapter URLs / parsing — only the *first reference* adapter is decided here

---

## Execution Checklist

### Part 1 — Planning (you are here)
- [x] Q1~Q8 모두 [Answer]: 채움 (2026-04-27, "all recommended" — Q1=A through Q8=A)
- [x] Ambiguity 분석: 없음 (option letters explicit)
- [x] Plan 명시적 승인

### Part 2 — Generation (after approval)
- [x] `aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md`
- [x] `aidlc-docs/construction/u1-sources/functional-design/business-rules.md`
- [x] `aidlc-docs/construction/u1-sources/functional-design/domain-entities.md`
- [x] aidlc-state.md / audit.md 업데이트
- [x] Functional Design 명시적 승인 (2026-04-27, "appvoe" → approve)

---

## Embedded Questions

### Q1: Plugin Registry Mechanism

How are Source Adapter modules discovered + registered?

A) **Decorator + module-import side-effect (권장)** — Each `sources/<name>.py` defines a class and applies `@register` at module level. A central `sources/__init__.py` `import`s every adapter module so registration is triggered. Adding a new source = (1) new file, (2) one `import` line in `__init__.py`. Static, predictable, no plugin runtime magic.
B) **`importlib.entry_points`** — Adapters are discovered via Python's `entry_points` distribution metadata. Cleaner for *external* plugins but overkill for a single-repo solo project; requires editable install for local dev.
C) **Explicit list in a config file (YAML)** — A central `sources.yml` lists modules to load. Allows ops-time enable/disable without code changes; adds parsing surface and one more secret-management concern.
D) **Hybrid** — A + opt-in disable via env var (e.g. `INVESTO_DISABLED_SOURCES=cnbc,yahoo`).

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q2: HTTP Client Lifecycle

Adapters are async; shared `httpx.AsyncClient` is best-practice for connection pooling. Where should the client live?

A) **Single shared `AsyncClient` injected into `fetch_all`** **(권장)** — `aggregator.fetch_all` opens one client (`async with`), passes it to every adapter's `fetch(client, target_date)`. Connection pool reused; lifecycle bounded by the call. Adds 1 parameter to the Protocol.
B) **Per-source `AsyncClient` instance held on the adapter** — Each adapter creates its own client. Simpler signature but loses connection-pool reuse and complicates close/cleanup.
C) **Per-call ad-hoc `AsyncClient`** — Each call opens a new client. Worst for performance but simplest.
D) **Module-level singleton** — `sources._http.shared_client` lazy-created. Process-scoped. Clean shutdown is harder; may leak warnings on test exit.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q3: Default Timeout / Retry Policy

Free APIs are flaky. What baseline timeout + retry policy should every adapter inherit?

A) **권장**: per-call timeout = 30 s; retries = 2 with exponential backoff (1s, 2s); retry on connection errors + 5xx + 429 only; total time budget per adapter ≤ 60 s.
B) Stricter: 15 s timeout, 1 retry, retry only on connection errors. Risks more "no data" results.
C) Looser: 60 s timeout, 5 retries. Risks blowing the 4-min collect budget (NFR-001 share).
D) Per-source override only — no defaults. Each adapter must declare. Rejected: violates NFR-005 (common base policy).

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q4: Failure Isolation Contract

When a single adapter fails, what does `aggregator.fetch_all` do?

A) **권장**: Adapter raises `SourceFetchError` (custom exception). Aggregator catches it, logs at WARNING with adapter name + cause, returns `[]` for that adapter, continues with others. Other exceptions (programmer bugs) propagate.
B) Adapter never raises — returns `Result[list[NormalizedItem], str]` (success or error message). Aggregator unwraps. More verbose; needs a `Result` type.
C) Adapter never raises — returns empty list on any error and logs internally. Loses error context; harder to debug.
D) Aggregator catches every Exception (broad) and continues. Hides programmer bugs; not recommended.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q5: Reference Adapter for PoC

To prove the plugin contract end-to-end, ONE reference adapter ships in the first Code Generation. Which?

Candidates (all free, no API key):
- **A) FOMC RSS feed** (Federal Reserve press releases) — Atom XML, dead simple, very stable, low volume. Maps to `category="calendar"`. **권장**.
- B) Yahoo Finance RSS — `news` category, more entries, less stable feed.
- C) `yfinance` Python package — pulls historical prices via Yahoo's unofficial API. Maps to `price`. Adds a heavier dep.
- D) FRED (Federal Reserve Economic Data) — releases / time series. Free + reliable + key-required (free tier). Maps to `macro`.
- E) CoinGecko free tier — crypto prices. No key. Maps to `price`.
X) Other (자유 기술 — 예: 본인이 신뢰하는 무료 소스)

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q6: Date-Range Semantics for `fetch(target_date)`

What does "items for `target_date`" mean across sources whose timestamps live in different timezones?

A) **권장**: Each adapter is told the **UTC date range it must cover** — i.e. `[target_date_start_utc, target_date_end_utc)` derived from KST midnight-to-midnight by the orchestrator (`resolve_target_date` already emits a UTC-aware `target_date`-equivalent). Adapters then filter their source data to that UTC window. Simple invariant; no per-adapter timezone fudging.
B) Each adapter interprets `target_date` in its own source's local timezone (e.g. yfinance uses NY time). Higher fidelity for that source but per-adapter timezone logic becomes ad-hoc.
C) Adapter receives a `(start_utc, end_utc)` pair instead of a `date`. More precise but breaks the spec'd `fetch(target_date)` signature; would also force the orchestrator to compute the window centrally.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q7: Rate-Limit Handling (HTTP 429)

A) **권장**: Treat 429 as a retryable status (already in Q3 retry list). Honour the `Retry-After` header if present (cap at 30 s); otherwise use the default backoff. After retries exhausted, raise `SourceFetchError("rate-limited")`.
B) Treat 429 as a hard fail — log and skip immediately. Loses recovery window.
C) Special "retry forever until success or pipeline budget" mode. Risks blowing the 4-min collect budget.

[Answer]: A (per "all recommended" 2026-04-27)

---

### Q8: Future Paid Sources Hook

Looking ahead to potential paid sources (e.g. Bloomberg, Refinitiv) without committing to them now:

A) **권장**: No hook. Reject paid sources at code-review time (NFR-002 enforcement is already in `/dev-investo` rules and `/code-review` skill). When the policy actually changes, add the hook in that PR. YAGNI.
B) Add a `requires_paid_key` flag on `SourceAdapter` Protocol; aggregator filters them out unless `INVESTO_ALLOW_PAID=1`. Adds complexity for a future that may never come.
C) Add a feature-flag config file slot. More machinery for the same hypothetical.

[Answer]: A (per "all recommended" 2026-04-27)

---

## Plan Summary Reference

| Aspect | Recommendation |
|--------|----------------|
| Q1 Plugin registry | A — decorator + import side-effect, central `__init__.py` |
| Q2 HTTP client | A — shared `AsyncClient` injected by `fetch_all` |
| Q3 Timeout/retry | A — 30 s / 2 retries / exp backoff / connect+5xx+429 |
| Q4 Failure isolation | A — `SourceFetchError`, log+skip, others propagate |
| Q5 Reference adapter | A — FOMC RSS (stable, no key) |
| Q6 Date range | A — UTC window centrally computed, filtered by adapter |
| Q7 Rate-limit | A — retry with `Retry-After` honored |
| Q8 Paid sources hook | A — none (YAGNI; review-time enforcement) |

---

## How to Fill Answers

Each Q1~Q8 `[Answer]:` accepts a letter (A/B/C/...) or free text. **"all recommended"** accepts every option marked A above.
