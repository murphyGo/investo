# NFR Requirements - `u109 domestic-anchor-sanity-quarantine`

**Date**: 2026-06-23
**Source**: `aidlc-docs/construction/plans/u109-domestic-anchor-sanity-quarantine-code-generation-plan.md`

This document fixes testable non-functional requirements for the domestic
anchor quarantine gate. It complements the functional-design rules and does not
expand u109 into a source-adapter, infrastructure, or archive-backfill unit.

ACs: `AC-1.1`-`AC-1.8`.

---

## NFR-Determinism

### AC-1.1 Classification is byte-stable

Given identical candidates, source outcomes, target date, and existing domestic
market close window, the helper returns the same trusted/withheld maps and
reason ordering.

Pinned by unit tests that classify the same candidate list twice and compare
serialized results.

### AC-1.2 Plausibility boundaries are inclusive and covered

Boundary values at the minimum and maximum close bands pass the band check.
Values one step outside the band classify as `implausible`.

Pinned by boundary tests for KOSPI, KOSDAQ, USD/KRW, Samsung Electronics, and
SK Hynix, including daily percent move limits.

## NFR-Graceful Degradation

### AC-1.3 Untrusted domestic anchors degrade without exact numbers

When domestic anchors are unavailable, stale, implausible, or missing
provenance, the public output omits exact values and uses number-free labels or
reader-safe notes. The segment may still publish when other content is valid.

Pinned by integration fixtures covering public markdown, chart sidecar, visual
payload text, and Telegram summary.

### AC-1.4 Exact domestic prose claims fail closed

If public body prose contains an exact claim for a registry symbol without a
matching trusted anchor, the existing anchor assertion gate blocks publication.

Pinned by `anchor_assertion_gate` tests for KOSPI, KOSDAQ, USD/KRW, Samsung
Electronics, and SK Hynix aliases.

## NFR-Observability

### AC-1.5 Withheld metadata is bounded and zero-defaulted

Quality history/snapshot records carry:

- `domestic_anchor_withheld_count: int = 0`
- `domestic_anchor_withheld_reasons: tuple[str, ...] = ()`

Allowed reason values are exactly `unavailable`, `stale`, `implausible`, and
`provenance_missing`. Rows with no withheld anchors serialize zero/empty
defaults.

Pinned by u96 quality snapshot/history tests.

### AC-1.6 Diagnostics are R13-safe

Diagnostics may include symbol, bounded reason, source name, and target date.
They must not include secrets, full raw source payloads, full raw URLs, Telegram
tokens, OpenAI keys, or unredacted environment values.

Pinned by a negative test that injects token-shaped strings into candidate
metadata and asserts public/diagnostic serialization redacts or omits them.

## NFR-Compatibility

### AC-1.7 US and crypto anchors are behavior-compatible

Existing US and crypto anchor reconciliation tests remain unchanged in expected
behavior. u109 may add shared helper imports, but policy decisions are limited
to the domestic registry.

Pinned by existing u70/u55 anchor reconciliation tests plus a regression that
US and crypto fixture payloads serialize without domestic withheld metadata.

## NFR-Performance and Infrastructure

### AC-1.8 Quarantine is in-process and linear

The helper performs no network I/O, subprocess calls, filesystem writes, sleep,
or external validation. Runtime is linear in the number of domestic anchor
candidates and source outcome records.

Pinned by a unit test with monkeypatched network/subprocess sentinels or by code
structure review plus focused helper tests. No new GitHub Actions job, secret,
environment variable, database, or deploy change is introduced.

---

## Validation Commands

```bash
uv run --extra dev pytest tests/unit/orchestrator/test_kr_anchors.py tests/unit/orchestrator/test_domestic_anchor_quarantine.py tests/unit/orchestrator/test_anchor_close_reconcile.py tests/unit/publisher/test_anchor_assertion_gate.py tests/unit/publisher/test_channel_anchor_block.py tests/unit/publisher/test_chart_sidecar.py tests/unit/visuals tests/unit/notifier/test_summary.py tests/unit/notifier/test_summary_extract.py
uv run --extra dev ruff check src/investo/orchestrator src/investo/publisher src/investo/visuals src/investo/notifier tests/unit/orchestrator tests/unit/publisher tests/unit/visuals tests/unit/notifier
uv run --extra dev mypy src
```
