# u159 요구사항 cross-check

2026-09-27. E8/E11, B8/B11 및 AC-159를 실제 stage receipt, 봉인 문서, 공개 이력/페이지, 원격 확인 집계와 대조했다. 코드 검증과 운영 수용 기준을 구분한다.

| 기준 | 결과와 증거 |
|---|---|
| AC-159.1 실제 내용 검사 | PASS. `test_event_quality.py`와 replay의 marker-only/URL-only/필수 사실 제거/요약 재노출을 실제 finalizer 후 검사한다. 숨긴 정상 TL;DR 및 중복 요약 우회도 차단한다. |
| AC-159.2 정직한 분모와 상태 | PASS. `test_event_stage_trace.py`, `test_event_publication.py`, `test_event_quality.py`에서 수집 실패/성공 0/미분류/부분 게시/알림만 실패를 분리한다. 전부 차단된 bundle도 구분별 hard 이유를 유지한다. |
| AC-159.3 이력·페이지 일치 | PASS. 역사 필드는 null이고 새 공개 counts는 봉인 문서 expected와 일치한다. terminal 표와 remote-confirmed 집계의 기준을 명시한다. 숨긴 정상 표, 중복 표, 서로 일치하지만 terminal과 다른 값은 거부한다. |
| AC-159.4 golden 구조·의미 | 자동 회귀 PASS, 사람 의미 수용 PENDING. 12개 그룹/25개 변형의 고정 must_include/required facts/forbidden claims를 검사한다. AI-authored synthetic 기대값이며 사람이 작성·검수한 5/5 기준 충족은 아직 주장하지 않는다. |
| AC-159.5 terminal/DTO 일치 | PASS. 실제 HTML의 필수 사실과 알림 DTO exact 값/순서를 대조한다. 본문 4개·5개는 DTO 3개이며 삭제된 사건은 재노출되지 않는다. |
| AC-159.6 privacy·호출 수 | PASS. 공개 품질에는 count/status/closed code만, private trace에는 bounded hash receipt만 저장한다. replay는 기록된 두 단계 응답을 사용하며 외부 호출·게시·파일 쓰기를 금지한 통합 fixture를 통과한다. |

과거 18편은 경로·revision·SHA의 출력 inventory다. 원본 수집 입력 재생으로 간주하지 않는다. 금요일 가격 기준일의 주말 뉴스 포착 제한은 현행 기대값으로 명시하며 u160에서 개선한다.

## 운영 경계

비게시 preview는 실제 coverage를 반환한다. 기본 off, active capability false, dry-run metadata 비갱신을 유지한다. scheduled shadow 5회, 인간 의미 검토, active 첫 3회 게시/알림/Pages 및 실제 운영 end-to-end 성능은 미실행이다. AC-159.4의 사람 검수가 남아 있으므로 코드 완료를 운영 수용 완료로 표시하지 않는다. u145/DEBT-090 및 다른 유닛 상태를 변경하지 않는다.

전체 테스트 및 최종 정적 검증 수치는 유닛 `code/validation.json`에 기록한다.
