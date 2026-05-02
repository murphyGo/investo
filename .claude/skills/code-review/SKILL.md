---
name: code-review
description: Analyze Investo code changes for correctness, security, quality, and test coverage.
---

# Code Review Skill - Investo

Automatically analyze code for quality issues, security vulnerabilities, and best-practices compliance for the Investo project (Python data pipeline + GitHub Actions runner).

## Project Configuration

**Language**: Python 3.11+
**Framework**: None (CLI / batch pipeline; no web framework)
**Lint Command**: `ruff check .`
**Format Check**: `ruff format --check .`
**Test Command**: `pytest`
**Type Check**: `mypy src/`

---

## Arguments

- `$ARGUMENTS` - One of the following:
  - `git` - Review files changed in git (staged + unstaged)
  - `session:<path>` - Review files listed in session log's "Files Modified" section
  - `files:<path1>,<path2>` - Review specific files
  - `dir:<path>` - Review all source files in directory

## Objective

Find real issues in code by reading and understanding it deeply — not by pattern-matching against a checklist.

---

## Pre-Review: Automated Checks

Before manual review, run automated tools:

```bash
ruff check .
ruff format --check .
mypy src/
pytest
```

**If any automated check fails, fix those issues before proceeding with manual review.**

---

## Execution Steps

### Step 1: Identify Files to Review

#### If `git`:
```bash
git diff --name-only HEAD
git diff --name-only --cached
```
- Combine staged and unstaged changes
- Filter to source files (exclude generated, cache, virtualenv)
- Separate test files for different handling

#### If `session:<path>`:
- Read session log file
- Parse "Files Modified" or "Files Changed" section
- Extract file paths

#### If `files:<paths>`:
- Split comma-separated paths
- Validate files exist

#### If `dir:<path>`:
- Glob source files recursively (`*.py`)
- Separate test files

### Step 2: Read and Understand Code

Read each file fully. Understand:
- What the code does and why
- How it interacts with other components (per `aidlc-docs/inception/application-design/`)
- What invariants it maintains
- What happens when things go wrong

### Step 2a: Protocol Selection (Triage)

After reading the code, check for deep-analysis triggers:

1. **Read** `protocols/INDEX.md` for signal-to-protocol mapping
2. **Scan** the code under review for each signal category in the index
3. **Load** the corresponding protocol file for each match
4. **Apply** each loaded protocol's analysis steps during Step 3

Common matches in Investo:
- `asyncio.gather`, `httpx.AsyncClient` → `protocols/concurrency.md`
- File writes, git ops → `protocols/data-integrity.md` + `protocols/resource-lifecycle.md`
- Custom error types, retry logic → `protocols/error-contract.md`
- Subprocess invocations (claude, git) → `protocols/security-boundary.md` + `protocols/resource-lifecycle.md`

### Step 3: Review with Focus Areas

Analyze the code from these perspectives, in priority order:

1. **Correctness** — Logic bugs, edge cases, spec non-compliance, off-by-one errors, None/empty handling
2. **Safety** — Resource leaks, concurrency bugs, security vulnerabilities, data loss risks
3. **Reliability** — Error handling quality, failure scenarios, graceful degradation
4. **Maintainability** — Unnecessary complexity, unclear naming, missing abstractions (or over-abstraction)

#### 3a: Apply Matched Protocols

For each protocol loaded in Step 2a, execute its full analysis steps against the code. Do NOT skip steps — each step builds on the previous one. Include protocol findings in the report (Step 6).

#### Project-Specific Rules (Investo)

These rules are blocking findings (🔴) when violated:

| Rule | Reference | Check |
|------|-----------|-------|
| **No Anthropic SDK import** | NFR-002, US-009 | grep `from anthropic`, `import anthropic`, `@anthropic-ai/sdk` — must be 0 hits in `src/` |
| **LLM call only via subprocess(claude -p)** | NFR-002, US-009 | All LLM-bound calls flow through `briefing/claude_code.py` |
| **Disclaimer auto-append in briefing** | NFR-004 | `briefing.append_disclaimer` is called and idempotent |
| **Disclaimer presence verified before publish** | NFR-004 | `publisher.verify_disclaimer` called before `commit_and_push` |
| **Module boundary** | Application Design | Only `orchestrator` imports `sources/briefing/publisher/notifier`. The 4 work units do not import each other. |
| **Telegram channel separation** | FR-004 vs FR-007 | `BriefingPublisher` and `OperatorAlerter` use distinct chat IDs — no shared instance |
| **Free APIs only** | NFR-002 | Source adapters do not require paid API keys |
| **Plugin extensibility** | US-008 | New sources go in `sources/<name>.py` with `@register` — no source-specific code in other components |

