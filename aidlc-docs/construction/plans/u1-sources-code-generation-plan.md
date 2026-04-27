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

### Step 5: `protocol.py` — SourceAdapter + SourceFetchError ✅

- [x] **5.1** `src/investo/sources/protocol.py` — canonical home for `SourceFetchError` (Exception subclass with `source_name` / `transient` / `cause: BaseException | None`, message format `source 'name' failed: message`) and the `SourceAdapter` Protocol (class-level `ClassVar[str] name`, `ClassVar[Category] category`, `async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]`). Pinned behavior: NOT `@runtime_checkable` (registry uses class-attribute inspection at registration time, not isinstance). `_retry.py` updated to `from investo.sources.protocol import SourceFetchError` + `__all__` re-exporting it for backward compatibility with prior imports.
- [x] **5.2** `tests/unit/sources/test_protocol.py` — 13 anchor tests covering: `SourceFetchError` is `Exception` (not `RuntimeError`); attribute presence (with/without cause); `from`-chain preserves `__cause__`; `BaseException` cause accepted; re-export identity (`investo.sources._retry.SourceFetchError is investo.sources.protocol.SourceFetchError`); Protocol introspection via `_is_protocol`; not-runtime-checkable via `_is_runtime_protocol`; annotation presence; concrete `_StubAdapter` assigned to `SourceAdapter`-typed binding (mypy-side proof) + async fetch returns `[]`.
- [x] **5.3** Sub-agent code review — APPROVE_WITH_NOTES; 0 Critical/High, 1 Medium (M1 weak `pytest.raises(TypeError)` pin) + 4 Lows + audit-log note:
  - **M1**: replaced `pytest.raises(TypeError)` shape-pin with direct `_is_runtime_protocol` introspection — applied
  - **L1**: replaced MRO walk with `_is_protocol` introspection — applied
  - **L3**: stub-fetch test opens an unused `httpx.AsyncClient` — skipped (cosmetic)
  - **L4**: confirm pytest-asyncio auto-mode — already set in `pyproject.toml`
  - **Audit-log note**: `fetch(client, window)` signature diverges from FD §E1 / R3 (`fetch(client, target_date)`) — defensible refinement (aggregator builds `FetchWindow` once instead of every adapter re-deriving it from `target_date`); ratified in audit log Step 5 entry

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅, pytest 199/199 (101 models + 22 window + 38 retry + 25 sanitize + 13 protocol).

---

### Step 6: `_registry.py` — @register decorator + list_sources ✅

- [x] **6.1** `src/investo/sources/_registry.py` — module-level `_ADAPTERS: dict[str, SourceAdapter] = {}`; `register(cls: type[_AdapterT]) -> type[_AdapterT]` (TypeVar bound to `SourceAdapter` so the decorator preserves the precise concrete type); duplicate-check fires before dict mutation, `RuntimeError("duplicate source name: '...')` on collision; `list_sources()` returns `list(_ADAPTERS.values())` — fresh copy each call; `_clear_for_test()` for fixture isolation.
- [x] **6.2** `tests/unit/sources/test_registry.py` — 12 tests with autouse `_isolate_registry` fixture (snapshot/clear/yield/restore via try-finally): happy-path register adds adapter; decorator returns `cls` unchanged; `list_sources` returns singleton instances with insertion-order preservation; empty registry initially; duplicate name → `RuntimeError` matching `"duplicate source name"`; error message contains the slug; failed registration does NOT replace existing entry; mutation of `list_sources()` return value does not affect the registry; each call returns a fresh list (but same singleton instances inside); `_clear_for_test` empties the registry; `_clear_for_test` allows re-registration of a previously-used name.
- [x] **6.3** Sub-agent code review — APPROVE; 0 Critical/High/Medium, 3 Lows (all optional polish):
  - L1 PEP 695 syntax — requires Python 3.12+; project pins 3.11+, skipped
  - L2 cosmetic nit on `sources.append("not an adapter")` test fixture — skipped (reads fine as-is)
  - L3 docstring cross-reference enhancement — skipped (cosmetic)
  - No TECH-DEBT registered

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅, pytest 211/211 (101 models + 22 window + 38 retry + 25 sanitize + 13 protocol + 12 registry).

---

### Step 7: `aggregator.py` — fetch_all ✅

