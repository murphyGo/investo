# Event v3 private preview 진단 검토

2026-10-25 KST. 실제 preview `40114529910`의 국내 분류 실패 manifest가 v3의 닫힌
`ContextEvidenceError` 사유를 누락했다. native 분류 오류는 기존 legacy 진단 매핑에 없었다.

`scripts/preview_event_briefing.py`는 실제 native exception의 정확한 문자열이 `ContextRule`의
13개 Literal 중 하나일 때만 `failure_code`와 단일 진단 코드를 보존한다. 원문·모델 출력·stdout/stderr는
계속 제외하며 위조 문자열과 list/dict 같은 비문자열은 공개하지 않는다. 생성 prompt, 재시도·예산,
검증 gate와 게시·알림·cursor 경로의 변경은 없다.

독립 reviewer의 판정은 **All Clear, 열린 P1/P2 0**이다. focused 22 PASS와 허용 rule 13개,
위조 값 8개, 비-native cause 3개 직접 probe를 수행했다. Security Boundary와 Error Contract를
검토했고 외부 호출·secret 접근·파일 편집은 하지 않았다.

private workflow의 schema 선택 8줄은 별도 리뷰를 통과했다. 기본값 2, 선택값 2/3,
quoted CLI 전달, private/main 제한, contents read, 기존 `queue: max`·auth cleanup·ciphertext 보관을 유지한다.
공개 reviewed template과 private queue 외의 bytes가 같다. 실제 native preview boundary 3시장과 parser/workflow
무변경 probe 5개도 통과했다. 운영 활성화와 사람 평가의 승인은 이 판정에 포함하지 않는다.
