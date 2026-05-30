---
name: dev-investo
description: Execute Investo AIDLC construction stages from design through build and test.
---

# Investo Development Skill

AIDLC Construction executor — the daily driver for developing the Investo service.

## Arguments

- `$ARGUMENTS` - (Optional) Target override:
  - (empty) - Auto-detect next construction target
  - `{unit-name}` - Work on specific unit
  - `{unit-name} {stage}` - Work on specific unit and stage (e.g., `auth-service code-generation`)

## Objective

Execute AIDLC Construction stages for each unit of work. This skill reads `aidlc-state.md` to determine the current unit and stage, loads the appropriate AIDLC rule, and executes the stage (design → code generation → build & test). One stage step at a time, incrementally.

---

## How This Skill Works

```
/dev-investo
    │
    ▼
Read aidlc-state.md → Find first incomplete unit
    │
    ▼
Determine current stage for that unit
(Functional Design → NFR Req → NFR Design → Infra Design → Code Gen → Build & Test)
    │
    ▼
Does per-stage plan file exist?
    │
    ├── No  → Enter stage: Load AIDLC rule → Part 1 (Planning)
    │         Create plan file with [ ] checkboxes
    │
    └── Yes → Find next [ ] checkbox
              │
              ├── Found → Execute that step (Part 2)
              │           Mark [x], update aidlc-state.md
              │
              └── All [x] → Stage complete
                            Present completion options
                            Move to next stage
```

---

## Execution Steps

### Step 0: Health Check (Automatic)

1. **TECH-DEBT Escalation Check**:
   - Read `docs/TECH-DEBT.md`
   - Check items exceeding thresholds:
     - Critical: Any age → Alert
     - High: > 14 days → Alert
     - Medium: > 21 days → Warn
   - Display if escalation candidates found:
     ```
     ⚠️ TECH-DEBT Alert

     | DEBT ID | Priority | Age | Action Suggested |
     |---------|----------|-----|------------------|
     | DEBT-001 | High | 16d | Consider /tech-debt promote |

     Continue with development? (yes/no/review-debt)
     ```

2. **Stage Completion Check**:
   - Read `aidlc-docs/aidlc-state.md`
   - Check if any unit has all construction stages complete but no cross-check
   - Check existing reports in `docs/cross-checks/`
   - If unchecked unit found:
     ```
     📋 Unit Cross-Check Pending

     Unit "{unit-name}" completed all construction stages but has no cross-check.
     Run cross-check now? (yes/no/later)
     ```
   - **yes**: Execute `/cross-check` for the unit before proceeding
   - **no**: Skip and proceed
   - **later**: Acknowledge, remind at next invocation

**Note**: Health check alerts are informational. You can proceed with "yes" or address issues first.

### Step 1: Environment Validation

1. **Verify Path Existence**:
   - `aidlc-docs/aidlc-state.md` (AIDLC state tracker — **primary**)
   - `aidlc-docs/inception/plans/execution-plan.md` (stage strategy per unit)
   - `docs/requirements.md` (requirements reference)
   - `docs/TECH-DEBT.md` (debt registry)
   - `CLAUDE.md` (project context)
   - `docs/DESIGN.md` (architecture reference)

2. **Load AIDLC Common Rules** (per core-workflow.md, MANDATORY):
   - `common/process-overview.md`
   - `common/session-continuity.md`
   - `common/content-validation.md`
   - `common/question-format-guide.md`

3. **Load Extension Opt-in Files** (if extensions enabled in aidlc-state.md):
   - Scan `extensions/` for `*.opt-in.md` files
   - Track which extensions are active for enforcement

### Step 2: Find Next Construction Target

1. **Read**: `aidlc-docs/aidlc-state.md`

2. **Read**: `aidlc-docs/inception/plans/execution-plan.md` — check which stages apply per unit

3. **Find current unit and stage** (scan in document order):

   For each unit listed in aidlc-state.md:
   - Check construction stage completion status
   - The **construction stage order** is:
     1. Functional Design (if applicable per execution-plan)
     2. NFR Requirements (if applicable)
     3. NFR Design (if applicable)
     4. Infrastructure Design (if applicable)
     5. Code Generation (always required)
     6. Build and Test (runs once after ALL units complete Code Generation)
   - Find the **first unit** with an **incomplete stage**
   - Skip stages marked N/A in execution-plan.md

