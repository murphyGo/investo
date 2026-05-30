# u59 Macro Actual Priority and Lineage — Code Generation Summary

**Date**: 2026-05-31
**Unit**: u59 macro-actual-priority-and-lineage
**Status**: Complete (9/9 steps)

## Goal

Make high-importance macro events (CPI/PPI/NFP/PCE/GDP/FOMC) deterministic
first-class pipeline inputs so the daily briefing does not silently drop a
source-backed macro actual, and so operators can diagnose at which stage a
watched macro event was lost — missing at source, dropped by routing/caps,
omitted by the LLM, or published. Motivated by the 2026-05-13 U.S. PPI miss
and the 10-subagent macro design review.

## Delivered slices

### Step 1 — Macro model + metadata bridge (`src/investo/models/macro.py`)

- Chose the lower-risk **flat `raw_metadata` bridge** over a typed
  `MacroPrint` field on `NormalizedItem`, keeping `raw_metadata` primitive-only.
- Pure helpers: `macro_event_key`, `macro_event_status`, `macro_priority`,
  `is_required_macro_actual`, `macro_required_sections`, `macro_event_date`,
  `macro_prompt_payload`, `macro_priority_rank`, plus `MacroImportance` /
  `MacroEventStatus` literals. Priority is inferred for known official FRED
  release/series ids and FOMC events when not explicitly stamped.

### Step 2 — PPI schedule + actual fixtures

- PPI schedule identity test pinned to `fred-economic-calendar` release id
  `46`, scheduled date, label, and `us-equity` routing.
- Added FRED `PPIFID` (Producer Price Index by Commodity: Final Demand) to
  `fred-macro` defaults after verifying the official FRED series page; new
  `PPIFID.json` fixture proves a P0 required macro actual with stable event
  key, prior value, release date, and FRED URL (no secret leakage).

### Step 3 — Priority-aware candidate selection

- `_select_llm_candidate_items(items, *, target_date=None)` reserves inferred
  /explicit P0/P1 macro items (bounded `_MAX_LLM_MACRO_PRIORITY_ITEMS = 12`)
  before the u58 crypto-policy and generic passes. u58 policy-priority
  behavior preserved byte-for-byte.

### Step 4 — Required macro Stage 1 prompt + parser contract

- Stage 1 macro contract wording in `STAGE1_SYSTEM`; `_required_macro_item_ids`
  threaded into `_parse_classification(..., required_item_ids=...)`, which now
  rejects required macro ids that are omitted or placed in `unassigned`.

### Step 5 — Stage 2 preservation + post-generation validator

- `SectionPlan.required_macro_items` + `_render_required_macro_actuals(...)`
  render required macro actuals outside the generic Stage 2 grouped/unassigned
  caps via a dedicated `required_macro_actuals` prompt block.
- `_validate_required_macro_mentions(...)` treats omission as a Stage 2
  synthesis validation failure, reusing the existing retry/exhaustion path
  (decision: one retry via the existing loop, then fail — no immediate fail).

### Step 6 — Macro severity + quality KPI

- `SEGMENT_MACRO_ACTUAL_SOURCES`, `MacroActualHealth`,
  `resolve_macro_actual_health(...)`, and macro actual reason codes — kept off
  `SEGMENT_REQUIRED_CATEGORIES` so normal days are not degraded.
- Append-only quality-history fields `macro_actual_missing_segments` and
  `required_macro_omitted`.

### Step 7 — Operator lineage artifact (`src/investo/briefing/lineage.py`)

- Pure `build_macro_lineage_traces(...)` with the seven-value diagnosis enum;
  orchestrator persists per-segment JSON under
  `archive/_meta/run_traces/{target_date}/{segment}.json` and emits compact
  `[diagnostics]` log lines. Persistence is best-effort.

### Step 8 — Macro carryover lifecycle (this slice)

- **Model + JSONL persistence** (committed earlier in Step 8):
  `models/macro_lifecycle.py` (`MacroLifecycleEvent`, `MacroLifecycleStatus`),
  `briefing/macro_carryover.py` `load_macro_lifecycle_events` /
  `upsert_macro_lifecycle_snapshot` against
  `archive/_meta/macro_event_carryover.jsonl` (atomic write, corrupt-row-skip).
- **Pure transition** `advance_macro_lifecycle(prior_events, collected_items,
  target_date, *, segment_for=None)` — deterministic, no wall clock; joins by
  `event_key` (never substring). Lifecycle rule implemented:
  - new future event (`scheduled_date > target_date`) -> `scheduled`
  - release day reached (`scheduled_date <= target_date`) with no confirmed
    actual for that key today -> `unresolved` (carried to the next run)
  - an `actual` print collected today for the key (item with
    `macro_event_status == "actual"`) -> `confirmed`, `confirmed_date =
    target_date`, `follow_up_until = target_date + 1 day`
  - still `unresolved` once `target_date > scheduled_date + 1 grace day` ->
    `stale`
  - a `confirmed` event whose `follow_up_until < target_date` is **dropped**
    from the snapshot unless reintroduced today
  - output sorted by `event_key` for determinism.
