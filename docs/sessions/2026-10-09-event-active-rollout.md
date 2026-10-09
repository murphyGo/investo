# 사건 본문 운영 전환 — 2026-10-09

## 승인과 범위

사용자는 직전 보고에서 코인 생성 실패, frozen12 사람 검수 미완료, 뉴스가 풍부한 날의 사람 baseline 미완료를 확인한 뒤 **“운영 활성화도 해줘”**라고 다시 지시했다. 이번 지시는 사건 본문 운영 전환 승인으로 반영한다. 사람 검수를 통과했다고 해석하거나 미완료 품질 수용을 완료로 바꾸지 않는다. 기존 출시 전 검수 조건은 이 제한된 운영 전환에 한해 후속 관찰로 남긴다.

대상은 u157/u158/u159 사건 본문과 연결된 u152/u162 관전 포인트다. `INVESTO_EVENT_BRIEFING_MODE=active`를 검증된 코드 pin에 적용한다. 뉴스 수집 범위와 cursor는 기존 `shadow`, 신규 공식 본문 HTTP는 `off`를 유지한다. 공개 daily는 계속 중지하고 `murphyGo/automation-runtime`만 운영 owner로 둔다. provider, 인증 보존, 알림 대상, 정상 sibling 게시와 숫자/entity/compliance/finalizer hard gate는 유지한다.

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
- [ ] 정확한 main 코드의 전체 CI를 확인한다.
- [ ] private 비게시 preview에서 수정 결과를 확인한다.
- [ ] 운영 pin과 사건 mode를 전환하고 실제 게시·알림·Pages를 분리 확인한다.

이미 완료된 예약 shadow 관찰은 5/5회(4성공,1부분)다. 수동 실행으로 예약 관찰을 대체하지 않는다. frozen12와 뉴스 풍부한 날 baseline은 후속 품질 수용 항목으로 계속 추적하며 자동 평가/이번 출시 승인으로 채점하지 않는다. 첫 3회 active 발행 관찰도 실제 확보한 횟수만 기록한다. DEBT-090 성능 목표 완료는 주장하지 않는다.

## 복구

집중 회귀 117개/6.84초 통과. 두 provider의 preview/active 경로가 정상 입력에서 각 2회 호출로 사건을 보존하며, 반복 entity 실패는 기존 상한에서 실패로 남는다. 독립 검토 CLOSED, P1/P2 없음: 생성 경계 53개/4.45초, receipt·news-window·preview 경계 93개/34.16초, 합계146개 통과. Ruff/format669/mypy290, 4개 policy guard, strict docs/Material와 diff 검사를 통과했다.

문제 발생 시 private `INVESTO_EVENT_BRIEFING_MODE`를 `shadow`로 되돌린다. 코드 자체 복구가 필요하면 검증된 이전 production pin `ca0ef610cdaafea7de188551f06d2107247e8472`로 복구한다. 발행 이력과 이미 게시된 archive는 재작성하지 않는다.
