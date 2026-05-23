---
name: briefing-unit-planner
description: Create Investo market-briefing improvement units from generated briefing reviews. Use when the user asks to review recent 시황/briefings, synthesize 개선점, deduplicate against existing AIDLC units, write detailed unit/code-generation plans, or delegate those units to subagents for review before implementation.
---

# Briefing Unit Planner

## Objective

Turn reader/operator reviews of generated Investo market briefings into concrete AIDLC units that can be implemented later by a contextless agent.

Use this skill for requests like:
- "최근 시황을 리뷰하고 개선 유닛 도출해"
- "중복 구현 제외하고 유닛 만들어"
- "서브에이전트에게 유닛 리뷰 위임해"
- "이번처럼 시황 개선 유닛 생성해"

Default mode is **planning/docs only**. Do not edit production code unless the user explicitly asks to implement a unit.

---

## Required Inputs To Inspect

Read only what is needed, but start with these:

- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/inception/application-design/unit-of-work.md`
- `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- `aidlc-docs/construction/plans/`
- `docs/requirements.md`
- `docs/TECH-DEBT.md`
- Latest generated briefing artifacts:
  - `archive/domestic-equity/YYYY/MM/YYYY-MM-DD.md`
  - `archive/us-equity/YYYY/MM/YYYY-MM-DD.md`
  - `archive/crypto/YYYY/MM/YYYY-MM-DD.md`
  - `archive/_meta/quality_history.jsonl`
  - `archive/_meta/coverage.jsonl` if present
  - `site_docs/quality.md`
  - `site_docs/watchlist/` when watchlist findings are involved

Use `rg`/`rg --files` first.

---

## Workflow

### 1. Orient

1. Check git status and leave unrelated dirty files untouched.
2. Locate the latest relevant briefing date from `archive/` and quality metadata.
3. Inspect existing units and plan files before proposing anything new.
4. Build a dedupe map:
   - Existing unit that already implements the finding.
   - Existing unit that should be improved.
   - Truly new unit.
   - Refactor-only unit.

### 2. Review Generated Briefings

If the user explicitly asks for subagents, spawn distinct read-only reviewers. Keep review angles separate, for example:

- First-time retail reader
- Domestic/Korean equity reader
- US equity reader
- Crypto reader
- Mobile UX
- Data trust/provenance
- Actionability
- Beginner Korean reader
- Watchlist/portfolio workflow
- Product roadmap

Ask each subagent for actionable reader-facing findings, not implementation. Then synthesize repeated issues into ranked themes.

If subagents were not requested, do the same review locally.

### 3. Derive Units

For each candidate unit, apply these filters in order:

1. **Already duplicated**: exclude and cite the existing unit.
2. **Similar existing function**: create an improvement unit that names the owner unit and the narrow extension.
3. **Structural issue**: create a refactor unit only if it reduces real cross-surface drift or module-boundary risk.
4. **Implementation-ready**: the unit must be understandable without chat context.

Do not create generic duplicates like:
- Generic quality KPI if u54/u62/u65 already cover it.
- Generic numeric validation if u55 already covers it.
- Generic first-viewport formatting if u51/u61 already cover it.
- Generic watchlist matching if u64 already covers it.
- Generic chart redesign if u50/compact chart work already covers it.

### 4. Write Unit Registrations

Update:

- `aidlc-docs/inception/application-design/unit-of-work.md`
- `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- `aidlc-docs/aidlc-state.md`

In `unit-of-work.md`, add each unit with:

- Purpose
- Stories / FR / NFR coverage
- Existing Coverage / Deduplication
- Module path
- Definition of Done

In `unit-of-work-story-map.md`, add a planning notes table:

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|

In `aidlc-state.md`, register the unit as backlog. If a unit depends on an unplanned or incomplete unit, mark it as blocked or partial-scope-ready.

### 5. Write Code-Generation Plans

Create one file per unit:

`aidlc-docs/construction/plans/{unit-id}-{unit-slug}-code-generation-plan.md`

Each plan must be detailed enough for a contextless agent:

```markdown
# Code Generation Plan: `{unit-id} {unit-slug}`

**Date**: YYYY-MM-DD
**Unit**: {unit-id} {unit-slug}
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: {review source}
**Estimated Effort**: ~N-N h
**Dependencies**:
- ...

---

## Problem Statement
Concrete examples from generated artifacts and why this matters to a reader.

## Goal
The target reader/operator outcome.

## Existing Coverage / Deduplication
Which existing units own nearby behavior, and exactly what this unit does not duplicate.

## Scope Boundary
In scope and out of scope.

## Stage Decision
Functional Design and NFR Requirements decision with reason.

## Implementation Steps
Checkbox steps with concrete file/function/module targets.

## Acceptance Criteria
Numbered ACs that are testable.

## Tests / Validation
Exact expected test files or fixture types and local gate.

## Non-Goals
Explicit exclusions.
```

Avoid vague phrases like "choose", "decide", "or equivalent", or "if needed" unless the plan also gives a fixed default and a decision rule.

### 6. Delegate Unit Reviews

If the user asks to delegate/review with subagents:

1. Spawn one read-only `explorer` per unit when possible.
2. Ask each reviewer to inspect:
   - The unit plan file
   - The `unit-of-work.md` section
   - The story-map notes
   - The `aidlc-state.md` row
3. Ask reviewers to check:
   - Contextless implementability
   - Deduplication against named existing units
   - Scope and acceptance criteria precision
   - Missing dependencies, tests, risks, module-boundary issues
4. Incorporate valid feedback with docs-only patches.
5. Close all agents.

Reviewer prompt pattern:

```text
Read-only review task for Investo docs.
Review exactly this unit plan and its registrations:
- aidlc-docs/construction/plans/{plan-file}
- aidlc-docs/inception/application-design/unit-of-work.md section for {unit}
- aidlc-docs/inception/application-design/unit-of-work-story-map.md relevant planning notes
- aidlc-docs/aidlc-state.md {unit} row

Do not edit files. Review from the perspective of a contextless implementation agent.
Check:
1. Is the unit detailed enough to implement without prior chat context?
2. Does it avoid duplicating {existing units}?
3. Are scope boundaries and acceptance criteria precise enough?
4. Are missing dependencies, tests, module-boundary risks, or blocked prerequisites present?
Return concise actionable findings only, with file references where possible.
```

### 7. Verify

For docs-only unit creation:

- Run `git diff --check` on touched docs/plans.
- Use `rg` to scan new plans for unresolved vague placeholders:
  - `Choose`
  - `Decide`
  - `or equivalent`
  - `TODO`
  - `TBD`
  - `likely`
- Report that production code was not changed.

Run `mkdocs build --strict` only if the changed docs are included in MkDocs or site output.

---

## Quality Bar

A good unit plan must answer:

- What exact generated-briefing defect or reader gap triggered it?
- Which existing unit already owns adjacent behavior?
- What is explicitly excluded to avoid duplication?
- Which files/functions should an implementer inspect first?
- What data contract or enum/table is fixed in the plan?
- What makes the unit blocked, ready, or partial-scope-ready?
- Which tests prove the fix on rendered/generated artifacts, not only helper functions?

If a subagent says "the implementer still has to decide the core contract," revise the plan before presenting it as ready.

---

## Reporting

Final response should include:

- Units created or updated.
- Where the docs/plans were written.
- Subagent review count and main feedback themes.
- What was changed after review.
- Validation commands run.
- Any blocked prerequisites or implementation order.

Do not commit unless the user explicitly asks.
