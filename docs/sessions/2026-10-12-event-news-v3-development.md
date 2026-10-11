# Event/news v3 개발과 통합

사용자의 “개발도 진행해줘”, 작업 중이면 별도 워크트리, “커밋 푸시해줘”, “나머지도 계속 진행해줘”를 적용했다.
별도 `.tmp/news-event-v3-dev-20261010`에서 native schema 3 전체 생성·봉인·원격 상태·독자 표면과 평가·출처 도구를 구현했다.
원격 `55c00fc8`의 UI·sector 변경을 함께 보존했다. root의 기존 dirty/untracked 파일은 건드리지 않았다.

구현 `8532d90b`, 통합 `cf704b9a`, 경계 수리 `703bbb1d`, 최종 renderer `ca631e24`.
[구현·검증 증거](../../aidlc-docs/construction/event-news-v3/implementation-evidence.md),
[독립 리뷰](../code-reviews/2026-10-12-event-news-v3.md), [AC 대조](../cross-checks/2026-10-12-event-news-v3.md).

u168/u169/u170 native 구현 단계는 완료했다. u171 viewport, u172 실제 사람·성능·운영 수용,
u173 private parser capture와 source 준비는 대기 항목으로 남겼다. default2/preview3/activefalse를 유지하고
실제 corpus0/12·slot0/8·예약0을 성공으로 바꾸지 않았다. [후속 실행 절차](../../aidlc-docs/construction/event-news-v3/private-acceptance-and-cutover-runbook.md).
