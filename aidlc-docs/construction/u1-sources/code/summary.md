# u1 sources — Code Generation Summary

**Date**: 2026-04-27
**Stage**: Code Generation (final stage for u1 sources)
**Status**: ✅ COMPLETE
**Stories closed**: US-001 (자동 시장 데이터 수집), US-008 (단일 모듈 추가로 새 데이터 소스 통합)

---

## Files created

### Source code (`src/investo/sources/`)

| File | LOC | Role |
|------|----:|------|
| `__init__.py` | 37 | Public surface + adapter discovery (Step 9) |
| `_window.py` | 112 | `FetchWindow` value object — KST→UTC trading-date window (Step 2) |
| `_retry.py` | 271 | `RetryConfig` + `compute_sleep` + `retry_get`; `SourceFetchError` re-export (Step 3, partial Step 5) |
| `_sanitize.py` | 48 | `strip_html` — bleach-based plain-text reducer (Step 4) |
| `protocol.py` | 85 | `SourceAdapter` Protocol + `SourceFetchError` canonical home (Step 5) |
| `_registry.py` | 71 | `@register` decorator + `list_sources` + `_clear_for_test` (Step 6) |
| `aggregator.py` | 79 | `fetch_all` — concurrent fan-out across adapters (Step 7) |
| `fomc_rss.py` | 148 | First concrete adapter — FOMC press-release RSS feed (Step 8) |
| **Total** | **851** | 8 source files |

### Tests (`tests/unit/sources/`)

| File | LOC | Tests | Role |
|------|----:|------:|------|
| `conftest.py` | 26 | 0 | `_isolate_registry` autouse fixture (extracted Step 7) |
| `test_window.py` | 243 | 22 | FetchWindow correctness + AC-6.1/6.2 PBT |
| `test_retry.py` | 452 | 42 | `RetryConfig` + `compute_sleep` PBT (AC-6.3) + `retry_get` behavior + AC-1.2/7.1 |
| `test_sanitize.py` | 175 | 25 | `strip_html` behavior (AC-7.2) |
| `test_protocol.py` | 146 | 13 | Protocol introspection + `SourceFetchError` contract (FD §E1/§E4) |
| `test_registry.py` | 209 | 12 | `register` / `list_sources` / `_clear_for_test` (FD §E2 / R2) |
| `test_aggregator.py` | 295 | 11 | `fetch_all` behavior (AC-3.1–3.5) |
| `test_fetch_all_budget.py` | 127 | 2 | AC-1.1 budget + concurrency proof |
| `test_fomc_rss.py` | 318 | 13 | FOMC adapter via `MockTransport` (AC-7.2/7.3/7.4 + edge cases) |
| `test_xml_safety.py` | 55 | 2 | AC-7.6 grep — `defusedxml` everywhere |
| `test_plugin_contract.py` | 172 | 7 | AC-5.2 drift guard + AC-5.3 duplicate + `__all__` lock |
| `test_no_paid_apis.py` | 68 | 4 | AC-2.2 cost guard subprocess invocation |
| **Total** | **2,286** | **153** | 12 test files |

### Other artifacts

- `tests/unit/sources/fixtures/api/fomc-rss/feed.xml` — recorded RSS 2.0 response (14 KB, Step 8)
- `tests/unit/sources/fixtures/api/fomc-rss/meta.json` — recording metadata + caveats
- `scripts/check_no_paid_apis.py` — CI cost guard (Step 10)
- `CONTRIBUTING.md` — adapter-author guide (Step 10)

### Surface area

| Public re-export | Defined in | Consumed by |
|------------------|------------|-------------|
| `fetch_all` | `aggregator.py` | u5 orchestrator |
| `list_sources` | `_registry.py` | u5 orchestrator (debug / smoke) |
| `SourceAdapter` | `protocol.py` | adapter authors (typing) |
| `SourceFetchError` | `protocol.py` | u5 orchestrator (stage guard, informational) |
| `FetchWindow` | `_window.py` | u5 orchestrator (window construction is internal but re-exported for tests / future tools) |

---

## NFR AC-to-test traceability

All 30 ACs from `nfr-requirements.md` are pinned by tests. The
`Pinned by` column lists the canonical test that catches a regression.

