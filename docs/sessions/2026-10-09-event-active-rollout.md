# 사건 본문 운영 전환 — 2026-10-09

## 승인과 범위

사용자는 직전 보고에서 코인 생성 실패, frozen12 사람 검수 미완료, 뉴스가 풍부한 날의 사람 baseline 미완료를 확인한 뒤 **“운영 활성화도 해줘”**라고 다시 지시했다. 이번 지시는 사건 본문 운영 전환 승인으로 반영한다. 사람 검수를 통과했다고 해석하거나 미완료 품질 수용을 완료로 바꾸지 않는다. 기존 출시 전 검수 조건은 이 제한된 운영 전환에 한해 후속 관찰로 남긴다.

대상은 국내·미국의 u157/u158/u159 사건 본문과 연결된 u152/u162 관전 포인트다. 코인은 실제 미리보기 실패가 남아 있어 기존 shadow/v1을 유지한다. `INVESTO_EVENT_BRIEFING_MODE=active`를 검증된 코드 pin에 적용한다. 뉴스 수집 범위와 cursor는 기존 `shadow`, 신규 공식 본문 HTTP는 `off`를 유지한다. 공개 daily는 계속 중지하고 `murphyGo/automation-runtime`만 운영 owner로 둔다. provider, 인증 보존, 알림 대상, 정상 sibling 게시와 숫자/entity/compliance/finalizer hard gate는 유지한다.

## Stage decision 및 수정

별도 Functional Design/NFR 단계는 생략한다. 기존 AC-158.3/5, NF1/7/9 및 실제 `37912037986`의 `event.entity_unsupported`를 다루는 좁은 후속 수정이다. 출시 순서의 예외만 위 사용자 지시와 함께 명시한다.

실제 실패 문장은 보관되지 않아 원인을 특정할 수 없다. 소스 검토에서는 재현 가능한 프롬프트 불일치를 확인했다. validator는 80자 이내 첫 문장에 actor/object 각 비어 있지 않은 그룹의 근거 이름을 요구하지만, 기존 첫 문장 안내에는 actor와 변화만 명시돼 있었다. 이름이 두 번째 문장에만 있는 합성 예시는 정확히 같은 오류로 거절된다.

- 첫 문장에 필요한 주체·대상의 원문 표기를 명시한다. 제목/후속 문장은 대신할 수 없다.
- 정확한 `event.entity_unsupported` 재시도에만 고정 안내를 추가한다. 실패한 모델 문장이나 임의 예외 내용을 피드백에 넣지 않는다.
- 기존 validator, 80자/240자 제한, 선정 사건 집합, 두 단계 호출과 attempt/budget은 변경하지 않는다. 과도하게 긴 원문 이름은 여전히 검증에 실패할 수 있다.
- 운영 전환 가능 상태만 열며 환경변수 기본값은 `off`로 유지한다. `preview`의 공개 진입은 계속 거절한다.

## 검증·실행 순서

- [x] 프롬프트/검증기 불일치와 원문 출력 미보관의 한계를 확인했다.
- [x] 첫 문장 안내와 고정 재시도 피드백, 활성화 capability, 회귀 테스트를 구현했다.
- [x] 집중 회귀, 정적 검사, 독립 코드 검토를 통과한다.
- [x] 정확한 main 코드의 전체 CI를 확인한다.
- [x] private 비게시 preview에서 수정 결과를 확인한다. 국내·미국은 성공, 코인은 실패로 유지한다.
- [x] 운영 pin과 사건 mode를 전환하고 실제 설정을 재조회한다.
- [ ] 첫 3회 active 예약 실행의 실제 게시·알림·Pages를 별도로 관찰한다.

이미 완료된 예약 shadow 관찰은 5/5회(4성공,1부분)다. 수동 실행으로 예약 관찰을 대체하지 않는다. frozen12와 뉴스 풍부한 날 baseline은 후속 품질 수용 항목으로 계속 추적하며 자동 평가/이번 출시 승인으로 채점하지 않는다. 첫 3회 active 발행 관찰도 실제 확보한 횟수만 기록한다. DEBT-090 성능 목표 완료는 주장하지 않는다.