- **Orchestrator wire** (`orchestrator/pipeline.py`): after collect/routing
  and before generation (segmented mode), `_advance_and_persist_macro_carryover`
  loads prior state, runs the transition over the collected items + the routed
  `segment_for` resolver, and upserts the new snapshot. Operator-only state
  under `archive/_meta/`; no reader-facing prose and no LLM prompt-contract
  change in this slice. Persistence/load failure is caught
  (`MacroCarryoverError` -> WARNING) and never crashes the pipeline, mirroring
  Step 7 lineage persistence.

### Step 9 — Documentation + gate (this slice)

- This summary; plan Step 8/Step 9 checkboxes and DoD AC-11 ticked.
- No new env vars introduced (v1 preference), so `docs/requirements.md`,
  `docs/tech-env.md`, and `.github/workflows/daily-briefing.yml` are untouched.

## Open questions — resolution

1. **Typed `MacroPrint` vs flat bridge** -> flat `raw_metadata` bridge
   (Step 1), avoiding a `NormalizedItem` migration.
2. **Which public PPI series** -> FRED `PPIFID` (Producer Price Index by
   Commodity: Final Demand), verified against the official FRED series page.
3. **Retry vs immediate fail on required-macro omission** -> one retry through
   the existing Stage 2 synthesis-validation loop, then fail (Step 5).
4. **`## (0) 오늘의 매크로` on a single P0 actual** -> left to the existing
   shared-macro trigger; not widened in this unit (out of scope, would be a
   reader-surface slice).
5. **Lineage / carryover staging** -> operator-only under `archive/_meta/`,
   kept out of reader-facing site navigation.
6. **Step 8 confirmation-window rule** (the formerly-open lifecycle decision)
   -> release day **plus one grace day** is the confirmation window; one
   follow-up day is retained after a confirmed actual, after which the event
   is dropped. Documented in the `macro_carryover.py` module docstring.

## Tests added/extended (Step 8)

- `tests/unit/briefing/test_macro_carryover.py` (+8 transition tests):
  scheduled -> unresolved (+carry) -> confirmed (+follow_up) -> dropped-after
  -follow-up; stale past window; confirmation-by-event-key-not-substring;
  distinct inferred keys for calendar vs fred-macro; deterministic sort order.
- `tests/unit/orchestrator/test_run_pipeline.py` (+2 wire tests): carryover
  snapshot persisted under the isolated archive root; pipeline survives a
  `MacroCarryoverError` persistence failure (graceful WARNING, run still
  SUCCESS).

## Quality gate (changed scope)

| Gate | Result |
|------|--------|
| `ruff check` (changed files) | All checks passed |
| `ruff format --check` (changed files) | 4 files already formatted |
| `mypy --strict` (changed source) | no issues in 2 source files |
| `pytest tests/unit/briefing/ tests/unit/orchestrator/` | **1136 passed** |
| `pytest` (full suite) | **2802 passed** |
| `mkdocs build --strict` | exit 0 |

`ruff format --check .` was run changed-scope only; the repo has known
out-of-scope unformatted/untracked files in the worktree.

## Hard-rule compliance

- No Anthropic SDK; LLM only via Claude Code CLI subprocess (unchanged).
- Module boundary preserved: `briefing/macro_carryover.py` imports only from
  `investo.models.*`; the orchestrator imports and wires it. No
  `briefing -> orchestrator` import.
- `raw_metadata` stays flat primitive-only; carryover JSONL stores only
  primitive lifecycle fields.
- R13: no secret-shaped values in carryover JSONL, logs, or errors.
- Macro source absence does not fail a segment when no macro claim is made
  (Steps 1-7 severity semantics unchanged).

## TECH-DEBT candidates

- **Calendar<->actual event-key linkage**: the `fred-economic-calendar`
  schedule key (`...release_id=46...`) and the `fred-macro` actual key
  (`...series_id=PPIFID...`) differ, so a schedule confirmed by its
  corresponding actual currently tracks as two lifecycle events (the
  calendar event ages to `stale`; the actual lands `confirmed`). A future
  slice could stamp a shared canonical `macro_event_key` (e.g. `us:PPI:
  2026-05`) on both adapters so a single event flows scheduled -> confirmed.
  Adapters that stamp an explicit `macro_event_key` already get the unified
  lifecycle today.
- **Segment identity by `is`**: `_segment_for_item` matches routed items by
  object identity, which is correct for the in-run routing pass but would not
  survive serialization round-trips; acceptable for the in-process wire.

## Intentionally out of scope

- Surfacing carryover as reader-facing watch points / LLM prompt-contract
  changes (separate unit).
- Forcing `## (0) 오늘의 매크로` from a single P0 actual.
- A `NormalizedItem` model migration to typed macro fields.
- New BLS/BEA/Census actual adapters beyond the FRED `PPIFID` path.