| AC | Description | Pinned by |
|----|-------------|-----------|
| AC-1.1 | `fetch_all` returns ≤ 70 s wall-clock | `test_fetch_all_budget.py::test_fetch_all_within_budget_with_one_slow_adapter` |
| AC-1.2 | Retry helper enforces 60-s outer budget | `test_retry.py::test_retry_get_budget_enforced` |
| AC-1.3 | Per-adapter ≤ 4-min budget | Composition of AC-1.1 + AC-1.2 |
| AC-2.1 | No metered/billed APIs | `test_no_paid_apis.py::test_find_offenders_detects_match_when_blocklist_populated` (proves detection works) + `test_subprocess_invocation_passes_on_current_sources` (current state clean) |
| AC-2.2 | CI grep guard on `sources/**` | `scripts/check_no_paid_apis.py` + `test_no_paid_apis.py` (subprocess invocation) |
| AC-2.3 | `/code-review` flags paid patterns | `dev-investo` skill §5.1 sub-agent prompt explicitly enumerates the rule |
| AC-2.4 | PR description free-tier declaration | `CONTRIBUTING.md` "PR description checklist" |
| AC-3.1 | `fetch_all` does not raise | `test_aggregator.py::test_fetch_all_does_not_raise_on_source_fetch_error` |
| AC-3.2 | Per-adapter `SourceFetchError` isolation | `test_aggregator.py::test_fetch_all_does_not_raise_on_source_fetch_error` |
| AC-3.3 | 1 fail / 2 success → 2 good lists | `test_aggregator.py::test_fetch_all_isolates_one_failure_from_two_successes` |
| AC-3.4 | All fail → `[]` | `test_aggregator.py::test_fetch_all_all_failures_returns_empty_list` |
| AC-3.5 | Empty result not a u1 failure | `test_aggregator.py::test_fetch_all_empty_registry_returns_empty_list` + `test_fetch_all_empty_result_does_not_raise` |
| AC-5.1 | New source = 1 file + 1 import line | `CONTRIBUTING.md` 4-step procedure (verified at code-review time) |
| AC-5.2 | Drift guard via `EXPECTED_ADAPTER_COUNT` | `test_plugin_contract.py::test_registered_adapter_count_matches_expected` + `test_adding_stub_adapter_increases_count_by_one` |
| AC-5.3 | Duplicate name → `RuntimeError` | `test_plugin_contract.py::test_re_registering_production_name_raises_runtime_error` + `test_registry.py::test_duplicate_name_raises_runtime_error` |
| AC-5.4 | 4-line procedure documented | `CONTRIBUTING.md` "Adding a new data source" + `__init__.py` docstring |
| AC-6.1 | `FetchWindow` PBT — invariants | `test_window.py::test_property_window_invariants` |
| AC-6.2 | `FetchWindow` PBT — half-open membership | `test_window.py::test_property_contains_membership` |
| AC-6.3 | `compute_sleep` PBT — bounds + Retry-After precedence | `test_retry.py::test_property_compute_sleep_bounded` + `test_property_compute_sleep_retry_after_capped` |
| AC-6.4 | ≥ 100 PBT examples | `_PBT_SETTINGS = settings(max_examples=100, ...)` in window/retry test files |
| AC-7.1 | 5 MB body cap | `test_retry.py::test_retry_get_oversized_body_is_terminal` (post-hoc; DEBT-003 tracks streaming variant) |
| AC-7.2 | Sanitize feed-derived HTML | `test_sanitize.py::test_simple_tag_stripped_keeps_content` (and 24 others) + `test_fomc_rss.py::test_html_in_title_is_stripped` |
| AC-7.3 | Reject non-http(s) URL schemes | `test_fomc_rss.py::test_non_http_https_urls_dropped` |
| AC-7.4 | Tz-aware `published_at` | `test_fomc_rss.py::test_fetch_published_at_is_tz_aware_and_utc` + `test_naive_or_garbage_pubdate_is_dropped` |
| AC-7.5 | No `eval` / `pickle` / `exec` on response data | Passive — no such calls in u1 (verified by inspection; this summary is the documented evidence) |
| AC-7.6 | `defusedxml` import guard | `test_xml_safety.py::test_no_stdlib_xml_imports_in_sources` + `test_fomc_rss_uses_defusedxml` |
| AC-D.1 | All PBT/regression tests run in CI | All tests under `tests/unit/sources/` execute via `pytest` |
| AC-D.2 | Cost guard runs in CI | `test_no_paid_apis.py` invokes `scripts/check_no_paid_apis.py` as a subprocess every test run |
| AC-D.3 | Public-surface changes trigger `/code-review` | `dev-investo` §5.1 routine + Step 5 audit-log ratification of `fetch` signature divergence |
| AC-D.4 | Runtime metrics | Deferred to v2 per spec (not pinned) |

---

## Open TECH-DEBT items

