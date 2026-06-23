# Code Generation Plan: `u109 domestic-anchor-sanity-quarantine`

**Date**: 2026-06-23
**Unit**: u109 domestic-anchor-sanity-quarantine
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-23 generated-briefing quality review with domestic-reader and data-trust findings
**Estimated Effort**: ~5-7 h
**Dependencies**:
- u55 numeric freshness and market fact gates are complete.
- u67 domestic channel depth is complete.
- u70 cross-surface numeric anchor reconciliation is complete.
- u74 market channel depth v2 is complete.
- u96 quality-current-run snapshot sync is complete.

---

## Problem Statement

June 2026 domestic archives show exact KOSPI/KOSDAQ and large-cap price claims surviving even when core price provenance is failed, missing, stale, or internally contradictory. A reader sees exact numbers in the anchor table and body while quality metadata indicates low figure presence or fallback-heavy generation.

This is a reader-trust failure. When exact domestic market anchors are untrusted, the system must quarantine the values before public rendering and block precise claims that depend on them.

## Goal

Add a deterministic domestic anchor trust layer that classifies domestic index/price anchors as trusted, unavailable, stale, or implausible before they reach table, prose, chart, channel-depth, or Telegram surfaces.

## Existing Coverage / Deduplication

- u55 owns general numeric freshness and market fact checks.
- u67 adds domestic fallback anchors.
- u70 reconciles numeric anchors across surfaces.
- u74 renders channel-depth blocks.
- u96 records current-run quality truth.
- This unit adds domestic-specific anchor quarantine and precise-claim blocking. It does not add a source adapter or replace existing reconciliation.

## Scope Boundary

In scope:
- Quarantine domestic index and large-cap anchors when provenance is missing, stale, or implausible.
- Remove quarantined values from public anchor tables and chart/Telegram summaries.
- Block exact domestic index/price claims when a trusted anchor is unavailable.
- Record quality metadata that explains exact values were withheld.

Out of scope:
- New KRX/KIND/KOFIA source work.
- Live external validation during publish.
- Rewriting all domestic prose.
- Changing US or crypto anchor policy beyond shared helper compatibility.
- Historical archive backfill.

## Stage Decision

Functional Design: skip. This is a trust-gate refinement over the existing anchor and publisher pipeline.

NFR Requirements: skip. Deterministic checks use existing data and add no dependency, network call, secret, or paid service.

## Fixed Contracts

### Domestic Anchor Trust States

Add a local enum or literal contract:

```python
DomesticAnchorTrust = Literal["trusted", "unavailable", "stale", "implausible", "provenance_missing"]
```

This trust state is private to the anchor-quarantine helper. Public channel-depth rendering continues to use u74 `MissingReason`. Map private states to u74 reasons as follows:

| Private trust state | Public u74 reason |
|---------------------|-------------------|
| `unavailable` | `not_collected` |
| `stale` | `stale` |
| `implausible` | `insufficient_items` |
| `provenance_missing` | `insufficient_items` |

Public rendering rules:

| Trust state | Anchor table | Body exact claims | Quality note |
|-------------|--------------|-------------------|--------------|
| `trusted` | render exact value | allowed when assertion gate passes | normal |
| `unavailable` | omit row or show unavailable label | blocked | exact value withheld |
| `stale` | omit row or show stale label without number | blocked | stale anchor withheld |
| `implausible` | omit row | blocked | implausible anchor withheld |
| `provenance_missing` | omit row | blocked | unprovenanced anchor withheld |

### Trusted Provenance Contract

A domestic anchor is `trusted` only when all required fields pass:

- symbol is one of the bounded domestic exact-claim registry:
  - `^KOSPI` aliases: `KOSPI`, `코스피`
  - `^KOSDAQ` aliases: `KOSDAQ`, `코스닥`
  - `KRW=X` aliases: `원/달러`, `USD/KRW`, `달러-원`
  - `005930.KS` aliases: `삼성전자`, `005930`
  - `000660.KS` aliases: `SK하이닉스`, `000660`
- source provenance is explicit in `NormalizedItem.source_name` or `raw_metadata.source_name`.
- index rows must have index provenance (`index_name` or an equivalent existing index metadata field), not only a stock ticker.
- item category is `price` or the existing domestic anchor category consumed by u67.
- observed/as-of date matches the report target date or the accepted domestic market close window already used by u8/u67.
- source outcome for the contributing source is not failed, terminal, or zero-items for that contract.

