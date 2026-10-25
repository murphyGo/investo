# Code Generation Plan: u181-macro-environment-dashboard

설계 2026-10-12 · 구현 검증 2026-10-25 · 사용자 후속 진행 지시로 설계 채택. 로컬 7/8 완료, 운영 Step8 pending.

## 문제와 목표

만기별 미 국채금리, 기준금리, 원달러 H.10 관측, 월간 CPI 지수·실업률을 기준일/단위와 함께 비교할 수 있는 공개 환경판을 만든다.

## Existing coverage / Deduplication

u180 코드·공통 source/time/permission/publication 계약. u176/u178 사이트 토큰·탐색·가독성 재사용. v3 native document 완료는 hard dependency 가 아니다.

[Program 중복 대조](../public-insights-20261012/README.md)와 [source 판정](../public-insights-20261012/source-assessment.md)을 따른다. source 별 defaults/tier/window/segment/registry 는 유지하며 raw numeric/event envelope 만 opt-in 추가한다.

## Scope boundary

기존 sources/treasury_rates.py/nyfed_reference_rates.py/bls_macro_actuals.py/fred_fx_close.py 의 opt-in envelope; models/insights_macro.py 의 macro13 metric definitions; orchestrator/insights_projection.py 의 metric recipe binding; publisher/insights/macro.py; site_docs/insights/index.md 및 macro/index.md·_data/macro; insights-scoped CSS/JS·mkdocs nav; source qualification entries 와 tests.

제외: FRED 제 3 자 series 확대, CPI YoY·NFP 증감의 새 산식, VIX/MOVE/credit spreads, 금리 인하 확률·합성 위험점수, 새 소스 호출, 정확한 원달러 종가 주장, 매크로→섹터 인과 자동 추론.

## Stage decision

- Functional Design: REQUIRED / ADOPTED. 새 public 데이터 의미·시간·상태·독자 workflow 와 cross-module contract 가 있다. [FD](../u181-macro-environment-dashboard/functional-design/business-logic-model.md).
- NFR Requirements: REQUIRED / ADOPTED. source rights/private 경계·신뢰·자원·retention/새화면·runtime 를 구체화한다. [NFR](../u181-macro-environment-dashboard/nfr-requirements/nfr-requirements.md).
- NFR Design: focused design in [shared contracts](../public-insights-20261012/contracts.md), 별도상투적문서 대신 C3–C7 의경계·cap·recovery 로구체화. 사용자 후속 진행 지시로 채택하고 실제 검증을 기록한다.
- Infrastructure Design: SKIP separate stage; u180 의 focused 기존 privatejob/Pages 계약을 재사용하며 새스케줄/환경/secret 은 없다.
- Code Generation: LOCAL VERIFIED7/8. “진행시켜” 지시에 따른 로컬 구현·검증이며 Step8 운영 수용은 대기다. commit/push/activation은 수행하지 않았다.
- Source requirements: 사용자 2026-10-12 지시, US-011; FR-027/026; 기존 FR-003/011/014/015/018; NFR-001~008/R10/R13. 신규공식 source 자격검증이있으면 별도 bounded source plan 에 handoff 한다.

## Fixed contracts

[C1–C7](../public-insights-20261012/contracts.md), [unit rules](../u181-macro-environment-dashboard/functional-design/business-rules.md), [entities](../u181-macro-environment-dashboard/functional-design/domain-entities.md)가 normative 초안이다. 입력/시간/identity/owner/permission/부분상태/파일원격확정순서를구현중임의로바꾸지않는다. DTO/private envelope 와 HTML·JSON·이력·receipt 의 role 을구별한다.

## Implementation steps

- [x] **Step 1** — Treasury/NY Fed/BLS/DEXKOUS 의 source fields·영업일·권리/고지·optional key/fixture 를 source qualification scope 로 고정하고 macro13 recipe 를 선언한다.
- [x] **Step 2** — 기존 응답에서 opt-in envelope 를 만든다. source HTTP/legacy raw_metadata/title/serializer/default bytes 를 보존하고 받은 실제 date·period 만 넣는다.
- [x] **Step 3** — macro typed projection/단위·범위·spread 검산·C4 freshness·고정 source priority 를 구현한다. FRED 대체 series 나 prose fallback 을 추가하지 않는다.
- [x] **Step 4** — publisher/insights/macro.py 와 current-only HTML,4point SVG+표 대안, 기본 13slot 상태/출처/고지·관련날짜 시황 링크를 구현한다.
- [x] **Step 5** — u180 의 bounded history 로 exact5 일 비교·30 관측 그래프를 연결하고 결측/정의/revision 변화를 억제한다. 부족한 이력은 그대로 표시한다.
- [x] **Step 6** — u176 토큰을 재사용한 insights scope CSS/JS, 대시보드 hub/nav 와 기존 sectors URL 보존을 구현한다. 두 viewport/테마/noJS/keyboard/200%를 실제 렌더로 확인한다.
- [x] **Step 7** — source/domain/render/integration focused 및 full/static/policy/strict docs 검증, AC 대조와 review 를 완료한다. 코드 완료와 원격 delivery 를 구별한다.
- [ ] **Step 8** — 별도 운영 지시에 따라 macro 만 modules 에 연결하고 exact-SHA5 회 예약관찰·private pin/mode·Pages/live 관측시점/hash 를 기록한다.