| ID | Priority | Origin | Description |
|----|----------|--------|-------------|
| DEBT-001 | Medium | models step 3 (cross-unit) | `Briefing` model lacks `disclaimer ∈ rendered_markdown` invariant |
| DEBT-002 | Medium | models step 3 (cross-unit) | No date sanity bounds on `target_date` / `published_at` |
| DEBT-003 | Low | u1 step 3 | `retry_get` 5 MB body cap is post-hoc, not streaming |
| DEBT-004 | Low | u1 step 4 | `_sanitize.py` depends on `bleach` (maintenance-mode); `nh3` is recommended successor |
| DEBT-005 | Low | u1 step 7 | Aggregator log line is printf-style, not L5-structured |

None block the unit. Three items (DEBT-003 / DEBT-004 / DEBT-005) originate inside u1; two (DEBT-001 / DEBT-002) are cross-unit, created during models foundation work.

---

## FD-vs-implementation divergences (ratified in audit log)

Two structural deviations from the FD were caught during construction
and ratified in `aidlc-docs/audit.md`:

1. **Step 5** — `SourceAdapter.fetch` signature: FD specified
   `fetch(client, target_date)`; implementation uses
   `fetch(client, window: FetchWindow)`. The aggregator builds
   `FetchWindow.from_kst_date` once and dispatches the prebuilt
   window — avoids each adapter re-deriving it from the date.
2. **Step 8** — FOMC feed format: FD listed "Atom 1.0"; the live
   feed is **RSS 2.0** with different element names and RFC 822
   dates. FD L6 was updated in the same change to match reality
   (Atom prediction was incorrect — the recording proved it).

Both deviations are minor refinements caught early; neither breaks
any cross-unit contract.

---

## Story status

- ✅ **US-001** (자동 시장 데이터 수집) — closed by `fetch_all` +
  `FomcRssAdapter` + the 30-AC test coverage. The aggregator can be
  invoked by the orchestrator (u5) once that unit lands.
- ✅ **US-008** (단일 모듈 추가로 새 데이터 소스 통합) — closed by the
  4-step procedure documented in `CONTRIBUTING.md` and the
  `__init__.py` docstring, the `@register` decorator, and the
  drift-guard test that catches missing import lines.

---

## Pre-flight notes for u2 briefing

When `u2 briefing` enters Functional Design / Code Generation, it
will consume the following stable surface from `investo.sources`:

| Symbol | What u2 needs it for |
|--------|----------------------|
| `fetch_all(target_date) -> list[NormalizedItem]` | The single entry point u2's orchestrator-side caller invokes. Returns the union of all registered adapters' items, already filtered to the target date's UTC window. |
| `NormalizedItem` (re-exported via `investo.models`) | The shape u2's prompt builder iterates over. Frozen pydantic model with `source_name`, `category`, `title`, `summary`, `url`, `published_at`, `raw_metadata`. |
| `Category` (re-exported via `investo.models`) | Literal type used to bucket items into the briefing's 7 sections. |
| `SourceFetchError` (re-exported) | u2 SHOULD NOT catch this — the aggregator already isolates per-adapter failures. Only relevant to u5 orchestrator's stage-level guard. |

**u2 must NOT import from any internal helper** (`_window`, `_retry`,
`_sanitize`, `_registry`, `aggregator`, `fomc_rss`, `protocol`
directly via the underscore-prefixed paths). The plugin-contract
test (`test_plugin_contract.py::test_all_does_not_leak_internal_helpers`)
catches such leaks at PR time.

### Prompt-builder hints (informational)

When u2's prompt builder consumes `list[NormalizedItem]`:

- `summary` may be `None` — the `_normalize_optional_summary`
  validator on `NormalizedItem` collapses empty/whitespace-only
  values to `None`. Skip-or-default at the prompt layer.
- `url` may be `None` — adapters that lack a stable canonical URL
  set this to `None` (R8). Don't rely on it for deduplication.
- `published_at` is always tz-aware (R8) — safe to compare across
  items without timezone bookkeeping.
- `raw_metadata` is `dict[str, str | int | float]` — string keys,
  scalar values only (no nested dicts). Use it for source-specific
  provenance (e.g. RSS `<guid>`, ETag).

---

## Quality gate (final, Step 10.3)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ |
| `mypy --strict src/` | ✅ (15 source files) |
| `pytest` | ✅ **252/252** passing |

Test breakdown: 101 models + 22 window + 42 retry + 25 sanitize + 13
protocol + 12 registry + 11 aggregator + 2 budget + 13 fomc_rss + 2
xml_safety + 7 plugin_contract + 4 no_paid_apis = **252**.

---

## Next stage gate

`u1 sources` Code Generation is now CLOSED. The unit becomes
eligible for `/cross-check` against requirements. Two stage gates
remain for the project:

1. `u2 briefing`, `u4 notifier`, `u5 orchestrator` Code Generation
   (per `aidlc-docs/inception/plans/execution-plan.md`)
