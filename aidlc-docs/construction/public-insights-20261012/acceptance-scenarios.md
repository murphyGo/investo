# 실행 시 확인할 수용 시나리오

아래는 시험 설계이며 이번 문서 작업에서 제품 테스트를 실행했다는 기록이 아니다. 출처 fixture 는 live recording 과 합성 domain fixture 를 구별하고 private/licensed recording 을 공개 fixture 로 복사하지 않는다.

| ID | 입력/상황 | 기대 결과 | owner |
| --- | --- | --- | --- |
| S01 | mode off 와 기존 item/clock/default window | 기존 HTTP/serialized input/output bytes 와 stage status 동일 | u180 |
| S02 | shadow 에서 모든 source envelopes 가용 | private bounded 결과만 생성, public/git/Pages/history/Telegram write0 | u180 |
| S03 | collection ok, macro 정상, 이후 LLM generation 실패 | macro remote-confirmed 유지, 시황 실패와 독립된 결과, 추가 fetch/LLM0 | u180/u181 |
| S04 | 정상 collection 의 active news window 경로 | 동일 insights handoff, cursor/event baseline 및 기존 input bytes 보존 | u180 |
| S05 | source envelope 소유자/metric/unit/time 불일치, NaN, bool | 해당 observation 차단; title/prose 복구 0 | u180 |
| S06 | rights missing/revoked, display 허용·Git 이력 불허, Git 허용·분석 이력 불허 | 미확인/철회/Git 불허 숫자 공개0; 분석 이력 불허는 current만 제공 | u180 |
| S07 | remote push unknown/CAS conflict/cancellation | 성공·이력 진전 0, verified baseline 유지, 관련 없는 metadata 보존 | u180 |
| S08 | 첫 source zero 와 last-good 이후 실패 | 첫 값 없음 표시; last-good 당시 날짜+실패 상태, missing 을 0 으로 바꾸지 않음 | u180 |
| S09 | NY Fed 와 Treasury 의 최신 유효일이 다름 | 각 카드 날짜 분리, 다른 source/date 의 spread 계산 0 | u181 |
| S10 | 10Y4.30%, 2Y4.10%의 같은 날짜 synthetic fixture | 20bp; 임의 실측 금융 값으로 표시하지 않음 | u181 |
| S11 | CPI index300, UNRATE4.0% | CPI 지수 300 와 실업률 4.0%; CPI YoY300% 생성 0 | u181 |
| S12 | DEXKOUS source date 와 pipeline target date 다름 | H.10 원천 관측일 표시, 한국 거래소 종가/달러 지수 표기 0 | u181 |
| S13 | FRED/auction scheduled_at UTC00:00 synthetic 값 | source local date+시간 미정, KST09:00/정확 countdown0 | u182 |
| S14 | ET08:30 단일 확인 시각, DST 전후 날짜 | 공식 timezone 변환으로 KST21:30/22:30 구별 | u182 |
| S15 | 2 일 FOMC 회의와 별도 statement/minutes | 회의 시작/종료 유지, 첫날을 결정 발표로 표시 0, 종류별 dedupe | u182 |
| S16 | 일정 종료, actual 근거 없음 | 기간 경과/결과 미확인, 발표 완료/consensus/surprise0 | u182 |
| S17 | BEA+FRED 같은 release/date, 서로 다른 source time | conservative canonical family key, same event ref 병합 또는 conflict 표시 | u182 |
| S18 | Bybit→OKX 또는 BTCUSDT→BTC-USD-SWAP 변경 | provider/instrument 표시, OI 이력/7 일변화 연결 0 | u183 |
| S19 | fundingRate fractional0.0001, fundingTime future | 명시된 주기 관찰 0.01%; 24h 평균/연율/settled 추정 0 | u183 |
| S20 | DeFiLlama 공급 또는 TVL7 일 증가 | 공급/TVL 관찰 변화; 투자자 신규 자금 유입 확정 0 | u183 |
| S21 | source_updated_at 없음, collection 구간 알려짐 | source 갱신 시각 미상, 수집 구간 관찰 표시, 24h close 발명 0 | u183 |
| S22 | 숫자 20 종 정상, 하나 failed, 하나 skipped | 모듈 부분 상태+가용 카드 유지, source truth 구별 | u180/u183 |
| S23 | history 가 D/D−7 또는 5 거래일 정확 날짜를 누락 | history_insufficient, carry-forward/근처날 대체 0 | u180/u181/u183 |
| S24 | fixture maximum 및 payload over limit | 지정 자원 상한; 초과 module 보존/억제, silent healthy truncation0 | u180 |
| S25 | 2027 calendar 미지원·발표 연기·미국 휴일 | unknown/delayed 정책, NYSE calendar 오용 0 | u180/u181 |
| S26 | 실제 빌드 390×844/1440×900, 두 테마, 키보드, 200% 확대, noJS | 핵심 값·시점·출처 접근, 전역 overflow/hidden meaning0 | u181/u182/u183 |
| S27 | dashboard push 정상, 이후 시황 실패 또는 Pages deploy 실패 | separate Pages-required 신호 보존, remote data 와 live 화면을 구별 | u180 |
| S28 | dry-run/선언된 historical replay 와 active mode | public snapshot/git/history/Pages 변경 0, 현재 crypto 값을 과거 target_date 로 저장 0 | u180 |
| S29 | H.10 목요일 정상 weekly 자료와 월요일 연방휴일 | 마지막 도래 공식 공표의 관측 범위로 freshness, 미공표 현재주 자료 기대 0 | u180/u181 |
| S30 | 2026-07-03 SOFR vs EFFR 공식 공표 예외 | 지표별 publication calendar 구별, 동일 NYSE/연방 table 만으로 판정 0 | u180/u181 |
| S31 | Bybit 경유 OKX 정상값과 standalone OKX 실패, 또는 origin 실패 | collector-origin/producing-source를 분리해 올바른 관찰만 사용, 가짜 ok와 실패 덮기0 | u180/u183 |

운영 수용은 모듈별 exact implementation SHA 에 연결한 5 회 예약 관찰, 실제 URL·관측일·snapshot hash·Pages 여부로 기록한다. 기존 10 날짜 coverage 와 합성 시나리오를 새 5 회 관찰 대신 쓰지 않는다. 5 회가 같은 원천 월간 값이어도 주기 특성상 정상일 수 있지만 actual/값 수정 시험은 별도 fixture 에서 검증한다.
