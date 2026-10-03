# u160 독립 코드 리뷰

Baseline `f056fbde`. 첫 wave에서 window/커서, source adapter, 실제 pipeline/Git 통합 테스트를 분리하고 parent가 producer/finalizer/publication을 연결했다. 두 번째 wave에서 다른 작성자가 window, source, parent를 교차 검토했고 parent는 통합 테스트의 실제 경로·대체 경계를 검토했다.

| 발견 | 수정 및 재확인 |
|---|---|
| 커서 blob 전체를 수신한 뒤 크기 제한 검사 | 같은 고정 SHA의 regular blob과 크기를 먼저 검사한다. 원래 초과 크기 재현에서 show 호출 0회를 독립 확인했다. |
| 시계 역행 hold에서 미래 상대 확정 revision 삭제 | 실제 retention 만료분만 제거한다. 원래 clock hold 재현에서 ledger 동일·seen 1→1, 정상 시계 복귀 후 중복 제거를 독립 확인했다. |
| 1–3칸 들여쓴 fence 안 watermark로 sealed receipt 획득 | fence 문자·길이·들여쓰기·EOF를 처리한다. 기존 실제 finalizer 재현이 projection mismatch로 차단됨을 독립 확인했다. |
| House RSS의 HttpUrl 검증 손실이 parse count에서 누락 | 잘못된 URL을 손실 1회/partial로 기록하고 valid sibling을 보존한다. 무관/기간외 항목은 손실 0/unknown이다. 실제 adapter 원재현 5개와 신규 회귀 4개를 독립 확인했다. |

통합 중 crypto 선택적 preamble 영역에 watermark를 넣어 region이 겹치는 문제도 발견했다. 기존 assembly 소유자 안에서 가장 이른 선택적 pre-section 앞에 넣어 실제 3/3 positive fixture가 통과했다. writer/seal 수와 구조 gate는 유지한다.

검토자는 실제 pipeline/finalizer/E11 경로를 확인했으며 외부 source transport, 합성 LLM 응답 및 관련 없는 visual sidecar만 대체했다. custom generator가 plan만으로 소비를 주장할 수 없고 모든 source 실패는 생성 전에 중단한다. 로컬 bare remote만 사용하며 외부 Python socket 연결은 금지한다.

모든 P2 네 건은 작성자와 다른 검토자가 원래 재현으로 해소를 확인했다. 독립 window 61개, parent projection 11개, source 교정 59개와 실제 통합 20개가 통과했다. 미해결 P1/P2는 없다. 최종 전체 회귀 5798개가 462.55초에 통과했다. Ruff/format648, mypy286, 정책 검사 4종, strict MkDocs9.22s/Material도 통과했다. 운영 활성화는 수행하지 않았다.