## Acceptance criteria

- AC-181.1:13slot 의 현재 값·원 source/series·unit·date/period/SA 가 fixture 와 일치; index 를 상승률/달러지수/종가로 오표시 0.
- AC-181.2: 같은 source/date/unit spread 계산·검산; synthetic4.30−4.10 은 20bp. 다른 기준일의 SOFR/EFFR 비교 0.
- AC-181.3: 월별·일별·원달러 daily 관측/weekly 공표·휴일이월과 조회 시계를 구별하고 optional FRED 실패가 다른 카드를 막지 않음.
- AC-181.4: 현재 값만으로 첫 발행 가능;5 일/30 관측은 exact compatible history 에 한정, missing fill0.
- AC-181.5: hub/메뉴·기존 sectors URL·기존 시황/홈/아카이브 bytes 보존, dead links0.
- AC-181.6: 실제 390×844/1440×900·두 테마·noJS·키보드·확대/출처/단위/면책·페이지 예산 통과.
- AC-181.7: exact implementation source/runtime permission 과 5 회 관측/Pages/live identity 를 각각 기록하고 설계 완료로 활성화를 선언하지 않음.

## Tests / Validation

신규 source/domain/render tests와 재현 가능한 tests/browser/macro_insights.cjs 및 synthetic preview helper를 구현했다.

- `tests/unit/orchestrator/test_macro_insights_projection_u181.py`
- `tests/unit/publisher/test_macro_insights_render_u181.py`
- `tests/unit/sources/test_macro_insights_envelopes_u181.py`
- `tests/browser/macro_insights.cjs` (실제 browser integration)
- `tests/_helpers/macro_insights_preview.py`

기존 publication local-Git 통합과 SiteShell 회귀도 실행했다.

기존 owner 회귀: tests/unit/sources/test_treasury_rates.py; test_nyfed_reference_rates.py; test_bls_macro_actuals.py; test_fred_fx_close.py; tests/unit/publisher/test_site_index.py 및 기존 UI built-HTML tests.

필수 공통 명령은 `uv sync --extra dev --extra docs --extra sector`, scoped+full `uv run python -m pytest`, changed Ruff/format·source mypy, `python scripts/check_no_paid_apis.py`, `python scripts/check_no_anthropic_sdk.py`, 기존 curated/image guards, `uv run mkdocs build --strict`, `python scripts/check_material_theme_contract.py`, `git diff --check`다. workflow 변경이 있는 u180 은 actionlint 와 private runtime template/output negative 검증을 포함한다.

각 source recording/문서조건·합성 domain case·실제 viewport·remote/livePages·5 회 scheduled 를서로구별해기록한다.  원래 설계 검증과 이번 실제 코드/렌더 검증을 구별해 기록한다. [시나리오](../public-insights-20261012/acceptance-scenarios.md)를 AC 에연결한다.

## Implementation evidence — 2026-10-25

전체 collection7046에 대한 full4 shards+수정 shard+최종 scoped를 node별 대조했다. 7045 passed/1 known skipped, 누락0. 최종 scoped112 passed. reviewer 직접29 tests 및 최종 확인한 C/H/M0. Ruff/format763·mypy322·정책/strictMkDocs/Material/Calendar, actual local Chromium16 render와 native theme/keyboard/hub reentry/hash negatives 검증.

Source rights는 정의별 9allow/4blocked이고 actual source/runtime/Pages 수용은 분리한다. Treasury actual response replay typed6개, SOFR200/BLS CPI503, FRED미호출. 최초 menu label 회귀 수정과 Decimal/부모 권한/lazy-load findings 및 최종 증거는 [summary](../u181-macro-environment-dashboard/code/summary.md), [validation](../u181-macro-environment-dashboard/code/validation.json), [cross-check](../../../docs/cross-checks/2026-10-25-u181-macro-environment-dashboard.md)에 있다.

Step8 pending: 최신 main 통합과 정확한 application SHA, source conditions, reviewed private pin/mode, Pages/live 및5회 scheduled. 다음 코드 유닛은 u182이다.
