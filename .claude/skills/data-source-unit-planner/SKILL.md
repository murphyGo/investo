---
name: data-source-unit-planner
description: Explore and evaluate Investo data sources, then create bounded AIDLC units for adding suitable news, indicator, chart, filing, market-data, or on-chain sources. Use when the user asks to find available data sources, audit source coverage, rank official/free/structured candidates, validate whether a source should be added, or write source-adapter/code-generation units for Investo.
---

# Data Source Unit Planner

Turn source-discovery work into shippable Investo AIDLC units. Default output is docs/planning only; edit production code only when the user explicitly asks for implementation.

## Required Context

Start with local evidence before proposing external sources:

- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/application-design/unit-of-work.md`
- `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- `aidlc-docs/construction/plans/`
- `docs/requirements.md`
- `docs/TECH-DEBT.md`
- `CONTRIBUTING.md`
- `scripts/check_no_paid_apis.py`
- `src/investo/sources/__init__.py`
- `src/investo/sources/aggregator.py`
- `src/investo/briefing/segments.py`
- source tier maps, config files, and tests found with `rg`

Use `rg` / `rg --files` first. Keep unrelated dirty worktree changes untouched.

## Workflow

1. Establish scope.
   - Confirm whether the user wants analysis only, AIDLC docs, implementation, or commit/push.
   - Treat requests for subagents, broad exploration, or "validate whether it is reasonable" as permission to fan out research and review.
   - Separate source discovery from source-adapter implementation unless implementation was requested.

2. Inventory current coverage.
   - Map registered adapters, tier routing, market-window routing, segment allow-lists, plugin discovery, and tests.
   - Identify existing units that already cover the same data family.
   - Record known gaps by data type: news, macro indicators, earnings/filings, market prices, rates/FX, charts, crypto/on-chain, sentiment, and calendars.

3. Explore candidates.
   - Prefer official, free, structured, low-overlap sources.
   - Verify current source availability, API docs, licensing/terms, auth requirements, rate limits, fields, and update cadence from primary sources.
   - Do not promote paid-only, scraping-only, JS-heavy, or unstable pages unless the user explicitly accepts that risk.
   - For time-sensitive or current-source claims, browse/verify instead of relying on memory.
   - Read `references/source-evaluation.md` for the scorecard and source fact template.

4. Rank and decide.
   - Classify each candidate as `ship-now`, `defer`, or `reject`.
   - Ship-now requires clear provenance, no-paid compliance, structured access, graceful degradation, useful fields, and non-trivial coverage gain.
   - Defer key-required candidates unless the repo already has the key path and failure behavior.
   - Reject candidates that duplicate existing coverage without improving trust, breadth, freshness, or user-facing output.

5. Write AIDLC units when appropriate.
   - Add registrations to:
     - `aidlc-docs/inception/application-design/unit-of-work.md`
     - `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
     - `aidlc-docs/aidlc-state.md`
   - Create one plan per source or tightly coupled source family:
     `aidlc-docs/construction/plans/{unit-id}-{slug}-code-generation-plan.md`
   - Use Functional Design / NFR docs, not only a terse code plan, when the unit introduces a new external dependency, trust boundary, key/secret path, public/private metadata rule, runtime cost, or source-of-truth contract.

6. Validate with review.
   - If subagents were requested, use separate read-only agents for source families or regions and a separate reviewer pass for overlap/provenance/no-paid compliance.
   - Main agent must re-check accepted findings against local repo files and primary-source evidence before editing plans.
   - Do not preserve findings from an aborted research turn as if they were validated.

7. Verify docs.
   - Run `git diff --check` on touched docs and skill files.
   - Scan new plans for unresolved placeholders: `TODO`, `TBD`, `Choose`, `Decide`, `or equivalent`, `likely`.
   - Run `mkdocs build --strict` only if changed docs are included in the site.
   - Report whether production code was changed.

## Unit Plan Requirements

Each source-addition plan must include:

- Source facts: owner, URL/docs, auth, free-tier/no-paid status, rate limit, fields, update cadence, license/terms, reliability notes.
- Existing coverage / deduplication: exact adapters, units, or outputs that already cover nearby data.
- Scope boundary: one adapter family, one routing surface, one output behavior, and explicit non-goals.
- Fixed contracts: module path, source name, data model fields, raw metadata policy, tier/routing updates, coverage diagnostics, and graceful degradation behavior.
- Acceptance criteria: testable behavior and public-output impact.
- Tests / validation: exact files or fixture styles, no-paid guard, plugin/registry tests, and any fetch dry-run.

Avoid vague language that forces a contextless implementer to rediscover architecture. If a plan says to register a source, name every required surface: registry import, tier map, market-window routing, segment allow-list, config, tests, and diagnostics.

## Subagent Prompt Patterns

Researcher:

```text
Read-only Investo source research task. Explore official/free/structured sources for {data family}. Verify current docs, auth, rate limits, fields, update cadence, licensing, overlap with existing Investo adapters, and graceful-degradation feasibility. Return only candidates classified as ship-now/defer/reject with evidence links and repo surfaces likely affected. Do not edit files.
```

Reviewer:

```text
Read-only Investo AIDLC review task. Review {unit plan files} and matching registrations. Check source provenance, official/free/no-paid fit, overlap with existing units/adapters, contextless implementability, routing/registry completeness, tests, and runtime/degradation risks. Return concise actionable findings with file references. Do not edit files.
```

## Final Response

Report:

- sources evaluated and disposition
- units created and file paths
- accepted/rejected review findings
- verification commands run
- whether code was changed or docs only
- unrelated dirty files left untouched