집중 회귀 117개/6.84초 통과. 두 provider의 preview/active 경로가 정상 입력에서 각 2회 호출로 사건을 보존하며, 반복 entity 실패는 기존 상한에서 실패로 남는다. 독립 검토 CLOSED, P1/P2 없음: 생성 경계 53개/4.45초, receipt·news-window·preview 경계 93개/34.16초, 합계146개 통과. Ruff/format669/mypy290, 4개 policy guard, strict docs/Material와 diff 검사를 통과했다.

## 정확한 코드와 실제 미리보기

프롬프트 보정 코드 `eea56bd0409d69f7d583a75a83ac5f4d1cbe0623`를 main에 푸시하고 원격 SHA를 확인했다. 동시 추가된 u163–u166 기획 `31bb9521`은 보존했다. 합친 트리에서도 집중117/7.80초와 strict docs/Material를 다시 통과했고 실행 코드의 변경 없음도 확인했다. exact-SHA [CI37937417645](https://github.com/murphyGo/investo/actions/runs/37937417645)는 **6207개/316.94초**, Ruff/format669/mypy290과 모든 policy/docs gate를 통과했다.

Private [미리보기37937493974](https://github.com/murphyGo/automation-runtime/actions/runs/37937493974)는 `REVIEWED_EVENT_PREVIEW_SHA`를 같은 코드로 고정하고 target2026-10-08로 실행했다. 공개 게시 없이 암호화 산출물을 받아 로컬에서 복호화하고 SHA256을 대조한다.

| 시장 | 선정/최종/요약 | 결과 | SHA256 |
|---|---|---|---|
| 국내 | 5/5/3 | sealed, 상세근거 제한5, qualified0, issue0 | `09d8ddf8af6771b959bbfdf31f47fce75508fbc2f27bb232ac1081a3dae3833c` |
| 미국 | 2/2/2 | sealed, 상세근거 제한2, qualified0, issue0 | `047d55476ba692d2598aaea93fd1a6b17db2966d57e69d995d4cc009a263176b` |
| 코인 | 알 수 없음 | synthesis3 / `event.narrative_invalid` 실패 | 본문 없음 |

전체 Actions는 코인 실패로 failure이며 국내·미국은 각각 성공했다. 국내·미국 manifest의 게시/알림/cursor/receipt write는 모두 false다. 원시 모델 출력이나 사건 본문은 공개 git에 넣지 않는다. 시간에 따라 수집 입력이 바뀌었으므로 이전 미리보기와 동일 입력 재생이라고 주장하지 않는다.

## 검증된 시장부터 단계 활성화

코인의 기존 `event.entity_unsupported`와 다른 `event.narrative_invalid`가 남았다. 성공할 때까지 다시 호출하거나 validator를 완화하지 않는다. reviewed code의 `EVENT_ACTIVE_SEGMENTS`를 국내·미국으로 제한하고 active 모드에서 코인은 기존 shadow config로 해석한다. Preview 모드는 세 시장 모두 계속 허용한다. 추가 환경변수·private workflow 수정은 없다.

- 시장별 생성 정책뿐 아니라 clock/baseline 적용과 shadow 로그도 실제 모드에 맞춘다.
- 공식 사건을 공유하는 입력은 국내·미국에만 확장한다. 코인은 기존 native 입력 순서·내용을 유지하고 전체 세 시장 mapping은 보존한다.
- 사건 coverage는 국내·미국에만 생성한다. 코인은 공개 사건 통계의 가짜 실패/0으로 만들지 않으며, 기존 aggregate의 제외 시장으로 표현한다.
- 실제 혼합 finalizer와 원격 확인 이후 receipt 경로를 검증한다. 코인 문서는 기존 bytes/DTO/빈 사건 receipt를 유지하며, 게시 뒤 coverage 키 오류가 발생하지 않도록 한다.
- 공유 event baseline/CAS는 혼합 bundle의 동일한 원자적 게시 경계를 유지한다. baseline 장애를 피해 코인만 별도 push하는 새 경로는 추가하지 않는다.

이 후속 변경은 운영에서 사용하는 시장 선택만 제한한다. 성공한 국내·미국의 실제 미리보기 코드 `eea56bd0` 대비 LLM 프롬프트, parser, validator와 렌더러는 바뀌지 않는다. 반복 비게시 호출로 성공 횟수를 채우지 않고 최종 코드의 혼합 생성/게시 회귀와 exact CI로 연결을 검증한다. frozen12·뉴스 풍부한 날 검수 및 코인 v2는 후속 항목이다.

시장 제한은 production orchestrator의 config 해석 경계다. 명시적으로 구성한 low-level generator/replay의 v2 능력을 제거하지 않는다. 기존 세 시장 전체 v2 frozen-window replay 검사는 해당 테스트에서만 전체 시장을 허용해 기존 범위를 보존한다. 새 혼합 회귀는 실제 config/생성 adapter/비참여 시장의 원문 입력/real finalizer/원격 확인 후 coverage·receipt를 검증한다.

단계 활성화 후속 집중 회귀는 **255개/73.55초** 통과했다. 독립 검토는 초기39통과/1fixture불일치를 찾아 테스트 범위의 의미를 보존해 수정했고, 해당 replay와 신규 혼합4개를 다시 실행해5개/2.21초 통과, CLOSED/P1·P2 없음으로 종료했다. Ruff/format670/mypy290와 diff 검사도 통과했다. 최종 전체 CI와 운영 설정 조회도 아래와 같이 완료했다.

## 실제 운영 활성화

2026-10-09 **14:47:50 UTC / 23:47:50 KST**에 `murphyGo/automation-runtime`의 `INVESTO_EVENT_BRIEFING_MODE=active`를 저장하고 재조회했다. 5초 앞서 `REVIEWED_CODE_SHA`를 전체 검증된 `7bc6d28793fdefc19d78652bdc3fd1cb25f87c7f`로 먼저 변경했다. 전환 직전 다른 실행은 없었고 기존 pin `ca0ef610`과 shadow 기본값을 확인했다.

| 항목 | 재조회한 운영 상태 |
|---|---|
| 국내·미국 사건 본문 | active — 검증된 코드의 시장별 설정 적용 |
| 코인 사건 본문 | shadow/v1 — 실제 narrative 실패로 v2 승격 제외 |
| 뉴스 관찰 기간 / 공식 본문 HTTP | shadow 기본값 / off |
| 비공개 daily / production gate | active / `CODEX_PRODUCTION_ENABLED=1` |
| 공개 daily | disabled_manually — 중복 owner 없음 |
| 별도 preview pin | `eea56bd0` — 실제 미리보기 결과와 일치 |
| 다음 예약 시각 | 2026-10-10 00:00 UTC / 09:00 KST (`0 0 * * 6`) |

운영 코드의 [CI37940803779](https://github.com/murphyGo/investo/actions/runs/37940803779)는 **6211개/327.34초**, Ruff/format670/mypy290, policy/docs/Material 전체 PASS다. 해당 SHA의 main 조상을 확인했고, 별도 u163 `756c4e3f`·u164 `60ef00ec` 변경은 문서 통합 시 보존했다. 이 두 후속 코드 변경은 이번 운영 pin에는 포함하지 않는다. 운영 기록의 후속 문서 커밋으로 검증된 pin을 움직이지 않는다.

활성 설정과 예약 연결은 완료했다. **첫 active 예약 발행 관찰은 0/3회**이며 게시·Telegram·Pages 성공은 아직 확인 전이다. 기존 날짜를 수동 재발행해 관찰 횟수를 채우지 않았다. frozen12 사람 검수, 뉴스 풍부한 날 baseline, 코인 v2 승격은 미완료다. 운영 전환 승인을 이 항목들의 통과로 기록하지 않는다.

## 복구

문제 발생 시 private `INVESTO_EVENT_BRIEFING_MODE`를 `shadow`로 되돌린다. 코드 자체 복구가 필요하면 검증된 이전 production pin `ca0ef610cdaafea7de188551f06d2107247e8472`로 복구한다. 발행 이력과 이미 게시된 archive는 재작성하지 않는다.
