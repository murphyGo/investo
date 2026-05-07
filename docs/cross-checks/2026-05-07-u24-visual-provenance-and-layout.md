# Cross-Check: u24 visual-provenance-and-layout

**Scope**: u24 visual-provenance-and-layout
**Date**: 2026-05-07
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 4 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **4** | **100%** |

**Overall Compliance**: 100%

---

## Scope Mapping

u24 is a second reader/operator review follow-up that preserves visual asset provenance and reduces first-viewport visual crowding. The unit does not introduce paid sources, accounts, trading, external image scraping, or new external dependencies — `EXTERNAL_IMAGE_SCRAPING_ENABLED` remains `False`, and the external/AI provenance schema is wired only as a contract for future opt-in flows.

**Plan**: `aidlc-docs/construction/plans/u24-visual-provenance-and-layout-code-generation-plan.md`
**Goal**: Preserve visual asset provenance and reduce first-viewport visual crowding in public archive pages.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 Korean briefing comprehension | ✅ | `src/investo/visuals/provenance.py`, `src/investo/visuals/assets.py` (`_provenance_caption_for`), `tests/unit/visuals/test_assets.py` | Generated/AI/external assets carry concise Korean captions (`Investo가 자동 생성한 데이터 카드`, `AI 생성 이미지`, `외부 이미지 — 출처: …`) under each image link. |
| FR-003 static web publishing | ✅ | `src/investo/visuals/assets.py` (`prepare_segment_visual_assets`, `_reposition_visual_links`), `tests/unit/visuals/test_assets.py` | Sidecar manifests are written as `<asset>.json` next to each archived SVG via atomic `.tmp` + `os.replace`; non-hero cards are repositioned closer to the relevant H2 (`① 요약`, `⑤ 주요 종목`, `⑥ 오늘의 관전 포인트`) so the first viewport carries at most one hero visual. |
| FR-004 Telegram summary safety | ✅ | `src/investo/orchestrator/pipeline.py` (visual fallback path unchanged), full gate | u24 only adds publish-side metadata + layout; Telegram payload size and channel separation are unchanged. |
| FR-008 segmented briefing | ✅ | `src/investo/visuals/assets.py` (per-segment provenance + layout), `tests/unit/visuals/test_assets.py` | Each domestic-equity / us-equity / crypto segment generates its own provenance manifests and runs hero/non-hero layout independently; cross-segment leakage of provenance text is impossible by construction (sidecars live next to per-segment assets). |
| NFR-002 cost / no paid APIs | ✅ | `src/investo/visuals/policy.py` (`EXTERNAL_IMAGE_SCRAPING_ENABLED=False`), `src/investo/visuals/provenance.py` | External image fetch is schema-only; the `external_image` provenance source type is gated by the existing policy flag and no external HTTP path is enabled. |
| NFR-003 graceful degradation | ✅ | `src/investo/visuals/assets.py` (dimension validation raises `VisualAssetError`), orchestrator visual-failure fallback | Corrupt / dimension-invalid SVG/PNG/JPEG assets raise `VisualAssetError` before publish; the orchestrator's existing visual-failure branch produces a text-only published briefing and `PARTIAL` result. |
| NFR-004 compliance / disclaimer boundary | ✅ | `src/investo/orchestrator/pipeline.py` (publish ordering unchanged), existing publisher disclaimer guard | Provenance writing and layout repositioning happen before publish; `verify_disclaimer` remains the publish-time gate. |
| NFR-006 testing | ✅ | `tests/unit/visuals/test_provenance.py` (10 tests), `tests/unit/visuals/test_assets.py` (+6 tests), `tests/unit/visuals/_image_bytes.py` | +16 targeted tests (1075 → 1091); full suite green. |
| NFR-007 secret hygiene (R8 / R13) | ✅ | `src/investo/visuals/provenance.py` (`sanitize_provenance_text` chokepoint), `tests/unit/visuals/test_provenance.py` | Every user/operator-derived field on `VisualProvenanceManifest` (`source_attribution`, `generator`, `version`) goes through `sanitize_provenance_text`, which delegates to u22's `sanitize_source_error_message`; bot-token / chat-id / high-entropy shapes are redacted before any sidecar JSON is written. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| External/AI images write provenance metadata without secrets. | ✅ | `src/investo/visuals/provenance.py` (`VisualProvenanceManifest` frozen+slots+`extra="forbid"`, `sanitize_provenance_text` field validator over `source_attribution` / `generator` / `version`, `build_external_provenance` / `build_ai_provenance` / `build_generated_svg_provenance` builders, `write_provenance_sidecar` atomic `.tmp` + `os.replace`); `tests/unit/visuals/test_provenance.py` (bot-token / chat-id / high-entropy redaction, `extra="forbid"` rejection, `source_type` Literal pin, atomic-write behavior). |
| Public markdown shows concise image provenance captions. | ✅ | `src/investo/visuals/assets.py` (`_provenance_caption_for` renders Korean captions for `generated_svg` / `ai_generated` / `external_image`); `tests/unit/visuals/test_assets.py` (caption-rendering assertions for each `source_type`). |
| First viewport prefers one hero visual and moves secondary cards closer to relevant sections. | ✅ | `src/investo/visuals/assets.py` (`_reposition_visual_links` — hero priority `external_image` > `ai_generated` > data-confidence; non-hero cards reinserted after their related H2 anchors `① 요약`, `⑤ 주요 종목`, `⑥ 오늘의 관전 포인트`; idempotent on re-run); `tests/unit/visuals/test_assets.py` (hero precedence + non-hero reposition + idempotence assertions). |
| Corrupt or dimension-invalid images are rejected before publish. | ✅ | `src/investo/visuals/assets.py` (SVG dimensions parsed via `defusedxml`, PNG IHDR, JPEG SOFn; valid range `[100, 2000]` per side; failures raise `VisualAssetError` → orchestrator PARTIAL/FAIL); `tests/unit/visuals/test_assets.py` (corrupt-SVG, oversize-PNG, sub-100px-JPEG, malformed-bytes rejection cases). |

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed (169 files)
- `uv run mypy --strict src/` — passed (65 source files)
- `uv run pytest -q` — 1091 passed (1075 → 1091, +16 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u20-u24 follow-up wave (no new mkdocs nav/content changes in u24)

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u24 introduces no LLM client; provenance + layout are deterministic over already-generated assets. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | New `visuals/provenance.py` lives under the existing `visuals` package; provenance is consumed by `visuals/assets.py` and surfaced in markdown there — sources/briefing/publisher/notifier are not touched. |
| 무료 API only (no paid keys) | ✅ | No new external endpoints. The `external_image` schema is **contract-only**; `EXTERNAL_IMAGE_SCRAPING_ENABLED` remains `False` and no external HTTP call is wired. |
| 면책조항 자동 삽입 | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate; u24 only adds caption text + sidecar JSON + layout reposition upstream of that gate. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u24 does not change notifier targets; public / operator chat separation is preserved. |
| R8 (NormalizedItem `raw_metadata` provenance shape) | ✅ | `sanitize_provenance_text` is the single chokepoint for every user/operator-derived field on `VisualProvenanceManifest`; it delegates to u22's `sanitize_source_error_message` so bot-token / chat-id / high-entropy shapes are redacted before any sidecar JSON is written. |
| R13 (no secret values in logs / errors / raw_metadata / fixtures) | ✅ | Pinned by `tests/unit/visuals/test_provenance.py` over `source_attribution`, `generator`, and `version`; the M2 fix routed `generator` and `version` through the same field-validator tuple as `source_attribution`. |
| `defusedxml` only (no raw stdlib XML) | ✅ | SVG dimension validation uses `defusedxml.ElementTree`; PNG/JPEG dimension validation reads IHDR / SOFn marker bytes directly with no XML path involved. |

---

## QA Verdict

- Verdict: **APPROVE_AFTER_FIXES**
- Pre-merge fixes applied (developer):
  - **M1** — removed unused `asset_path` parameter from `build_generated_svg_provenance` in `src/investo/visuals/provenance.py`.
  - **M2** — promoted `field_validator("source_attribution", "generator", "version")` to a single tuple-form validator that routes all three user-/operator-derived fields through `sanitize_provenance_text`. Closes a partial-coverage gap where `generator` / `version` previously bypassed the chokepoint.
- Deferred to TECH-DEBT (no Critical / High findings outstanding):
  - **M3** → `DEBT-040 (Medium)` — layout reposition ordering when multiple non-hero cards land at the same anchor.
  - **M4** → `DEBT-041 (Medium)` — corrupt manifest sidecar `ValueError` swallowed by `_provenance_caption_for` when `prepare_segment_visual_assets` is bypassed.

---

## TECH-DEBT Surfaced by This Unit

Four new low/medium items registered (`docs/TECH-DEBT.md`):

- **DEBT-040 (Medium)** — Layout reposition ordering: same-anchor non-hero cards are inserted in `asset_paths` reverse order via `lines[insert_at:insert_at]`; the ordering intent is unspecified and untested. Recommend a stable secondary key `(anchor_line, -original_index)` or an explicit docstring documenting the inversion.
- **DEBT-041 (Medium)** — `_provenance_caption_for` swallows the pydantic `ValueError` raised on corrupt sidecars; because validation runs after caption rendering, captionless images can be produced when `prepare_segment_visual_assets` is bypassed. Recommend running validation before caption rendering, or re-raising as `VisualAssetError` from `_provenance_caption_for`.
- **DEBT-042 (Medium)** — Sanitizer policy unification: 3 call sites of `sanitize_source_error_message` (coverage badge, provenance, self) plus `briefing.leak_guard` use distinct policies. A new sanitizer can drift silently. Recommend a single named policy object (extends DEBT-035 / DEBT-036).
- **DEBT-043 (Low)** — External image fetch builder bypass risk: `build_external_provenance` is the only sanitize hook today, but `VisualProvenanceManifest.model_validate({...source_type: "external_image"...})` would skip per-field pre-sanitize. Recommend either a builder-mandate assertion or a runtime check inside the model validator.

---

## Gaps Analysis

No gaps found.

## Proposed Actions

- No requirements/design changes.
- TECH-DEBT updates already registered (DEBT-040..DEBT-043).
- `mkdocs build --strict` to be re-verified once the broader u20-u24 follow-up wave closes.
