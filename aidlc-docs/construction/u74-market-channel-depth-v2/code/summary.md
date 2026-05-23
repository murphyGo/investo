# u74 market-channel-depth-v2 — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u74 market-channel-depth-v2
**Status**: Complete (5/5 steps)

## Goal

Give every segment a deterministic native anchor block with a common presentation contract: native index/FX/crypto anchors render in a fixed schema, unavailable native rows render explicit reason rows instead of silent omission or invented values, and any cross-market explanation is gated through u57-approved macro/systemic links so segment boundaries hold. The unit standardizes the reader-facing presentation after u66 (crypto-native indicators) and u67 (domestic depth) landed — it does not reopen either.

## Scope

In scope: channel-specific anchor block schema; explicit missing-data rows with source/status reasons; crypto indicator presentation consuming u66 output; domestic presentation consuming u67 output without reopening precedence; cross-market cause-map text guarded by u57 scope rules.
Out of scope: new domestic source adapters; new crypto adapters beyond u66; paid providers; cross-channel prediction / trade recommendations; rewriting u57 lint rules.

## Stage Decision

- **Functional Design — SKIP** (per plan conditional). Implementation reuses existing reconciled `MarketAnchor` sets, the u66 `indicator` raw_metadata contract, and the u57 `BundleContext`; it introduces presentation/renderer modules only, no new shared channel-depth domain model. The plan permitted FD only if a new shared model were introduced — none was, so FD is SKIP. Confirmed at closeout — no FD file created.
- **NFR Requirements — SKIP** (per plan). No new source, dependency, secret, or runtime budget; u66/u67 own their source/NFR implications. Confirmed at closeout — no NFR file created.

## Deduplication / Non-Overlap (consumes u66/u67, no re-implementation)

u74 **standardizes presentation** over existing producers; it does not re-collect or re-decide source data.

- **u67 consumed as-is**: the channel anchor block reads the reconciled `MarketAnchor` set already passed into each segment (the same `anchors` the top table swap consumes). No source-precedence change, no new domestic adapter. Domestic rows (`kospi`/`kosdaq`/`usd_krw`/`sector`) come from u67 output.
- **u66 consumed as-is**: crypto rows read the existing u66 `indicator` raw_metadata contract (`global_market` / `fear_greed` / `btc_funding` / `btc_oi`). u66-unlanded indicators (the liquidation leg) render `아직 미제공`. No new crypto source. The fear/greed cell is **value-only** — the `(분류)` gloss is owned by u66 `## ⓪-A`, so u74 renders the value without re-glossing to avoid a dedupe collision.
- **u49/u55 anchors**: US `sp500`/`nasdaq`/`dow` and the crypto `btc`/`eth` price legs come from existing generic anchors. Index/FX labels resolve through the u70 `anchor_label` registry (no new label source).
- **u57 unchanged**: the cause-map reads `BundleContext.shared_macro_block` (only keys hit by ≥2 segments) plus the `cross_market_core_allowed` gate; `cross_segment_lint` is byte-unchanged (29/29 pass).

## Key Deliverables

- **New** `src/investo/publisher/channel_anchor_block.py`: channel anchor schema + deterministic renderer; `MissingReason` enum (`source_empty` / `market_closed` / `not_collected` / `insufficient_items` / `stale` / `not_yet_available`). All-missing renders an empty result (caller omits — no noise grid); missing rows render a reason label only (no number).
- **New** `src/investo/publisher/cross_market_cause_map.py`: compact observational cause-map line, double-gated on u57 `shared_macro_block` (≥2-segment keys) and `cross_market_core_allowed`. Does not read tickers; forbidden cause-map types are suppressed + logged (never demoted into public prose).
- **Changed** `src/investo/orchestrator/pipeline.py`: imports both modules; injects the channel anchor block and cause-map into `_apply_reader_format_to_segments`.
- **Tests**: new `tests/unit/publisher/test_channel_anchor_block.py` + `tests/unit/publisher/test_cross_market_cause_map.py`.

