# u182 Business rules

작성일: 2026-10-12 · u182 · 상태: 2026-10-25 사용자 후속 진행 지시로 설계 채택. 로컬 구현·검증 진행 중이며 운영 활성화는 별도다.

- R182.1: 첫 화면 categories=economic_release/central_bank/treasury_auction, ranges7/30, events≤128. earnings 필터와 미제공 카드로 기능을 약속하지 않는다.
- R182.2: event_key 는 kind+official occurrence identity+source-local start/end date+verified target_period 다. Fed meeting·minutes·statement 는 다른 kind. CUSIP+auction_date+reopening 을 입찰 identity 로 사용하고 CUSIP 없는 입찰은 source-local own key 로 분리한다.
- R182.3: FRED release date+release_id 와 BEA 공식 제목의 reviewed release family map(News/Data 유형만으로 family를 추론하지 않음) 에 의해 동일 family 가 검증된 경우만 병합. title similarity 나 같은 CPI 단어만으로 병합 0. 목표 기간이 원천에 없으면 null 이다.
- R182.4: UTC00:00 synthetic scheduled_at 는 exact time 아님. source local date+timezone 을 보존하고 09:00KST countdown0. exact 시간만 zoneinfo ET→KST.
- R182.5:2 일 range 는 start≤end, 같은 calendar/date basis, 최대 7 일 범위. 일부 days token 가 파싱되지 않으면 range 임의 완성 0.
- R182.6: source 별 collect cap/30 일 lookahead 와 official full calendar 를 구별한다. 선택 128 을 넘으면 먼저 date/kind/source identity 로 deterministic 선택하고 excluded count 를 표기하며 upstream cap 도 제한 상태로 보존한다.
- R182.7: 지나간 schedule 은 snapshot 갱신에서 upcoming 범위 밖으로 제외하거나 진행/기간 경과·결과 미확인으로 표시한다. actual 발표완료/취소를 날짜 경과·목록 누락으로 확정 0.
- R182.8: “왜 확인하나”는 고정 method guide 이며 현재시장 영향·예상 결과·임의 중요도 점수를 생성하지 않는다. official URL 와 출처 시간을 함께 제공한다.

[공통 C1–C7](../../public-insights-20261012/contracts.md)이 숫자·시간·권리·상태·보관·게시의 기본 계약이다. 여기서 정의한 source/metric/event 의미를 다른 module 에서 재정의하지 않는다. 충돌하는 raw metadata 는 검증 실패이며 임의 보정을 하지 않는다.

구현 구체화: 공식 ID가 없는 Fed 일정은 원천 title/time/location/description을 정규화한 source-local hash로 occurrence를 구별한다. 이 구별은 공개 exact time이나 원문 prose 복사가 아니다. 같은 발표자의 같은날 별도 연설이 합쳐지지 않도록 기존 recording 회귀를 둔다.