4. **Check for per-stage plan file**:
   - Look in `aidlc-docs/construction/plans/` for:
     - `{unit-name}-functional-design-plan.md`
     - `{unit-name}-nfr-requirements-plan.md`
     - `{unit-name}-nfr-design-plan.md`
     - `{unit-name}-infrastructure-design-plan.md`
     - `{unit-name}-code-generation-plan.md`
   - If plan file **exists**: Find next `[ ]` checkbox (incomplete step)
   - If plan file **does not exist**: This is a fresh stage entry — will create plan in Step 4
   - If **all checkboxes are `[x]`**: Stage is complete — update aidlc-state.md and find next stage

5. **Handle $ARGUMENTS override**:
   - If unit name provided, jump to that unit
   - If unit + stage provided, jump to that specific stage
   - Validate the override is valid (unit exists, stage applies)

### Step 3: Present Construction Target

Present identified target:

```
## Next Construction Target

**Unit**: {unit-name}
**Stage**: {stage-name} (e.g., Functional Design, Code Generation)
**Status**: {New stage / Step N of M}

### AIDLC Rule: `construction/{stage-file}.md`

### Context:
- Stories: {US-XXX mappings from unit-of-work}
- Design artifacts: `aidlc-docs/construction/{unit-name}/` {existing artifacts listed}
- Dependencies: {unit dependencies from unit-of-work.md}

### What happens next:
{For new stage}: Load AIDLC rule → Generate plan with questions/steps
{For in-progress}: Execute step {N}: "{step description}"

Proceed? (yes/no/skip-to:{stage})
```

**Wait for user approval before proceeding.**

### Step 4: Execute Construction Stage

After user approval, behavior depends on the **stage type**:

#### 4A: Design Stages (Functional Design, NFR Requirements, NFR Design, Infrastructure Design)

1. **Load the AIDLC rule file**:
   - Read `aidlc-workflows/aidlc-rules/aws-aidlc-rule-details/construction/{stage}.md`
   - Follow the rule's instructions exactly

2. **If entering stage fresh** (no plan file):
   - Follow the rule's Part 1 / Planning section
   - Create plan file: `aidlc-docs/construction/plans/{unit-name}-{stage}-plan.md`
   - Include questions with `[Answer]:` tags for user responses
   - Present questions to user, wait for answers

3. **If resuming stage** (plan file exists with unanswered questions or incomplete steps):
   - Load existing plan, find where we left off
   - Continue from that point

4. **Generate design artifacts** (per the AIDLC rule):
   - Write to `aidlc-docs/construction/{unit-name}/{stage}/`
   - Validate content per `common/content-validation.md`

5. **On stage completion**:
   - Mark all plan checkboxes `[x]`
   - Present 2-option AIDLC completion message:
     ```
     Stage "{stage-name}" complete for unit "{unit-name}".

     1. Request Changes — modify artifacts before proceeding
     2. Continue to Next Stage — proceed to {next-stage}
     ```
   - Wait for explicit user approval
   - Update `aidlc-state.md` with stage completion

#### 4B: Code Generation

1. **Load rule**: `construction/code-generation.md`

2. **Part 1: Planning** (if no plan file):
   - Read all design artifacts for this unit
   - Create `aidlc-docs/construction/plans/{unit-name}-code-generation-plan.md`
   - Include a `Stage Decision` section before implementation steps:
     ```markdown
     ## Stage Decision
     - Functional Design: Required/Skipped
     - NFR Requirements: Required/Skipped
     - Reason: <why the separate stage is needed, or why existing FR/NFR/design coverage is enough>
     - Source of requirements: `docs/requirements.md` FR/NFR ids, story-map entries, review finding, TECH-DEBT item, or user request
     ```
   - If Functional Design or NFR Requirements is `Required`, stop after creating the plan and route the unit to that stage before code generation
   - Document explicit numbered steps with `[ ]` checkboxes
   - Include file paths, implementation approach, test strategy
   - Get explicit user approval of plan

3. **Part 2: Execution** (plan exists):
   - Find next `[ ]` step
   - **Enter Plan Mode** (EnterPlanMode tool) for research
   - Read related requirements, design artifacts, existing code
   - Write implementation plan
   - **Exit Plan Mode** and implement:
     - Write clean, idiomatic code
     - Application code → workspace root (NEVER in aidlc-docs/)
     - Documentation summaries → `aidlc-docs/construction/{unit-name}/code/`
     - Include comprehensive unit tests
     - Run tests to verify
   - Mark step `[x]` in plan file immediately

