# Code Generation Plan: `u59 macro-actual-priority-and-lineage`

**Date**: 2026-05-23
**Unit**: u59 macro-actual-priority-and-lineage
**Stage**: Code Generation
**Status**: In progress (3/9 full steps complete; Step 4 parser/prompt contract complete; PPI schedule identity sub-step complete)
**Source**: 2026-05-23 user request after the 2026-05-13 U.S. PPI miss analysis and 10-subagent macro design review.
**Estimated Effort**: ~8-12 h
**Dependencies**:
- u13 LLM input candidate cap: current Stage 1 caps that can drop lookahead/macro candidates.
- u22 source-coverage-transparency: source outcomes and public/private coverage diagnostics.
- u36 source expansion bundles: official/free/public source selection discipline.
- u43 lookahead adapters: scheduled event category and release-calendar handling.
- u52 prior-briefing-context-and-carryover: prior event carryover concepts.
- u54 source-status-severity-and-quality-kpi: severity policy, source outcomes, quality KPI history.
- u55 numeric-freshness-and-market-fact-gates: source-backed numeric fact discipline.
- u57 segment-narrative-scope-and-time-reconciliation: shared macro block and bundle context.
- u58 crypto-regulation-policy-sources: bounded priority-preservation precedent.

---

## Problem Statement

The daily briefing can collect a major macro schedule item, such as U.S. PPI, but still omit it from the final market narrative because the pipeline treats macro events mostly as ordinary calendar/news items. The current system does not consistently distinguish:

1. **Schedule**: an event is expected today or soon.
2. **Actual print**: the official value has been released.
3. **Priority**: the event is market-moving enough to reserve candidate budget.
4. **Coverage proof**: the event reached each stage of generation.
5. **Final output proof**: the briefing actually mentioned the required macro event.

The PPI miss showed two separate gaps:
- PPI schedule can be collected but dropped by candidate caps or prompt-stage caps.
- PPI actual/forecast-surprise data is not guaranteed to be collected as structured macro actual data.

---

## Goal

Make high-importance macro events deterministic first-class inputs so the pipeline does not miss source-backed CPI/PPI/NFP/PCE/GDP/FOMC actuals, and so operators can diagnose whether a macro item was missing at source, dropped by routing/caps, omitted by the LLM, or published.

---

## Scope Boundary

In scope:
- Typed macro actual metadata for `NormalizedItem` or a compatibility-safe flat metadata bridge.
- Deterministic macro priority scoring before Stage 1 candidate caps.
- Required macro preservation through Stage 1 and Stage 2.
- Prompt and parser contract that prevents required macro actuals from becoming `unassigned`.
- Post-generation macro coverage validation.
- Operator-only macro lineage artifacts.
- Macro actual source-health severity and quality KPI hooks.
- Structured macro event carryover lifecycle.
- Fixture-backed tests for PPI schedule and actual data path.

Out of scope:
- Paid consensus/forecast providers.
- Unlicensed "expected vs actual" surprise claims.
- Browser-only or brittle scraping.
- Full rewrite of the two-stage LLM architecture.
- Broad global macro coverage beyond the first official/free U.S. macro path.
- Legal/economic interpretation beyond source-backed factual release and market-context wording.

---

## Implementation Map for a Fresh Agent

This section is intentionally concrete so an agent with no prior conversation context can start from the current repository state.

### Current chokepoints

