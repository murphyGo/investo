# Code Generation Plan: `u133 watchlist-registry-source-impact-suppression`

**Date**: 2026-07-17
**Unit**: u133 watchlist-registry-source-impact-suppression
**Stage**: Code Generation
**Status**: Backlog (Ready)
**Source**: 2026-06-29/2026-06-30 production bundle review (briefing-unit-planner, 2026-07-17)
**Estimated Effort**: ~3 h
**Dependencies**:
- u64 watchlist entity matching (Complete) — matching semantics unchanged.
- u73 watchlist-impact-center-v2 (Complete) — Direct/Related/Uncertain/Rejected grouping unchanged.
- u111 watchlist-public-impact-language-cleanup (Complete) — public label projection unchanged.
- u115 source-spec-registry-unification (Complete) — `_internal.source_specs.SourceSpec` is where the new flag lives.
- u104 sec-company-facts-and-symbol-directory (Complete) — the sources stay collected.
- u101 verified-fact-cache-and-entity-guard (Complete) — keeps consuming registry data.

---

## Problem Statement

`archive/us-equity/2026/06/2026-06-30.md` line 14 renders:

```
> **내 관심 자산 영향**: 14건 확인 (기본 바스켓) — AAPL: 직접 관련 · [nasdaq-symbol-directory] AAPL listing metadata: Apple Inc. - Common Stock; AAPL: 직접 관련 · [sec-company-facts] AAPL SEC company facts: Apple Inc.; …
```

The "14건 확인" impact count and the visible rows are dominated by **static registry metadata**: exchange listing-directory rows (`nasdaq-symbol-directory`) and SEC company-facts registry rows (`sec-company-facts`). These are reference datasets that mention every large ticker every day — they are not market events, carry no daily information, and labeling them "직접 관련" tells the reader something happened to AAPL/AMZN/GOOGL when nothing did.

The same noise reaches §⑤ as a pseudo-news block ("워치리스트 매치 — 가격 데이터 미제공": "…META·MSFT·NVDA·TSLA도 상장 정보가 갱신됐으나 …") — a narrated non-event.

The crypto segment shows the correct contrast: its impact rows (2026-06-29 line 10) come from CFTC positioning, CoinGecko prices, OKX derivatives — actual daily observations.

## Goal

Registry-class sources never create public impact rows, never count toward "N건 확인", and never anchor a §⑤ narrative block on their own — while remaining fully available for entity verification (u101), diagnostics, and price/fact cross-checks.

## Existing Coverage / Deduplication

- **u64** matching (aliases, boundaries, confidence) — unchanged; registry items still *match*, they are just routed differently downstream.
- **u73** grouping contract — unchanged; this adds a source-class routing input before public projection, exactly like the existing Uncertain/Rejected diagnostics-only routing.
- **u111** public label map — unchanged.
- **u101** fact cache/entity guard — unchanged; it may keep consuming registry items.
- **u115** — the flag lives on the existing `SourceSpec`; no new registry structure.
- Not in scope: removing the adapters (u104), changing collection windows, or altering Telegram summary format beyond count agreement.

## Scope Boundary

In scope: `reference_registry` spec flag; impact-center routing; public count exclusion; Stage-2 prompt rule for §⑤; diagnostics preservation; cross-surface count agreement (site callout, Telegram, visual card).
Out of scope: matcher changes, new sources, u101 behavior, historical archives.

## Stage Decision

Functional Design: SKIP — routing refinement over the existing u73 impact-center contract; no new entity.
NFR Requirements: SKIP — deterministic routing; no new dependency, source, secret, or cost.

## Fixed Contracts

