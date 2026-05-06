# Code Generation Plan: `u7 segmented briefing`

**Date**: 2026-05-07
**Unit**: u7 segmented briefing
**Stage**: Code Generation

---

## Goal

Implement FR-008: one daily run creates separate domestic-equity, us-equity, and crypto briefings, publishes three archive pages, and sends one Telegram message containing three links.

---

## Definition of Done

- [ ] Segment routing is deterministic and unit-tested.
- [ ] Archive paths become `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` for new runs.
- [ ] Public URLs become `{SITE_URL_BASE}/archive/{segment}/YYYY/MM/YYYY-MM-DD/`.
- [ ] Existing disclaimer, leak guard, retry, and Claude Code CLI-only checks remain green.
- [ ] Integration test writes three archive files and sends one Telegram message with three links.
- [ ] `ruff check .`, `ruff format --check .`, `mypy --strict src/`, `pytest -q`, and `mkdocs build --strict` pass.

---

## Steps

### Step 1 — Segment Domain Helpers ✅

- [x] Add `MarketSegment` constants or Literal alias.
- [x] Add pure `segment_items(items)` helper.
- [x] Add tests covering:
  - Yonhap / Korean ticker routes to domestic-equity.
  - yfinance / Nasdaq / SEC / FOMC / FRED routes to us-equity.
  - CoinGecko / TheBlock routes to crypto.
  - Fed/liquidity cross-market routing where appropriate.
  - Low-signal unrelated item routes nowhere.

**Implemented**: `src/investo/briefing/segments.py`, `tests/unit/briefing/test_segments.py`, and the no-dynamic-execution drift guard now includes `investo.briefing.segments`.

**Verification**: `pytest tests/unit/briefing/test_segments.py tests/unit/briefing/test_no_eval.py -q` ✅; `ruff check .` ✅; `ruff format --check .` ✅; `mypy --strict src/` ✅.

### Step 2 — Segment-Aware Briefing Generation

- [ ] Add a segment context parameter to the u2 generation path without weakening existing contracts.
- [ ] Add data-limited instruction when routed item count is below threshold.
- [ ] Test prompt/context behavior without live Claude.

### Step 3 — Segment Archive Paths and URLs

- [ ] Add segment archive path helper.
- [ ] Add segment URL helper.
- [ ] Keep historical unsegmented archive files readable.
- [ ] Update tests that currently assume unsegmented URLs for new pipeline output.

### Step 4 — Orchestrator Multi-Segment Flow

- [ ] Generate all three segment briefings in fixed order.
- [ ] Publish all three files in one commit.
- [ ] Fail the whole run if any segment generation fails.
- [ ] Preserve existing collect/publish/notify alert behavior.

### Step 5 — Telegram Segmented Summary

- [ ] Build one message with domestic/us/crypto labels, one-line summaries, and three links.
- [ ] Preserve all three URLs under truncation.
- [ ] Add notifier/unit and integration tests.

### Step 6 — Docs, State, and Verification

- [ ] Update archive/site docs for segmented paths.
- [ ] Update `aidlc-state.md` u7 row and global Build/Test row.
- [ ] Write `aidlc-docs/construction/u7-segmented-briefing/code/summary.md`.
- [ ] Run full quality gate.

---

## Non-Goals

- Add paid APIs.
- Replace all Yahoo sources in this unit. Yahoo fallback alternatives should be a separate u1 extension if needed.
- Send three separate Telegram channel messages per run.
- Backfill all historical unsegmented archives.
