---
name: investo-team
description: Coordinate Investo work with the project's lead, planner, developer, QA, and ops roles adapted from .claude/agents. Use when the user asks to use the Investo team, convert or apply the agent workflow, make autonomous progress, decompose work across specialists, implement AIDLC/code/QA/ops tasks with role discipline, or run parallel Codex workers using Investo role prompts.
---

# Investo Team

## Overview

Use this skill to run the Investo project with the same role boundaries as the `.claude/agents` team, adapted to Codex. Codex skills do not register custom `subagent_type` names, so apply these roles as operating guidance locally and, when the user explicitly asks for agent/team/parallel work, pass the relevant reference file instructions to Codex `worker` or `explorer` subagents.

## Role Selection

- **Lead**: Use by default for vague or high-level requests such as "진행해줘", "make progress", "fix this", or "팀으로 해줘". Read `references/lead.md`.
- **Planner**: Use for AIDLC plans, `aidlc-docs/`, `docs/requirements.md`, `docs/TECH-DEBT.md`, `docs/DESIGN.md`, audit entries, state updates, and session logs. Read `references/planner.md`.
- **Developer**: Use for Python implementation, tests, fixtures, and quality gates under `src/` and `tests/`. Read `references/developer.md`.
- **QA**: Use for independent review, spec compliance, NFR coverage, and TECH-DEBT candidates after implementation. Read `references/qa.md`.
- **Ops**: Use for `.github/workflows/*.yml`, `mkdocs.yml`, `site_docs/`, GitHub Secrets plumbing, and operator docs. Read `references/ops.md`.

## Codex Mapping

Claude's original agents use `Agent(subagent_type="investo-developer")` and Claude-only tools such as `TaskCreate`. In Codex:

- Use `update_plan` for visible task tracking.
- Use local execution directly for the critical path unless the user explicitly asks for subagents, delegation, a team, or parallel work.
- If delegation is allowed, spawn `worker` for implementation/ops/planner write tasks and `explorer` for read-only codebase questions. Put the role name and the relevant reference content in the prompt.
- Tell workers they are not alone in the codebase and must not revert others' edits.
- Keep write scopes disjoint when running multiple workers.
- Integrate and verify results locally before final reporting.

## Operating Loop

1. Orient from `aidlc-docs/aidlc-state.md`, `aidlc-docs/audit.md`, `docs/TECH-DEBT.md`, `aidlc-docs/inception/plans/execution-plan.md`, and task-relevant files.
2. Choose the lead role for decomposition unless the user requested a specific role.
3. Read only the role references needed for the task.
4. Make a concise plan for multi-file or multi-role work.
5. Execute or delegate according to Codex's subagent rules.
6. Run the appropriate verification gate for changed files.
7. Report work done, state/doc changes, tests, unresolved risks, and the next concrete step.

## Project Rules

Reject or fix work that violates these rules:

- No Anthropic SDK imports or dependencies. LLM calls go through `briefing/claude_code.py` and the `claude -p` subprocess pattern.
- No paid APIs or paid API keys.
- Only `orchestrator` may import `sources`, `briefing`, `publisher`, or `notifier`; those work units share only `models`.
- Published briefings must pass `publisher.verify_disclaimer`.
- Telegram public channel ID and operator chat ID must remain separate.
- Source XML parsing must use `defusedxml`, not raw stdlib XML.
- Do not leak secrets in logs, errors, fixtures, or `raw_metadata`.
- Do not commit unless the user explicitly asks.

## References

- `references/lead.md`
- `references/planner.md`
- `references/developer.md`
- `references/qa.md`
- `references/ops.md`
