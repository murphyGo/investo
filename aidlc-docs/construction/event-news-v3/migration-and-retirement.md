# Event/news v3 — 폐기와 전환

**Date**: 2026-10-10. **Status**: 목표 계약. 실행 코드와 운영은 아직 변경하지 않았다.

## 폐기·대체·유지 결정

| 기존 계약·기능 | 결정 | 대체 기능과 구현 owner |
|---|---|---|
| 신규 문서의 필수 ①~⑦와 6개 자유 본문 | 폐기 | EventEditionDraft 하나와 사건·context·후속·참고 모델, u169 |
| 가격표가 요약보다 먼저 나오는 순서 | 폐기 | 사건 요약 우선, 시장표는 접힌 참고 영역, u169/u171 |
| 정확히 3개 요약과 부족분 fallback | 폐기 | 유효 digest 0~3개와 명시적 availability, u169 |
| 본문 첫 문장 80자와 주체·대상 원문명 동시 포함 | 폐기 | source-backed entity, 본문 600자·요약 140자 독립, u168/u169 |
| 의미·반응 ref를 identity/fact ref의 부분집합으로 제한 | 대체 | 같은 사건의 독립 역할 chunk/ref, u167 |
| detail_limited 하나로 여러 부족 원인을 통합 | 대체 | 품질 vector와 축별 reason; 과거 카운트 의미는 보존, u167/u172 |
| 원문 표현 변경을 실제 변화로 취급 | 대체 | metric·기간·단위·상태를 보존한 canonical fact delta, u168 |
| 7일 hash 이력만으로 사건 연속성 제공 | 확장 | 30일 identity와 근거 있는 장기 상태·질문·해결, u168/u170 |
| 이름·ticker 재등장 또는 일정 경과에 의존하는 상태 추론 | v3에서 사용 금지 | 종류별 전이와 명시적 resolution evidence, u170 |
| 새 발표 없는 월간값·주간 잔액의 매일 headline 승격 | 폐기 | 사건 관련성이 없으면 날짜가 있는 참고 자료로 배치, u169 |
| macro·thesis·conclusion·driver·caution의 중복 상단 블록 | v3에서 폐기 | 같은 내용을 사건과 context에서 한 번 설명, u169/u171 |
| 무관한 hero와 가격·신뢰도 이미지의 자동 상단 삽입 | v3에서 폐기 | 기본 hero 없음, 관련 이미지만 사건 뒤; 가격·품질은 참고, u171 |
| 가격·ticker 매칭만으로 확정하는 뉴스 영향 | 폐기 | 사건 fact와 자산의 mechanism·condition, u171 |
| v3를 위해 7개 빈 section을 만드는 bridge | 금지 | discriminated payload와 sealed accessor, u169 |
| 과거 archive·URL·자산 | 유지 | read-only historical reader, u171/u172 |
| numeric·entity·actual/forecast·freshness·compliance·면책 | 유지 | 새 schema의 claim/region adapter와 기존 gate owner |
| u144 단일 finalizer·SHA·seal·asset·remote·부분 발행 | 유지 | 같은 owner와 lifecycle에 v3 variant 추가 |
| u160 뉴스창·u161 body HTTP·u165 source 상태 | 유지, 별도 수용 | v3 mode 선택으로 자동 활성화하지 않음 |

위 표는 구형 표현·생성 계약의 폐기 결정이다. 과거 완료 기록과 신뢰·출판의 불변조건을 보존한다. 현재 코드가 실제로 하지 않는 동작을 이미 제거했다고 주장하지 않는다.

## M1. 문서와 foundation

FR-024/025와 공통 설계를 목표 계약으로 등록한다. FR-002/009/023의 완료 AC는 v1/v2 이력으로 유지하고 v3의 대체 범위를 표시한다. u154 계획에도 legacy·전환용 역할과 u169/u171의 v3 소유권을 구별한다.

u167/u168은 typed foundation을 구현하며 기본 schema2와 기존 bytes를 유지한다. u168이 shared story DTO를 먼저 선언하여 u169/u170의 순환을 막는다. 기존 ledger를 새 semantic fact로 자동 변환하지 않는다. 이전 근거는 명시적으로 재주석한 replay 입력으로만 사용한다.

