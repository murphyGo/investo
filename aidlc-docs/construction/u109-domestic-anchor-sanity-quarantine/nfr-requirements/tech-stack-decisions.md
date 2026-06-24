# Tech-Stack Decisions - `u109 domestic-anchor-sanity-quarantine`

**Date**: 2026-06-23
**Source**: `aidlc-docs/construction/plans/u109-domestic-anchor-sanity-quarantine-code-generation-plan.md`

`TS-1`-`TS-5` record the binding implementation and infrastructure decisions
for u109.

---

## TS-1. No new source adapter or live market validation

- **Decision**: u109 consumes only existing `NormalizedItem`, domestic anchor,
  source outcome, and quality snapshot data already present in the pipeline.
- **Rationale**: The defect is unsafe public projection of untrusted domestic
  anchors, not missing source coverage. Source expansion belongs to separate
  adapter units.

## TS-2. No third-party dependency

- **Decision**: classification uses stdlib types plus existing project data
  classes. No parser, market-data SDK, HTTP client, or validation dependency is
  added.
- **Rationale**: Trust classification is fixed-band, fixed-registry, and
  deterministic. Existing code already carries the candidate metadata needed
  for the gate.

## TS-3. Reuse u70/u74/u96 surfaces instead of parallel rendering

- **Decision**: u109 filters domestic anchors before u70 reconciliation, maps
  private trust states to u74 public `MissingReason`, and writes bounded
  metadata through u96 quality snapshot/history paths.
- **Rationale**: A parallel public rendering path would create cross-surface
  drift. Reusing existing gates keeps prose, channel-depth blocks, quality
  dashboards, and notifications aligned.

## TS-4. Infrastructure delta is none

- **Decision**: u109 adds no GitHub Actions workflow, scheduled task, database,
  cache service, secret, environment variable, deployment config, or Pages
  pipeline change.
- **Rationale**: The gate is an in-process transformation during the existing
  daily briefing pipeline. Validation is covered by existing unit/integration
  test jobs.

## TS-5. Public/private boundary stays text-only and R13-safe

- **Decision**: private trust states may appear in structured quality metadata
  and collapsed diagnostics only. Public prose uses number-free u74 missing
  labels or `국내 기준값 일부 비공개`.
- **Rationale**: This keeps operator observability while avoiding the same
  machine-written public-language failure that triggered the u108-u112 bundle.

---

**Net dependency delta for u109: none.**

**Net infrastructure delta for u109: none.**