4. **On all steps complete**:
   - Present 2-option completion:
     ```
     Code Generation complete for unit "{unit-name}".

     1. Request Changes
     2. Continue to Next Stage / Build and Test
     ```
   - Update `aidlc-state.md`

#### 4C: Build and Test

Runs **once** after ALL units complete Code Generation.

1. **Load rule**: `construction/build-and-test.md`
2. Follow the rule's steps to generate:
   - `aidlc-docs/construction/build-and-test/build-instructions.md`
   - `aidlc-docs/construction/build-and-test/unit-test-instructions.md`
   - `aidlc-docs/construction/build-and-test/integration-test-instructions.md`
   - Additional test instruction files as applicable
   - `aidlc-docs/construction/build-and-test/build-and-test-summary.md`
3. Execute build and tests
4. Update `aidlc-state.md`

### Step 5: Self-Review & Documentation

After successful implementation (Code Generation steps only):

**5.1 Code Review** (delegated to separate agent for fresh-eyes analysis):

Delegate code review to a **separate agent** using the Agent tool.

```
Agent(subagent_type="general-purpose", prompt="""
You are reviewing Python code for the Investo project.

## Files to Review
[list changed source files from `git diff --name-only HEAD` + `git diff --name-only --cached`]

## Review Focus (priority order)
1. Correctness — logic bugs, edge cases, spec non-compliance
2. Safety — resource leaks, concurrency bugs, security, data loss risks
3. Reliability — error handling quality, failure scenarios
4. Maintainability — unnecessary complexity, unclear naming

## Deep Analysis Protocols
After reading the code, check for these signals and apply the corresponding
protocol from `.claude/skills/code-review/protocols/`:
- Concurrent access (locks, channels, threads, async) → Read and follow concurrency.md
- Database/file writes, transactions, WAL → Read and follow data-integrity.md
- Custom error types, error wrapping, ignored errors → Read and follow error-contract.md
- Caches, buffers, unbounded collections → Read and follow memory.md
- Nested loops, hot-path handlers, repeated expensive calls → Read and follow performance.md
- Open/Close, acquire/release, connection pools → Read and follow resource-lifecycle.md
- User input, auth checks, secrets, query construction → Read and follow security-boundary.md

Only load protocols whose signals are present in the code.

## Project-Specific Rules

**LLM call constraint (NFR-002, US-009)**:
- Never import the Anthropic SDK (`from anthropic ...`, `import anthropic`, `@anthropic-ai/sdk` are all forbidden)
- All LLM calls go through `briefing/claude_code.py` using the `subprocess.run(["claude", "-p", ...])` pattern
- Reject any attempt to add the `anthropic` package as a dependency

**Disclaimer enforcement (NFR-004)**:
- `briefing.append_disclaimer` must be idempotent (no-op if disclaimer already present)
- `publisher.verify_disclaimer` runs immediately before publish — block publish on failure
- Do not rely on LLM output alone for disclaimer presence

**Module boundary (Application Design DAG)**:
- Only `orchestrator` may import `sources / briefing / publisher / notifier`
- The other 4 work units must not import each other (only `models` is shared)
- Reject violations and require refactoring

**Zero-cost principle (NFR-002)**:
- Reject attempts to register paid data-API keys
- Any new external call must declare its cost impact in the PR description

**Telegram channel separation (FR-004 vs FR-007)**:
- Briefing body goes through `BriefingPublisher` (public channel) only
- Operator alerts go through `OperatorAlerter` (1:1 chat) only
- The two classes must not share a chat_id (assert at construction or test)

**Plugin interface (US-008)**:
- A new source = single `sources/<name>.py` file + one `@register` decorator line
- No source-specific code is allowed in any other component (orchestrator, briefing, etc.)

## Output Format
Generate a code review report with:
1. Summary table (Correctness/Safety/Reliability/Maintainability/Test Coverage × Pass/Warn/Fail)
2. Protocols Applied table (which protocols triggered, key findings)
3. Issues detail grouped by severity (Critical/High → Medium → Low)
   - Each issue: File:Line, Category, Issue description, Concrete fix suggestion
4. Self-review checklist with evidence
5. TECH-DEBT candidates if any

Read each file fully. Understand what the code does, then analyze.
Do NOT just pattern-match — reason about the code's behavior.
""")
```

