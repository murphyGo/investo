# u157 독립 코드 리뷰

2026-09-27, baseline 04978d81. 구현 worker와 다른 reviewer가 publication, parent integration, foundation 경계를 검토했다. 두 wave 안에서 발견된 항목을 수정하고 failure-injection 회귀 테스트를 추가했다.

| 발견 | 조치와 증거 |
|---|---|
| P1 무관한 staged 파일 동반 게시 | transaction 밖 index 경로 pre_commit 거부; local bare Git와 index byte 보존 테스트 |
| P2 private receipt 부분 쓰기 | temp write/flush/fsync 후 atomic exclusive link; write/fsync/install 실패 후 재시도 |
| P2 cancellation이 pre_commit phase를 숨김 | worker terminal error 별도 보존; pre/post cancellation의 서로 다른 복구 결과 |
| P2 remote 확인 후 sink 실패가 게시 실패가 됨 | remote_confirmed 유지, 내용 없는 경고로 diagnostic 실패 구분 |
| P2 rebase timeout 상태 미정리 | 총 deadline 안에 cleanup 예산 예약, abort/HEAD 검증, 불확실하면 unknown 및 추가 push 금지 |
| P2 v2 macro/section 맥락 손실 | 기존 macro payload·필수 IDs 및 section legend 전달 |
| P2 추적용 URL 중복이 source cap 소비 | E1 canonical 문서/revision key로 중복 제거 |
| P2 중복행이 round-robin 위치 소비 | lane slicing 전에 canonical 중복 제거; 다중 source 포화 fixture |
| P2 비필수 actual 발표 reservation 누락 | 명시적 실제 발표도 예약·shadow 진단에 포함; inferred 월간 배경/예정은 구분 |
| P2 병합 후 새 사실이 repeat으로 제외 | 병합 facts 전체와 committed baseline으로 novelty 재계산 |
| P2 날짜 보강이 새 사건 ID 생성 | semantic tuple+동일 alias+비충돌 날짜로 canonical 유지; 후속 공식 문서까지 검증 |
| P2 unknown timing이 supported | detail_limited 강제 |
| P2 동일 fact ID의 상충 status 마지막값 승리 | 실제 값/상태/period/unit 충돌 거부, 동일 fact만 collapse |

검토 범주: correctness/data integrity, architecture, resource/performance, security/error contract, tests/compatibility. 새 네트워크 API·유료 API·LLM 단계는 추가하지 않았다. 단순 헤드라인 키워드로 글로벌 사건을 승인하지 않는다. 원문은 private generation input이며 공개 history에는 해시만 저장한다.

판정 Pass. 전체5415 및 최종경계61, 통합129 테스트 통과; 남은 P1/P2 없음. 운영 활성화 및 이후 u158/u159 소비자는 이 리뷰의 완료 주장에 포함하지 않는다.
