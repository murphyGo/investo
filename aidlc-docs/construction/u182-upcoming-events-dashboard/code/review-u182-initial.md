# u182 independent code review — initial

작성일: 2026-10-25. 별도 reviewer. 상태: **확정 Critical 0 / High 0 / Medium 1 — Fed occurrence identity 수정 후 좁은 재검토 필요**.

## 범위와 방법

`.codex/skills/code-review/SKILL.md`, protocol INDEX와 앞선 동일 작업에서 읽은 security-boundary/data-integrity/error-contract/memory/performance/resource-lifecycle/concurrency 절차를 이번 변경의 해당 경계에 적용했다. u182 FD business logic/rules, focused NFR, code-generation plan, 공통 C1–C7을 읽고 실제 구현과 대조했다. u180/u181 전체를 다시 검토하지 않았다.

검토 파일은 models/insights.py의 event details/references/coverage/omit serialization 추가, 신규 models/insights_events.py, orchestrator/calendar_insights.py, insights_projection.py의 calendar/rights 분기, insights_publication.py의 inactive sanitizer, publisher/insights/calendar.py 및 store의 선택/cap, 기존4 calendar adapter opt-in diff, calendar DOM filter JS 및 CSS/nav/hub, qualification의 calendar24개 설정, *_u182.py와 synthetic helper다.

자동화의 broader Ruff/format/mypy325/전체 regression 진행 상태는 lead가 제공한 증거다. reviewer가 전체 checks를 중복 실행한 것으로 표현하지 않는다.

## M182-01 — 실제 Fed의 별도 당일 행사가 title-only identity로 손실됨

위치: `src/investo/sources/fomc_calendar.py`의 `_insight_event()`, `official_id = "fed:" + digest(title.encode())[:32]`.

kind·현지 날짜·title이 같은 당일 별도 행사의 time/location/description 차이를 identity에 포함하지 않는다. date-only precision으로 내리는 과정에서 두 원천 행사가 완전히 같은 typed event가 되어 projection이 조용히 하나로 dedupe한다. occurrence는 같다고 검증되지 않았는데 합쳐지며 conflict/excluded count에도 나타나지 않는다. R182.2/R182.3의 conservative occurrence identity와 맞지 않는다.

**기존 source recording 기반 reviewer 직접 재현:** `tests/unit/sources/fixtures/api/fomc-calendar/upcoming.json`의 다음 두 원천 row를 사용했다. 새 live HTTP를 호출하지 않았다.

```text
2026-02-09 Discussion - Governor Stephen I. Miran
5:00 p.m. — Conversation with Governor Miran
2:30 p.m. — A Conversation with Stephen Miran
```

두 row를 `_insight_event`로 변환하고 collector origin을 결속한 뒤 synthetic qualification으로 실제 `project_module(calendar, ...)`을 실행한 결과:

```text
typed identities ['event:d68a0bf9c6dab5d5241a16ac6b7bad25219d2aeea0d4b1732f187d5c8562a1f6',
                  'event:d68a0bf9c6dab5d5241a16ac6b7bad25219d2aeea0d4b1732f187d5c8562a1f6']
projected events 1 conflicts 0 invalid 0
```

**수정 제안:** 원천 occurrence를 구별하는 정규화된 time/location/description 또는 공식 link/ID의 bounded hash를 source-local official_id에 포함한다. 공개 precision은 date-only로 유지하며 identity용 원천 시각을 exact schedule로 승격하지 않는다. 같은 row의 중복은 계속 안정적으로 dedupe하고, 위 실제 recording의 두 별도 행사는 두 개로 보존하는 회귀가 필요하다. lead가 수정에 착수했다고 전달했지만 이 초기 보고서 시점에는 수정 후 결과를 아직 검증하지 않았다.

## 확인한 경계와 근거

- date-only는 declared America/New_York 날짜/범위로 유지하고 exact BEA만 KST로 표시한다. year 근거와 DST ambiguity/nonexistent wall clock negative, synthetic midnight를 exact로 만들지 않는 분기를 대조했다.
- Fed meeting/statement/press conference/minutes kind 분리, auction CUSIP+date+reopening 및 CUSIP 없는 source-local key, BEA가 명시한 기간과 FRED null period 분리를 읽었다.
- cross-source merge는 reviewed economic family+현지 start/end+같은 verified/null period의 BEA/FRED 한 쌍에 한정한다. source당 여러 occurrence가 있으면 별도로 유지한다. conflicting same-source occurrence를 제거하고 count한다.
- failed/zero/skipped last-good는 원래 collection clock과 reference별 출처를 유지한다. successful fresh source는 이전 일정을 대체한다. 경과/누락을 actual·취소로 확정하지 않으며 30일 범위에서 제외하거나 결과 미확인 상태로 표시한다.
- merged reference 권리도 검사하고 inactive calendar를 sanitize할 때 permitted primary/secondary를 재투영한다. 캘린더는 analytics history를 만들지 않는다.
- input512KiB/current256KiB와128선택/excluded/HTML120KiB 경계를 읽었다. source upstream cap와 쿼리 범위는 전체 시장 calendar와 구별한다. 공통 module cap 초과는 값 없는 상태로 제한한다.
- no-JS30일 전체 목록·anchor, JS7/30 및 category DOM 필터, status/aria-pressed와 empty 상태를 확인했다. JS는 fetch/clock 재계산/외부 dependency를 추가하지 않는다. labels/links/notice escape와 고정 method guide를 대조했다.
- 새 optional details/references/coverage가 없는 schema-v1 numeric snapshot에서 필드를 생략하여 기존 snapshot identity를 유지하는 serializer와 회귀를 확인했다.

## reviewer 직접 실행한 검증

```text
.venv/bin/python -m pytest tests/unit/orchestrator/test_upcoming_insights_projection_u182.py tests/unit/publisher/test_upcoming_insights_render_u182.py tests/unit/sources/test_upcoming_insights_envelopes_u182.py tests/integration/test_upcoming_insights_site_u182.py -q
45 passed in 11.72s
```

같은 검토에서 M182-01 recording replay를 별도로 직접 실행했다. source4종의 opt-in/off 기존 JSON bytes·요청 수 parity, exact KST/DST·date-only negative, merge/권리 철회/last-good·inactive sanitation,128선택/no-history/byte cap 등의 테스트가 위 실행에 포함된다. API key는 테스트의 synthetic 값만 사용했고 production source 조회는 하지 않았다.

qualification loader의 실제 calendar24개/14allow/10 FREDblocked/all retention false 및 primary evidence link·checked_on·attribution 존재를 read-only 확인했다. 각 원천의 실제 재배포 권리에 대한 독립 법적 판정 또는 추가 live source qualification 성공을 주장하지 않는다. lead가 보고한 실원천 개발 조회3 HTTP200/offline replay와 broader static/full checks는 reviewer 직접 실행 결과와 구분한다.

실제 viewport/테마/200%/keyboard·production Pages·private pin·activation·scheduled observation은 이 리뷰로 수용되지 않는다. source/test 수정·commit/push/배포 없이 이 보고서만 작성했다. 확정한 Medium은 유닛 내부 correctness 문제이므로 기술부채로 미루기보다 수정 후 좁은 재검토가 필요하다.