1. **Registry source set (initial, pinned)**: `nasdaq-symbol-directory`, `sec-company-facts`. Expressed as a boolean field `reference_registry: bool = False` on `_internal.source_specs.SourceSpec`, set to `True` for exactly these two specs. Future additions go through the spec table, not through name matching in consumer code.
2. **Routing rule**: a u64-accepted match whose evidencing item's source spec has `reference_registry=True` is routed to the diagnostics bucket (same rendering rules as u73's Uncertain/Rejected: collapsed `<details>` only, R13-safe wording). It is not Direct, not Related, not publicly rendered, and not counted.
3. **Count rule**: "N건 확인" (site callout, Telegram summary, visual card, watchlist daily page) counts only non-registry public rows. If zero non-registry rows remain, the existing u73 "no public impact" state renders (do not invent a new empty-state text).
4. **Stage-2 prompt rule** (append to the existing §⑤ instruction block in `briefing/prompts.py`): registry metadata items are entity-identification evidence only; a §⑤ subsection may cite them solely alongside a same-run non-registry item about the same ticker; a registry-only ticker set must not produce a §⑤ subsection.
5. **Deterministic backstop**: the impact-center routing (contract 2) is the enforcement point; the prompt rule is best-effort input shaping. No new post-render scanner.

## Implementation Steps

- [ ] Step 1 — Add `reference_registry` to `SourceSpec` in `src/investo/_internal/source_specs.py`, default `False`, `True` for the two pinned specs; extend the spec-table tests.
- [ ] Step 2 — In `src/investo/briefing/watchlist_impact.py`, route accepted matches with registry-source evidence to diagnostics (Fixed Contract 2). Inspect `build_impact_center` and the existing Uncertain/Rejected diagnostics path first; reuse its rendering, add a distinct diagnostic reason label such as `reference-registry` (public surfaces never show it — R13 wording rules from u73/u111 apply).
- [ ] Step 3 — Verify every "N건 확인" consumer derives its count from the public rows produced in Step 2 (`briefing/watchlist.py:441` renderer, `notifier/summary.py`, `visuals/` watchlist card, `publisher/watchlist_pages.py`); fix any consumer that counts raw matches.
- [ ] Step 4 — Add the Stage-2 §⑤ prompt rule (Fixed Contract 4) in `src/investo/briefing/prompts.py`; extend prompt tests.
- [ ] Step 5 — Rendered regression: fixture reproducing the 2026-06-30 us-equity match set (5+ registry rows, 0 non-registry rows for MSFT/NVDA/TSLA) asserting the public callout count excludes registry rows and the registry rows appear only in collapsed diagnostics.
- [ ] Step 6 — Telegram non-leakage: extend the existing u73 Telegram test to assert registry rows/count do not appear.
- [ ] Step 7 — Quality gate: scoped ruff/format, `mypy src`, `pytest tests/unit/briefing tests/unit/notifier tests/unit/publisher tests/unit/visuals tests/unit/sources`.

## Acceptance Criteria

1. AC-133.1: With the 2026-06-30 us-equity match set, the public callout count equals the number of non-registry public rows (not 14), and no `listing metadata`/`SEC company facts` text renders outside collapsed diagnostics.
2. AC-133.2: Registry-evidenced matches appear in collapsed diagnostics with R13-safe wording and a `reference-registry` diagnostic reason.
3. AC-133.3: Site callout, Telegram summary, visual card, and watchlist daily page report the same public count.
4. AC-133.4: u64 matching and u73 grouping tests pass unchanged (semantics preserved).
5. AC-133.5: The Stage-2 prompt contains the registry-narration rule, and prompt tests pin it.
6. AC-133.6: u101 entity-guard tests pass unchanged.

## Tests / Validation

- `tests/unit/sources/test_source_specs.py` (or the existing spec test module) — flag presence/defaults.
- `tests/unit/briefing/test_watchlist_impact.py` — routing, count, diagnostics reason.
- `tests/unit/briefing/test_watchlist.py` — callout renderer count.
- `tests/unit/notifier/test_summary.py` — Telegram count agreement + non-leakage.
- `tests/unit/publisher/test_watchlist_daily_page.py`, `tests/unit/visuals/` — surface agreement.
- `tests/unit/briefing/test_prompts.py` — §⑤ rule.
- Local gate: scoped ruff/format, `mypy src`, focused pytest above.

## Non-Goals

- No matcher/alias changes, no adapter removal, no new empty-state wording.
- No suppression of registry sources from u101 fact verification or price cross-checks.
- No archive backfill.
