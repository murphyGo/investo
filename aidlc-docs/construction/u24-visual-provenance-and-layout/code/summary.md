# Code Summary: u24 visual-provenance-and-layout

**Date**: 2026-05-07

## Completed

- Added `VisualProvenanceManifest` (frozen + slots, `extra="forbid"`, `source_type: Literal["generated_svg", "external_image", "ai_generated"]`) plus `build_generated_svg_provenance` / `build_ai_provenance` / `build_external_provenance` builders in a new `src/investo/visuals/provenance.py`.
- Wrote provenance sidecars as `<asset>.json` next to each archived SVG via atomic `.tmp` + `os.replace`, ensuring partially written manifests cannot leak into the publish step.
- Centralised user-/operator-derived field sanitization on `VisualProvenanceManifest` through `sanitize_provenance_text`, which delegates to u22's `sanitize_source_error_message`. The M2 fix promoted the validator to tuple form (`field_validator("source_attribution", "generator", "version")`), closing a partial-coverage gap where `generator` / `version` previously bypassed the chokepoint.
- Rendered concise Korean captions under each segmented briefing image (`Investo가 자동 생성한 데이터 카드`, `AI 생성 이미지`, `외부 이미지 — 출처: …`) via `_provenance_caption_for` in `src/investo/visuals/assets.py`.
- Implemented `_reposition_visual_links`: hero priority `external_image` > `ai_generated` > data-confidence; non-hero cards reinserted after their related H2 anchors (`① 요약`, `⑤ 주요 종목`, `⑥ 오늘의 관전 포인트`); the layout is idempotent on re-run.
- Added dimension validation: SVG via `defusedxml.ElementTree`, PNG via IHDR, JPEG via SOFn marker bytes; valid range `[100, 2000]` per side. Failures raise `VisualAssetError` and are surfaced through the orchestrator's existing PARTIAL/FAIL visual-failure path.
- Wired the `external_image` provenance source type as **contract-only** under the existing `EXTERNAL_IMAGE_SCRAPING_ENABLED=False` gate so future opt-in flows have a typed home without enabling external HTTP today.
- Applied M1 (removed unused `asset_path` parameter from `build_generated_svg_provenance`) pre-merge. M3 / M4 deferred to TECH-DEBT (DEBT-040 / DEBT-041).

## Files Changed

- `src/investo/visuals/provenance.py` (new)
- `src/investo/visuals/assets.py`
- `src/investo/visuals/__init__.py`
- `tests/unit/visuals/test_provenance.py` (new — 10 tests)
- `tests/unit/visuals/_image_bytes.py` (new — shared PNG/JPEG/SVG byte helper)
- `tests/unit/visuals/test_assets.py` (+6 tests)
- `aidlc-docs/construction/plans/u24-visual-provenance-and-layout-code-generation-plan.md`
- `aidlc-docs/aidlc-state.md`
- `docs/cross-checks/2026-05-07-u24-visual-provenance-and-layout.md`
- `docs/TECH-DEBT.md` (DEBT-040..DEBT-043 added)

## Linked Requirements / FRs / NFRs / ACs

- **FR-002** — segmented briefing markdown carries Korean provenance captions under each image link.
- **FR-003** — sidecar manifests + hero/non-hero layout reposition reduce first-viewport visual crowding while preserving the relative-link archive contract.
- **FR-004** — Telegram payload size and channel separation are unchanged (visual changes are publish-side only).
- **FR-008** — provenance + layout run independently per `domestic-equity` / `us-equity` / `crypto` segment; cross-segment provenance leakage is impossible by construction.
- **NFR-002** — no paid APIs introduced; `external_image` source type is contract-only under `EXTERNAL_IMAGE_SCRAPING_ENABLED=False`.
- **NFR-003** — corrupt / dimension-invalid assets raise `VisualAssetError` and degrade through the existing visual-failure → text-only / PARTIAL fallback.
- **NFR-004** — `verify_disclaimer` remains the publish-time gate; provenance / caption / layout all run before publish.
- **NFR-006** — +16 targeted tests (1075 → 1091); full suite green.
- **NFR-007 (R8 / R13)** — `sanitize_provenance_text` is the single chokepoint for every user-/operator-derived field on `VisualProvenanceManifest`; tests pin bot-token / chat-id / high-entropy redaction across `source_attribution`, `generator`, and `version`.

## Architecture Summary

```
visuals/
  policy.py          # EXTERNAL_IMAGE_SCRAPING_ENABLED gate (unchanged)
  provenance.py      # NEW - VisualProvenanceManifest + builders + sanitize_provenance_text
                     #       + write_provenance_sidecar (.tmp + os.replace)
  assets.py          # prepare_segment_visual_assets(...)
                     #   - builds provenance manifests per asset
                     #   - _reposition_visual_links(hero priority + per-anchor non-hero)
                     #   - _provenance_caption_for(source_type -> Korean caption)
                     #   - dimension validation (SVG defusedxml / PNG IHDR / JPEG SOFn)
  __init__.py        # re-exports
```

The provenance module is a single chokepoint: `build_*_provenance` builders are the only way the rest of the codebase constructs `VisualProvenanceManifest`, and the model's `field_validator` over `("source_attribution", "generator", "version")` enforces sanitization regardless of which builder is called. The orchestrator and publisher layers are not touched — u24's surface is contained inside `visuals/`.

## QA Outcome

- Verdict: APPROVE_AFTER_FIXES.
- M1 (unused parameter) and M2 (single sanitize chokepoint via tuple-form `field_validator`) applied pre-merge.
- M3 deferred -> DEBT-040 (Medium) — layout reposition ordering at shared anchors.
- M4 deferred -> DEBT-041 (Medium) — corrupt-sidecar `ValueError` swallowed by caption rendering when `prepare_segment_visual_assets` is bypassed.
- Cross-cutting policy unification -> DEBT-042 (Medium); external builder bypass risk -> DEBT-043 (Low).
- Cross-check: `docs/cross-checks/2026-05-07-u24-visual-provenance-and-layout.md`.

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .` (169 files)
- `uv run mypy --strict src/` (65 source files)
- `uv run pytest -q` (1091 passed; 1075 → 1091, +16 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u20-u24 follow-up wave.
