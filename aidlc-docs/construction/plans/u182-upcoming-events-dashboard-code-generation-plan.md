# Code Generation Plan: u182-upcoming-events-dashboard

작성일: 2026-10-12 · u182 · 상태: 2026-10-25 사용자 후속 진행 지시로 설계 채택. 로컬 구현·검증6/7 완료이며 운영 Step7은 별도다.

## 문제와 목표

공식 경제지표·중앙은행·국채 입찰의 예정 날짜와 확인된 시각을 7 일 기본/30 일 선택 목록으로 보여주고 원천으로 연결한다.

## Existing coverage / Deduplication

u180 shared time/snapshot/publication, u181 hub/nav 구현 이후 전달한다. u35/u43 기존 calendar sources 재사용. 새 source/actual join/DEBT-079 closeout 는 prerequisite 가 아니다.

[Program 중복 대조](../public-insights-20261012/README.md)와 [source 판정](../public-insights-20261012/source-assessment.md)을 따른다. source 별 defaults/tier/window/segment/registry 는 유지하며 raw numeric/event envelope 만 opt-in 추가한다.

## Scope boundary

sources/fomc_calendar.py/fred_economic_calendar.py/us_economic_calendar.py/treasury_auctions.py 의 기존 응답 기반 opt-in event envelope; models/insights.py event definition/identity; orchestrator/insights_projection.py calendar selection; publisher/insights/calendar.py; calendar/index.md 와 _data/calendar/current.json; insights CSS/JS 필터/nav·qualification·tests.

제외: BLS ICS 신규 adapter, Nasdaq earnings 재배포, real-time countdown, actual 발표완료·consensus/surprise·schedule actual join, calendar history backfill, generic topic/ticker 사건 ID·v3 story reducer.

## Stage decision

- Functional Design: REQUIRED / ADOPTED. 새 public 데이터 의미·시간·상태·독자 workflow 와 cross-module contract 가 있다. [FD](../u182-upcoming-events-dashboard/functional-design/business-logic-model.md).
- NFR Requirements: REQUIRED / ADOPTED. source rights/private 경계·신뢰·자원·retention/새화면·runtime 를 구체화한다. [NFR](../u182-upcoming-events-dashboard/nfr-requirements/nfr-requirements.md).
- NFR Design: focused design in [shared contracts](../public-insights-20261012/contracts.md), 별도상투적문서 대신 C3–C7 의경계·cap·recovery 로구체화. 승인·실제검증은미기록.
- Infrastructure Design: SKIP separate stage; u180 의 focused 기존 privatejob/Pages 계약을 재사용하며 새스케줄/환경/secret 은 없다.
- Code Generation: LOCAL VERIFIED6/7. 사용자 “진행시켜” 지시로 u182 로컬 구현·검증을 진행한다. commit/push/운영 활성화는 수행하지 않는다.
- Source requirements: 사용자 2026-10-12 지시, US-012; FR-028/026; 기존 FR-003/020/011; NFR-001~008/R10/R13. 신규공식 source 자격검증이있으면 별도 bounded source plan 에 handoff 한다.

## Fixed contracts

[C1–C7](../public-insights-20261012/contracts.md), [unit rules](../u182-upcoming-events-dashboard/functional-design/business-rules.md), [entities](../u182-upcoming-events-dashboard/functional-design/domain-entities.md)가 normative 초안이다. 입력/시간/identity/owner/permission/부분상태/파일원격확정순서를구현중임의로바꾸지않는다. DTO/private envelope 와 HTML·JSON·이력·receipt 의 role 을구별한다.

## Implementation steps

