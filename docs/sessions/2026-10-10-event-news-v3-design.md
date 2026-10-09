# 2026-10-10 — 이벤트·뉴스 중심 시황 v3 설계

사용자는 기존 기능의 폐기와 구조 변경을 허용하며 우선 문서 작성을 요청했다. 분석 기준 `19c89b92`에서 시작하여 최종 main `487627931e27548a4a755a53df2dadc7c03543b8`으로 갱신한 격리 branch `codex/news-event-v3-design-20261010`에 설계와 실행 단위 u167–u173을 작성했다.

[프로그램 설계](../../aidlc-docs/construction/event-news-v3/README.md), [공통 계약](../../aidlc-docs/construction/event-news-v3/contracts.md), [폐기·전환](../../aidlc-docs/construction/event-news-v3/migration-and-retirement.md), [수용·운영](../../aidlc-docs/construction/event-news-v3/acceptance-and-rollout.md)이 후속 구현의 기준이다. FR-024/025와 TD-016, aidlc-state와 두 inception 등록도 갱신했다. 기존 완료 AC에는 legacy 버전 범위를 명시했다.

신규 필수 7섹션·가격표 우선·강제 3요약·중복 상단 블록·본문 첫 문장 80자·빈 legacy bridge를 폐기 대상으로 정했다. source 권한, 수치·entity·actual/forecast·compliance·면책, 단일 finalizer, 원격 확인과 부분 발행은 유지한다.

두 독립 문서 리뷰의 지적을 반영하여 타입 의존, 사실 metric, occurrence alias, 상태 해결 대상과 clock, 실패 outcome, public projection, historical sidecar, 본문 visual과 OG의 실행 순서를 정리했다. [검토 반영](../../aidlc-docs/construction/event-news-v3/review-resolution.md)에 결정과 한계를 기록했다.

모든 신규 유닛은 구현 0이며 Functional/NFR Design은 작성 상태다. 별도 승인·구현·사람 수용·배포를 완료 표시하지 않았다. 코드, archive, runtime, 진행 중 u154/u165/u166 branch를 수정하지 않았고 commit/push도 수행하지 않았다. 문서 구조·링크·등록·의존·whitespace 검증만 수행했다. 구현 테스트와 site build는 변경 범위상 실행하지 않았다.

최신 main 갱신은 fast-forward이며 새로운 문서 commit은 생성하지 않았다. stash 적용의 audit/u154 계획 충돌은 최신 완료 기록을 보존하고 v3 메모를 추가하는 방식으로 해결했다. 원본 작업 디렉터리의 기존 dirty 항목은 그대로다.