| Concern | Current file/function | Current behavior to preserve/change |
|---------|-----------------------|-------------------------------------|
| Item schema | `src/investo/models/items.py::NormalizedItem` | `raw_metadata` is flat primitive-only (`str | int | float`). Nested dicts are rejected. Prefer a flat metadata bridge first unless doing a deliberate model migration. |
| Source health | `src/investo/models/coverage.py::SourceOutcome` | Already carries `latest_item_at`; use it for macro staleness before adding new outcome shape. |
| Source aggregation | `src/investo/sources/aggregator.py::collect_sources` | Returns `SourceCollectionReport(items, outcomes)` with per-source isolation. Do not make macro source failure fatal. |
| FRED macro actuals | `src/investo/sources/fred.py::FredMacroAdapter` | Default series are currently `CPIAUCSL`, `UNRATE`, `DFF`; PPI actual is not included. |
| FRED calendar schedule | `src/investo/sources/fred_economic_calendar.py::FredEconomicCalendarAdapter` | PPI schedule already exists as release id `46`; items carry `raw_metadata["release_id"]` and `raw_metadata["release_name"]`. |
| Segment routing | `src/investo/briefing/segments.py::segment_items` | `fred-economic-calendar` and `fred-macro` are routed to `us-equity`; crypto-policy priority has a special route helper. |
| Coverage status | `src/investo/briefing/segments.py::evaluate_segment_coverage` | Required categories are currently `news`/`price` centered; macro actual health must be a separate axis. |
| Candidate caps | `src/investo/briefing/pipeline.py::_select_llm_candidate_items` | Caps are 96 total, 24 per source, 12 lookahead. It already preserves bounded official crypto policy items by `policy_priority=crypto_regulation` + `official_source=true`. |
| Stage 1 parse | `src/investo/briefing/pipeline.py::_parse_classification` | Validates only known ids; extend it to reject missing required macro ids and required macro ids in `unassigned`. |
| Stage 2 caps | `src/investo/briefing/pipeline.py::_render_grouped_sections` / `_render_unassigned` | Caps are 48 total, 14 per section, 8 unassigned. Required macro actuals need a dedicated render path outside these caps. |
| Stage 2 prompt | `src/investo/briefing/prompts.py` | Add a `required_macro_actuals` placeholder/rule; keep prompt text compact. |
| Trace footer | `src/investo/briefing/trace_footer.py` and `pipeline.py` footer append | Current trace sees selected Stage 1 candidates only; lineage must also record dropped candidates. |
| Shared macro block | `src/investo/orchestrator/bundle_context.py` + `src/investo/publisher/shared_macro.py` | `## ⓪ 오늘의 매크로` currently triggers only for narrow shared patterns across >= 2 segments. Decide whether a single P0 required macro actual should force it. |
| Carryover | `src/investo/briefing/carryover_parser.py` + `src/investo/models/carryover.py` | Existing carryover is text/section based. u59 needs event-key based macro lifecycle, not substring matching. |
| Quality history | `src/investo/briefing/quality_eval.py` / `quality_history.py` | Add append-only macro KPI fields; do not change historical meaning of existing KPI columns. |
| Workflow env | `.github/workflows/daily-briefing.yml` and `docs/tech-env.md` | `FRED_API_KEY` is already optional. Add new env vars only if absolutely needed and document them as optional. |

### Existing fixtures/tests to extend

| Area | Existing test/fixture |
|------|-----------------------|
| FRED actuals | `tests/unit/sources/test_fred.py`, `tests/unit/sources/fixtures/api/fred-macro/` |
| FRED calendar | `tests/unit/sources/test_fred_economic_calendar.py`, `tests/unit/sources/fixtures/api/fred-economic-calendar/release_46_ppi.json` |
| Source registry contract | `tests/unit/sources/test_plugin_contract.py` |
| Source tiers | `tests/unit/sources/test_tiers.py` |
| Segment routing/coverage | `tests/unit/briefing/test_segments.py` |
| Pipeline candidate rendering | existing `tests/unit/briefing/test_pipeline_*` files; add a focused `test_pipeline_macro_priority.py` if no natural home exists |
| Orchestrator wire-through | `tests/unit/orchestrator/test_run_pipeline.py` |

### Non-negotiable compatibility rules

- Do not store nested dicts/lists in `NormalizedItem.raw_metadata`.
- Do not make `FRED_API_KEY` boot-critical; missing key must degrade only the FRED adapters.
- Do not introduce paid or unofficial consensus data for "예상치".
- Do not widen crypto-policy priority behavior while adding macro priority; preserve u58 semantics.
- Do not let required macro reservation exceed global LLM caps without an explicit bounded limit.
- Do not publish operator lineage as reader-facing prose; it belongs under `_meta` diagnostics.
- Do not let macro source absence fail a segment when no macro-sensitive claim is made.
- Do not render unsupported numeric/surprise claims; u55 numeric gates remain authoritative for core numeric facts.

