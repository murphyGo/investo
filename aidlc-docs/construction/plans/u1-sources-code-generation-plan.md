# Code Generation Plan: `u1 sources`

**Date**: 2026-04-27
**Unit**: u1 sources — Source Adapters (plugin layer)
**Stage**: Code Generation (final stage for u1)
**Plan source**:
- `aidlc-docs/construction/u1-sources/functional-design/` — entities, rules, business-logic-model
- `aidlc-docs/construction/u1-sources/nfr-requirements/` — 30 ACs + tech-stack-decisions
- `src/investo/models/` — already-shipped foundation

---

## Unit Context

### Stories Closed by This Stage
- **US-001 매일 시장 데이터를 자동 수집한다** (closes when this unit's CG completes)
- **US-008 새 데이터 소스를 단일 모듈 추가로 통합한다** (closes when this unit's CG completes)

### Dependencies
- `investo.models.NormalizedItem`, `Category` — foundation
- `httpx` — locked
- NEW deps: `defusedxml>=0.7`, `bleach>=6` — added at Step 1

### Definition of Done
- [ ] Every NFR AC from `nfr-requirements.md` has a test pinning it (30 ACs)
- [ ] FOMC RSS reference adapter passes against a recorded fixture
- [ ] CONTRIBUTING.md (or README section) documents the 4-line new-adapter procedure
- [ ] Quality gate green: `ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest`
- [ ] `aidlc-docs/construction/u1-sources/code/summary.md` written
- [ ] PBT (NFR-006 AC-6.1, 6.2, 6.3) passes with ≥100 examples

---

## Steps

### Step 1: Project bootstrap for `u1` deps ✅

- [x] **1.1** `pyproject.toml` `[project.dependencies]` += `httpx>=0.27`, `defusedxml>=0.7`, `bleach>=6` (`httpx` was previously assumed-locked but wasn't actually in the file — added here)
- [x] **1.2** `pip install -e ".[dev]"` refreshed venv (httpx 0.28.1, defusedxml 0.7.1, bleach 6.3.0 + transitives anyio/certifi/h11/httpcore/idna/webencodings)
- [x] **1.3** Skeleton: `src/investo/sources/__init__.py` (docstring placeholder), `tests/unit/sources/__init__.py` (empty), `tests/unit/sources/fixtures/api/.gitkeep`
- [x] **1.4** Quality gate clean: ruff ✅, ruff format ✅, mypy --strict ✅, pytest 101/101 ✅, imports smoke ✅

---

### Step 2: `_window.py` — FetchWindow value object

**Spec**: domain-entities.md §E3, business-rules.md R7, NFR ACs 6.1, 6.2.

- [ ] **2.1** Create `src/investo/sources/_window.py`:
  - `FetchWindow` (frozen dataclass or pydantic model — frozen, extra="forbid")
    fields `start_utc: datetime`, `end_utc: datetime`, `target_date: date`
  - `FetchWindow.from_kst_date(target_date: date) -> FetchWindow` classmethod
  - `FetchWindow.contains(dt: datetime) -> bool` — half-open [start, end)
  - Tz-aware datetime invariants enforced via post-init or validator
  - Use `zoneinfo.ZoneInfo("Asia/Seoul")` for KST resolution
- [ ] **2.2** `tests/unit/sources/test_window.py`:
  - Construction with valid date produces 24-h tz-aware window
  - `contains` boundary tests (start inclusive, end exclusive)
  - Naive datetime in `contains` rejected (or returns False — pin behavior)
  - Specific known case: `from_kst_date(date(2026, 4, 27))` → `start_utc = 2026-04-26 15:00 UTC`, `end_utc = 2026-04-27 15:00 UTC`
- [ ] **2.3** `tests/unit/sources/test_window.py` PBT (hypothesis):
  - **AC-6.1**: arbitrary `date` → window is tz-aware, `start < end`, span exactly 24 h
  - **AC-6.2**: arbitrary tz-aware `datetime` → `contains(dt)` is exactly `start <= dt < end`
- [ ] **2.4** Sub-agent code review for `_window.py`. Apply or defer findings.

**Exit**: FetchWindow API stable; PBT pins NFR-006 AC-6.1/6.2.

---

### Step 3: `_retry.py` — shared retry/backoff helper

**Spec**: business-rules.md R4, R5, R6 (transient/terminal classification), NFR AC-6.3, AC-1.2 (60-s outer cap), AC-7.1 (5MB payload).

- [ ] **3.1** Create `src/investo/sources/_retry.py`:
  - `RetryConfig` value object (frozen dataclass): `timeout_s=30`, `retries=2`, `backoffs=(1.0, 2.0)`, `total_budget_s=60`, `max_retry_after_s=30`, `max_response_bytes=5*1024*1024`
  - `compute_sleep(attempt: int, retry_after_header: str | None, config: RetryConfig) -> float` — pure function
  - `async retry_get(client, request_kwargs, *, source_name, config=DEFAULT) -> httpx.Response` — runs the GET with retry/backoff/Retry-After honoring; raises `SourceFetchError(transient=True)` after retries exhausted; checks payload size and raises `SourceFetchError(transient=False, ...)` if exceeded
  - HTTP status classification: 5xx + 429 + connection error = retryable; 4xx-not-429 + decode error = terminal
- [ ] **3.2** `tests/unit/sources/test_retry.py`:
  - `compute_sleep` PBT (**AC-6.3**): `0 ≤ sleep ≤ max_retry_after_s`; `Retry-After` precedence; fallback to deterministic schedule
  - Retry behavior with `httpx.MockTransport`: 5xx then 200, 429 with Retry-After, connection error then 200, exhausted retries → SourceFetchError(transient=True)
  - 4xx-not-429 → immediate SourceFetchError(transient=False)
  - Payload over 5 MB → SourceFetchError(transient=False) (**AC-7.1**)
  - Outer 60-s budget enforcement: even with eager retries, helper returns by 60 s
- [ ] **3.3** Sub-agent code review. Apply or defer findings.

**Exit**: retry helper proven against mock transport; NFR-006 AC-6.3 + NFR-007 AC-7.1 pinned.

---

### Step 4: `_sanitize.py` — HTML strip helper

**Spec**: NFR AC-7.2.

- [ ] **4.1** Create `src/investo/sources/_sanitize.py`:
  - `strip_html(text: str) -> str` — wraps `bleach.clean(text, tags=[], strip=True)`, also normalizes whitespace
- [ ] **4.2** `tests/unit/sources/test_sanitize.py`:
  - Plain text passes through unchanged
  - `<script>alert(1)</script>` → empty (or escaped, depending on bleach config)
  - `<b>title</b>` → `title`
  - HTML entities (`&amp;`, `&lt;`) decoded to literals
  - Mixed Unicode (Korean + emoji) preserved
- [ ] **4.3** Sub-agent code review (small file — likely self-check).

**Exit**: HTML stripping bounded behavior; NFR-007 AC-7.2 pinned.

---

### Step 5: `protocol.py` — SourceAdapter + SourceFetchError

**Spec**: domain-entities.md §E1, §E4, business-rules.md R3.

- [ ] **5.1** Create `src/investo/sources/protocol.py`:
  - `class SourceFetchError(Exception)` with `source_name`, `cause`, `transient` attributes
  - `class SourceAdapter(Protocol)` with class-level `name: str`, `category: Category`, and `async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]`
  - Module re-exports `SourceFetchError` and `SourceAdapter` for public use
- [ ] **5.2** `tests/unit/sources/test_protocol.py`:
  - `SourceFetchError` construction (with/without cause/transient)
  - `SourceFetchError` is an `Exception` subclass (not a `RuntimeError`)
  - `SourceAdapter` is a `Protocol` (runtime-checkable or not — pin chosen behavior)
- [ ] **5.3** Sub-agent code review.

**Exit**: public adapter contract is locked; consumers can reference it.

---

### Step 6: `_registry.py` — @register decorator + list_sources

**Spec**: domain-entities.md §E2, business-logic-model.md L3, business-rules.md R2.

- [ ] **6.1** Create `src/investo/sources/_registry.py`:
  - Module-level `_ADAPTERS: dict[str, SourceAdapter] = {}`
  - `register(cls)` class decorator — registers an instance keyed by `cls.name`; raises `RuntimeError` on duplicate
  - `list_sources() -> list[SourceAdapter]` — returns a fresh list copy
  - `_clear_for_test()` private utility for test isolation (used by monkeypatch fixtures)
- [ ] **6.2** `tests/unit/sources/test_registry.py`:
  - Register a stub adapter → `list_sources()` contains it
  - Re-registration with same `name` → `RuntimeError` ("duplicate source name")
  - Mutation of `list_sources()` return value does not affect the registry
- [ ] **6.3** Sub-agent code review.

**Exit**: registry mechanism proven independently of any specific adapter.

---

### Step 7: `aggregator.py` — fetch_all

**Spec**: business-logic-model.md L1, business-rules.md R6, NFR ACs 1.1, 3.1, 3.2, 3.3, 3.4, 3.5.

- [ ] **7.1** Create `src/investo/sources/aggregator.py`:
  - `async def fetch_all(target_date: date) -> list[NormalizedItem]`
  - Opens shared `httpx.AsyncClient` via `async with`
  - Builds `FetchWindow.from_kst_date(target_date)`
  - `asyncio.gather(*[adapter.fetch(client, window) for adapter in list_sources()], return_exceptions=True)`
  - Per-result handling:
    - `list[NormalizedItem]` → flatten into result
    - `SourceFetchError` → log WARNING with source_name + transient flag → contribute `[]`
    - Other `Exception` → re-raise (programmer error guard)
  - Returns flattened list
- [ ] **7.2** `tests/unit/sources/test_aggregator.py`:
  - **AC-3.1, 3.2**: `fetch_all` never raises for `SourceFetchError`
  - **AC-3.3**: 3 adapters where 1 raises → returns 2 good lists' concatenation
  - **AC-3.4**: all adapters raise → returns `[]`
  - **AC-3.5**: empty result list does not raise from u1 (confirms orchestrator-owned policy)
  - Programmer-error exception (e.g. `KeyError`) propagates
- [ ] **7.3** `tests/unit/sources/test_fetch_all_budget.py`:
  - **AC-1.1**: 1 mock adapter sleeping 60 s + 2 fast adapters → `fetch_all` returns ≤ 70 s. Use `asyncio.wait_for` or a timer assertion to keep it deterministic.
- [ ] **7.4** Sub-agent code review.

**Exit**: aggregator behavior pinned for failure isolation + time budget.

---

### Step 8: `fomc_rss.py` reference adapter + recorded fixture

**Spec**: business-logic-model.md L6, business-rules.md R8, NFR-007 AC-7.2/7.3/7.4.

- [ ] **8.1** Capture a recorded fixture: a real FOMC RSS response (Atom XML) saved to `tests/unit/sources/fixtures/api/fomc-rss/feed.xml` (≤ 200 KB). Plus a `meta.json` with `{status: 200, headers: {...}}`. Capture once; commit to repo.
  - **Note**: this step requires a one-off network call to record. After capture, all tests are offline.
- [ ] **8.2** Create `src/investo/sources/fomc_rss.py`:
  - `class FomcRssAdapter` with `name="fomc-rss"`, `category="calendar"`
  - `_FEED_URL = "https://www.federalreserve.gov/feeds/press_all.xml"`
  - `async def fetch(self, client, window)` — calls `retry_get`, parses with `defusedxml.ElementTree`, maps each entry to `NormalizedItem` (title via `_sanitize.strip_html`, summary truncated to 280 chars after strip, url validated http/https else dropped, published_at from `<updated>` parsed to tz-aware UTC), filters by `window.contains(item.published_at)`
  - Apply `@register` decorator at class definition
- [ ] **8.3** `tests/unit/sources/test_fomc_rss.py`:
  - Use `httpx.MockTransport` returning the recorded fixture
  - Adapter returns `list[NormalizedItem]` against a window covering the fixture's known dates
  - Window outside the fixture's dates → empty list
  - Each returned item has `source_name == "fomc-rss"`, `category == "calendar"`, `published_at` tz-aware (**AC-7.4** verified by explicit `defusedxml` import + grep test)
  - **AC-7.3**: mock fixture with a `file://` URL entry → that entry is dropped, others kept
  - **AC-7.2**: mock fixture with `<title><b>x</b></title>` → title stored as `"x"` (HTML stripped)
- [ ] **8.4** Add a grep test (`tests/unit/sources/test_xml_safety.py`) that verifies no source file under `src/investo/sources/` imports `xml.etree.ElementTree` directly — must use `defusedxml` (**AC-7.6**).
- [ ] **8.5** Sub-agent code review.

**Exit**: reference adapter proves the contract end-to-end on a real-world feed shape.

---

### Step 9: `__init__.py` — adapter discovery + plugin contract test

**Spec**: business-rules.md R2, NFR ACs 5.1, 5.2, 5.3.

- [ ] **9.1** Update `src/investo/sources/__init__.py`:
  - Import every adapter module (currently just `fomc_rss`) so `@register` triggers
  - Re-export public API: `SourceAdapter`, `SourceFetchError`, `list_sources`, `fetch_all`, `FetchWindow`
  - Define `__all__`
- [ ] **9.2** `tests/unit/sources/test_plugin_contract.py`:
  - **AC-5.2** drift guard: `len(list_sources()) == EXPECTED_ADAPTER_COUNT` (constant in test, currently `1`); the names list matches `{"fomc-rss"}` exactly
  - Adding a stub adapter via `monkeypatch` to `_ADAPTERS` increases count by exactly +1 and exposes the stub at the registered name
  - **AC-5.3**: registering twice with the same name raises `RuntimeError` ("duplicate source name")
  - Star import from `investo.sources` exposes only `__all__` (no `_validators`/`_registry`/`_retry`/etc. leaks)

**Exit**: public surface for `u1` is locked and drift-guarded.

---

### Step 10: CI cost guard + CONTRIBUTING + final closeout

**Spec**: NFR ACs 2.2, 5.4, drift AC-D.1/D.2/D.3.

- [ ] **10.1** Create `scripts/check_no_paid_apis.py`:
  - Greps `src/investo/sources/**` for known-paid-API patterns (initial blocklist: empty list — populated as adapters land)
  - Exit non-zero if a match is found; exit 0 otherwise
  - Add a CI step (`.github/workflows/...`) — but `u6 infra/CI` owns the actual workflow file, so for now the script + a `pytest` invocation that runs it satisfies the in-repo guard
  - `tests/unit/sources/test_no_paid_apis.py` invokes the script as a subprocess and asserts exit 0
- [ ] **10.2** Add a CONTRIBUTING section (either `CONTRIBUTING.md` new file or a section under `README.md`):
  - The 4-line new-adapter procedure (**AC-5.4**)
  - Required PR description checklist (free-tier declaration per **AC-2.4**)
  - How to record a fixture for a new adapter
- [ ] **10.3** Run final quality gate:
  - `ruff check .` ✅
  - `ruff format --check .` ✅
  - `mypy --strict src/` ✅
  - `pytest` ✅ (all old tests still pass; new tests pin all 30 ACs from nfr-requirements.md)
- [ ] **10.4** Write `aidlc-docs/construction/u1-sources/code/summary.md`:
  - Files created + LOC
  - NFR AC-to-test traceability table
  - Open TECH-DEBT (if any)
  - Story status: US-001 ✅ closed, US-008 ✅ closed
  - Pre-flight for `u2 briefing`: which `u1` types/functions u2 will consume

**Exit**: `u1 sources` Code Generation stage CLOSED. Stories US-001 and US-008 close. Two stage gates remain for the project: `u2..u4..u5` Code Generation runs, then global `Build and Test`.

---

## Step Dependency Graph

```
1 bootstrap
  ├── 2 _window
  │     └─→ used by 7 aggregator
  ├── 3 _retry
  │     └─→ used by 8 fomc_rss
  ├── 4 _sanitize
  │     └─→ used by 8 fomc_rss
  ├── 5 protocol
  │     └─→ used by 6 _registry, 7 aggregator, 8 fomc_rss
  ├── 6 _registry
  │     └─→ used by 7 aggregator, 8 fomc_rss
  ├── 7 aggregator   (depends on 2, 5, 6)
  ├── 8 fomc_rss     (depends on 3, 4, 5)
  ├── 9 __init__     (depends on 6, 7, 8)
  └── 10 closeout    (depends on all)
```

Steps 2/3/4/5 can run in any order (no inter-step deps). 6 needs 5. 7 needs 2/5/6. 8 needs 3/4/5. 9 needs 6/7/8. 10 needs everything.

In practice: execute 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 sequentially (one step per `/dev-investo` invocation per the skill rule).

---

## Estimated Scope

- ~10 source files, ~9 test files
- ~10 plan steps, each yielding 1 commit
- Solo dev: ~1.5 days

---

## NFR AC Coverage Map

| AC | Pinned at step |
|----|----------------|
| AC-1.1 | 7 |
| AC-1.2 | 3 |
| AC-1.3 | 7 |
| AC-2.1, 2.4 | 10 (CONTRIBUTING) |
| AC-2.2, 2.3 | 10 |
| AC-3.1–3.5 | 7 |
| AC-5.1, 5.4 | 10 |
| AC-5.2, 5.3 | 9 |
| AC-6.1, 6.2 | 2 |
| AC-6.3 | 3 |
| AC-7.1 | 3 |
| AC-7.2 | 4, 8 |
| AC-7.3 | 8 |
| AC-7.4, 7.6 | 8 |
| AC-7.5 | (passive — no eval/pickle/exec used; documented in step 10 summary) |
| AC-D.1, D.2, D.3 | 10 |

All 30 ACs traced.

---

## How to Approve

This plan is the single source of truth for `u1` Code Generation. Reply
**approve** to begin Step 1; **changes [N]** to revise step N.
