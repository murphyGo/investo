# Macro reference sources — functional design

User approved the three ranked candidates with “진행시켜” on 2026-10-30. Implement in priority order; stage transitions and routine validation are within this authorization. Current authorization does not request a new release.

- [x] Review existing u106 source adapters, u102 descriptors, u144 publication boundary and u164 observation-time contract.
- [x] Define source-specific normalization and shared immutable `MacroObservation` metadata.
- [x] Define deterministic US reference display and degradation.

## Contract

u188 `treasury-tga-balance`, u189 `nyfed-gscpi`, u190 `ofr-financial-stress` each emit at most one `macro` NormalizedItem. US-only window, item and outcome routing; tier S for Treasury/OFR, A for NY Fed research index. Registry and tier/segment views derive from source_specs. No mandatory-release flags or fabricated publication dates, forecasts or trading signals. New observations remain reference items in both event profiles.

Shared model `models/macro_reference.py`: source_name, observation_date, decimal-string value, collected_at, as_of, release_vintage (GSCPI YYYY-MM only). `published_at` is retrieval time for the transport model; it is not a provider release timestamp. Current downloads can include revisions and cannot reconstruct historical publication availability. No point-in-time claim. Observation cutoff is UTC; source calendar dates retain provider meaning. Freshness bounds: daily observations 10 calendar days, GSCPI 75 days. Native panel additionally requires a same-run cutoff within 24h. Duplicated conflicting observations fail closed.

TGA uses one latest-page query (32 rows, record_date descending, cutoff filter). Require four exact Table I account types on the latest completed observation date: opening, deposits, withdrawals and closing. Metadata must declare USD millions/CURRENCY0. Current API puts all four amounts in `open_today_bal`; `close_today_bal` is null. Require opening + deposits - withdrawals = closing. Display closing only; do not construct net liquidity or infer price direction.

GSCPI reads the official chart CSV (not rendered HTML). Select the newest release-vintage column, retain its YYYY-MM identity, and select its latest nonempty month-end observation. Validate unique date/header columns; reject a malformed/conflicting latest value rather than silently using older values. Never use an older vintage to claim historical availability. Render standard-deviation units, monthly cadence, NY Fed copyright/terms, research-not-official-Fed disclaimer, revision notice.

OFR reads the official chart JSON once per adapter fetch. Parse only OFRFSI aggregate, latest completed UTC date, finite bounded value; validate exact Unix millisecond midnight stamps and conflicting duplicate dates. No proprietary constituent series or chart assets. Per-run collected NormalizedItem is reused by both renderers; no persistent raw-data cache, repeated per-segment fetch or stale-cache fallback.

Output: `_internal/macro_reference.py` validates metadata against source identity and canonical URL, renders at most three rows in priority order plus source-specific attribution. Native `MarketReferencePanel.macro_observations` is rebuilt from collected inputs at the finalizer. Legacy US `channel_anchor_block` adds the same rows/notes inside its existing owned numeric block. Domestic/crypto display remains outside this scope. Public Insights dashboard, article news activation, scheduler, secrets and historical archive rewrites are outside scope.
