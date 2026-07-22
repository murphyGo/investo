# Tech Stack Decisions: `u145 sector-dashboard-public-hf-limited-radar`

**Date**: 2026-07-22
**Status**: Complete

## 1. No new runtime dependency

Use the existing Python 3.11+, `httpx`, Pydantic v2, `Decimal`, `zoneinfo`, pytest,
Hypothesis, Ruff, and mypy-strict stack. Do not add a provider SDK, dataframe library,
database, scheduler, browser tool, or JavaScript data client.

Rationale: the endpoint surface is small, the response envelope is bounded, existing typed
HTTP/testing conventions are sufficient, and a provider SDK would expand secret/error/payload
surfaces without removing the need for explicit source validation.

## 2. HTTP ownership

`sector_dashboard.hf_data` accepts an injected `httpx.AsyncClient` and a typed config. The
dedicated entrypoint owns one client with fixed timeouts, host policy, redirect policy, limits,
and event hooks. It does not register the provider in the general briefing `sources` aggregator
during qualification.

## 3. Model ownership

Public sector entities remain in `models/sector.py` only if they stay side-effect free and the
file remains reviewable; otherwise they move to a sibling `models/sector_public.py` that imports
only shared sector identities/value objects. The Step 1 code review chooses the split by size,
not by broadening private literals.

`SectorSeriesBundle` and `SectorDashboardSnapshot` are never converted to unions with public
source ids. Sibling types keep Pydantic validation exhaustive.

## 4. Mathematical kernel extraction

Extract generic kernels into `sector_dashboard/metric_kernels.py` or expose private helpers from
`metrics.py` only after golden tests pin every existing u139 result and artifact hash. Existing
`nav_*` public functions remain wrappers. Public snapshot assembly lives separately so public
field names are IEX-price-specific.

## 5. Calendar

Reuse the versioned NYSE calendar owner under `models.market_calendar` after adding tests for
the u145 freshness boundary. Do not introduce a new calendar dependency for v1. When the static
calendar lacks the target year/holiday authority, fail freshness as `unknown`; never silently
fall back to weekday-only production promotion.

## 6. Persistence and Pages

Reuse existing publisher staged-file validation/transaction primitives where their contracts
fit, but keep a dedicated sector build outcome and pair verifier. Artifacts are Markdown and
JSON under `site_docs/sectors/`; no SQLite/object store/cache is introduced.

Probe workflow has no write/deploy permission. Scheduled/publishing workflow and MkDocs nav are
separate Step 6 activation changes after five probes.

## 7. Test data

Provider tests use hand-authored schema-equivalent synthetic payloads derived from the accepted
shape, not copied live bars or raw response recordings. Credentialed probe evidence records
only schema/semantics/count/date/status summaries. Hypothesis generates normalized value/bar
series within bounded domains and never invokes network.

## 8. Security chokepoints

Extend `_internal.redaction.SECRET_ENV_VARS` and reuse `redact_text`/`scan_for_leak`. Do not add a
local regex catalogue. Reuse the project no-paid guard and public language/leak scanning rather
than creating provider-specific bypasses.

## 9. Deployment posture

GitHub Actions remains the only runtime; GitHub Pages remains the only public host. No Telegram
integration is added. Key rotation is manual because the provider requires an external account
and email verification; Investo automates detection and validation, not identity actions.
