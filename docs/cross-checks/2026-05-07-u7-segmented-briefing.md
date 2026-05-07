# Cross-Check Report: u7 segmented briefing

**Date**: 2026-05-07
**Scope**: Unit `u7 segmented briefing` / FR-008
**Checked by**: Codex

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 1 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **1** | **100%** |

**Verdict**: ✅ Complete. FR-008 is implemented, tested, documented, and shipped.

## Compliance Matrix

### Functional Requirements

| ID | Description | Status | Evidence | Notes |
|----|-------------|--------|----------|-------|
| FR-008 | 세그먼트별 시황 생성 | ✅ Complete | `src/investo/briefing/segments.py`, `src/investo/briefing/pipeline.py`, `src/investo/orchestrator/pipeline.py`, `src/investo/publisher/paths.py`, `src/investo/notifier/summary.py`, `tests/unit/briefing/test_segments.py`, `tests/unit/orchestrator/test_run_pipeline.py`, `tests/integration/test_pipeline.py` | Production run now generates domestic-equity, us-equity, and crypto briefings, publishes three archive files, and sends one Telegram message with all three links. |

## Acceptance Criteria Detail

### FR-008: 세그먼트별 시황 생성

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 매 실행마다 `domestic-equity`, `us-equity`, `crypto` 세그먼트를 생성한다. | ✅ | `SEGMENT_ORDER` and `_stage_generate_segments()` in `src/investo/orchestrator/pipeline.py`; covered by `test_run_pipeline_default_generates_and_publishes_three_segments`. |
| 각 세그먼트는 독립 제목과 ①~⑥ 본문 섹션을 가진다. ⑦ 면책조항은 기존처럼 코드가 공통 삽입한다. | ✅ | `generate_briefing(..., segment=..., data_limited=...)` reuses u2 `parse_six_sections()` and `append_disclaimer()`; prompt context is segment-specific while section contract stays unchanged. |
| 세그먼트별 입력은 source/category/ticker/news provenance 기반으로 분리한다. | ✅ | `segment_items()` routes by source names, Korean exchange ticker patterns, US ticker/market terms, crypto terms, and Fed/liquidity cross-market signals; covered by `tests/unit/briefing/test_segments.py`. |
| 특정 세그먼트의 핵심 소스가 부족하면 다른 세그먼트 뉴스로 대체하지 않고 "데이터 부족"을 명시한다. | ✅ | `SegmentedItems.is_data_limited()` plus prompt context uses the data-limited note; covered by `test_generate_briefing_passes_segment_context_to_both_stages`. |
| 텔레그램 메시지는 세 세그먼트의 짧은 요약과 각 상세 링크를 포함한다. | ✅ | `build_segmented_summary()` and `_stage_notify_segmented_briefing()` compose one public message with all three labels and URLs; covered by notifier unit tests and `tests/integration/test_pipeline.py`. |

## Cross-Cutting Requirements

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Claude Code CLI only / no Anthropic SDK | ✅ | u7 extends existing u2 `generate_briefing()` path; `tests/unit/briefing/test_no_anthropic_sdk.py` remains green. |
| Disclaimer enforcement | ✅ | u2 appends disclaimer; publisher verifies before write. Segmented publish now pre-validates all segment disclaimers and rolls back partial writes on write failure. |
| Historical archive compatibility | ✅ | `archive_path(..., segment=None)` and `_briefing_url_for(..., segment=None)` retain unsegmented history; new segmented runs use `archive/{segment}/...`. |
| Telegram length and link preservation | ✅ | `build_segmented_summary()` truncates summaries, preserves all three URLs, and rejects fixed-content overflow so orchestrator records `PARTIAL` instead of crashing. |

## Verification

Final commands run after the latest review fixes:

- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅
- `uv run mypy --strict src/` ✅
- `uv run pytest -q` ✅ 959 passed
- `uv run mkdocs build --strict` ✅

## Gaps Analysis

No gaps found for FR-008.

## Proposed Actions

No new development tasks or TECH-DEBT items are required for this unit.
