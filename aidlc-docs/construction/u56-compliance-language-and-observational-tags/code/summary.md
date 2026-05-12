# u56 Compliance Language + Observational Tags — Code Generation Summary

**Date**: 2026-05-13
**Unit**: u56 compliance-language-and-observational-tags
**Status**: Complete (9/9 steps, 70+ checkboxes, all ACs)
**FR**: FR-012

## Goal

Prevent briefings/Telegram from drifting into investment-advice wording; absorb 평가 Finding #5 (crypto 면책 — 가상자산이용자보호법) + Finding #12 (한국 retail 톤). Footer disclaimer remains the gate; first-viewport short disclaimer is additive.

## Quality Gate

| Gate | Result |
|------|--------|
| `ruff check .` | passed |
| `ruff format --check` | 312 files clean |
| `mypy --strict src/` | 121 files, 0 issues |
| `pytest -q` | **2206 passed** (2089 → +117, plan est. +52-68) |
| `mkdocs build --strict` | exit 0 |

## Key Deliverables

- **`models/compliance_phrases.py`** — single-source catalogue: 16 P0 action verbs (대칭 buy/sell) + 7 certainty + 2 quantified-outcome regex + 5 crypto-only (가상자산법 §10) + 2 P1 + closed causation regex.
- **`publisher/compliance_language.py`** — `scan_compliance(markdown, segment) -> ComplianceReport`; `ComplianceLanguageError(PublisherError)` blocks publish. 6-token-window context classifier demotes `진입/청산/편입` symmetric matches + `목표가` left-only quotative (`증권사 X ... 목표가`). Block masking strips code fences, table rows, disclaimer footer.
- **`DISCLAIMER_CRYPTO`** — 가상자산이용자보호법 §10·§19 reference + 24h/비제도권/변동성/원금손실. `COMPLIANCE_CUTOFF_DATE=2026-05-13`.
- **Segment-aware disclaimer**: `append_disclaimer(md, segment)` + `verify_disclaimer(md, segment, *, legacy)` — default args make 1-arg call sites byte-compat.
- **Additive first-viewport gate**: `verify_short_disclaimer_first_viewport` runs alongside footer gate. Three composing gates at publish boundary: scan_compliance → verify_disclaimer → verify_short_disclaimer_first_viewport.
- **ActionTag 5→4 migration**: `[관망][변동성↑][강세][약세][혼조]` → `[상승 관찰][하락 관찰][혼재][변동성 확대]` + `[데이터부족]`. `LEGACY_TAG_ALIASES` normalises legacy LLM emissions. **No archive re-render** — forecast_log + monthly_retrospective parsers normalise on read.
- **Retail tone caps** (Finding #12, WARN-only):
  - `check_sentence_ending_diversity` — dominant 종결 어미 >60% → `tone.sentence_ending_dominance`
  - `check_filler_phrase_density` — `여부/전망/우려/가능성/작용` >8.0/1000 chars → `tone.filler_density`

## Disclaimer Invariant (regression-pinned)

- 1-arg `verify_disclaimer(briefing_md)` byte-equal to pre-u56 behaviour (equity-footer substring check).
- Footer missing → `verify_disclaimer` fail (existing pin).
- First-viewport disclaimer missing → new gate fail.
- crypto segment + us-equity footer → `verify_disclaimer(segment="crypto")` fail.

## Files

**New src (2)**:
- `src/investo/models/compliance_phrases.py`
- `src/investo/publisher/compliance_language.py`

**Modified src (14)**: `briefing/{action_tag,accuracy,date_corruption,disclaimer,forecast_log,monthly_retrospective,pipeline,prompts}.py`, `orchestrator/pipeline.py`, `publisher/{__init__,reader_format,verifier,weekly_digest,writer}.py`.

**New tests (7 files, +94)**:
- `tests/unit/briefing/test_prompts_p0_forbid.py` (8)
- `tests/unit/publisher/test_compliance_language.py` (36)
- `tests/unit/publisher/test_first_viewport_disclaimer.py` (12)
- `tests/unit/publisher/test_verifier_segment_aware.py` (16)
- `tests/unit/publisher/test_retail_tone.py` (8)
- `tests/unit/notifier/test_summary_action_tag.py` (6)
- `tests/integration/test_compliance_pipeline.py` (8)

**Docs**: FR-012 in `docs/requirements.md`; u56 row updated in `aidlc-docs/aidlc-state.md`; audit entry appended.

## TECH-DEBT Candidates

- **D56-A** `DISCLAIMER_CRYPTO` 변호사 정식 검토 (가상자산법 §10/§19 reference 정확도).
- **D56-B** 종결 어미 분류기 KoNLPy/Mecab 형태소화 (현재 regex; `필요하다`의 `~다` compound false-positive 가능).
- **D56-C** P0 phrase 정기 갱신 cadence (분기/반기) — 자본시장법·가상자산법 개정 추적.
- **D56-D** Quantified outcome regex 영문 case (`30% return expected`, `2x gain`) — MVP는 한국어만.
