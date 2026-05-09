# u41 dart-disclosure-adapter — Code stage summary

**Closed**: 2026-05-10
**Status**: Partial (Steps 1-4 + Step 6 quality-gate complete; Step 5 + Step 6 manual deferred)
**Persona**: #5 국내 (P0)

## What landed

- New adapter `src/investo/sources/dart_disclosure.py` (`name="dart-disclosure"`, `category="news"` — see "Category Literal" note below).
- OpenDART list.json endpoint `https://opendart.fss.or.kr/api/list.json` (corrected from the Plan's `fsc.go.kr` typo, verified against live recordings).
- Status-code routing: `000` ok / `013` non-error empty / `010 011 100` terminal / `020 800 900` transient / unknown → terminal.
- Subcategory keyword classifier (`buyback` / `dividend` / `capital_change` / `ownership_change`); reports not matching any keyword (분기보고서, 감사보고서, 약관, 일괄신고, 증권발행실적 등) are dropped.
- KST trading-day window strict R7 enforcement; `published_at` = `rcept_dt` 09:00 KST → UTC.
- Tier registry: `dart-disclosure` → `S` (regulator-of-record, on par with SEC EDGAR).
- Segment routing: `_DOMESTIC_ONLY_SOURCES` membership; us-equity / crypto leak guarded by anti-regression test.
- R13: `OPENDART_API_KEY` fetch-time read; missing → `SourceFetchError(transient=False)` with env-var name (no key value); already enrolled in `_internal/redaction.py::SECRET_ENV_VARS` from a prior session.
- R10: 7 live fixtures recorded against the live OpenDART endpoint with the operator's API key. Fixtures are byte-equal to live responses; the JSON bodies do not echo the `crtfc_key` parameter (it lives in URL query only). `meta.json` sidecar carries `recorded_at`, masked URL templates, and per-fixture rationale.

## What was deferred (out of scope for this session)

- Step 5: `DOMESTIC_DISCLOSURE_QUIET` reason code in `models/coverage.py` + aggregator emit logic. Touches u22 coverage machinery and is best landed as a follow-up unit so the coverage change ships with its own dedicated test surface.
- Step 6 manual: operator-side dry-run with `INVESTO_DRY_RUN=1` is an operator action.

## 4-Category Subcategory Mapping + Live Fixture Distribution

| subcategory | 키워드 | recent_all (5/8) 분포 |
|-------------|--------|----------------------|
| `buyback` | 자기주식, 자사주 | 1 (자기주식처분결정) |
| `dividend` | 현금ㆍ현물배당, 현금배당, 주식배당 | 0 (5/8 데일리 슬라이스에 없음 — 별 fixture 로 보강) |
| `capital_change` | 유상증자, 무상증자, 감자, 전환사채, 신주인수권부사채 | 7 |
| `ownership_change` | 최대주주변경, 주식등의대량보유, 특정증권 | 32 |
| (드롭) | 분기보고서, 감사보고서, 증권발행실적, 약관, 일괄신고 등 | ~60 |

## R10 Fixture Recording Session

Location: `tests/unit/sources/fixtures/api/dart-disclosure/`

| fixture | bytes | status | list_len | 녹화 query |
|---------|-------|--------|----------|-----------|
| `recent_all.json` | 24539 | 000 | 100 | `bgn_de=20260501&end_de=20260508` |
| `treasury_stock.json` | 24552 | 000 | 100 | `bgn_de=20260301&end_de=20260508&pblntf_detail_ty=B001` |
| `dividend.json` | 32279 | 000 | 100 | `bgn_de=20260301&end_de=20260315` |
| `capital.json` | 24380 | 000 | 100 | `bgn_de=20260401&end_de=20260508&pblntf_ty=B` |
| `major_holder.json` | 5006 | 000 | 20 | `bgn_de=20260501&end_de=20260508&pblntf_ty=D` |
| `empty.json` | 65 | 013 | 0 | `bgn_de=20990101&end_de=20990101` |
| `invalid_key.json` | 68 | 010 | 0 | `crtfc_key=invalid&...` |
| `meta.json` | 2802 | n/a | n/a | sidecar — 모든 url_query 에 `crtfc_key=***` 마스킹 |

R13 grep verification: plaintext OPENDART_API_KEY value present in **0 hits** across all fixtures.

## Project rule compliance

- Module boundary: adapter lives in `sources/`; no cross-module import added.
- R8 (no raw stdlib XML): JSON path; not applicable.
- R10 (real fixtures): 7 live recordings; plaintext-key grep returns 0 hits across all fixtures.
- R13 (secret hygiene): API key never echoed in error messages, `raw_metadata`, or fixtures. Sentinel test pins this contract.
- R14 (fair-access UA): OpenDART has no specific UA requirement.
- No paid APIs: OpenDART REST is free with registration. `tests/unit/sources/test_no_paid_apis.py` green.

## Test surface

- **32 new tests** in `tests/unit/sources/test_dart_disclosure.py` — missing-key R13, status code mapping (013/010/020/100/unknown), 4 category fixture replays, window filter, classifier parametrize, class identity, tier registry pin.
- **2 new anti-regression tests** in `tests/unit/briefing/test_segments_exclusivity.py` — dart-disclosure routes to domestic-equity only; even a fabricated `BTC홀딩스` corp name does not trigger crypto routing (source-anchored wins over keyword fallback).
- Plugin-contract bumps: `EXPECTED_ADAPTER_COUNT` 19→20, `EXPECTED_ADAPTER_NAMES` += `"dart-disclosure"`, isolation fixture registers `DartDisclosureAdapter`.

## Quality gate

All 5 green:

| Gate | Result |
|------|--------|
| `ruff check` | passed |
| `ruff format` | applied (2 files reformatted) |
| `mypy --strict src` | 102 source files, no issues |
| `pytest -q` | **1728 passed** in 84.51s |
| `mkdocs build --strict` | built in 0.47s |

## TECH-DEBT candidates surfaced

1. **`models/items.py::Category` Literal extension** — add `"disclosure"`. Adapter currently uses `"news"` + `raw_metadata["subcategory"]` for traceability. Coverage / segment-required-category logic does not see disclosure as a distinct category today.
2. **Plan host typo** — `opendart.fsc.go.kr` → `opendart.fss.or.kr` (planner action: update plan body).
3. **Plan Step 2 spec drift** — Plan said "missing key → empty list, INFO log" but R13 / fred precedent dictates `SourceFetchError(transient=False)`. Plan body needs alignment.
4. **`pblntf_detail_ty` parameter ineffective** — does not actually filter the live response. Future per-category pagination would need to filter post-fetch via `report_nm` keywords (which is what the adapter already does).
5. **Step 5 follow-up unit** — `DOMESTIC_DISCLOSURE_QUIET` reason code lands as a separate unit so the coverage machinery change ships with its own dedicated test surface.

## Out of scope (per plan)

DART 외 다른 한국 공시 소스 (KIND, KRX), 첨부 PDF/문서 다운로드, 공시 본문 파싱, Category enum 확장.
