# u157 요구사항 교차 검증

2026-09-27. 범위: 승인된 u157의 E1–E5/E9–E11, AC-157.1–7, NF1/2/3/6/7/9/10. 판정 APPROVE (u157 코드 범위). 전체5415(377.62초), 통합129, 최종경계61 테스트와 Ruff/format/mypy/정책/문서/Material 검사 통과.

| AC | 구현 및 검증 증거 | 판정 |
|---|---|---|
| 157.1 | event_evidence/selection; 숫자 없는 휴전·발언·제품 양성, background/repeat 음성, 순열 불변 | Pass |
| 157.2 | event_input; 1000건, canonical URL 중복, source/total/lookahead cap, 명시적 P2 actual 예약; required actual 누락은 오류 | Pass |
| 157.3 | integration/test_event_prompt_budget; 가격14+뉴스2에서 뉴스2와 근거 보존, 실제②14행/8KiB | Pass |
| 157.4 | strict v2 parse; invalid IDs/span/revision/future/conflict, missing events unavailable; 예외 원문 제거 | Pass |
| 157.5 | source+Fed host+monetary/speech path 공유, native coverage 보존; unqualified war/Fed headline 거부 | Pass |
| 157.6 | 같은 v1 응답 off/shadow의 2개 prompt와 Briefing bytes 동일; preview/active는 모든 생성·발행 전에 차단 | Pass (u157 범위) |
| 157.7 | 두 제품 identity, 새 fact·공식 문서·날짜 보강, fixed remote SHA/7일 ledger, 실제 Git push/rebase/CAS/취소/rollback | Pass |

NF1/2/7/9/10은 기존 CLI 2단계·기본 off·기존 trust gate 및 source bounds 유지로 검증한다. NF3 결정론적 경로는 benchmark_event_selection.py의 1000건/10회 p95 57.239ms로 200ms 예산을 통과했다. 운영 전체 p95와 DEBT-090, 5개 scheduled shadow 및 active 게시/알림/Pages는 별도 운영 증거가 필요하며 완료로 표시하지 않는다.

u157에는 Stage2 소비자 API와 opt-in publication transaction까지 제공한다. v2 생성·terminal survivor·summary의 실제 소비는 계획된 u158/u159 범위이므로 현재 차단한다. FR-023 전체 체크박스를 이 foundation만으로 완료하지 않는다. 별도 미해결 기술부채는 추가하지 않는다.