### Plausibility Bands

Use deterministic bands only as a quarantine guard, not as truth:

- KOSPI close must be within inclusive `[1000, 12000]`.
- KOSDAQ close must be within inclusive `[300, 3000]`.
- USD/KRW close must be within inclusive `[500, 2500]`.
- Samsung Electronics and SK Hynix close must be within inclusive `[1000, 2000000]` KRW.
- Index and large-cap absolute daily percent change must be `<= 30.0`.
- USD/KRW absolute daily percent change must be `<= 20.0`.
- Large-cap equity close must not be reused as an index close.
- A domestic index row sourced from a stock-price adapter without an explicit index provenance flag is `provenance_missing`.

Comparisons are inclusive. Missing values classify as `unavailable`; unparsable numeric values classify as `implausible`.

### Pipeline Ordering Contract

u109 extends u70 without duplicating it:

1. Quarantine removes or withholds untrusted domestic anchors before `anchor_table_input`.
2. Visual preparation must consume post-quarantine anchors, or the quarantine must be applied before `_stage_prepare_segment_visual_assets()`.
3. `_reconcile_anchor_closes()` then derives the canonical anchor payload from trusted anchors only.
4. Existing `enforce_anchor_assertions` blocks prose claims using that canonical payload.
5. Telegram market snapshots must consume trusted anchor data or filtered `price_items`; they must not read quarantined domestic values from raw `price_items`.

## Implementation Steps

- Inspect `src/investo/orchestrator/stage_context.py` and `_build_kr_anchors_from_items` in `src/investo/orchestrator/pipeline.py`.
- Add a small pure helper to classify domestic anchor trust before `_reconcile_anchor_closes()`.
- Ensure `anchor_table_input` receives only trusted domestic anchors with precise values.
- Extend `src/investo/publisher/anchor_assertion_gate.py` so exact domestic index/large-cap claims require a trusted matching anchor.
- Extend `src/investo/publisher/channel_anchor_block.py` to render missing reasons without precise quarantined numbers.
- Move/apply quarantine before visual asset preparation, or make visual asset preparation consume the post-quarantine anchor map.
- Update notifier summary extraction so domestic market snapshot entries are built from trusted anchor data or filtered `price_items`.
- Record explicit quality snapshot fields using existing u96 metadata patterns:
  - `domestic_anchor_withheld_count: int = 0`
  - `domestic_anchor_withheld_reasons: tuple[str, ...] = ()`
  - serialize bounded reason values only: `unavailable`, `stale`, `implausible`, `provenance_missing`
  - quality dashboard visible wording: `국내 기준값 일부 비공개`
- Add fixtures for contradictory domestic June snippets.
- Confirm US and crypto anchor paths keep existing behavior.

## Acceptance Criteria

1. Implausible KOSPI/KOSDAQ anchor values do not render as public closes.
2. Exact domestic body claims are blocked when matching trusted anchors are unavailable.
3. Quarantined values do not enter chart sidecars, visual cards, or Telegram summaries.
4. Quality metadata distinguishes withheld exact values from ordinary absence.
5. The quarantine helper is deterministic and unit-tested with boundary values.
6. US and crypto anchor reconciliation tests remain unchanged in behavior.
7. Archive regression fixtures cover domestic contradictions from June 2026.
8. Chart sidecar JSON, visual/OG-card payload text, and Telegram summaries do not contain quarantined domestic values.
9. Quality history rows carry bounded withheld-count and withheld-reason metadata with zero/empty defaults.
10. Existing u70 prose gating remains the prose enforcement mechanism; u109 only controls domestic anchor trust before u70 consumes anchors.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/orchestrator/test_anchor_close_reconcile.py tests/unit/orchestrator/test_stage_context.py tests/unit/publisher/test_anchor_assertion_gate.py tests/unit/publisher/test_channel_anchor_block.py tests/unit/publisher/test_chart_sidecar.py tests/unit/visuals tests/unit/notifier/test_summary.py tests/unit/notifier/test_summary_extract.py
uv run --extra dev ruff check src/investo/orchestrator src/investo/publisher src/investo/visuals src/investo/notifier tests/unit/orchestrator tests/unit/publisher tests/unit/visuals tests/unit/notifier
uv run --extra dev mypy src
```

## Non-Goals

- No new domestic source adapter.
- No external live market verification.
- No historical archive repair.
- No change to US or crypto anchor semantics.
- No LLM rewrite of domestic body prose.