After receiving the agent's report:
- If 🔴 Critical/High issues found, fix before proceeding or document in TECH-DEBT
- If ⚠️ Medium severity issues found, propose as improvement items:
  ```
  ### Code Review Improvement Suggestions

  The following issues were found during code review.
  Would you like to address them now or add to the stage plan?

  | # | Severity | Issue | Suggested Action |
  |---|----------|-------|------------------|
  | 1 | ⚠️ Medium | [issue description] | [concrete fix suggestion] |

  Options:
  - fix: Address now before proceeding
  - plan: Add as step to current stage plan file
  - skip: Acknowledge and continue
  ```
  - **fix**: Implement the fix, re-run tests, update code review results
  - **plan**: Add a new `[ ]` step to the current `{unit-name}-code-generation-plan.md`
  - **skip**: Document in session log as "Acknowledged, not addressed" with rationale

**5.2 Create Session Log** (`docs/sessions/YYYY-MM-DD-{unit}-{stage}-{step}.md`):

```markdown
# Session Log: YYYY-MM-DD - {Unit} - {Stage} Step {N}

## Overview
- **Date**: YYYY-MM-DD
- **Unit**: {unit-name}
- **Stage**: {stage-name}
- **Step**: {step number and description}

## Work Summary
[Brief description of completed work]

## Files Changed
- Created: [List]
- Modified: [List]

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| [What] | [Why] |

## Code Review Results
| Category | Status |
|----------|--------|
| Correctness | ✅/⚠️/🔴 |
| Safety | ✅/⚠️/🔴 |
| Reliability | ✅/⚠️/🔴 |
| Maintainability | ✅/⚠️/🔴 |
| Test Coverage | ✅/⚠️/🔴 |

## Potential Risks
- [Identified risks]

## TECH-DEBT Items
- [New items to track, if any]
```

**5.3 Update TECH-DEBT.md** (if applicable):
- Add new debt items discovered during implementation
- Add unfixed issues from code review
- Mark resolved debt items

**5.4 Create ADR** (if significant architectural decision was made):

ADR-worthy decisions:
- Affects system architecture or component boundaries
- Chooses between multiple valid approaches
- Has long-term implications worth documenting

If ADR needed:
1. Find highest existing number in `docs/adr/`
2. Create `docs/adr/NNNN-<short-title>.md` using ADR template
3. Reference ADR in session log

### Step 6: Update Construction State

After documentation:

1. **Update per-stage plan file**:
   - Mark completed step with `[x]`
   - If all steps in plan are `[x]`, stage is complete

2. **Update aidlc-state.md**:
   - Mark stage completion for the unit
   - Follow AIDLC's native state tracking format

3. **Log to audit.md**:
   - Append stage/step completion entry per AIDLC audit format

4. **Unit Completion Auto-Actions** (if all stages for a unit just completed):
   - Detect: All construction stages for current unit are now complete
   - Prompt user:
     ```
     🎉 Unit "{unit-name}" Construction Complete!

     All construction stages are done.
     Run cross-check against specs now? (yes/no/later)
     ```
   - **yes**: Execute `/cross-check` for the completed unit
   - **no**: Proceed to next unit or Build & Test
   - **later**: Skip for now, flag in Step 0 health check next time

5. **All Units Complete → Build & Test**:
   - When all units have completed Code Generation
   - Automatically transition to Build and Test stage
   - Notify user:
     ```
     All units have completed Code Generation.
     Proceeding to Build and Test stage.
     ```

### Step 7: Summary Report

Provide completion summary:

```
## Construction Step Complete

**Unit**: {unit-name}
**Stage**: {stage-name}
**Step**: {step number} of {total} {or "Stage entry — plan created"}
**Status**: Complete

### Changes Made:
- Created: [List of new files]
- Modified: [List of modified files]

### Tests: (Code Generation only)
- Added: [count] new tests
- All tests passing: Yes/No

### Documentation:
- Session Log: [filename]
- TECH-DEBT: [Added/resolved items, if any]

### Construction Progress:
- Unit "{unit-name}": Stage {N} of {total stages} — {stage-name}
- Plan progress: {completed}/{total} steps [x]
- Overall: {units complete}/{total units} units done

### Next Target:
{Brief description of next step/stage/unit}
```

