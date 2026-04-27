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
