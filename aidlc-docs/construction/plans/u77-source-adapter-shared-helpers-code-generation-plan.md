# Code Generation Plan: `u77 source-adapter-shared-helpers`

**Date**: 2026-05-28
**Unit**: u77 source-adapter-shared-helpers
**Stage**: Code Generation (refactor)
**Status**: Code-complete — all 5 steps done (full gate green; closeout docs pending)
**Source**: 2026-05-28 abstraction review — `sources/` module
**Estimated Effort**: ~3-4 h
**Dependencies**: none
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first. The Refactor Contract there (behavior-preserving, existing tests stay green, module boundary, full gate) governs this unit.

---

## Problem Statement

The 30+ source adapters under `src/investo/sources/` already share a good plugin spine (`protocol.py`, `_registry.py`, `_retry.py`, `_sanitize.py`, `_window.py`, `_config.py`, `_xml_namespaces.py`, `_core_fact_map.py`). But several mechanical patterns are copy-pasted across adapters instead of living in a shared helper. A change to any of these patterns (e.g. error wording, backoff behavior) currently has to be applied N times and silently drifts.

Verified duplication (file:line evidence from the review):

1. **JSON-decode boilerplate — 17 adapters.** Each wraps `response.json()` in an identical `try/except json.JSONDecodeError` that raises `SourceFetchError(source_name=self.name, message="malformed JSON: …", transient=False, cause=exc)`. Examples: `binance_crypto_market.py:72-80`, `coingecko.py:74-81`, `fred.py:138-146`, `dart_disclosure.py:152-160`.
2. **`asyncio.gather` + exception sorting — 6 adapters.** `fred.py:101-116`, `binance_crypto_market.py:40-55`, `stooq_price.py:187-205` (also yfinance, fsc_krx_stock_price, stooq_kr_market) repeat: gather with `return_exceptions=True`, keep `NormalizedItem`, skip `SourceFetchError`, re-raise any other `BaseException`.
3. **Numeric/string parse helpers — 4 adapters.** `binance_crypto_market.py:133-151`, `defillama_market_structure.py`, `fsc_krx_index_price.py`, `fsc_krx_stock_price.py` each define their own `_parse_float` / `_parse_int` / `_required_str`.
4. **Datetime→UTC parsing — 6 adapters.** RFC-822 (`fomc_rss.py:108-114`, `theblock_crypto.py:202-208`, `yonhap_market.py:132-138`) and ISO-8601 (`coingecko.py:173-186`) with the same tz-aware-or-raise logic.
5. **`_ATOM_NS` constant defined twice** — `sec_edgar_8k.py:63` and `treasury_rates.py:22` (plus Treasury's dataservices namespaces).

---

## Goal

One canonical implementation per pattern, in the existing `sources/` private helper layer; every adapter delegates. No adapter behavior changes — same exceptions, same parsed values, same items.

---

## Existing Coverage / Deduplication

- This is purely a `sources/`-internal extraction. It touches no other unit and adds no cross-unit import.
- Do not modify `protocol.py` / `_registry.py` contracts — the adapter interface (`name`, `category`, async `fetch`) is unchanged.
- `_retry.py::retry_get` and `_window.py::FetchWindow` already exist and are correct — do not duplicate them; the new helpers sit beside them.

---

## Scope Boundary

In scope:
- New/extended private helpers in `sources/` and migrating duplicating adapters to them.
- New focused unit tests for each helper.

Out of scope:
- Data-driven unification of fred/coingecko/stooq into one parameterized adapter (the review flagged this as blocked on a `protocol.py` change — defer; not this unit).
- Any change to fetched data, error semantics, or fixtures.
- RSS base-class extraction (larger; deferrable — keep this unit mechanical and low-risk).

---

## Stage Decision

- **Functional Design — SKIP.** No new domain entity; internal helper extraction over existing adapters.
- **NFR Requirements — SKIP.** No new external service, dependency, secret, or runtime cost. R10 (4-path source fixtures) and R14 (UA policy) are unchanged.

---

## Implementation Steps

### Step 1 — JSON-decode helper `[x]`
- [x] Add `parse_json_response(response, *, source_name, message="malformed JSON", append_exc=True) -> Any` to **new `sources/_parse.py`** (kept `_retry.py` HTTP/backoff-focused per the unit instruction). `append_exc=False` reproduces the adapters that name only the resource (DART / FRED / fred_calendar / official_policy).
- [x] Migrated the 15 `response.json()` adapters to call it; deleted the local `try/except`. The 2 `json.loads(...)` adapters (`fomc_calendar` catches `UnicodeDecodeError` too; `yfinance_history` uses positional args on pre-decoded `body`) are DIFFERENT contracts and left as-is — TECH-DEBT candidate: a `parse_json_text` sibling.
- **Acceptance**: existing source tests pass unchanged; the raised `SourceFetchError` keeps `source_name`, `transient=False`, and `cause`. A new test pins malformed-JSON → `SourceFetchError`.

### Step 2 — gather-with-error-isolation helper `[x]`
- [x] Added `gather_with_error_isolation(coros, *, source_name, raise_if_all_failed=False) -> list[NormalizedItem]` in **new `sources/_fanout.py`** (its own concern — not parsing, not HTTP). The `raise_if_all_failed` flag preserves the two real escalation modes: default pure-isolation (fred / yfinance / stooq_price) and re-raise-first-on-all-failed (binance / fsc_krx_stock_price).
- [x] Migrated 5 fan-out adapters. `stooq_kr_market` keeps its bespoke symbol-keyed dict + Yonhap fallback loop (a DIFFERENT contract) and is NOT migrated.
- **Acceptance**: existing per-adapter tests pass unchanged; a new test pins the three result classes (item kept / SourceFetchError skipped / other exception re-raised).

### Step 3 — numeric/string parse helpers `[x]`
> **CORRECTED after review (2026-05-28): the parse helpers are NOT one semantic — do not force-unify them.** Verified against source, the three `_parse_float` implementations encode *different contracts*:
> - `binance_crypto_market.py:140` → `-> float`, no comma stripping, raises `ValueError` on empty.
> - `fsc_krx_index_price.py:236` / `fsc_krx_stock_price.py:247` → `-> float`, **strips commas** (`.replace(",", "")`), raises on empty.
> - `defillama_market_structure.py:190` → `-> float | None`, **never raises** (returns `None`), rejects `bool`, requires `math.isfinite`.
> One signature cannot be both `float` and `float | None`, nor both comma-stripping and not. A single `parse_float` would either change behavior (violating the prime directive) or accrete flags (the wrong-abstraction trap, guide §9.5). Also note `krx_foreign_flows.py:326` has its own `_parse_int_with_commas(...) -> int | None` — a fourth, distinct contract.
- [x] Created `sources/_parse.py` with `required_str(payload, key) -> str` (byte-identical across `binance`/`fsc_krx_index_price`/`fsc_krx_stock_price`) and migrated those three.
- [x] Unified `parse_float(value, *, strip_commas=False)` / `parse_int(...)`: `strip_commas=False` reproduces binance byte-for-byte; `strip_commas=True` reproduces fsc_krx (strip+replace ordering is result-equivalent for all inputs). **`defillama` (`float | None`, never raises) and `krx_foreign_flows` (`int | None`, comma) left untouched** — distinct None-returning contracts.
- **Acceptance**: existing tests pass unchanged; new helper tests cover empty / valid / non-numeric for each retained variant; the `defillama`/`krx_foreign_flows` None-returning parsers remain untouched.

### Step 4 — datetime→UTC helpers `[x]`
- [x] Added `parse_rfc822_to_utc(text) -> datetime` and `parse_iso8601_to_utc(text) -> datetime` to `sources/_config.py` (None/naive/unparseable → `ValueError`, returns tz-aware UTC). Callers that previously dropped silently wrap in `try/except (TypeError, ValueError): return None`, reproducing all three original drop branches byte-for-byte.
- [x] Migrated 6 adapters: RFC-822 = `fomc_rss`, `theblock_crypto`, `yonhap_market`, `cnbc_top_news`, `nasdaq_stocks_news` (all share the byte-identical parse+drop+`astimezone(UTC)` block); ISO-8601 = `coingecko`. Left bespoke/divergent parsers as-is: DART (`YYYYMMDD→KST 09:00`), Treasury (`YYYY-MM-DD→NY close`), `korea_policy_rss`/`official_policy` (divergent post-processing), and `sec_edgar_8k`'s `<updated>` ISO (scoped to Step 5 ns-only here; its identical-to-coingecko ISO block is a TECH-DEBT consolidation candidate).
- **Acceptance**: existing tests pass unchanged; new tests cover RFC-822 and ISO-8601 happy/naive paths.

### Step 5 — XML namespace constants + gate `[x]`
- [x] Added `ATOM_NS`, `DATASERVICES_M_NS`, `DATASERVICES_D_NS` to `sources/_xml_namespaces.py`; `sec_edgar_8k.py` and `treasury_rates.py` now import instead of define.
- [x] Full gate green (ruff / mypy --strict / pytest 2696 passed / mkdocs --strict) and `check_no_paid_apis` exit 0. (Two pre-existing `ruff format --check` drifts — `briefing/summary_quality.py`, `tests/unit/visuals/test_assets.py` — are unrelated to u77 and out of scope.)
- **Acceptance**: full gate green; `defusedxml` still the only XML parser.

---

## Acceptance Criteria

- **AC-77.1** — The genuinely-identical patterns (JSON-decode, gather-error-isolation, `required_str`, `ATOM_NS`, datetime→UTC) each have exactly one implementation; no adapter redeclares them. The numeric float/int parsers are consolidated ONLY where contracts are byte-identical (see Step 3) — `defillama` and `krx_foreign_flows` keep their distinct None-returning contracts. "One implementation per pattern" does NOT apply blindly to the parse helpers.
- **AC-77.2** — Every pre-existing `sources/` test passes without modification (proof of behavior preservation).
- **AC-77.3** — New helpers have focused unit tests covering happy + error paths.
- **AC-77.4** — No new cross-unit import; `defusedxml`-only and free-API rules intact; mypy --strict clean.

---

## Tests / Validation

- `tests/unit/sources/test_retry.py`, `test_fred.py`, `test_stooq_price.py`, `test_yfinance.py`, `test_theblock_crypto.py`, `test_fomc_calendar.py`, `test_yonhap_market.py`, `test_dart_disclosure.py`, `test_sec_edgar_8k.py`, `test_aggregator.py` — must stay green unchanged.
- New: `tests/unit/sources/test_parse_helpers.py` (or extend `test_retry.py`) for the four new helpers.
- Minimum gate: targeted `sources/` pytest + full `ruff`/`mypy --strict` on changed scope; full `pytest` + `mkdocs build --strict` before closeout.

---

## Non-Goals

- Data-driven adapter unification (blocked on protocol change).
- RSS base-class / template-method extraction.
- Any change to source data, error wording semantics, fixtures, or HTTP behavior.
