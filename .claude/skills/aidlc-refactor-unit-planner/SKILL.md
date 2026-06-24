---
name: aidlc-refactor-unit-planner
description: Convert Investo-wide clean-code, architecture, or refactoring audits into reviewed AIDLC implementation units. Use when the user asks to analyze the repository against a guide or architecture standard, derive 개선점, split them into AIDLC units, delegate drafting to subagents, delegate independent review to other subagents, validate the review findings, and update `aidlc-docs/aidlc-state.md` plus construction plan files.
---

# AIDLC Refactor Unit Planner

Turn broad refactoring findings into bounded, reviewable Investo AIDLC units. The output is documentation only unless the user explicitly asks to implement the units.

## Required Inputs

- Current repo root: `/Users/user/Desktop/Projects/investo`.
- Primary state file: `aidlc-docs/aidlc-state.md`.
- Plan output directory: `aidlc-docs/construction/plans/`.
- Architecture references: `docs/DESIGN.md`, `CLAUDE.md`, relevant existing plan/summary files, and any user-supplied external guide.
- If the user references an external guide URL, fetch or inspect the guide before using it unless its contents were already provided in the current context.

## Workflow

1. Establish scope.
   - Determine whether the user wants analysis only, AIDLC docs only, or implementation.
   - Treat "서브에이전트에게 맡겨", "리뷰 위임", or "타당성 검증" as authorization to spawn subagents.
   - Keep unrelated worktree changes out of scope.

2. Gather local evidence before drafting.
   - Read `aidlc-docs/aidlc-state.md` and identify the latest unit number.
   - Search existing units and summaries for overlap before naming new units.
   - Inspect the code surfaces implicated by the audit; do not rely on abstract clean-code commentary.
   - Check especially for completed units that already own the same concern, such as stage abstraction, validator registry, source registry coverage, surface-quality gates, publish atomicity, or briefing decomposition.

3. Group findings into units.
   - Prefer small implementation units with one architectural boundary or defect family each.
   - Split when tests, ownership, or blast radius differ.
   - Merge when findings require the same files and same acceptance criteria.
   - For each candidate, define: problem, goal, scope boundary, non-goals, dependencies, fixed contracts, implementation steps, acceptance criteria, and validation commands.

4. Delegate drafting.
   - Spawn writer subagents for independent units or unit clusters.
   - Give each writer a concrete file responsibility and forbid implementation unless requested.
   - Ask writers to ground every proposed unit in local code evidence and existing AIDLC deduplication.
   - Integrate their drafts yourself; do not paste unverified output directly into the repo.

5. Write AIDLC plan files.
   - Create `aidlc-docs/construction/plans/{unit-name}-code-generation-plan.md`.
   - Use Code Generation stage unless the unit introduces new product behavior, external dependency, source, secret, infrastructure, runtime cost, or unresolved domain decision.
   - Mark Functional Design/NFR Requirements as skipped only with a concrete reason.
   - Add the new rows to `aidlc-docs/aidlc-state.md` in numeric order.

6. Delegate independent review.
   - Use different subagents from the writers.
   - Partition review by overlap risk, for example publish/CI, shared contracts/models, source/generation boundaries.
   - Ask reviewers to check:
     - architectural validity against actual code and `docs/DESIGN.md`
     - overlap with completed AIDLC units
     - contextless LLM readiness
     - realistic validation commands and test files
     - contracts that are underspecified or would cause boundary drift

7. Validate reviewer findings.
   - Do not accept all review comments automatically.
   - Re-open the referenced files and decide whether each finding is real, overstated, or out of scope.
   - Patch only validated issues.
   - Typical validated fixes include missing focused tests, wrong canonical module ownership, underspecified compatibility exports, and plans that would reintroduce sibling imports.

8. Final verification.
   - Run:
     ```bash
     git diff --check -- aidlc-docs/aidlc-state.md aidlc-docs/construction/plans
     rg -n "uNNN|unit-slug" aidlc-docs/aidlc-state.md aidlc-docs/construction/plans
     git status --short
     ```
   - Do not run implementation tests unless code was changed or the user asked for implementation.
   - Close all subagent sessions used for drafting or review.

## Plan File Expectations

Each generated code-generation plan should contain:

- title, date, unit, stage, status, source, effort, dependencies
- Problem Statement
- Goal
- Existing Coverage / Deduplication
- Scope Boundary with in-scope and out-of-scope lists
- Stage Decision
- Fixed Contracts
- Implementation Steps with checkboxes
- Acceptance Criteria
- Tests / Validation
- Non-Goals

Keep contracts explicit enough for a contextless LLM to implement without inventing architecture. If a plan says "move shared contract", state the exact canonical owner and compatibility owner. If a plan says "add diagnostics", state the concrete dataclass/TypedDict/Literal shape or say which existing shape to reuse.

## Subagent Prompt Pattern

Writer prompt:

```text
역할: AIDLC unit writer. cwd=/Users/user/Desktop/Projects/investo.
Draft one code-generation plan for {unit}. Ground it in actual code evidence and existing AIDLC deduplication. Do not edit files. Include scope, non-goals, fixed contracts, implementation steps, acceptance criteria, and validation commands.
```

Reviewer prompt:

```text
역할: AIDLC document reviewer. Review only {plan files} and the matching rows in aidlc-state.md. Check actual code evidence, overlap with completed units, contextless LLM readiness, compatibility strategy, and validation commands. Do not edit files. Report findings by severity with file/line references.
```

## Final Response

Report:

- units created and where
- which review findings were accepted or rejected, with short reasons
- verification commands run
- whether code was changed or docs only
- any unrelated worktree files left untouched