## M2. 비게시 v3와 단일 문서

u169는 같은 두 LLM 단계 안에 schema3, EventEditionDraft, PublicEditionView, 단일 finalizer를 구현한다. 한 시장·한 실행에서 한 schema만 생성한다. 동일 날짜에 두 본문을 public archive에 쓰지 않는다. preview는 게시·알림·production receipt·ledger·cursor 쓰기 0회다.

u169는 최종 Markdown hash와 연결된 공개 projection sidecar도 제공한다. u171의 다음 실행·회고는 이를 검증해 당시 사실과 상태를 복원한다. private chunk나 실패 문장은 저장하지 않는다. sidecar와 본문은 같은 publication transaction/CAS/rollback에 포함한다.

u170이 typed proposal·terminal delta와 원격 ledger를 연결하고 u171이 독자 표면을 전환한다. 본문 visual은 봉인 전에 stage하여 survivor에 맞는 자산만 선택한다. OG는 봉인된 공개 필드로 기존 publish transaction에서 생성한다. 본문 봉인 후 rewrite는 없다.

## M3. 시장별 운영 전환

u172가 정확한 SHA의 code/full CI, 균형 합성 36개, 실제 private 문서 12개, 사람 5/5, fact 보존 100%, 근거 없는 사건·인과 0, 실제 두 단계 호출·예산·성능, viewport와 source 범위를 수용한다. 명시적 release 지시와 reviewed SHA·policy·시장 allowlist를 확인한 뒤 시장별로 전환한다.

각 시장의 최초 3회 실제 예약 발행에서 게시·알림·해당 commit의 Pages·ledger를 확인한다. cursor가 비활성이라면 변화 없음으로 확인하며 활성화를 추정하지 않는다. 한 시장 실패와 유효 sibling 성공을 분리하고 코인은 자체 수용이 필요하다. 전체 프로그램의 시장 수용은 세 시장 모두 accepted일 때 완료한다.

## M4. 정착과 구형 생성 제거

세 시장 accepted와 최소 10회의 서로 다른 실제 v3 예약 관찰 뒤 u172 Step9의 별도 reviewed cleanup을 수행한다. 부분 실패·제외 시장·알림 실패를 별도 집계한다. 수동 replay·재시도·취소·skip으로 횟수를 채우지 않는다.

v1/v2 generator, 6개 자유 본문, 구형 Stage2 template, 활성 legacy rewrite, 빈 bridge, 옛 generated model로 돌아가는 표면 fallback을 기본 runtime에서 제거한다. 기본 schema는 3, 정상 생성은 active/schema3, 비게시 검증은 preview/schema3다. 폐기한 off/shadow/schema2 요청은 명시적으로 거절한다.

과거 archive reader와 정적 출력·URL·provenance, 이전 reviewed commit 전체 rollback은 유지한다. 제거 전에 v2 합성 terminal HTML/DTO snapshot과 SHA를 고정하고 이후 검사는 historical reader/output 회귀로 바꾼다. 구형 generator 전체 replay는 보관한 이전 commit에서만 수행한다.

cleanup 코드에도 full/static/policy 검사, 독립 리뷰, v3 recorded-response byte parity를 적용한다. 실제 runtime pin과 policy를 다시 읽은 뒤 cleanup_complete로 표시한다. 관찰 횟수만으로 코드나 환경변수를 자동 변경하지 않는다.

## M5. 복구와 병행 작업

전환 중과 cleanup 뒤의 rollback은 이전 reviewed commit과 policy 전체로 복귀하는 방식이다. identity/story의 신규 경로를 구형 코드가 잘못 읽지 않도록 분리한다. 기존 archive와 확정 metadata 이력을 reset하거나 force push하지 않는다.

최종 main `48762793`의 u154/u165/u166 완료 기록과 u156 예약 owner는 별도 작업의 결과다. 이번 문서는 최신 main으로 갱신하면서 그 기록을 보존했다. 구현 직전 current main과 대조하고 이미 완료된 공통 기능을 재사용한다. 이번 문서 작성에서는 다른 branch를 수정·완료·통합하지 않는다.