- [x] **7.1** `src/investo/sources/aggregator.py` — `async def fetch_all(target_date: date) -> list[NormalizedItem]`. Early-return `[]` if registry is empty. Otherwise: build `FetchWindow.from_kst_date(target_date)`, open shared `httpx.AsyncClient` via `async with`, dispatch via `asyncio.gather(*(adapter.fetch(client, window) for adapter in adapters), return_exceptions=True)`. Per-result loop: `SourceFetchError` → WARNING log with exception's self-reported `source_name` + `transient` flag (intentionally surfaces R8 violations); other `BaseException` (incl. CancelledError / KeyboardInterrupt / SystemExit) → re-raise; `list[NormalizedItem]` → flatten into result.
- [x] **7.2** `tests/unit/sources/test_aggregator.py` — 11 anchor tests covering: AC-3.5 (empty registry + empty result do not raise); happy path (single adapter, multiple adapters concatenated, window dispatched correctly); AC-3.1/3.2 (`SourceFetchError` caught + logged with source_name and `transient=True`/`False`); AC-3.3 (1 fail / 2 success → 2 good lists); AC-3.4 (all fail → `[]`); programmer-error propagation (`KeyError` and `RuntimeError` both kill the run, even with sibling-success adapters).
- [x] **7.3** `tests/unit/sources/test_fetch_all_budget.py` — 2 timing tests: AC-1.1 scaled by 100x (1 slow 0.5s + 2 fast → returns ≤ 0.7s); concurrency proof (3 × 0.3s sleeping adapters → returns ≤ 0.75s, distinguishing concurrent vs sequential dispatch).
- [x] **7.4** Sub-agent code review — APPROVE_WITH_NOTES; 0 Critical/High, 2 Mediums + 3 Lows + 1 TECH-DEBT, all applied:
  - **M1** BaseException catch covers CancelledError/KeyboardInterrupt/SystemExit — added inline comment confirming the breadth is deliberate
  - **M2** Log uses `result.source_name` (exception-reported) not `adapter.name` (registry-authoritative) — kept current behavior with comment justifying the choice (R8 violations surface as debug signal)
  - **L3** Bumped concurrency-test bound from `< 0.6` to `< 0.75` for slow-CI headroom
  - **L4** Extracted duplicated `_isolate_registry` autouse fixture to `tests/unit/sources/conftest.py` (3 copies → 1)
  - **DEBT-005** registered (Low): printf-style log line vs L5's structured-fields spec; revisit on operations ADR
- **Side-fix during Step 7 quality gate**: hypothesis surfaced a pre-existing bug in `_parse_retry_after` (Step 3) where `"NaN"` parses to `float('nan')` and bypasses the `[0, max_retry_after_s]` bound (NaN comparisons return False). Added `math.isfinite` guard + 4 regression tests (`NaN`, `nan`, `Infinity`, `-Infinity`, `inf` all return `None`). Same fix covers `Inf` family.

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅, pytest 226/226 (101 models + 22 window + 42 retry + 25 sanitize + 13 protocol + 12 registry + 11 aggregator).

---

### Step 8: `fomc_rss.py` reference adapter + recorded fixture ✅