- [x] **Step 1** — 기존 4calendar endpoint·source cap·date/time precision·Fed days·BEA time·auction ID 와 공개 조건을 실제 source fixtures 와 대조하여 per-source event mapping 을 고정한다.
- [x] **Step 2** — opt-in event envelopes 를 기존 source parsers 에 추가한다. 기존 scheduled_at/target publish clock/routing/소스 숫자·문자열 bytes 를 보존하고 원 응답 range/precision 만 새 typed input 에 전달한다.
- [x] **Step 3** — calendar identity·date/exact union·range 검증·conservative dedupe/conflict·7/30 일 selection/cap 를 구현한다. source 없는 target_period 를 infer 하지 않는다.
- [x] **Step 4** — publisher/insights/calendar.py 의 7 일 목록과 date-only/exact KST 표시, 고정 guide·official links·부분/empty/source 상태를 구현한다.
- [x] **Step 5** — u181 hub/nav 에 calendar 를 추가하고 scoped category/range DOM filters 와 noJS30 일 앵커를 제공한다. date basis 를 숨기지 않고 DST/range/keyboard 를 실제 렌더 확인한다.
- [x] **Step 6** — source/domain/render/site 집중 및 full/static/policy/docs 검증, AC·existing lookahead/source parity review 를 기록한다.
- [ ] **Step 7** — 후속 운영 지시의 범위에서 calendar module 을 순차 활성화하고 exact-SHA5 회 예약관찰/live 일정·precision·identity/Pages 상태를 기록한다.

## Acceptance criteria

- AC-182.1:4source 의 official 일정·kind/range/원천 href 와 실제 precision/cap 가 보존된다. 미확인 source 와 일정없음 구별.
- AC-182.2:date-only UTC00:00 을 KST09:00 으로 표시 0; exact ET 의 DST 변환·KST grouping 이 fixture 와 일치.
- AC-182.3:2 일 회의·발표·minutes 는 서로 구별되고 reviewed key 가 없는 cross-source duplicate merge0; inferred period 의 verified 승격 0.
- AC-182.4:7/30 일·categories·128 cap·conflict/partial 표현과 noJS 접근이 일치; source cap 를 full coverage 로 주장 0.
- AC-182.5:경과/누락/TTL 로 발표완료·취소·actual·consensus·surprise 를 생성 0. 기존 lookahead/carryover/Telegram 입력 유지.
- AC-182.6:두 viewport/theme/keyboard/200% 확대와 payload 예산, exact-SHA 운영·Pages/live 수용을 code 완료와 구별.

## Tests / Validation

새 source/domain/render/integration tests와 실제 browser QA를 구현했다. 전체7,091pass/기존1skip(현재collection7,092), 최종focused236pass, 독립리뷰C/H/M0. [검증](../u182-upcoming-events-dashboard/code/validation.json)에 checkpoint와 집계 방식을 구별한다.

- `tests/unit/orchestrator/test_upcoming_insights_projection_u182.py`
- `tests/unit/publisher/test_upcoming_insights_render_u182.py`
- `tests/integration/test_upcoming_insights_site_u182.py`

기존 owner 회귀: tests/unit/sources/test_fomc_calendar.py; test_fred_economic_calendar.py; test_treasury_auctions.py; test_us_economic_calendar.py; 기존 lookahead/summary tests.

필수 공통 명령은 `uv sync --extra dev --extra docs --extra sector`, scoped+full `uv run python -m pytest`, changed Ruff/format·source mypy, `python scripts/check_no_paid_apis.py`, `python scripts/check_no_anthropic_sdk.py`, 기존 curated/image guards, `uv run mkdocs build --strict`, `python scripts/check_material_theme_contract.py`, `git diff --check`다. workflow 변경이 있는 u180 은 actionlint 와 private runtime template/output negative 검증을 포함한다.

각 source recording/문서조건·합성 domain case·실제 viewport·remote/livePages·5 회 scheduled 를서로구별해기록한다.  현재문서작업은제품 test 결과가아니다. [시나리오](../public-insights-20261012/acceptance-scenarios.md)를 AC 에연결한다.

## 2026-10-25 구현 결과

Steps1–6 로컬 검증 완료. [Summary](../u182-upcoming-events-dashboard/code/summary.md), [AC 대조](../../../docs/cross-checks/2026-10-25-u182-upcoming-events-dashboard.md). Fed occurrence 충돌을 기존 recording으로 재현·수정했다. 원천별14allow/10blocked, defaultoff, commit/push/production 변경 없음. Step7의 latest-main/exact implementation SHA·source 조건·private pin/mode·Pages·5회 scheduled 수용은 pending. 다음 코드 유닛은 u183이다.
