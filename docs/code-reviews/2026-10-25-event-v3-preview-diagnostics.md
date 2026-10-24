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

## Stage 1 source span 지시 보완

실제 미국 진단 preview가 `context.fact_invalid`를 보존한 뒤, 검증기가 이미 요구하던 세부 규칙을
Stage 1 지시에 추가했다. Unicode end-exclusive/1–240 codepoints, 숫자 token만의 value 참조,
matching metadata field와 actual/forecast/consensus 상태 구분이다. gate와 원본 buffer는 바꾸지 않았다.
whole-fact numeric ref 거부 후 같은 buffer의 올바른 numeric ref가 두 번째 시도에 성공하는 회귀를 추가했다.

별도 reviewer가 실제 Python slice·span validator·숫자 정규식·metadata field owner와의 일치를 확인했다.
독립 focused 104 PASS(57 native replay 포함), Ruff/format/diff PASS, 열린 P1/P2 0이다.
이 synthetic 결과로 실제 모델의 정확한 offending component나 개선 효과를 확정하지 않는다.

## 필수 actual과 실제 홈 회귀

후속 실제 preview의 `context.required_missing`에 따라 기존 required-item/actual fact와 metric/unit/period/status
proof 조건을 prompt에 명시했다. 회귀는 필수 event 전체 누락도 같은 budget의 재시도에서 거부하고 올바른
source-owned fact만 수용한다. 첫 prompt 변경의 실제 수용 성공을 주장하지 않는다.

원격 전체 CI가 찾은 홈 두 실패는 본문의 제한 문구가 짧은 요약에도 있어야 한다는 가정이었다.
해당 integration 검사를 실제 계약인 카드별 visible quality/data-quality와 발행본 canonical 상태 일치로
바꿨다. 링크·날짜·미발행 검사와 기존 unit의 품질 모순 거부는 유지한다. 로컬 집중 106 PASS를 확인했다.
독립 검토도 focused 125 PASS, 실제 directory/flat build와 품질 attribute/visible text/동시 상향/field 삭제
4개 변조 거부를 확인했다. 선택 요약의 한계 문구 보존 unit도 그대로 통과했다. 최종 이 diff의 열린 P1/P2는 0이다.