---

## Source Strategy

### v1 official/free path

| Layer | Source | Role | Notes |
|-------|--------|------|-------|
| Calendar | `fred-economic-calendar` | scheduled releases | Keep schedule-only; PPI release id `46` remains an event identity anchor. |
| Calendar | `fomc-calendar` | scheduled FOMC events | Preserve current event-type metadata. |
| Actuals | `fred-macro` | structured observations | Expand to include selected PPI actual series after verifying the exact public FRED/BLS series. |
| Actuals | `treasury-rates` | rates/yield macro actuals | Existing macro/rate actual input. |
| Actuals | future `bls-actuals` | source-of-record BLS actual prints | Add after v1 priority/model contract is stable. |
| Actuals | future `bea-actuals` / `census-actuals` | GDP/PCE/retail/housing actuals | Add in later adapter slices. |

### Forecast/consensus rule

Do not render "예상치 상회/하회" unless `forecast` or `consensus` is present from an approved source with an explicit source/license decision. When forecast is absent, render actual vs prior or actual-only language.

---

## Data Model

Preferred typed shape:

```python
MacroImportance = Literal["P0", "P1", "P2", "P3"]
MacroEventStatus = Literal["scheduled", "actual", "unresolved", "confirmed", "stale"]

class MacroPrint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_key: StrictStr
    label: StrictStr
    status: MacroEventStatus
    importance: MacroImportance
    actual: StrictStr | None = None
    prior: StrictStr | None = None
    forecast: StrictStr | None = None
    consensus: StrictStr | None = None
    surprise: StrictStr | None = None
    release_period: StrictStr | None = None
    source_release_id: StrictStr | None = None
```

Compatibility bridge:
- If model migration risk is high, start with flat `raw_metadata` keys:
  - `macro_event_key`
  - `macro_event_label`
  - `macro_event_status`
  - `macro_priority`
  - `macro_actual`
  - `macro_prior`
  - `macro_forecast`
  - `macro_surprise`
  - `macro_release_period`
- Keep all metadata primitive-safe; no nested dicts in `raw_metadata`.

---

## Priority Policy

Priority is assigned before LLM selection, not only inside prompts.

| Priority | Examples | Candidate behavior |
|----------|----------|--------------------|
| P0 | Today actual CPI/PPI/NFP/PCE/GDP, FOMC decision/minutes, official rate shock, major Treasury yield shock | Reserve before generic caps; required macro contract applies. |
| P1 | Today/tomorrow scheduled CPI/PPI/NFP/FOMC/PCE/GDP without actual yet | Preserve bounded schedule context; can become carryover. |
| P2 | Central-bank speech, secondary official macro release, policy context that affects rates/liquidity | Prefer over generic low-signal news but do not crowd out price/news core. |
| P3 | Ordinary calendar rows, low-signal macro commentary | Normal cap behavior. |

Sort key:
1. `macro_priority`
2. event proximity to `target_date`
3. source tier / official source flag
4. event status (`actual` before `scheduled`)
5. original item order as stable tie-breaker

---

## Required Macro Contract

Required macro actuals must carry a deterministic contract:

```json
{
  "macro_event_key": "us:PPI:2026-05",
  "macro_event_status": "actual",
  "macro_priority": "P0",
  "required_sections": "0,2,4"
}
```

Behavior:
- Stage 1 candidate selection reserves required macro items before generic lookahead/news caps.
- Stage 1 parser rejects a classification where required macro actuals are missing or `unassigned`.
- Stage 2 prompt receives a compact `required_macro_actuals` block.
- Stage 2 rendered prompt keeps required macro actuals outside generic section caps.
- Post-generation validator checks final markdown for each required macro event key/label/source URL.
- Missing required macro mention triggers a retry or segment downgrade/fail according to severity rules.

---

## Macro Coverage and Severity

Add macro actual health as a separate axis from price/news core coverage.

Proposed source groups:

