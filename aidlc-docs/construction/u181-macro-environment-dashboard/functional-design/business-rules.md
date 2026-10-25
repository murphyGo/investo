# u181 Business rules

설계 2026-10-12 · 구현 검증 2026-10-25 · 사용자 후속 진행 지시로 설계 채택. 로컬 7/8 완료, 운영 Step8 pending.

- R181.1: macro slots13 은 ust_3m/ust_2y/ust_10y/ust_30y/ust_10y_2y_bp/ust_10y_3m_bp/sofr/effr/sofr_effr_bp/usd_krw_h10/cpi_sa_index/core_cpi_sa_index/unemployment_rate 다. 공개 metric recipe 목록은 새 adapter registry 가 아니다.
- R181.2: spread 는 같은 date+같은 source family·단위로 계산. percent point 차×100 을 bp 로 표시하며 원 source spread metadata 와 맞지 않으면 invalid_value 다.
- R181.3: Treasury4 만기 점만 표시하고 전체 yield curve 나 실시간 금리를 약속하지 않는다. negative rate 자체는 invalid 가 아니다.
- R181.4: CPI/Core CPI>0 index; 실업률 0..100 percent; FX finite>0 KRW/USD. index 를 YoY percent 로 변환하지 않는다. source period/revision/seasonal adjustment 를 recipe definition 에 넣는다.
- R181.5: DEXKOUS source_date 를 기준으로 표시하고 target_date/NYSE close/KRX close 로 덮지 않는다. daily 관측/weekly 공표와 월요일휴일이월을 freshness 에 반영하고 달러 지수와 원달러를 구별한다.
- R181.6: headline current card 의 일부 실패는 해당 card 의 unavailable/last-good 상태로 표시한다. snapshot 전체의 날짜 하나로 월간/일별 값을 오늘 자료처럼 표시하지 않는다.
- R181.7: 5 일 비교는 source 영업일 정책의 exact 날짜 쌍에 한정. source/methodology/revision 차이와 missing baseline 에 변화값 0. current-only 첫 발행도 유효하다.
- R181.8: hub/nav 는 구현되어 공개된 모듈만 링크한다. sectors/index.md 영구 경로와 기존 메뉴·search/theme 동작을 보존한다.

[공통 C1–C7](../../public-insights-20261012/contracts.md)이 숫자·시간·권리·상태·보관·게시의 기본 계약이다. 여기서 정의한 source/metric/event 의미를 다른 module 에서 재정의하지 않는다. 충돌하는 raw metadata 는 검증 실패이며 임의 보정을 하지 않는다.
