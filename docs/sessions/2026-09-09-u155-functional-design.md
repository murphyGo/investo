# Session — u155 Functional Design

**Date**: 2026-09-09 KST
**Base**: `origin/main@f93def427be2d16365685102c7e9dcf1cad073e1`
**Branch**: `codex/codex-provider-20260909`
**Worktree**: `.tmp/codex-provider-20260909` under the original Investo root.

## Work completed

Registered u155 with the unit definition, story map, execution plan and state.
Recorded the new user-authorized scope as an extension of the historical
Claude-only requirement. Wrote a design brief, business logic, R1–R14 rules,
domain contracts, seven-step FD plan and nine-step Code Generation plan.
FD artifacts are validated but user approval is pending. NFR/Infrastructure
remain required; code and operational steps remain unchecked.

## Current evidence and decisions

- Remote main refreshed; existing root is behind and dirty. Used an isolated
  worktree; original modified/untracked paths and local main were preserved.
- Latest registry ends at u154; u155 is a distinct provider/auth unit.
- Debt dashboard has Critical/High/Medium 0; 34 Low items. No unrelated debt
  or earlier unit was promoted, closed or executed.
- Claude calls are centralized but hardcoded; environment preflight and
  runtime boot always require Claude OAuth today.
- Auth checkpoint must precede public publication; adding only an end-of-
  workflow write-back cannot provide that guarantee.
- GitHub Repository Secrets are captured at queue time. Proposed rotation
  storage is an Environment Secret plus fixed workflow serialization and
  same-process CLI serialization.
- Current production policy differs from module defaults: per-call 1,800s,
  US total 3,900s, domestic/crypto 5,700s; workflow timeout 240 minutes.
  Private Actions cost/latency require measurement before activation.
- Codex raw auth/event output is not a public artifact; synthetic token-leaf
  leakage tests and a clean CLI environment are planned.

## Validation

- Six new Markdown files: relative links, final newline, whitespace and
  balanced fences passed.
- Exactly 12 AC identifiers and 14 business-rule identifiers; nine Code
  Generation steps remain unstarted.
- Five unit/state/execution/requirement registration references verified.
- `git diff --check` passed; tracked and untracked changes are Markdown only.
- No source/test/workflow/site-docs edit; no runtime test or MkDocs build run.
- Local review only; no independent code review claim before implementation.

## Handoff

Review [the design brief](../../aidlc-docs/construction/u155-codex-chatgpt-briefing-provider/design-brief.md).
The dev-investo design-stage completion rule requires explicit approval.
No credentials were opened/copied/registered, private repo created, schedule
changed, live generation run, Telegram sent, Pages deployed, commit or push made.
Next stage after FD approval: focused NFR Requirements, then Infrastructure
Design and reviewed implementation. Activation remains a concrete later step.