```python
SEGMENT_MACRO_ACTUAL_SOURCES = {
    "domestic-equity": frozenset({"krx-foreign-flows"}),
    "us-equity": frozenset({"treasury-rates", "fred-macro"}),
    "crypto": frozenset({"treasury-rates", "defillama-market-structure"}),
}
```

Reason codes:
- `MACRO_ACTUAL_MISSING`
- `MACRO_ACTUAL_ZERO`
- `MACRO_ACTUAL_FAILED`
- `MACRO_ACTUAL_STALE`
- `MACRO_REQUIRED_OMITTED`
- `MACRO_FORECAST_UNVERIFIED`

Policy:
- If no macro claim is made, macro actual absence should not fail the segment.
- If a macro-sensitive claim is made while macro actual sources are missing, downgrade to at least `limited`.
- If a hard numeric macro claim is unsupported or conflicting, block or remove the segment output.
- If shared macro block is emitted while required macro actuals are unavailable, fail the block or segment.

---

## Operator Lineage Artifact

Add an operator-only artifact:

`archive/_meta/run_traces/{target_date}/{segment}.json`

Suggested `watched_events` fields:
- `event_key`
- `label`
- `source_name`
- `release_id`
- `scheduled_date`
- `collected`
- `routed_segment`
- `selected_for_stage1`
- `selected_stage1_id`
- `stage1_assignment`
- `stage1_state`
- `rendered_in_stage2_grouped_sections`
- `rendered_in_lookahead_block`
- `final_body_mentions`
- `final_body_has_source_link`
- `diagnosis`

Diagnosis enum:
- `missing_at_source`
- `dropped_by_segment_routing`
- `dropped_by_stage1_candidate_cap`
- `dropped_by_stage1_classification`
- `dropped_by_stage2_prompt_cap`
- `llm_omitted`
- `published`

Also emit compact structured logs, for example:

```text
[diagnostics] segment=us-equity event=PPI collected=true routed=true stage1=true stage2=true final=false diagnosis=llm_omitted
```

---

## Macro Carryover Lifecycle

Persist macro lifecycle state in:

`archive/_meta/macro_event_carryover.jsonl`

Statuses:
- `scheduled`: future event is known.
- `unresolved`: release day arrived but actual print was not confirmed.
- `confirmed`: actual print confirmed by approved source.
- `stale`: event remained unresolved past the confirmation window.

Lifecycle:
- Before release: show as scheduled watch point.
- Release day before actual: mark unresolved and carry to next run.
- After actual: mention in §②/§④ and keep one follow-up day for market absorption/rate reaction.
- After one confirmed follow-up day: drop unless reintroduced.

---

## Definition of Done

- [ ] **AC-1 Macro metadata contract**: macro schedule and actual items carry stable primitive metadata or typed `MacroPrint` fields with event key, status, priority, label, and release period.
- [ ] **AC-2 PPI schedule identity**: PPI release calendar fixture/test asserts release id `46`, scheduled date, event label, source name, and segment routing to `us-equity`.
- [ ] **AC-3 PPI actual path**: `fred-macro` or an approved official actual adapter emits a PPI actual item with latest value, prior value when available, observation/release date, source URL, and no secret leakage.
- [ ] **AC-4 Forecast discipline**: no "예상치 상회/하회" wording is allowed unless a licensed/approved forecast field is present.
- [ ] **AC-5 Priority-aware candidate selection**: `_select_llm_candidate_items(items, target_date=...)` preserves P0/P1 macro events under generic news/lookahead pressure while retaining bounded caps.
- [ ] **AC-6 Required macro Stage 1 contract**: required macro actuals cannot be dropped, omitted, or classified as `unassigned` without a retry/fail signal.
- [ ] **AC-7 Required macro Stage 2 contract**: required macro actuals are rendered outside generic Stage 2 caps and exposed in a compact dedicated prompt block.
- [ ] **AC-8 Post-generation validation**: final markdown is checked for required macro event mention/source linkage; missing required macro output triggers retry or severity downgrade/fail.
- [ ] **AC-9 Macro severity policy**: macro actual missing/zero/failed/stale reason codes affect coverage only when macro actuals are required or macro-sensitive claims are made.
- [ ] **AC-10 Lineage artifact**: operator-only run trace diagnoses whether each watched macro event was missing at source, dropped by routing/caps, omitted by LLM, or published.
- [ ] **AC-11 Macro carryover**: scheduled/unresolved/confirmed/stale lifecycle persists across runs and can carry release-day unresolved events forward.
- [ ] **AC-12 Quality metrics**: `macro_actual_missing_segments` and `required_macro_omitted` are available in quality history or operator diagnostics.
- [ ] **AC-13 R10 fixtures**: new/expanded macro source fixtures pin PPI schedule and actual behavior without live network calls.
- [ ] **AC-14 R13 secret hygiene**: macro diagnostics, lineage, source errors, and quality rows do not expose API keys or secret-shaped substrings.
- [ ] **AC-15 Gate green**: targeted tests plus repo quality gate pass for the changed scope.

