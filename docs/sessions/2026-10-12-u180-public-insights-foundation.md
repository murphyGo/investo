# Session: u180 공개 인사이트 기반

2026-10-12 · 사용자 “유닛 하나씩 진행시켜” · 로컬 Code Generation Steps 1–7, 운영 Step 8 대기.

## 결과

첫 유닛 u180의 typed 입력, source/time/rights gate, 제한된 이력, multi-file snapshot 저장, remote-confirmed 게시와 private workflow 출력 연계를 구현했다. foundation의 기본 renderer만 있으며 매크로/일정/크립토 화면·실제 원천 parser는 후속 u181–u183 범위다. 기존 수집을 1회 재사용하고 private envelope를 기존 consumers 전에 제거한다.

변경 파일과 설계 결정은 [summary](../../aidlc-docs/construction/u180-public-insights-snapshot-and-publication/code/summary.md), [계획](../../aidlc-docs/construction/plans/u180-public-insights-snapshot-and-publication-code-generation-plan.md)에 연결한다. 수용 기준은 [cross-check](../cross-checks/2026-10-12-u180-public-insights-foundation.md)에 있다.

## 리뷰와 수정

- private journal/backup 및 atomic rename 후 parent directory를 fsync하여 crash recovery 순서를 보강했다. rollback 전 backup hash와 모든 owned files를 검증한다.
- 새 미래·unknown/stale numeric은 공개하지 않고, remote-confirmed이며 여전히 허용된 last-good만 재사용한다. 2026 지원 범위를 넘어선 daily/monthly freshness는 unknown이다.
- metric 정의 문자열뿐 아니라 module/public ID/unit/provider/scope/method/sample/cadence/calendar semantic identity를 권한 matrix와 비교한다.
- 이력 직렬화/readback의 전체 객체 그래프 복제를 줄이고 compact immutable row/time, 스트리밍 canonical bytes 및 bounded Git binary blob 읽기로 RSS 기준을 충족했다.
- 실제 커밋 내용 검증, writer lock, unknown receipt reconciliation, 비활성 모듈의 권한/보관 철회와 sibling 오류 격리를 검증했다.
- 독립 초기 리뷰는 [review-initial](../../aidlc-docs/construction/u180-public-insights-snapshot-and-publication/code/review-initial.md)에 기록한다.

## 검증 범위

전체 suite는 초기 구현 checkpoint에서 6,987 passed / 1 known skipped였다. 이후 보완한 코드에 관련 704 tests 및 최종 scoped suite **173 passed / 42.52s**를 실행했다. 정적 검사·정책·MkDocs/Material/Calendar·actionlint를 확인했다. [validation](../../aidlc-docs/construction/u180-public-insights-snapshot-and-publication/code/validation.json)에 정확한 결과를 기록한다.

합성 데이터 자원 시험은 실서비스 원천이나 권리 승인 증거가 아니다. 임시 로컬 bare Git만 사용하여 새 커밋·push·정확한 remote SHA를 확인했다. production qualification은 빈 목록으로 유지한다.

## 상태와 경계

- 작업 위치: `.tmp/public-insights-unit-design-20261012`, branch `codex/public-insights-unit-design-20261012`, base `55c00fc85e2828f62cd69d5583afd3761ef86d45`.
- root의 기존 dirty files, 과거 유닛 상태, u145 store 및 event/news ledger를 보존했다.
- commit/push·실서비스 배포·private reviewed pin/mode·Telegram 발송은 수행하지 않았다. 기본값은 off다.
- 새 debt 등록은 없다. DEBT-090와 기존 운영 수용은 종료하지 않았다.
- 다음 구현 유닛은 u181 매크로 환경판이다. Step 8의 source qualification·실제 Pages·5회 예약 실행은 후속 모듈 구현 이후 수용한다.

독립 리뷰 H180-01: git add 후 종료 시 owned index 복구 누락을 재현했다. stage journal에 initial HEAD를 fsync하고 같은 HEAD/owned staged hash/HEAD baseline hash를 검증한 뒤 해당 index만 reset한다. HEAD 변경 또는 owned index mismatch면 journal을 유지한다. reviewer가 29 tests를 직접 실행했고 최종 C/H/M 0; [최종 재검토](../../aidlc-docs/construction/u180-public-insights-snapshot-and-publication/code/review-final.md).
