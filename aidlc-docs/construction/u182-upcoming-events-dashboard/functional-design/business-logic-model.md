# u182 이번 주 주요 일정 — Business logic

작성일: 2026-10-12 · u182 · 상태: 2026-10-25 사용자 후속 진행 지시로 설계 채택. 로컬 구현·검증 진행 중이며 운영 활성화는 별도다.

## 목표와 사용자

공식 경제지표·중앙은행·국채 입찰의 예정 날짜와 확인된 시각을 7 일 기본/30 일 선택 목록으로 보여주고 원천으로 연결한다.

사용자: P1 운영자/개인 투자자, P2 인증 없는 공개 독자. US-012 와 FR-028/026; 기존 FR-003/020/011 를 구현할 후속 기준이다. 기술 단계와 public 데이터/화면/운영 수용은 구별한다.

## 책임과 선행 조건

u180 shared time/snapshot/publication, u181 hub/nav 구현 이후 전달한다. u35/u43 기존 calendar sources 재사용. 새 source/actual join/DEBT-079 closeout 는 prerequisite 가 아니다.

구현 범위: sources/fomc_calendar.py/fred_economic_calendar.py/us_economic_calendar.py/treasury_auctions.py 의 기존 응답 기반 opt-in event envelope; models/insights.py event definition/identity; orchestrator/insights_projection.py calendar selection; publisher/insights/calendar.py; calendar/index.md 와 _data/calendar/current.json; insights CSS/JS 필터/nav·qualification·tests.

제외 범위: BLS ICS 신규 adapter, Nasdaq earnings 재배포, real-time countdown, actual 발표완료·consensus/surprise·schedule actual join, calendar history backfill, generic topic/ticker 사건 ID·v3 story reducer.

## 데이터 흐름과 행동


1. 기존 4 개 calendar 응답에서 semantic event family, 공식 원출처 날짜/기간, 정확한 시간 근거, 원천 ID/source ref 를 opt-in envelope 에 담는다. 기존 scheduled_at/published_at 와 lookahead cap/routing 은 바꾸지 않는다.
2. Fed 의 2 일 회의는 first day 뿐 아니라 마지막 day 를 원 응답에서 보존한다. statement/press conference/minutes 는 별도 kind/occurrence 이며 회의 첫날을 발표일로 만들어내지 않는다.
3. FRED/auction 의 date-only 는 원천 현지 날짜+America/New_York 를 사용한다. BEA 의 확인된 exact ET 만 KST 로 바꾸며 불명확 time 은 date-only 로 보존한다.
4. conservative occurrence key 로 같은 official release 의 중복 source ref 만 병합한다. source family/release identity·local date·target period 의 일치가 필요하며 기간이 infer 된 metadata 를 검증된 대상 기간으로 승격하지 않는다.
5. exact event 는 KST display date 로, date-only 는 source-local date 로 묶어 표시한다. mixed timeline 에는 “한국 시각 확인”과 “현지 날짜·시간 미정”을 구별한다.7/30 일 선택범위는 각 event 의 declared calendar basis 에 적용한다.
6. source missing/failure·conflict·상한·부분 coverage 를 snapshot 상태로 표시한다. “해당 일정 없음”과 “해당 소스 미확인”을 구별한다. 일정 경과는 결과 확인이 아니다.


## 실패와 대체

[공통 계약](../../public-insights-20261012/contracts.md)의 C2–C7 을 적용한다. available 숫자·일정에 없는 time/period/단위/원천을 발명하지 않는다. 해당 source 실패·미확인·key 없음은 해당 card/module 의 명시된 상태와 유효 last-good 로 표현하며 정상 sibling 을 유지한다. 권리가 미확인/철회된 숫자는 current/history 에 포함하지 않는다. LLM text 또는 다른 source 의 유사 제목으로 채우지 않는다.

## 수용 시나리오

[시나리오 목록](../../public-insights-20261012/acceptance-scenarios.md)과 [실행 계획](../../plans/u182-upcoming-events-dashboard-code-generation-plan.md)의 numbered AC 를 함께 따른다. 현재 문서 작성은 제품 test/pass 결과가 아니다.