---

## Implementation Steps

Recommended implementation order:

1. Land metadata/priority helpers with tests and no source behavior change.
2. Add PPI fixture/source identity tests.
3. Change candidate selection and prompt contracts.
4. Add validation/lineage after the behavior is pinned.
5. Add quality/carryover surfaces last.

This order keeps early slices small and avoids mixing source expansion with LLM-stage contract changes.

### Step 1 - Freeze macro model and metadata bridge

- [x] Choose typed `MacroPrint` model vs flat `raw_metadata` bridge for the first slice.
- [x] Add priority/status literal enums in a stable import location.
- [x] Update serialization into LLM prompts so macro actual fields are visible.
- [x] Tests: model validation, primitive metadata compatibility, prompt serialization.
Recommendation for first implementation:
- Start with `src/investo/models/macro.py` pure helpers plus flat `raw_metadata` keys.
- Add helper functions such as `macro_event_key(item)`, `macro_priority(item)`, `is_required_macro_actual(item)`, and `macro_required_sections(item)`.
- Re-export only if multiple packages need the helpers; avoid a broad `NormalizedItem` migration until tests prove the contract.
Result:
- Implemented `src/investo/models/macro.py` with `MacroImportance`, `MacroEventStatus`, `macro_event_key`, `macro_event_status`, `macro_priority`, `is_required_macro_actual`, `macro_required_sections`, `macro_event_date`, `macro_prompt_payload`, and `macro_priority_rank`.
- Kept `NormalizedItem` unchanged and preserved flat primitive-only `raw_metadata`.
- `serialize_items_for_prompt` now includes a compact `macro` object only for macro-recognized items; non-macro prompt JSON remains byte-compatible.

### Step 2 - PPI schedule and actual source fixture

- [x] Add a dedicated PPI schedule identity test around `fred-economic-calendar` release id `46`.
- [ ] Verify and add the selected public PPI actual series to `fred-macro` or a source-of-record adapter.
- [ ] Add fixture metadata sidecars for replay.
- [ ] Tests: success, no-key behavior where applicable, stale/empty payload.
Implementation notes:
- Extend `tests/unit/sources/test_fred_economic_calendar.py` near the existing CPI identity test; assert `release_id == "46"`, release name/title includes Producer Price Index/PPI, `scheduled_at` is NY release-day normalized as the adapter currently defines it, and `segment_items(...).us_equity` contains the item.
- For actuals, add the PPI series only after verifying the exact series id. Do not guess in code. Record the choice in fixture metadata and this plan/audit.
- If using `fred-macro`, update `_DEFAULT_SERIES` in `src/investo/sources/fred.py`, fixture bytes under `tests/unit/sources/fixtures/api/fred-macro/`, and `tests/unit/sources/test_fred.py`.
Result:
- Added a dedicated `release_id=46` PPI schedule identity test in `tests/unit/sources/test_fred_economic_calendar.py`, including inferred P1 macro identity and `us-equity` routing.
- PPI actual source path remains open; do not choose a FRED series id without official verification.

### Step 3 - Priority-aware candidate selection

