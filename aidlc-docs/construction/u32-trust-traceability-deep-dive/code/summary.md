# u32 Trust Traceability Deep-Dive — Code Generation Summary

**Date**: 2026-05-09
**Unit**: u32 trust-traceability-deep-dive
**Status**: ✅ Complete (5/5 steps)

---

## Goal

Give the critical-analyst persona day-by-day verification primitives: source-tier metadata, Stage 3 numeric self-check, traceability footer, hashed signatures, and an automated daily evaluation harness. Persona evaluation 2026-05-07 (#3, wish-list).

## Steps

### Step 1 — Source tier metadata
- New `models.SourceTier = Literal["S", "A", "B", "C"]` plus `SourceOutcome.tier: SourceTier = "B"`.
- New module `sources/tiers.py` with `ADAPTER_TIERS` registry mapping every registered adapter name to a tier (S = regulatory/exchange/sovereign; A = first-party/official; B = aggregator/news; C reserved). `adapter_tier(name)` returns the tier with a warned fallback to `"B"` for unregistered names.
- Aggregator stamps each `SourceOutcome` with `tier=adapter_tier(...)` at collection time.
- `SegmentCoverage.tier_mix_label` renders a deterministic `S=2 / A=1 / B=4` style label from the per-segment ok outcomes; `_render_coverage_badge` adds a "소스 등급 분포" line when the label is non-empty.
- GHA Step Summary source table grows a "Tier" column.

### Step 2 — Stage 3 numeric self-check
- New module `briefing/numeric_self_check.py`:
  - `extract_flaggable_numbers(text)` returns the deterministic ordered tuple of decimal-, separator-, or unit-bearing numeric tokens, plus integers with ≥4 digits. Bare 1-3-digit integers and lone years are intentionally ignored to keep the false-positive rate low.
  - `find_unverified(stage2_text, candidates)` builds a haystack of numeric substrings present in any candidate's title / summary / raw_metadata and returns the tokens that are *not* substrings of the haystack (with thousands separators collapsed). Empty tuple → numerically verified end-to-end.
  - `render_warning_line(unverified)` emits the brief-header callout `> **수치 검증 경고**: 입력에서 확인되지 않은 수치 — ... 외` (capped at 5 tokens).
- `_enhance_reader_experience` accepts `candidates: Sequence[NormalizedItem] | None`; when supplied, it computes `find_unverified` over the body markdown and inserts the warning line into the header.
- Both call-sites (data-limited boilerplate path and the LLM-output path) thread `candidates=`.

### Step 3 — Traceability footer + hashed signatures
- New module `briefing/trace_footer.py`:
  - `compute_input_hash(items)` — sha256 over a deterministic JSON serialisation of the Stage 1 candidate items (title / summary / published_at / category / sorted raw_metadata). 12-char hex prefix.
  - `compute_stage1_hash(classification_dict)` — sha256 over `json.dumps(..., sort_keys=True)` of the parsed `ClassificationResult.model_dump()`. 12-char hex prefix.
  - `compute_stage2_hash(stage2_text)` — sha256 over the raw Stage 2 body markdown. 12-char hex prefix.
  - `render_traceability_footer(items, classification, stage2_text)` returns a `<details>` block with the three hashes plus a `| 항목 ID | 소스 | 카테고리 | 섹션 | 제목 |` table listing every published candidate. Long titles truncated at 60 chars with a trailing ellipsis. Pipe characters in titles are stripped to avoid breaking the table layout.
- `generate_briefing` appends the rendered footer to `enhanced_markdown` just before the disclaimer is added.

### Step 4 — Evaluation harness + quality page
- New module `briefing/quality_eval.py`:
  - `QualityKPIs` frozen dataclass with three rate properties.
  - `compute_quality_kpis(today, *, coverage_path, archive_root, window_days=7)` reads the coverage time series, walks the archive directory for the trailing window, and computes:
    - **Source liveness rate** — runs without any failed source / total runs.
    - **Figures presence rate** — non-data-limited briefings carrying ≥1 flaggable numeric token / non-data-limited briefings.
    - **Fallback ratio** — data-limited briefings / total briefings (data-limited detected via the `데이터 부족 안내` marker).
  - `render_quality_page(kpis)` produces the `site_docs/quality.md` body (Korean Markdown table). Empty-data branch emits an explicit placeholder.
- New `publisher/site_index.update_quality_page(target_date, *, coverage_path, archive_root, quality_page_path=None)` writes the body atomically. Default path resolved at call time so test monkeypatch reaches it.
- Orchestrator `_stage_publish_segments` snapshots the quality page, regenerates it via `update_quality_page`, and appends the path to `index_paths` so it is committed alongside the briefing. Coverage path comes from `source_health.resolve_coverage_path()` (u31).
- mkdocs nav adds "데이터 품질: quality.md"; stub `site_docs/quality.md` ships so the first build under `--strict` passes.

### Step 5 — Verification
Full quality gate:
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ (218 files)
- `uv run mypy --strict src/` ✅ (87 source files)
- `uv run pytest -q` ✅ (1450 passed)
- `uv run mkdocs build --strict` ✅

## New / Modified Files

### New source
- `src/investo/sources/tiers.py`
- `src/investo/briefing/numeric_self_check.py`
- `src/investo/briefing/trace_footer.py`
- `src/investo/briefing/quality_eval.py`

### New tests
- `tests/unit/sources/test_tiers.py` (7)
- `tests/unit/briefing/test_numeric_self_check.py` (9)
- `tests/unit/briefing/test_trace_footer.py` (8)
- `tests/unit/briefing/test_quality_eval.py` (7)

### Modified source
- `src/investo/models/coverage.py` — `SourceTier` Literal + `SourceOutcome.tier` field; tier-aware factory kwargs.
- `src/investo/models/__init__.py` — re-export `SourceTier`.
- `src/investo/sources/aggregator.py` — stamp tier on each outcome.
- `src/investo/briefing/segments.py` — `SegmentCoverage.tier_mix_label` property.
- `src/investo/briefing/pipeline.py` — `_enhance_reader_experience(candidates=)` for numeric self-check; trace footer appended just before disclaimer.
- `src/investo/__main__.py` — Step Summary source table grows the Tier column.
- `src/investo/publisher/site_index.py` — `QUALITY_PAGE_PATH` + `update_quality_page`.
- `src/investo/orchestrator/pipeline.py` — quality page write + snapshot.
- `mkdocs.yml` — nav entry for `quality.md`.

### Modified tests
- `tests/unit/models/test_init.py` — adds `SourceTier` to the public-name set.
- `tests/unit/orchestrator/conftest.py` — autouse fixture also redirects `QUALITY_PAGE_PATH` to `tmp_path`.

### New site assets
- `site_docs/quality.md` — bootstrap stub so first `mkdocs build --strict` passes; orchestrator overwrites on every successful publish.

## Test Delta

- 1419 → 1450 (+31 tests).

## TECH-DEBT

- None new.
- Operator-alert escalation on numeric mismatch is deferred (brief-header warning is enough for now); the orchestrator-side hook can land alongside u32 follow-up work without regressing the trust contract today.

## Source

Persona evaluation 2026-05-07: persona #3 (wish-list).
