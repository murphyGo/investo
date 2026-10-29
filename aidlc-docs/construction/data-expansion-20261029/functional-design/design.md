# u43 / u66 추가 데이터 도입 설계

2026-10-29 KST. 사용자 승인: “1~2순위ㄷ 도입해보자”. 2026-10-28 연구의 KRX 월물 옵션 만기와 Coin Metrics Community BTC/ETH 거래소 흐름을 구현한다. 기존 u43 일정과 u66 deterministic crypto 지표 및 native v3 시장 기준 자료 패널에 연결한다. u182/u183 별도 인사이트 dashboard/history는 확장하지 않는다.

## 동작 및 수용 조건

- `krx-option-expiry`: 국내/calendar, KOSPI 200 월물 옵션 최종거래일만 생성. 둘째 목요일, 휴장 시 직전 거래일, 15:20 KST. 최종결제일/위클리/전체 파생상품 만기로 확대하지 않는다. 계산 일정임을 title/summary에 표기. 30일 전망, 2026년만 지원, 연말에는 검증된 2026년 일정만 표시하고 유효기간을 보존한다. 미지원 연도 또는 연도 경계를 넘어 검증된 일정이 하나도 없으면 명시적 SourceFetchError. 규칙·달력 버전과 공식 URL을 보존. 원문을 매일 수집/재게시하지 않는다.
- 2026 달력의 May 1, July 17 누락을 보정한다. KRX 휴장 규칙(공휴일·근로자의 날·연말), 한국은행 2026 공식 공휴일 목록을 대조한다. 임시휴장·특례는 운영자가 캘린더 버전을 갱신해야 한다. 미검증 연도를 정상 빈 일정으로 취급하지 않는다.
- `coinmetrics-exchange-flows`: crypto/macro, 무키 Community API 한 번의 batch GET(재시도 별도), BTC/ETH native 일별 FlowInExNtv/FlowOutExNtv. 최근 완료된 UTC 일자 최대 3일, 최대 6행, 자산별 최신 유효 1행만 출력. 누락/NaN/무한대/음수/잘못된 상태/충돌 중복은 제외, 결측을 0으로 대체하지 않음. 모든 행이 불량이면 실패, 정상 empty는 빈 결과. 예상 밖 pagination/schema는 실패하고 외부 next URL은 따라가지 않음.
- 같은 자산·관측일 유입−유출을 정확한 Decimal로 계산. 날짜 시작은 발표시각이 아님. 유입/유출별 flash/reviewed/revised와 status-time, 실제 수집시각을 보존. 기준시각은 현재·window end·명시된 evidence cutoff 중 가장 이른 값. 일자 종료 및 두 status-time 모두 그 이전이어야 한다. 과거 재생에서는 나중에 수정된 값을 당시에 알았던 값으로 사용하지 않음.
- 기존 crypto 지표 표에 BTC/ETH 일별 순유입·관측일·상태를 표시. 청산은 계속 미수집. 지표 제목의 일괄 UTC 24h 스냅샷 표기를 제거하여 일별 지연값과 혼동하지 않음. 순유입 양수=유입 초과, 음수=유출 초과. 추적 거래소 주소 범위이며 거래소 간 이체 제외, 체결량/전체 시장 아님을 명시.
- 최종 publisher는 LLM이 쓴 같은 지표 블록을 검증된 렌더로 교체하여 숫자/잠정/출처/라이선스가 보존되게 한다. 이미 저장한 과거 브리핑은 덮어쓰지 않으며 새 발행은 해당 수집시점 상태를 기록한다.

## 공식 근거

- [KRX 상품명세](https://global.krx.co.kr/contents/GLB/02/0201/0201040202/GLB0201040202.jsp), [안내서 인쇄58쪽](https://global.krx.co.kr/contents/GLB/02/0201/0201041003/Guide_to_Night_Session_in_KRX_Derivatives_Market.pdf): 월물 둘째 목요일, 휴장 앞당김. 규정 우선.
- [KRX 휴장 규칙](https://global.krx.co.kr/contents/GLB/06/0602/0602020204/GLB0602020204T1.jsp), [한국은행 2026 공휴일](https://www.bok.or.kr/eng/main/contents.do?menuNo=400373): 근로자의 날/제헌절 포함. 은행 목록만을 거래소 달력이라고 부르지 않는다.
- [Coin Metrics API](https://docs.coinmetrics.io/api/v4/), [Community catalog](https://community-api.coinmetrics.io/v4/catalog/asset-metrics), [공식 데이터/CC BY-NC 4.0](https://github.com/coinmetrics/data). 직접 HTTP 확인/해시: 전일 연구 probe-summary.json.

## 코드 리뷰로 보완한 통합 계약

- 운영 변수 INVESTO_EVENT_BRIEFING_MODE=active를 read-only 조회로 확인. 2026-10-30 설치된 워크플로까지 확인한 실제 운영은 schema 2 / role_v1이다. 별도로 native v3 호환을 위해 MarketReferencePanel에 타입이 있는 순유입/계산 일정을 추가하고 최종 발행기는 수집 입력에서만 해당 패널을 재구성한다. 생성 모델이 넣은 값은 대체한다.
- v3 CollectStage에도 v2와 같은 evidence_received_at을 전달하여 실행 시작 기준시각과 adapter as_of가 일치하도록 한다.
- 가격 검증기는 수집 입력에서 재구성한 정확한 순유입 행만 USD 가격 검사에서 제외한다. 변조 행이나 별도 가격 문장은 계속 검사한다.