- [x] Extend `_select_llm_candidate_items` to accept `target_date`.
- [x] Reserve bounded P0/P1 macro events before generic lookahead cap.
- [x] Preserve the existing official crypto-policy priority path from u58.
- [x] Tests: PPI/FOMC/CPI survive after many low-priority rows; caps remain bounded.
Implementation notes:
- Current function: `src/investo/briefing/pipeline.py::_select_llm_candidate_items(items)`.
- Existing constants: `_MAX_LLM_ITEMS = 96`, `_MAX_LLM_ITEMS_PER_SOURCE = 24`, `_MAX_LLM_LOOKAHEAD_ITEMS = 12`.
- Existing u58 reservation detects `item.raw_metadata["policy_priority"] == "crypto_regulation"` and `official_source == "true"`. Keep that behavior byte-compatible.
- Add a separate macro reservation pass with a small cap, for example `_MAX_REQUIRED_MACRO_ITEMS`, before generic iteration.
- Change call site in `generate_briefing` to pass `target_date`.
Result:
- Added `_MAX_LLM_MACRO_PRIORITY_ITEMS = 12`.
- `_select_llm_candidate_items(items, *, target_date=None)` now reserves inferred/explicit P0/P1 macro items before u58 crypto-policy and generic passes.
- Existing u58 policy priority condition remains unchanged.

### Step 4 - Required macro prompt and parser contract

- [x] Add Stage 1 required macro prompt contract.
- [x] Update Stage 1 prompt rules so required macro actuals must be assigned.
- [x] Update Stage 1 parser validation for missing/`unassigned` required macro ids.
- [x] Tests: valid assignment, missing required id, required id in `unassigned`.
Implementation notes:
- Stage 1 prompt builder lives around the `STAGE1_USER_TEMPLATE` path in `src/investo/briefing/prompts.py`.
- `_parse_classification` currently validates ids are known. Add an optional `required_item_ids` argument rather than relying on global state.
- `build_section_plan` currently forwards assigned + unassigned items. Required macro actuals should never depend on `unassigned` forwarding.
Result:
- Added Stage 1 macro contract wording to `STAGE1_SYSTEM`.
- Added `_required_macro_item_ids(items)` and passed it through `_classify` to `_parse_classification`.
- `_parse_classification(..., required_item_ids=...)` now rejects required macro ids in `unassigned` and required macro ids omitted from assignments.
- No Stage 2 dedicated render block yet; that remains Step 5.

### Step 5 - Stage 2 preservation and post-generation validator

- [ ] Ensure required macro actuals are rendered outside generic grouped-section caps.
- [ ] Add final markdown validation for required macro label/source/event key.
- [ ] Decide retry vs segment downgrade/fail behavior.
- [ ] Tests: final body includes required event, omitted event fails/downgrades deterministically.
Implementation notes:
- `_render_grouped_sections` caps classified items to 48 total / 14 per section.
- `_render_unassigned` caps unassigned to 8.
- Add a dedicated `_render_required_macro_actuals(...)` and thread it into `STAGE2_USER_TEMPLATE` so required macro actuals do not compete with generic section caps.
- The validator should not require exact prose. Match stable event key/label/source URL/token with conservative aliases such as PPI / Producer Price Index / 생산자물가 only for known event types.

### Step 6 - Macro severity and quality KPI

- [ ] Add macro actual health resolver.
- [ ] Add reason codes and quality history/operator diagnostic fields.
- [ ] Ensure no macro claim + missing macro source does not over-penalize a segment.
- [ ] Tests: macro claim without actual downgrades; no macro claim remains normal.
Implementation notes:
- Extend `src/investo/briefing/segments.py` near `SEGMENT_CORE_SOURCES`, `_derive_reason_codes`, and `_resolve_severity`.
- Keep macro actual sources separate from `SEGMENT_REQUIRED_CATEGORIES`; otherwise all normal days become degraded.
- Add quality fields append-only in `quality_eval.py` / `quality_history.py`; never rename existing columns.

### Step 7 - Operator lineage artifact