---

## Guidelines

### Commit Policy

**No Auto-Commit**: Do not automatically commit changes. Always show changes to the user and get explicit approval before committing.

### Execution Rules

1. **One step per execution** — Execute one plan step (or enter one new stage) per `/dev-investo` invocation
2. **Skip N/A stages** — Stages marked N/A in execution-plan.md are skipped automatically
3. **Record stage decisions** — Every new code-generation plan must state whether Functional Design and NFR Requirements are required or skipped, with a concrete reason
4. **Follow AIDLC rules exactly** — Each stage has a rule file in `construction/`. Load and follow it
5. **Sequential stage order** — Stages must be completed in order within each unit
6. **Unit order** — Process units in the order defined in `aidlc-state.md`
7. **Build & Test is global** — Runs once after ALL units complete Code Generation

### Stage Decision Guidance

Use separate Functional Design and/or NFR Requirements only when they add real decision value. Do not create boilerplate design documents for small follow-up corrections that are already covered by existing requirements and architecture.

Functional Design is usually **Required** when the unit:
- introduces a new user-visible capability or new product workflow
- changes cross-component contracts, data models, routing, prompt contracts, or publish/notify behavior across multiple modules
- adds a new source-adapter family or external integration contract
- needs explicit business rules, state transitions, or failure semantics before code can be safely planned

Functional Design is usually **Skipped** when the unit is:
- a narrow bug fix, wording/layout adjustment, operational hardening slice, or test-only correction
- a follow-up that refines an existing FR/US/NFR without changing module boundaries
- already specified concretely enough in the code-generation plan's DoD, AC table, constants, and step traceability

NFR Requirements are usually **Required** when the unit:
- introduces or changes reliability, timeout, retry, cost, compliance, privacy, security, performance, fixture, or public-data-source policy
- adds secrets, optional API keys, external network behavior, public rendering of diagnostics, or operator alerting semantics
- changes the meaning of an existing NFR or creates a new NFR/FR entry in `docs/requirements.md`

NFR Requirements are usually **Skipped** when:
- the unit only reuses already-defined NFR contracts such as NFR-002 zero-cost, NFR-003 graceful degradation, NFR-004 disclaimer/compliance, or R10/R13 fixture/secret hygiene
- no new external dependency, public exposure surface, runtime policy, or failure mode is introduced

When skipping a stage, the code-generation plan must still preserve traceability: list the FR/NFR ids or review finding it implements, describe the existing design/NFR coverage being reused, and put any new AC/DoD in the plan itself.

### Development Standards

1. **Requirements Compliance**:
   - All implementations must match `docs/requirements.md`
   - Reference requirement IDs in code comments (e.g., FR-001, NFR-001)

2. **Language Best Practices**:
   - Follow language-specific style guides
   - Use type annotations where applicable
   - Error handling with context
   - Comprehensive testing

3. **Test Requirements** (Code Generation stage):
   - Unit tests required for all new functions/methods
   - Test both success and error paths
   - Use appropriate test fixtures
   - Mock external dependencies

4. **Code Structure**:
   - Application code goes in workspace root (NEVER in aidlc-docs/)
   - Follow existing project structure patterns
   - Documentation summaries go in `aidlc-docs/construction/{unit-name}/code/`

### AIDLC Compliance

1. **Audit logging** — Append to `aidlc-docs/audit.md` for every stage entry, completion, and user decision
2. **Content validation** — Validate Mermaid/ASCII diagrams per `common/content-validation.md`
3. **Extension enforcement** — Check enabled extensions before stage completion; non-compliance = blocking
4. **2-option completion** — Always present "Request Changes" / "Continue" at stage end
5. **Session continuity** — On resume, auto-load all previous stage artifacts before continuing

---

## Error Handling

- **All stages complete**: Report "All construction stages are complete! Project is ready."
- **Test failures**: Don't mark step as complete; report failures and suggest fixes
- **Build errors**: Fix before proceeding; don't update plan until resolved
- **Missing AIDLC rule file**: Report error with expected path
- **Missing aidlc-state.md**: Report error, suggest running `/init-project` first

---

## Example Invocations

Continue from where you left off:
```
/dev-investo
```

Work on specific unit:
```
/dev-investo auth-service
```

Work on specific stage:
```
/dev-investo auth-service code-generation
```
