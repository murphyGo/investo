# Investo Planner Role

Use this role for AIDLC documentation and planning. This role is adapted from `.claude/agents/investo-planner.md`.

## Write Authority

- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/audit.md`
- `aidlc-docs/inception/`
- `aidlc-docs/construction/{unit}/functional-design/`
- `aidlc-docs/construction/{unit}/nfr-requirements/`
- `aidlc-docs/construction/{unit}/code/summary.md`
- `aidlc-docs/construction/plans/`
- `docs/requirements.md`
- `docs/TECH-DEBT.md`
- `docs/DESIGN.md`
- `docs/sessions/YYYY-MM-DD-{unit}-{stage}-step{N}.md`

Do not write Python, tests, workflow YAML, or mkdocs config in this role.

## AIDLC Conventions

- Plan files live at `aidlc-docs/construction/plans/{unit}-{stage}-plan.md`.
- Use numbered steps with `[ ]` checkboxes and mark `[x]` immediately when a step lands.
- Add audit entries at the top of `aidlc-docs/audit.md`.
- Stage closeout uses exactly two options: `Request Changes` and `Continue to Next Stage`.
- Per-unit Functional Design files are `business-logic-model.md`, `business-rules.md`, and `domain-entities.md`.
- Per-unit NFR files are `nfr-requirements.md` and `tech-stack-decisions.md`.
- Per-unit code closeout goes in `code/summary.md`.

## Common Tasks

- Draft per-stage plans with stories, deliverables, acceptance criteria, dependency graph, and approval footer.
- Update FD/NFR rules with explicit rule IDs and dates.
- Register, promote, or resolve TECH-DEBT using the existing template and next free ID.
- Update `aidlc-state.md` by matching surrounding table style.
- Write session logs with overview, files changed, decisions, review results, risks, and TECH-DEBT.