- [ ] Add pure lineage builder under `src/investo/briefing/lineage.py` or adjacent diagnostics module.
- [ ] Persist per-segment JSON traces from orchestrator/publisher space.
- [ ] Add compact structured log line for watched events.
- [ ] Tests: diagnosis enum for source missing, routing drop, candidate cap drop, Stage 2 cap drop, LLM omission, published.
Implementation notes:
- The lineage builder should be pure and testable with synthetic `NormalizedItem`, `SourceOutcome`, `ClassificationResult`, rendered prompt metadata, and final markdown.
- Persistence belongs in orchestrator/publisher space, likely near segmented archive staging, not inside low-level source adapters.
- Include cap values in the artifact so future cap changes remain diagnosable.

### Step 8 - Macro carryover lifecycle

- [ ] Add macro lifecycle model and JSONL persistence.
- [ ] Ingest scheduled macro events after collect/routing and before generation.
- [ ] Confirm actual releases by event key, not substring matching.
- [ ] Tests: scheduled -> unresolved -> confirmed -> dropped-after-follow-up.
Implementation notes:
- Do not reuse ticker watchlist pages for macro lifecycle.
- Use event ids shaped like `{segment}:{source_name}:{normalized_event_name}:{expected_date}`.
- Existing carryover parser has macro keywords, but this unit should use structured metadata confirmation instead of substring matching.

### Step 9 - Documentation and gate

- [ ] Update `docs/requirements.md`, `docs/tech-env.md`, and source plugin documentation if new env vars are added.
- [ ] Add summary under `aidlc-docs/construction/u59-macro-actual-priority-and-lineage/code/summary.md`.
- [ ] Run targeted tests, ruff, mypy strict, pytest, mkdocs strict as appropriate.
- [ ] Update `aidlc-state.md` and append audit evidence.
Implementation notes:
- If the implementation is split across commits, update `aidlc-state.md` step count after each closed step.
- Record any chosen PPI series id, source URL, and fixture-recording method in `aidlc-docs/audit.md`.
- If a new env var is added, wire `.github/workflows/daily-briefing.yml` and `docs/tech-env.md`; prefer no new env vars for v1.

---

## Test Plan

Targeted tests:
- `tests/unit/sources/test_fred_economic_calendar.py` for PPI release id `46`.
- `tests/unit/sources/test_fred_macro.py` or new `test_bls_actuals.py` for PPI actual.
- `tests/unit/briefing/test_pipeline_macro_priority.py` for candidate preservation.
- `tests/unit/briefing/test_macro_required_contract.py` for Stage 1/Stage 2 validation.
- `tests/unit/briefing/test_macro_lineage.py` for diagnostics.
- `tests/unit/briefing/test_macro_carryover.py` or `tests/unit/orchestrator/test_macro_carryover.py`.
- `tests/unit/briefing/test_segments.py` for macro severity interactions.
- `tests/unit/orchestrator/test_run_pipeline.py` for wire-through.

Quality gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/
uv run pytest
uv run mkdocs build --strict
```

If full `ruff format --check .` remains blocked by known out-of-scope files, record the blocker and run changed-file format checks.

---

## Risks and Decisions

- **Forecast licensing**: keep v1 actual-only unless an approved forecast source is explicitly added.
- **Stale official data**: include observation date, latest item date, and source lag in diagnostics; downgrade stale actuals.
- **Over-prioritization**: priority reserves must be bounded so macro events do not crowd out price/news core.
- **US bias**: route P0 U.S. macro primarily to `us-equity` and shared macro only when cross-segment relevance is deterministic.
- **LLM omission**: required macro validation must happen after generation; prompt-only guarantees are insufficient.
- **Token budget**: render one compact macro actual per event, not raw API payloads.

---

## Open Questions

1. Should the first implementation use a typed `MacroPrint` field on `NormalizedItem`, or a lower-risk flat metadata bridge followed by a model migration?
2. Which exact public PPI actual series should v1 use for source-backed "PPI" in the U.S. briefing?
3. Should required macro omission trigger one LLM retry before downgrade/fail, or fail immediately?
4. Should `## ⓪ 오늘의 매크로` be emitted for a single P0 macro actual, or only when at least two segments share it?
5. Should macro lineage artifacts be staged into public repo archive or kept out of reader-facing site navigation?
