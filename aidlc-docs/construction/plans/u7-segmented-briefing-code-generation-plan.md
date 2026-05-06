# Code Generation Plan: `u7 segmented briefing`

**Date**: 2026-05-07
**Unit**: u7 segmented briefing
**Stage**: Code Generation

---

## Goal

Implement FR-008: one daily run creates separate domestic-equity, us-equity, and crypto briefings, publishes three archive pages, and sends one Telegram message containing three links.

---

## Definition of Done

- [x] Segment routing is deterministic and unit-tested.
- [x] Archive paths become `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` for new runs.
- [x] Public URLs become `{SITE_URL_BASE}/archive/{segment}/YYYY/MM/YYYY-MM-DD/`.
- [x] Existing disclaimer, leak guard, retry, and Claude Code CLI-only checks remain green.
- [x] Integration test writes three archive files and sends one Telegram message with three links.
- [x] `ruff check .`, `ruff format --check .`, `mypy --strict src/`, `pytest -q`, and `mkdocs build --strict` pass.

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

- [x] Add a segment context parameter to the u2 generation path without weakening existing contracts.
- [x] Add data-limited instruction when routed item count is below threshold.
- [x] Test prompt/context behavior without live Claude.

**Implemented**: `generate_briefing(..., segment=..., data_limited=...)` now renders one shared segment context for Stage 1 and Stage 2. Prompt text remains centralized in `src/investo/briefing/prompts.py`, and the unsegmented default path remains available for existing callers.

**Verification**: `pytest tests/unit/briefing/test_prompts.py tests/unit/briefing/test_budget_happy_path.py tests/unit/briefing/test_pipeline_no_prompt_strings.py -q` ✅.

### Step 3 — Segment Archive Paths and URLs

- [x] Add segment archive path helper.
- [x] Add segment URL helper.
- [x] Keep historical unsegmented archive files readable.
- [x] Update tests that currently assume unsegmented URLs for new pipeline output.

**Implemented**: `archive_path(..., segment=...)`, `write_briefing(..., segment=...)`, and `_briefing_url_for(..., segment=...)` now support `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` and matching GitHub Pages URLs while keeping the default unsegmented path/URL unchanged.

**Verification**: `pytest tests/unit/publisher/test_paths.py tests/unit/publisher/test_writer.py tests/unit/orchestrator/test_run_pipeline.py -q` ✅.

### Step 4 — Orchestrator Multi-Segment Flow

- [x] Generate all three segment briefings in fixed order.
- [x] Publish all three files in one commit.
- [x] Fail the whole run if any segment generation fails.
- [x] Preserve existing collect/publish/notify alert behavior.

**Implemented**: production `run_pipeline` now uses segmented generation by default, routing items once and generating `domestic-equity`, `us-equity`, and `crypto` in fixed order. It writes all three segment archives and commits/pushes them together; injected legacy `generate=` keeps existing orchestrator tests and one-off seams available.

**Verification**: `pytest tests/unit/orchestrator/test_run_pipeline.py -q` ✅; `ruff check .` ✅; `ruff format --check .` ✅; `mypy --strict src/` ✅.

### Step 5 — Telegram Segmented Summary

- [x] Build one message with domestic/us/crypto labels, one-line summaries, and three links.
- [x] Preserve all three URLs under truncation.
- [x] Add notifier/unit and integration tests.

**Implemented**: `build_segmented_summary` composes one UTF-16-aware Telegram message with domestic/us/crypto labels, one-line summaries, and all three archive links. Segmented `run_pipeline` now sends this multi-link message while preserving the domestic URL as the model-level `site_url` field.

**Verification**: `pytest tests/unit/notifier/test_summary.py tests/unit/orchestrator/test_run_pipeline.py tests/integration/test_pipeline.py -q` ✅.

### Step 6 — Docs, State, and Verification

- [x] Update archive/site docs for segmented paths.
- [x] Update `aidlc-state.md` u7 row and global Build/Test row.
- [x] Write `aidlc-docs/construction/u7-segmented-briefing/code/summary.md`.
- [x] Run full quality gate.

**Implemented**: README, requirements, design, technical environment, build instructions, state tracker, and u7 code summary now document segmented archive paths, public URLs, and one-message/three-link Telegram behavior.

**Verification**: `ruff check .` ✅; `ruff format --check .` ✅; `mypy --strict src/` ✅; `pytest -q` ✅; `mkdocs build --strict` ✅.

---

## Non-Goals

- Add paid APIs.
- Replace all Yahoo sources in this unit. Yahoo fallback alternatives should be a separate u1 extension if needed.
- Send three separate Telegram channel messages per run.
- Backfill all historical unsegmented archives.
