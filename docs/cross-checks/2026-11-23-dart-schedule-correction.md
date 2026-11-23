# DART 일정 정정 파서 검수

범위는 기존 u173 Step4/u184 Step5의 보관본 분석과 versioned offline parser다. [계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-20261123/plan.md), [결과](../sessions/2026-11-23-dart-schedule-correction.md), [증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-20261123/evidence.json)를 대조했다.

| 요구사항 | 근거 | 판정 |
| --- | --- | --- |
| FR-001/017/024·실제 원문과 필수 항목 | retained5파일 hash 확인; 7개 정정행/9개 주석 요소; 5slot/22refs/76XML binding 원문 역검증 | 오프라인 통과 |
| FR-024·정정 전후·current-series·예정 상태 | 본문 field 유일성/같은 표·단위·날짜·정정 후 값 대조; 완료 상태/다른 차수/행 변조 거절 | 통과 |
| FR-017·정확한 source locator와 native 전달 | XML path/attribute·digest, native3chunks·661자·모든 ref 동등 | 통과 |
| NFR-003·미지원/부분 조건 차단 | exact7행, 주석 전체/구조, PGBRK/추가 문구/tail/parent text 거절 | 통과 |
| NFR-005/006·호환성과 검증 | 기존 가격 fixture item/context bytes·refs·bindings 동일, 별도 새 진입점; 회귀/PBT | 통과 |
| NFR-002/008·비용/원문 경계 | 새 HTTP/모델0; 기존 ZIP/XML cap; actual raw는 ignored0700/0600; 공개 합성 fixture | 통과 |
| 기존 source/transport 자격 유지 | ops 두 파일/기존 fixture hash 불변, 기본 파서의 새 양식 거절 | 통과 |
| 새 버전 source/runtime 자격·live 연결 | 아직 실행/승격하지 않음 | 미완료 |
| u172 실제 기사·사람·화면/성능·예약 발행 | 이번 범위 아님; 기존 수용 횟수 유지 | 미완료 |

독립 검수는 Correctness/Safety/Reliability/Maintainability/Test Coverage 모두 Pass, 잔여 C/H/M/L0이다. Medium2건(주석 끝/혼합 text 누락, 평탄 표 구조 충돌)을 수정하고 회귀로 확인했다. 독립 최종 집중150PASS/1.92초, 변경 범위 Ruff/format·소스 strict mypy PASS. Root 최종 통합 결과는 기계 증거의 validation에 기록한다. 전체 저장소 pytest나 원격 CI를 실행했다고 주장하지 않는다.

Root 최종 관련433PASS/16.92초, 변경 범위 Ruff/format, 프로젝트 `.venv` 전체소스 mypy384파일, SDK/유료API guard, strictdocs5.71초, diff-check PASS. 신규49cases에는 날짜 생성값50개를 다루는 PBT2개가 포함된다.

PBT Partial: source 날짜 변환의 원문 binding/동일 ref/자원 한도/반복 출력 불변성과 본문 단독 변조 거절을 생성값으로 확인했다. 새로운 직렬화 규약은 없고 기존 context 모델을 재사용한다. 전체 원문→제한 projection은 의도적인 손실 변환이며 원문을 재구성한다고 주장하지 않는다.

**판정:** 새 양식의 bounded offline 지원 완료. source qualification·운영 전환과 상위 유닛 전체는 미완료다. 기본 v1 및 기존 local3/8·runtime0·activationfalse·human0/12·v3예약0을 유지한다.