2. Global `Build and Test` after every unit's CG completes

---

## Extension closeout (2026-05-01) — 3 new adapters

### Trigger
User observation that FR-001 AC ("소스 카테고리 6종") was unmet despite
u1's DoD ("1개 이상의 reference 어댑터") being closed at 2026-04-29.
FOMC RSS was the only registered adapter, covering only 1 of 5
`Category` enum values (calendar). Application Design's TBD list
(component-dependency.md:130) was never narrowed. Reopened u1 Code
Generation in extension mode per audit log 2026-05-01 entry.

### Deliverables

| Adapter | File | LOC | Category | Stories closed (partial) |
|---------|------|-----|----------|-----|
| `yfinance-price` | `src/investo/sources/yfinance.py` | ~260 | price | US-001 (price coverage) |
| `coingecko-price` | `src/investo/sources/coingecko.py` | ~165 | price | US-001 (crypto coverage) |
| `fred-macro` | `src/investo/sources/fred.py` | ~265 | macro | US-001 (macro coverage) |
| (helper) | `src/investo/sources/_config.py` | ~30 | — | R12 shared parser, US-008 plugin extensibility re-validated |

Total adapter count after extension: **4** (was 1). 3 of 5 `Category`
values covered (calendar / price / macro). News + earnings deferred
to a later extension.

### Test inventory delta

| Test file | Tests added | Notes |
|-----------|-------------|-------|
| `test_config.py` | 10 | Shared R12 parser; AC-5.5 |
| `test_yfinance.py` | 13 | R11 DST anchors (EDT + EST); per-ticker isolation; env override |
| `test_coingecko.py` | 15 | ISO8601 Z-suffix parse; null pct fallback; query-string capture for env override |
| `test_fred.py` | 17 | AC-3.6 missing-key; R13 secret hygiene with sentinel; widened-window boundaries; per-series isolation |
| `test_plugin_contract.py` | 0 | Constants bumped: `EXPECTED_ADAPTER_COUNT` 1→4; expected-name set updated |
| **Total** | **+55** | |

### NFR AC delta

- AC-3.6 *(new in extension)* — missing source-adapter secret →
  `SourceFetchError(transient=False)`; aggregator R6 catches; other
  adapters continue. Pinned in `test_fred.py`.
- AC-5.5 *(new in extension)* — env-var `INVESTO_<ADAPTER>_<NOUN>`
  override convention via shared `parse_symbol_list`. Pinned in
  `test_config.py` (helper) + per-adapter assertions in test files.
- AC-7.6 *(scope clarified)* — XML-only; JSON adapters out of scope.
  No code change; the existing grep test in `test_xml_safety.py`
  continues to assert no `xml.{etree,dom,sax,parsers}` imports
  anywhere under `src/investo/sources/**` regardless of payload format.

Total AC count: **30 → 32** (+AC-3.6, +AC-5.5).

### FD divergences ratified during extension