- [x] **8.1** Recorded `tests/unit/sources/fixtures/api/fomc-rss/feed.xml` (14 KB, real one-off `curl` to `https://www.federalreserve.gov/feeds/press_all.xml`) + `meta.json` (status 200, content-type, etag, last-modified). **FD-vs-impl divergence**: feed turned out to be **RSS 2.0**, not Atom 1.0 as the FD listed. Updated FD L6 to match reality + ratified in audit log Step 8.
- [x] **8.2** `src/investo/sources/fomc_rss.py` — `FomcRssAdapter` with `@register`, `name="fomc-rss"`, `category="calendar"` (with comment justifying calendar-vs-news taxonomy choice), `_FEED_URL` constant, `fetch` calls `retry_get`, `defusedxml.ElementTree.fromstring` parse, per-entry normalization: `<title>` HTML-stripped, `<description>` HTML-stripped + truncated to 280, `<link>` scheme-guarded (http/https only), `<pubDate>` RFC 822 → tz-aware UTC via `email.utils.parsedate_to_datetime`, `<guid>` + `<category>` to `raw_metadata`, `pydantic.ValidationError` per-entry → drop. `_normalize_entry` parameter typed `Any` (importing `Element` would either touch stdlib XML — forbidden by AC-7.6 grep — or require type-stub gymnastics).
- [x] **8.3** `tests/unit/sources/test_fomc_rss.py` — 13 tests covering: real-fixture happy path (window includes 2 entries dated 2026-04-24 20:00 GMT against KST 2026-04-25 trading day); empty window returns `[]`; tz-aware UTC `published_at` (AC-7.4); full field population including `raw_metadata` keys; AC-7.2 (HTML-in-title `<b>Stress test</b>` → `"Stress test"`); AC-7.3 (3 entries: https + `file://` + `javascript:` → only https survives); malformed XML → terminal `SourceFetchError`; missing-required-fields entries dropped; summary truncation at 280-char + boundary tests (280 unchanged, 281 trimmed); naive-pubDate (`-0000`) + garbage-pubDate both dropped; class-attribute identity check.
- [x] **8.4** `tests/unit/sources/test_xml_safety.py` — 2 grep tests pinning AC-7.6: forbidden regex matches `xml.{etree,dom,sax,parsers}.*` top-level imports across `src/investo/sources/**`; positive guard asserts `fomc_rss.py` imports `defusedxml` via top-level import statement (regex match, not just substring).
- [x] **8.5** Sub-agent code review — APPROVE_WITH_NOTES; 0 Critical/High, 2 Mediums + 6 Lows + 1 doc note. Applied: M1 (tightened naive-pubDate test to `assert items == []`); L2 (calendar-vs-news comment); L4 (boundary tests for summary truncation at 280/281); L5 (regex extended to include `xml.parsers.expat`); L6 (defusedxml positive guard tightened to regex); doc note (FD L6 corrected to RSS 2.0). Skipped: M2 (`Any` typed-`_normalize_entry`) — agent's proposed `defusedxml.ElementTree.Element` import doesn't actually export at runtime (verified); current Any is documented + tested. L1 (NBSP-only title) skipped — chain works through `strip_html`. L3 (AC-7.5 grep) deferred to Step 10 per plan.
- **Side-update**: added `types-defusedxml>=0.7` to dev deps.

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅, pytest 241/241 (101 models + 22 window + 42 retry + 25 sanitize + 13 protocol + 12 registry + 11 aggregator + 13 fomc_rss + 2 xml_safety).

---

### Step 9: `__init__.py` — adapter discovery + plugin contract test ✅

- [x] **9.1** `src/investo/sources/__init__.py` — populated with adapter discovery (`from . import fomc_rss  # noqa: F401` triggers `@register` at first package import) and public re-exports (`SourceAdapter`, `SourceFetchError`, `list_sources`, `fetch_all`, `FetchWindow`). `__all__` lists exactly that 5-name surface — internal helpers (`_window`, `_retry`, `_sanitize`, `_registry`, `register`, `RetryConfig`, etc.) are intentionally NOT re-exported. Module docstring documents the **NFR AC-5.4** 4-step procedure for adding a new adapter (create file → define class → apply `@register` → add `from . import <name>`).
- [x] **9.2** `tests/unit/sources/test_plugin_contract.py` — 7 tests with an autouse-fixture override that snapshots / clears / re-registers `FomcRssAdapter` / yields / restores (mirrors production state instead of conftest's clean-slate isolation). Covers: **AC-5.2** drift guard (count + names sets); +1 stub registration proves the guard is meaningful (not tautological); **AC-5.3** duplicate-name with the production slug `"fomc-rss"` raises `RuntimeError("duplicate source name")`; `__all__` content lock; internal-helper non-leak guard; re-export identity (each public name `is` the canonical object from its defining module).
- **Code review**: Sub-agent APPROVE; 0 Critical/High/Medium, 4 Lows (all optional polish):
  - L1 docstring "4-line" wording — skipped (mirrors NFR AC-5.4 phrasing)
  - L2 merge count + names tests — skipped (kept split for diagnostic clarity)
  - L3 comment near `EXPECTED_ADAPTER_COUNT` reminding to bump on adapter add/remove — applied
  - L4 actual `import *` execution test — skipped (`__all__` IS the contract; asserting on it directly is the canonical approach)

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅, pytest 248/248 (101 models + 22 window + 42 retry + 25 sanitize + 13 protocol + 12 registry + 11 aggregator + 13 fomc_rss + 2 xml_safety + **7 plugin_contract**).

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
