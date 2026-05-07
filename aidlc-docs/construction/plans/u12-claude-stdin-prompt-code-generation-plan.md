# Code Generation Plan: `u12 claude-stdin-prompt`

**Date**: 2026-05-07
**Unit**: u12 claude-stdin-prompt
**Stage**: Code Generation

---

## Goal

Prevent segmented briefing generation from failing when a recovered source set produces a prompt too large for the operating system argv limit.

---

## Definition of Done

- [x] Production Claude Code CLI invocation no longer puts the full prompt in argv.
- [x] Prompt text is passed via stdin using list-form subprocess execution.
- [x] Existing timeout, capture, and runner-seam behavior remains intact.
- [x] FakeClaudeRunner supports both stdin prompt delivery and legacy direct test calls.

---

## Steps

### Step 1 — Subprocess Prompt Delivery

- [x] Change `call_claude_code` from `["claude", "-p", prompt]` to `["claude", "-p"]` plus `input=prompt`.
- [x] Extend the `ClaudeRunner` protocol and default runner to accept stdin input.

### Step 2 — Test Seam Compatibility

- [x] Update direct runner tests to assert prompt delivery via stdin.
- [x] Update `FakeClaudeRunner` to derive fixture keys from stdin input.
- [x] Keep legacy direct `["claude", "-p", prompt]` replay calls working.
