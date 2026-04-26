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

### Step 2: `_window.py` — FetchWindow value object ✅

- [x] **2.1** `src/investo/sources/_window.py` — frozen+slots dataclass; `from_kst_date` classmethod (KST→UTC via `zoneinfo`); `contains` half-open `[start, end)`; tz-aware checks via shared `_ensure_tz_aware` helper
- [x] **2.2** Anchor tests: known case `2026-04-27 → [2026-04-26 15:00 UTC, 2026-04-27 15:00 UTC)`; 24-h span; frozen; naive rejection on both bounds + on `contains`; inverted/zero-length window; year-boundary; leap day; fixed-offset tz
- [x] **2.3** PBT: AC-6.1 window invariants + AC-6.2 half-open membership, 100 examples each
- [x] **2.4** Sub-agent code review — fixed in-step:
  - **M1**: `from_kst_date` boundary dates (`date.min`/`date.max`) now wrap `OverflowError` → `ValueError("out of supported range")` + 2 regression tests
  - **L2**: hostile `tzinfo` whose `utcoffset()` raises → wrapped to `ValueError` + 2 regression tests using a synthetic `_RaisingTZ` subclass
  - **L1**: documented copy/pickle bypass caveat in module docstring
  - **L3**: cosmetic, skipped

**Quality gate**: ruff ✅, mypy strict ✅, pytest 123/123 (101 models + 22 window). PBTs each ran 100 examples.

---

### Step 3: `_retry.py` — shared retry/backoff helper ✅

- [x] **3.1** `src/investo/sources/_retry.py` — `RetryConfig` (frozen+slots dataclass with validation in `__post_init__`); `SourceFetchError` (lives here pending Step 5 relocation to `protocol.py`); pure `compute_sleep`; `async retry_get` wrapping inner loop in `asyncio.wait_for(timeout=total_budget_s)` for outer cap. Surface diverges from plan: explicit `url` / `headers` / `params` kwargs instead of `request_kwargs` dict (better mypy strict ergonomics; documented in module docstring). HTTP status classification: 5xx + 429 + `TimeoutException`/`NetworkError`/`RemoteProtocolError` = retryable; 4xx-not-429 + other `httpx.HTTPError` (e.g. `UnsupportedProtocol`) + oversized body = terminal.
- [x] **3.2** `tests/unit/sources/test_retry.py` — 38 tests including 2 PBTs at 100 examples each:
  - PBT 1 (**AC-6.3**): `0 ≤ compute_sleep ≤ 30` for arbitrary `attempt` ∈ [-2,10] and arbitrary `retry_after_header` ∈ {None, arbitrary text up to 64 chars}
  - PBT 2 (**AC-6.3**): `compute_sleep(1, str(seconds))` = `min(seconds, 30)` for arbitrary non-negative `seconds`
  - MockTransport scenarios: first-try success; 5xx then 200; 429+Retry-After then 200; ConnectError then 200; exhausted 5xx → `SourceFetchError(transient=True)` after 3 calls; exhausted ReadTimeout → same; 4xx-not-429 → `transient=False` no retry; oversized body → `transient=False`; `file://` URL → `transient=False`
  - Retry-After honoring (FD R5): timing test confirms 50 ms Retry-After overrides 1 s default backoff
  - Outer budget (**AC-1.2**): 100 ms budget vs 1 s handler sleep → `transient=True, "budget"` at ~100 ms
- [x] **3.3** Sub-agent code review — APPROVE; 0 Critical/High/Medium, 3 Lows + 1 TECH-DEBT:
  - **L1**: `last_exc` tracking variable was dead code → removed; defensive trailer simplified to `raise AssertionError(...)  # pragma: no cover`
  - **L2**: `_mock_client` test helper carries one `# type: ignore[arg-type]` (cosmetic, mypy already passes) — skipped
  - **L3**: surface choice (explicit kwargs vs `request_kwargs` dict) already documented in module docstring — skipped
  - **DEBT-003**: post-hoc 5 MB body cap (httpx buffers full body before len-check fires) — registered in `docs/TECH-DEBT.md` as Low; revisit when a non-RSS adapter lands

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅, pytest 161/161 (101 models + 22 window + 38 retry). PBTs each ran 100 examples.

---

### Step 4: `_sanitize.py` — HTML strip helper ✅

- [x] **4.1** `src/investo/sources/_sanitize.py` — `strip_html(text: str) -> str` pipeline: `bleach.clean(text, tags=[], strip=True, strip_comments=True)` → `html.unescape` → whitespace collapse via `re.compile(r"\s+")` (matches Unicode whitespace including U+00A0/U+3000, desirable for CJK feeds). Empty/whitespace-only input returns `""`.
- [x] **4.2** `tests/unit/sources/test_sanitize.py` — 25 anchor tests covering: empty/whitespace input; plain-text passthrough; tag stripping (`<b>` / nested / `<br/>` self-closing / `<a href=javascript:>` attributes); script + style content neutralized (no `<` / `>` in output); HTML comments stripped; entity decoding (named `&amp;` / `&lt;` / `&gt;`, numeric `&#39;`, double-escape decodes once); Unicode preservation (Korean / emoji / mixed); whitespace normalization (spaces, newlines, tabs, outer); lone `<` and comparison expressions (`a < b > c`); idempotence on clean and dirty input.
- [x] **4.3** Sub-agent code review — APPROVE_WITH_NOTES; 0 Critical/High/Medium, 4 Lows + 1 TECH-DEBT:
  - **L1**: `strip_comments=True` is the bleach 6 default but defensible to keep explicit — left as-is
  - **L2**: added comment documenting that `\s` matches Unicode whitespace (NBSP / U+3000) — applied
  - **L3**: added `test_comparison_expression_preserved` for `"price < 100"` and `"a < b > c"` — applied
  - **L4**: reworded `test_script_tag_content_neutralized` comment to keep the assertion local (no cross-references to downstream renderer) — applied
  - **DEBT-004**: bleach is in maintenance-only mode; `nh3` is the actively-maintained successor — registered in `docs/TECH-DEBT.md` as Low; revisit on bleach EOL or deprecation warnings

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅ (added `types-bleach>=6` to dev deps), pytest 186/186 (101 models + 22 window + 38 retry + 25 sanitize).

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
