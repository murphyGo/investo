# u181 매크로 환경판 — Business logic

설계 2026-10-12 · 구현 검증 2026-10-25 · 사용자 후속 진행 지시로 설계 채택. 로컬 7/8 완료, 운영 Step8 pending.

## 목표와 사용자

만기별 미 국채금리, 기준금리, 원달러 H.10 관측, 월간 CPI 지수·실업률을 기준일/단위와 함께 비교할 수 있는 공개 환경판을 만든다.

사용자: P1 운영자/개인 투자자, P2 인증 없는 공개 독자. US-011 와 FR-027/026; 기존 FR-003/011/014/015/018 를 구현할 후속 기준이다. 기술 단계와 public 데이터/화면/운영 수용은 구별한다.

## 책임과 선행 조건

u180 코드·공통 source/time/permission/publication 계약. u176/u178 사이트 토큰·탐색·가독성 재사용. v3 native document 완료는 hard dependency 가 아니다.

구현 범위: 기존 sources/treasury_rates.py/nyfed_reference_rates.py/bls_macro_actuals.py/fred_fx_close.py 의 opt-in envelope; models/insights.py 의 macro13 metric definitions; orchestrator/insights_projection.py 의 metric recipe binding; publisher/insights/macro.py; site_docs/insights/index.md 및 macro/index.md·_data/macro; insights-scoped CSS/JS·mkdocs nav; source qualification entries 와 tests.

제외 범위: FRED 제 3 자 series 확대, CPI YoY·NFP 증감의 새 산식, VIX/MOVE/credit spreads, 금리 인하 확률·합성 위험점수, 새 소스 호출, 정확한 원달러 종가 주장, 매크로→섹터 인과 자동 추론.

## 데이터 흐름과 행동


1. Treasury 의 같은 date 3M/2Y/10Y/30Y 만 읽고 두 spread 를 검산한다. 네 점을 원래 만기로 표시한다.
2. NY Fed SOFR/EFFR 의 각 effective_date 를 보존한다. 두 값의 유효일이 같을 때만 SOFR−EFFR bp 를 만든다. 각 카드의 latest 날짜가 서로 다를 수 있다.
3. BLS 의 정확한 CUSR0000SA0/CUSR0000SA0L1E SA index 와 LNS14000000 percent 를 읽는다. 최신 대상 월을 표시하고 FRED 의 다른 정의/조정치로 조용히 대체하지 않는다.
4. FRED DEXKOUS 값은 KRW per USD H.10 원천 관측이다. 현재 adapter는 raw_metadata의 source_date를 보존하고 published_at을 NY 12:00으로 구성한다. 이 관측 convention을 실제 H.10 주간 공표시각으로 표시하지 않는다. 새 카드에는 source_date/정의와 C2 date precision을 소비하며 FRED 키가 없으면 해당 카드만 unavailable로 격리한다.
5. 모든 값의 qualification·시점·단위를 u180 으로 검증한다. 비교 가능한 5 거래일 이력이 있으면 exact 두 시점의 변화값을 제공하고 부족하면 current 값만 보여준다.
6. 첫 화면 4 카드(2Y/10Y/10Y−2Y/원달러), 4 개 만기 비교, 단기자금시장, 최신물가·고용, 관련시황·출처 순서로 renderer 에 전달한다. 해당 날짜 시황이 없으면 다른 날짜를 같은 날짜라고 표시하지 않는다.


## 실패와 대체

[공통 계약](../../public-insights-20261012/contracts.md)의 C2–C7 을 적용한다. available 숫자·일정에 없는 time/period/단위/원천을 발명하지 않는다. 해당 source 실패·미확인·key 없음은 해당 card/module 의 명시된 상태와 유효 last-good 로 표현하며 정상 sibling 을 유지한다. 권리가 미확인/철회된 숫자는 current/history 에 포함하지 않는다. LLM text 또는 다른 source 의 유사 제목으로 채우지 않는다.

## 수용 시나리오

[시나리오 목록](../../public-insights-20261012/acceptance-scenarios.md)과 [실행 계획](../../plans/u181-macro-environment-dashboard-code-generation-plan.md)의 numbered AC 를 함께 따른다. 현재 문서 작성은 제품 test/pass 결과가 아니다.