### Step 4: Python Language Reference

Common Python pitfalls to check:

| Pattern | Issue | Severity |
|---------|-------|----------|
| Bare `except:` clause | Catches too much (incl. KeyboardInterrupt) | Medium |
| `except Exception` swallowing without re-raise/log | Silent failure | High |
| Missing type hints on public funcs | Type ambiguity | Low |
| `open()` without context manager | Resource leak | Medium |
| Mutable default argument (`def f(x=[])`) | Shared state bug | High |
| `subprocess.run` without `check=True` and explicit `timeout` | Silent failure / hang | High |
| `subprocess` with `shell=True` + dynamic input | Command injection | Critical |
| `async def` not awaited (returning coroutine) | Silent no-op | High |
| `asyncio.gather` swallowing per-task exceptions w/o `return_exceptions` handling | Lost errors | High |
| `pydantic.BaseModel` without `model_config` extra control where needed | Silent ignored fields | Medium |
| String concat for paths (use `pathlib.Path`) | Path bugs | Low |
| `datetime.now()` without tz | Naive datetime ambiguity | Medium |
| Logging `print()` instead of `logging` | No log structure | Low |

### Step 5: Test Coverage Check

For each new/modified function:

| Check | Method | Severity |
|-------|--------|----------|
| Test file exists | Find `tests/unit/<module>/test_*.py` | Medium |
| Function has test | Find test for function name | Medium |
| Error paths tested | Find tests asserting on raised exceptions or `Result.ok=False` | Medium |
| PBT applied where applicable | `models/`, pure-function builders, serialization round-trip | Low (informational) |

### Step 6: Generate Report

```markdown
## Code Review Report

**Scope**: [N files reviewed]
**Languages**: Python
**Date**: YYYY-MM-DD HH:MM

---

### Summary

| Category | ✅ Pass | ⚠️ Warn | 🔴 Fail |
|----------|---------|---------|---------|
| Correctness | X | Y | Z |
| Safety | X | Y | Z |
| Reliability | X | Y | Z |
| Maintainability | X | Y | Z |
| Test Coverage | X | Y | Z |
| **Total** | **X** | **Y** | **Z** |

**Status**: ✅ All Clear / ⚠️ Warnings Found / 🔴 Issues Found

---

### Protocols Applied

| Protocol | Triggered By | Key Findings |
|----------|-------------|--------------|
| {protocol name} | {signal that triggered it} | {summary of findings or "No issues"} |

_If no protocols were triggered, write: "No deep-analysis protocols triggered."_

---

### Project-Specific Rule Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| No Anthropic SDK import | ✅/🔴 | [grep result] |
| LLM via subprocess only | ✅/🔴 | [callsite list] |
| Disclaimer auto-append | ✅/🔴 | [where verified] |
| Disclaimer verified pre-publish | ✅/🔴 | [where verified] |
| Module boundary (DAG) | ✅/🔴 | [import graph note] |
| Telegram channel separation | ✅/🔴 | [chat ID source] |
| Free APIs only | ✅/🔴 | [API key check] |

---

### Issues Detail

#### 🔴 Critical/High Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|
| 1 | src/investo/briefing/claude_code.py:45 | Security | `shell=True` with user input | Use list args; never `shell=True` |

#### 🟡 Medium Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|

#### 🟢 Low Severity

| # | File:Line | Category | Issue | Suggestion |
|---|-----------|----------|-------|------------|

---

### Self-Review Checklist

| Item | Status | Evidence |
|------|--------|----------|
| No logic bugs or edge case gaps | ✅/⚠️/🔴 | [brief evidence] |
| Resources properly cleaned up (context managers, async closes) | ✅/⚠️/🔴 | [brief evidence] |
| Concurrency is safe (no unawaited coroutines, gather error handling) | ✅/⚠️/🔴 | [brief evidence] |
| No hardcoded secrets | ✅/⚠️/🔴 | [brief evidence] |
| Errors handled with context (chained `raise ... from e`) | ✅/⚠️/🔴 | [brief evidence] |
| Failure scenarios covered (graceful degradation per Q9=B) | ✅/⚠️/🔴 | [brief evidence] |
| Unit tests cover key paths | ✅/⚠️/🔴 | [brief evidence] |
| Type hints on public APIs (mypy strict) | ✅/⚠️/🔴 | [brief evidence] |

---

### TECH-DEBT Candidates

Issues that should be tracked as technical debt:

| DEBT ID | Priority | Location | Description | Effort |
|---------|----------|----------|-------------|--------|
| DEBT-XXX | Medium | `file.py:78` | [description] | 15 min |

Add to TECH-DEBT.md? (yes/no)
```