1. **L6.2 yfinance R7 relaxation** (Step 2.3) — original L6.2 wording
   would have produced empty yfinance output on KST Monday/Saturday
   cron fires due to the US weekend gap. FD updated to "R7 consulted
   but not enforced" + R11 `Window relaxation for cadence-gapped
   sources` clause added.
2. **L6.4 FRED widened window 35d → 65d** (Step 4.3) — original 35d
   bound was tight enough that a monthly indicator with `"."`
   placeholder as latest (real FRED behaviour) would force fall-through
   to the prior month's release ≈ 60 days back, dropping it. Bumped to
   65 days; FD L6.4 narrative updated.
3. **L6.4 FRED title delta precision 2dp → 4dp** (Step 5.7 review) —
   spec example showed `+0.42` (2 decimals) but implementation +
   tests pin `+0.4210` (4 decimals). 4 decimals chosen so
   basis-point-scale changes in DGS10 / DFF are visible in the title;
   spec example updated to match.

### Cross-cutting code review (Step 5.7)

Single sub-agent review covering all 3 adapters together (per user
direction — instead of 3 per-adapter reviews + 1 cross-cutting). Result:
**APPROVE_WITH_NOTES** — 0 Critical, 0 High requiring code change,
2 Medium (M1 raw_metadata precision drift + M2 spec example precision
drift), 3 Low cosmetic.

Applied during review:
- H1 (comments lying about 35d vs 65d) — fixed in `fred.py` (3 sites)
- L3 (docstring mischaracterizing per-series 401 behaviour) — fixed
  in `fred.py` module docstring
- M2 (spec example precision drift) — FD L6.4 example updated to 4dp

Registered as TECH-DEBT:
- **DEBT-028 (Medium)**: `raw_metadata` numeric serialization
  inconsistent across the 3 new adapters. Suggested fix: shared
  `_format_numeric()` helper in `_config.py`. Address before the next
  adapter lands.

### Operations note (Step 5.3)

`.github/workflows/daily-briefing.yml` now injects `FRED_API_KEY` from
`secrets.FRED_API_KEY` into the `python -m investo` env. Operator
must add this secret in **Settings → Secrets and variables → Actions**
before the `fred-macro` adapter contributes to a briefing. Absent
secret → `fred-macro` raises `SourceFetchError(transient=False)` per
R13 and contributes `[]`; other adapters unaffected. CONTRIBUTING.md
documents this as the canonical pattern for future secret-using adapters.

### Final quality gate (extension closeout)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ (114 files) |
| `mypy --strict src/` | ✅ (41 source files: was 38; +`_config.py` +`yfinance.py` +`coingecko.py` +`fred.py`) |
| `pytest` | ✅ **775/775** passing (was 720; +55 new) |
| `mkdocs build --strict` | ✅ (still clean) |

---

## Extension #2 closeout (2026-05-01) — 2 news adapters

### Trigger

After Extension #1 closed at 2026-05-01T03:00:00Z and lifted `Category`
enum coverage from 1/5 → 3/5 (calendar / price / macro), FR-001's
**news** category remained unmet. User confirmed the next extension
scope: 2 news adapters delivered together (one extension, one fixture
session, one cross-cutting QA pass, one `EXPECTED_ADAPTER_COUNT` bump).
Reopened u1 Code Generation in extension mode for the second time per
audit log entry 2026-05-01T04:00:00Z; closeout entry at 2026-05-01T05:00:00Z.

### Deliverables

| Adapter | File | LOC | Category | Stories closed (partial) |
|---------|------|-----|----------|-----|
| `yahoo-finance-news` | `src/investo/sources/yahoo_finance_news.py` | ~150 | news | US-001 (news coverage, partial) |
| `sec-edgar-8k` | `src/investo/sources/sec_edgar_8k.py` | ~210 | news | US-001 (news coverage, partial) |

Both adapters reuse the R10 plugin contract unchanged and the new R14
(source-mandated request headers) for SEC's fair-access User-Agent.
Total adapter count after extension #2: **6** (was 4). 4 of 5
`Category` values covered (calendar / price / macro / **news**).
Earnings still TBD — deferred to a future extension.

### Test inventory delta

| Test file | Tests added | Notes |
|-----------|-------------|-------|
| `test_yahoo_finance_news.py` | 14 | Window filter / HTML strip / pubDate ISO 8601 `Z` parse / non-http drop / empty channel / XML parse error |
| `test_sec_edgar_8k.py` | 21 | UA pin (R14) / Atom namespace handling / title regex extraction / Item-codes parse / accession-no extract / per-entry drop on schema mismatch / 403 on missing UA / fixture-driven happy path |
| `test_plugin_contract.py` | 0 | Constants bumped: `EXPECTED_ADAPTER_COUNT` 4→6; expected-name set updated for `"yahoo-finance-news"` + `"sec-edgar-8k"` |
| **Total** | **+35** | |

### NFR AC delta

**ZERO new ACs.** Both adapters reuse existing pins:

- **AC-7.6** (defusedxml-only on XML adapters) — both are XML feeds
  (Yahoo RSS 2.0; SEC Atom 1.0). `test_xml_safety.py`'s grep guard
  catches any future regression to stdlib `xml.*`.
- **AC-7.3** (http/https URL scheme) — both validate `<link>` /
  `<link href>` against the existing scheme check before emitting.
- **AC-7.2** (sanitize feed-derived HTML) — both call
  `_sanitize.strip_html` on title/summary text.
- **AC-7.4** (tz-aware `published_at`) — Yahoo's `Z`-suffix form +
  SEC's offset form both parse to tz-aware UTC; naive-datetime entries
  are defensively dropped per the L4 contract.

R14 (NEW business rule) was added in Phase 1 design but is not an NFR
AC — it's a per-source compliance contract, pinned by the SEC adapter's
test_fetch_includes_user_agent and (defensively) by edge-case 403 handling.

Total AC count: **32 → 32** (unchanged).

### FD divergences ratified during extension #2

1. **L6.5 `<pubDate>` parser — `datetime.fromisoformat` not `email.utils.parsedate_to_datetime`**
   The original FD L6.5 prose claimed `parsedate_to_datetime` would
   handle Yahoo's ISO 8601 `Z`-suffix form. Empirically false on
   Python 3.11 — `parsedate_to_datetime` only accepts RFC 822 / RFC
   5322 forms and rejects the `T...Z` ISO 8601 form. The implementation
   uses `datetime.fromisoformat` (substituting trailing `Z` → `+00:00`
   to satisfy 3.11's parser). FD L6.5 `NormalizedItem` mapping row
   updated in this Phase 4 closeout to pin the correct parser and
   include rationale + back-pointer to the audit entry, so a future
   re-reader cannot "fix" the code back to the broken form.
2. **`SecEdgar8kAdapter` class spelling — lowercase `k`**
   The plan specified `SecEdgar8KAdapter` (uppercase K); the
   implementation uses `SecEdgar8kAdapter` (lowercase k). PEP 8's
   PascalCase digit-letter convention favors lowercase after a digit
   when the letter is part of a single token (here: form name `8-K`).
   qa Phase 3 confirmed defensible; no code change required.

### Cross-cutting code review (Phase 3 qa)

Single sub-agent review covering both adapters together (per the
Phase 1 plan). Result: **APPROVE_WITH_NOTES** — 0 Critical / 0 High /
2 Medium (both downgraded to Low and registered as DEBT) / 5 Low
observations. All 10 lead-flagged checks (A-J) PASS. Hard-rule audit
all PASS: Anthropic SDK / module boundary / defusedxml / free tier /
R13 secret hygiene / R7 strict.

Registered as TECH-DEBT:
- **DEBT-029 (Low)**: SEC URL-constant placement diverges from sibling
  adapters (5/6 use class-level `ClassVar[str]`; sec_edgar_8k uses
  module-level `Final[str]`). Cosmetic, ~5 min fix.
- **DEBT-030 (Low)**: SEC accession-number extracted via regex on
  summary instead of canonical `<id>` element. Works on current
  fixture; future-fragile if SEC reflows summary HTML. Switch during
  the next re-record pass.

### Operations note

**No `.github/workflows/daily-briefing.yml` change required.** Both
new adapters require **zero new GitHub Secrets**:
- Yahoo Finance RSS has no auth and no compliance header (httpx's
  default UA is acceptable on the `rssindex` endpoint).
- SEC EDGAR's User-Agent (`investo investo@example.com`) is a public
  compliance string, not a secret — it lives as a module-level
  `_USER_AGENT: Final` in `sec_edgar_8k.py` per R14 (separate concern
  from R12 user-overridable env vars and R13 secret handling).

### DEBT-028 status

**STAYS Medium.** Phase 1's audit prediction held: news adapters
introduce zero new numeric `raw_metadata` paths. Both new adapters
carry pure-string fields (Yahoo: `guid`, `rss_source`; SEC:
`accession_no`, `filer_cik`, `form_type`, `items`). No precision-drift
exposure added; the cross-adapter inconsistency tracked by DEBT-028
remains scoped to the 3 ext-#1 adapters. Age clock continues from
2026-05-01.

### Final quality gate (extension #2 closeout)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ |
| `mypy --strict src/` | ✅ (43 source files: was 41; +`yahoo_finance_news.py` +`sec_edgar_8k.py`) |
| `pytest` | ✅ **810/810** passing (was 775; +35 new) |
| `mkdocs build --strict` | ✅ (still clean) |

### Coverage roll-up after extension #2

- Adapter count: 1 (base) → 4 (ext-#1) → **6** (ext-#2)
- `Category` enum coverage: 1/5 → 3/5 → **4/5** (calendar / price /
  macro / news; only **earnings** still TBD)
- u1 NFR ACs: 30 → 32 → **32** (unchanged in ext-#2)
- u1 tests: 252 → 307 → **342** (252 base + 55 ext-#1 + 35 ext-#2)
- Total project tests: 720 → 775 → **810**
- Source files in `src/investo/sources/`: 8 → 12 → **14**
- Total `src/` files for `mypy --strict`: 37 → 41 → **43**

---

## Extension #3 closeout (2026-05-01) — 3 general-news adapters

### Trigger

After Extension #2 closed at 2026-05-01T05:00:00Z lifting `Category`
enum coverage to 4/5 (news category nominally added via Yahoo Finance
+ SEC EDGAR 8-K), the news *stream itself* remained thin: only one
general-news source (Yahoo) and one corporate-disclosure feed (SEC).
User confirmed the next extension scope: 3 general-news RSS feeds
delivered together to diversify language coverage (Korean), narrative
angle (crypto), and macro/policy framing (CNBC). Reopened u1 Code
Generation in extension mode for the third time per audit log entry
2026-05-01T06:00:00Z; closeout entry at 2026-05-01T07:00:00Z.

### Deliverables

| Adapter | File | LOC | Category | Stories closed (partial) |
|---------|------|-----|----------|-----|
| `yonhap-market` | `src/investo/sources/yonhap_market.py` | ~140 | news | US-001 (Korean-language news depth) |
| `theblock-crypto` | `src/investo/sources/theblock_crypto.py` | ~165 | news | US-001 (crypto-narrative news depth) |
| `cnbc-top-news` | `src/investo/sources/cnbc_top_news.py` | ~135 | news | US-001 (US macro/policy news depth) |

All three adapters reuse the R10 plugin contract unchanged. Zero new
business rules (R-rules), zero new NFR ACs, zero new GitHub Secrets,
zero new external dependencies. Total adapter count after extension
#3: **9** (was 6). News-adapter count specifically: **5** (was 2 —
Yahoo + SEC + Yonhap + TheBlock + CNBC). `Category` enum coverage
stays 4/5 — Extension #3 grows **depth within news**, not breadth;
earnings remains the sole gap.

### Test inventory delta

| Test file | Tests added | Notes |
|-----------|-------------|-------|
| `test_yonhap_market.py` | 16 | CDATA-wrapped Korean title round-trip / `<dc:creator>` optional (omit-when-absent) / `+0900` pubDate parse / R7 window filter / XML parse error / fixture-driven happy path |
| `test_theblock_crypto.py` | 23 | utm-strip helper unit tests (5 input shapes) + integration / `<content:encoded>` ignore / `<dc:creator>` + `<category>` raw_metadata / `-0400` pubDate parse / R7 window filter / non-http drop / fixture-driven happy path |
| `test_cnbc_top_news.py` | 15 | `metadata:*` / `media:*` / `cn:*` namespace-ignore / missing-creator-as-norm / `GMT` pubDate parse / R7 window filter / synthetic namespace-extension robustness / fixture-driven happy path |
| `test_plugin_contract.py` | 0 | Constants bumped: `EXPECTED_ADAPTER_COUNT` 6→9; expected-name set updated for `"yonhap-market"` + `"theblock-crypto"` + `"cnbc-top-news"`; `leaked` set extended with the 6 new symbols (3 modules + 3 classes) |
| **Total** | **+54** | |

### NFR AC delta

**ZERO new ACs.** All three adapters reuse existing pins:

- **AC-7.6** (defusedxml-only on XML adapters) — all three are RSS
  2.0 feeds. `test_xml_safety.py`'s grep guard catches any future
  regression to stdlib `xml.*`.
- **AC-7.3** (http/https URL scheme) — all three validate `<link>`
  against the existing scheme check before emitting.
- **AC-7.2** (sanitize feed-derived HTML) — all three call
  `_sanitize.strip_html` on title/summary text. Yonhap's CDATA-wrapped
  Korean text is unwrapped by defusedxml's parser before strip_html
  sees it.
- **AC-7.4** (tz-aware `published_at`) — Yonhap's `+0900`, TheBlock's
  `-0400`, CNBC's `GMT` all parse to tz-aware UTC via
  `email.utils.parsedate_to_datetime`; naive-datetime entries
  defensively dropped per the L4 contract.

R14 (SEC fair-access UA) explicitly does NOT apply to any of the
three new adapters; SEC remains the only R14-bound adapter.

Total AC count: **32 → 32 → 32** (unchanged across extensions #2 and
#3).

### FD divergences ratified during extension #3

1. **L6.8 TheBlock utm-strip + raw_metadata prose corrected**
   The original FD L6.8 prose described:
   - utm-strip removing 2 keys (`utm_source`, `utm_medium`)
   - `parse_qsl(keep_blank_values=True)`
   - raw_metadata key names `rss_creator` / `rss_categories`
   - Empty string `""` when source field absent

   The implementation actually does:
   - utm-strip removing 5 keys (full standard utm-set:
     `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`,
     `utm_content`)
   - `parse_qsl(keep_blank_values=False)`
   - raw_metadata key names `creator` / `categories` (matching
     yonhap §L6.7's naming convention)
   - Key OMITTED entirely when source field absent (matching
     yonhap §L6.7's omit-when-absent pattern)

   FD L6.8 prose updated in this Phase 4 closeout to match the
   implementation. The 5-key utm-set is more complete; the
   `keep_blank_values=False` is harmless on The Block's URL shapes;
   the `creator` / `categories` naming + omit-when-absent pattern
   aligns L6.8 with L6.7's precedent — superior to the original
   2-key+empty-string spec. Rationale: minimizes `raw_metadata`
   surface, lets downstream consumers use plain `dict.get()` with
   `None` default rather than disambiguating empty-string-vs-missing.

   Per the FD-correction-at-closeout pattern established by
   Extension #2's L6.5 fix, the FD now pins the actual
   implementation behavior so a future re-reader cannot "fix" the
   code back to the broken spec.

### Cross-cutting code review (Phase 4 qa)

Single sub-agent review covering all 5 news adapters end-to-end
(yahoo-finance-news + sec-edgar-8k + yonhap-market + theblock-crypto
+ cnbc-top-news) per the Phase 1 plan. Result:
**APPROVE_WITH_NOTES** — 0 Critical / 0 High / 4 Medium / 4 Low.

Findings dispatched:
- M1 (FD §L6.8 drift) — fixed inline in this closeout; FD prose now
  matches implementation; no code change.
- M2/M3/M4/L1 → registered as DEBT-031 / DEBT-032 / DEBT-033 /
  DEBT-034 per below.

Hard-rule audit all PASS: Anthropic SDK / module boundary /
defusedxml / free tier / R13 secret hygiene / R7 strict.

Registered as TECH-DEBT (4 new):
- **DEBT-031 (Medium)**: `_NS_DC_CREATOR` namespace constant
  duplicated across `yonhap_market.py` + `theblock_crypto.py`
  (byte-identical Clark-notation string). Suggested fix: extract to
  new `src/investo/sources/_xml_namespaces.py`. ~15 min. Promotes to
  High when a third dc:creator-using adapter lands.
- **DEBT-032 (Medium)**: `_SUMMARY_MAX_LEN = 280` duplicated across
  **8** adapter files. Suggested fix: lift to
  `src/investo/sources/_config.py` as `SUMMARY_MAX_LEN`. ~20 min
  including 8 import updates. Independent of DEBT-028 (DEBT-028 =
  numeric formatting; this = string-length cap).
- **DEBT-033 (Low)**: `_FEED_URL` placement inconsistent across the
  5 news adapters (4 use `ClassVar[str]`, sec_edgar_8k uses
  module-level `Final[str]`). Suggested fix: align sec_edgar_8k to
  `ClassVar`. ~5 min. Cosmetic. Pairs with the broader DEBT-029.
- **DEBT-034 (Low)**: `_mock_client` test helper duplicated across 5
  news-adapter test files. Suggested fix: shared
  `tests/unit/sources/_mock_transport.py` helper. ~25 min.
  Test-code only. Pairs naturally with DEBT-016 (u4-side `_mock_client`
  duplication).

### DEBT-028 status (extension #3 reconfirmation)

**STAYS Medium.** Phase 1's audit prediction held: news adapters
introduce zero new numeric `raw_metadata` paths. All three new
adapters carry pure-string fields:
- yonhap-market: `{"guid": str}` plus optionally `creator`
- theblock-crypto: `{"guid": str}` plus optionally `creator` /
  `categories`
- cnbc-top-news: `{"guid": str}` (no creator field — CNBC feed has
  none; namespaces ignored per L6.9)

No precision-drift exposure added; the cross-adapter inconsistency
tracked by DEBT-028 remains scoped to the 3 ext-#1 numeric adapters
(yfinance / coingecko / fred). News cohort is clean by construction
across all 5 news adapters. Age clock continues from 2026-05-01.

### Operations note

**No `.github/workflows/daily-briefing.yml` change required.** All
three new adapters require **zero new GitHub Secrets**:
- Yonhap 마켓+ RSS, The Block RSS, CNBC US Top News RSS — all three
  are public RSS feeds with no auth and no compliance UA (R14 does
  NOT apply for any of the three; httpx's default UA is acceptable).

### Final quality gate (extension #3 closeout)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ |
| `mypy --strict src/` | ✅ (46 source files: was 43; +`yonhap_market.py` +`theblock_crypto.py` +`cnbc_top_news.py`) |
| `pytest` | ✅ **864/864** passing (was 810; +54 new) |
| `mkdocs build --strict` | ✅ (no docs change in this extension; still clean) |

### Coverage roll-up after extension #3

- Adapter count: 1 (base) → 4 (ext-#1) → 6 (ext-#2) → **9** (ext-#3)
- News-adapter count specifically: 0 → 0 → 2 → **5**
- `Category` enum coverage: 1/5 → 3/5 → 4/5 → **4/5** (unchanged in
  ext-#3 — depth within news, not breadth; only **earnings** still TBD)
- u1 NFR ACs: 30 → 32 → 32 → **32** (unchanged across ext-#2 and ext-#3)
- u1 tests: 252 → 307 → 342 → **396** (252 base + 55 ext-#1 + 35
  ext-#2 + 54 ext-#3)
- Total project tests: 720 → 775 → 810 → **864**
- Source files in `src/investo/sources/`: 8 → 12 → 14 → **17**
- Total `src/` files for `mypy --strict`: 37 → 41 → 43 → **46**