## Channel Anchor Schema

Per the plan minimal schema (no newly invented row set):

| Segment | Rows | Producer |
|---------|------|----------|
| domestic-equity | `kospi` / `kosdaq` / `usd_krw` / `sector` | u67 |
| us-equity | `sp500` / `nasdaq` / `dow` (+ macro/yield optional) | u49/u55 |
| crypto | `btc` / `eth` price 24h + `dominance` / `fear_greed` / `funding_oi` (liquidation → `not_yet_available`) | u66 / u49 |

Index/FX labels resolve through the u70 `anchor_label` registry. A row counts as a numeric fact only when a value is present; reason-only rows never increase numeric-success counts.

## Cause-Map Scope Safety

- **Double gate**: u57 `BundleContext.shared_macro_block` (only keys hit by ≥2 segments) AND `cross_market_core_allowed`. The cause-map does not read tickers.
- **Allowed types** (per plan): `geopolitical_oil_macro`, `fed_policy_event`, `global_systemic_risk`. `global_systemic_risk` is **dormant** — no detector emits it today (plan-aware).
- **Forbidden links** are suppressed + logged/replay-reported, never demoted into public prose. Wording stays observational ("연결 고리" / "관찰"), no prediction.

## Idempotency

- The block renders only when ≥1 native value is present (avoids an all-missing macro assertion).
- The fear/greed cell is value-only, avoiding a gloss-dedupe collision with u66 `## ⓪-A`.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-74.1 | Each channel has a deterministic native anchor block schema | MET | `channel_anchor_block.py` schema; per-segment fixtures in `test_channel_anchor_block.py` |
| AC-74.2 | Missing native anchors render explicit reason rows, not silent omission / invented values | MET | `MissingReason` enum; partial-channel fixture shows reason-only rows; missing rows do not count as numeric facts |
| AC-74.3 | Crypto presentation consumes u66 indicators when available, labels missing ones when not | MET | reads u66 `indicator` raw_metadata contract; liquidation leg renders `not_yet_available`; u66-not-present fixture |
| AC-74.4 | Domestic presentation consumes u67 outputs without changing source precedence | MET | reads reconciled `MarketAnchor` set as-is; no new domestic adapter / precedence change |
| AC-74.5 | Cross-market cause-map limited to u57-approved links and stays observational | MET | double-gated cause-map; forbidden-link fixture suppressed; `cross_segment_lint` 29/29 unchanged |

## FD Divergences Ratified

None. FD was SKIP (presentation/renderer over existing u66/u67/u49/u55/u57 models; no new entity). No code-vs-spec divergence to ratify.

## TECH-DEBT Registered

- **DEBT-076** (Low) — `BundleContext` currently exposes only the *rendered* shared-macro string, so `cross_market_cause_map` re-derives the cause-map type by matching Korean macro labels (`국제 유가` / `FOMC 일정` / `미 국채 수익률`). This label-coupling is brittle to label-text changes. Additive fix: add a structured `detected_macro_keys` field to `BundleContext` (a model change — planner/scope-gated) and key the cause-map off it.

## Potential Risks

- **Cause-map label-coupling**: type re-derivation off the rendered Korean macro label string (see DEBT-076). Non-reader-facing correctness is preserved (forbidden links are still suppressed by the double gate); the risk is maintenance brittleness, not a public misfire.
- **`global_systemic_risk` dormant**: the cause-map type exists but no detector emits it today (plan-aware). No behavior change until a detector lands.
- **Integration regression resolved**: 2 integration tests regressed during wiring; root-caused and passing in the final gate.

## Verification Gate

- ruff check: clean
- ruff-format: clean
- mypy --strict: 143 files clean
- pytest: 2613 passed (2 integration regressions root-caused, then passing)
- mkdocs build --strict: pass