---

## Ignore Directives

Code can be excluded from review with comments:

```python
# code-review:ignore-next-line
secret = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")  # Read from env, not literal

# code-review:ignore-block-start
# Legacy fixture, will be replaced
def old_fixture():
    pass
# code-review:ignore-block-end
```

---

## Severity Definitions

| Severity | Meaning | Action |
|----------|---------|--------|
| 🔴 Critical | Security vulnerability or data loss risk | Must fix before commit |
| 🔴 High | Likely bug or resource leak | Should fix before commit |
| 🟡 Medium | Code quality issue | Fix or document as TECH-DEBT |
| 🟢 Low | Style/convention issue | Fix if easy, else ignore |

---

## Example Invocations

Review git changes:
```
/code-review git
```

Review from session log:
```
/code-review session:docs/sessions/2026-04-30-u1-code-generation-step1.md
```

Review specific files:
```
/code-review files:src/investo/briefing/claude_code.py,src/investo/briefing/generator.py
```

Review directory:
```
/code-review dir:src/investo/sources
```

---

## Python Style Guide (Investo)

### Naming Conventions
- `snake_case` for functions, variables, modules
- `PascalCase` for classes
- `UPPER_CASE` for constants
- `_private` prefix for module-internal
- Module names match unit IDs (`sources`, `briefing`, `publisher`, `notifier`, `orchestrator`)

### Code Organization
- Imports: stdlib → third-party → local. Sorted alphabetically within group (ruff isort).
- One class per file when class is non-trivial. Small dataclasses can colocate.
- Keep functions short; extract helpers when > ~30 lines.
- Use `__all__` for public API in module `__init__.py`.

### Error Handling
```python
# Good
try:
    result = await source_adapter.fetch(target_date)
except SourceFetchError as e:
    logger.warning("source %s fetch failed: %s", source_adapter.name, e)
    return []
except Exception as e:
    logger.exception("unexpected source failure: %s", source_adapter.name)
    raise

# Bad
try:
    result = await source_adapter.fetch(target_date)
except:                # bare except
    pass               # silent
```

### Type Hints
- Required on all public functions and methods
- Use `T | None` (Python 3.10+) instead of `Optional[T]`
- Use `Literal[...]` for enum-like string params
- pydantic v2 BaseModel for I/O boundaries

### Async
- All Source adapters must implement `async def fetch`
- `asyncio.gather(..., return_exceptions=True)` when collecting per-source results
- Always close async clients via `async with httpx.AsyncClient()` or explicit `aclose`
- Never call sync I/O in `async def` hot paths

### Subprocess
- Always pass `args` as **list** (never `shell=True`)
- Always set explicit `timeout=`
- Always pass `check=False` and inspect `returncode` explicitly (or `check=True` with `try/except CalledProcessError`)
- Capture `stdout`/`stderr` with `capture_output=True` for retry/logging

### Logging
- Use `logging` (not `print`) — `logger = logging.getLogger(__name__)`
- Use lazy formatting: `logger.info("fetched %d items", count)` (not f-string)
- INFO for normal pipeline steps, WARNING for graceful-degraded failures, ERROR for stage failures

---

## Project-Specific Patterns

These patterns are derived from `docs/DESIGN.md` and `aidlc-docs/inception/application-design/`:

- **Plugin registry**: Source adapters live in `src/investo/sources/`, each as a standalone module with `@register` decorator. Registry is loaded at import time.
- **Two-stage prompt**: `briefing.generate_briefing` orchestrates `(1) build_classification_prompt → call_claude_code → parse → (2) build_briefing_prompt → call_claude_code → render`. Each stage is independently testable.
- **Disclaimer constant**: `briefing.disclaimer.DISCLAIMER` is a module-level string constant. `append_disclaimer` is idempotent (checks last lines for substring presence).
- **Result types**: Notifier methods return `SendResult` and never raise on HTTP failure (raise only on programmer errors, e.g. invalid types).
- **Pipeline result**: `PipelineResult.status` is one of SUCCESS / PARTIAL / FAILED — used to decide exit code and whether to alert.
