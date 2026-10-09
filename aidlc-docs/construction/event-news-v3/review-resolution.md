# Event/news v3 — 문서 독립 검토와 반영

**Date**: 2026-10-10. **Status**: 문서 검토·수정 완료. 설계 승인, 구현 합격, 사람 의미 수용, 운영 전환은 아직 기록하지 않았다.

## 검토 범위와 방식

두 writer가 u168/u170과 u172/u173을 나누어 작성했고 부모가 공통 계약, u167/u169/u171, 세 등록 문서를 통합했다. 작성자와 다른 두 reviewer가 실제 코드와 설계·계획·등록을 read-only로 검토했다. 한 writer는 파일 작성 뒤 사용량 제한으로 최종 보고에 실패하여 부모가 파일을 직접 확인하고 통합했다.

product reviewer는 u169/u171, 요구사항과 최종화·시각·알림·회고 경로를 확인했다. foundation reviewer는 u167/u168/u170/u172/u173과 입력·identity·상태·평가·source 경계를 확인했다. reviewer의 지적을 부모가 실제 코드에서 재확인하여 아래 수정에 반영했다. 수정된 전체 문서에 대한 마지막 통합 검증은 부모가 수행했으며, 두 reviewer가 최종 수정본을 다시 합격 판정한 것으로 기록하지 않는다.

## 반영한 지적

| 지적 | 최종 결정과 위치 |
|---|---|
| 과거 v3 사건·digest·당시 상태의 복원 계약 부재 | [C5a](contracts.md#c5a-공개-projection과-다음-실행의-복원): 공개 sidecar, Markdown/projection hash, 동일 transaction, u171 archive reader와 누락·불일치 처리 |
| 본문 visual의 sealed 입력 순환 | [C5](contracts.md#c5-finalizercompatibility와-영구-이력--u169): EventVisualInput 선언과 E1 staging, survivor used-only 선택 |
| OG와 본문 자산의 실행 순서 혼동 | 기존 pipeline의 post-seal write_og_card를 확인. OG는 reader-page transaction artifact로 유지하고 본문 rewrite는 금지 |
| 실패 availability와 absence의 중복 | [C4](contracts.md#c4-전체-문서-모델생성렌더링--u169): draft/view는 normal·quiet·source_limited, 실패는 기존 generation_absent/trust_blocked outcome |
| 가격 기준일과 뉴스창 handoff 부재 | C4/C5a: 봉인된 price_reference_date·price_time_basis·news_window; 달력 추론 금지 |
| public 하위 타입과 private ref 혼재 | C5a: public event/fact/digest/follow-up/asset 타입, 검증 locator projection; chunk text 제외 |
| 유효 본문이 있고 digest만 없는 표면의 표시 차이 | C5a/u171: digest→같은 terminal headline→사건 0건일 때 availability |
| 같은 값의 서로 다른 metric fact 병합 가능 | [C2/C3](contracts.md): 성분별 ContextFactDraft binding, 숫자 metric_key_hash 필수, revenue/net_income 음성 fixture |
| 늦게 발견한 공식 occurrence alias 유실 | [u168](../u168-canonical-event-identity-and-fact-delta/design-brief.md): hash-only occurrence_aliases 저장, 기존 ID 유지, alias-only delta/freshness 0 |
| remote receipt가 actor/object/action 역할 상충을 판별하지 못함 | u168: occurrence key와 독립적인 canonical_tuple_hash, 충돌 시 자동 병합 금지 |
| 원문 label 120자와 긴 이름 본문 수용의 충돌 | u168: 원문·display 240자, headline/digest 상한과 독립; 임의 약칭 금지 |
| closed_at과 push 완료 시각의 불가능한 사전 결속 | [C6](contracts.md#c6-story-state와-후속-확인--u170)/u170: 고정 observed_clock, 원격 확인 후 retention authority, 실제 확인시각은 PublishReceipt |
| 예정 발표와 actual 결과가 별도 event인데 같은 occurrence만 해결 허용 | u170: source-backed ResolutionTarget으로 release/thread·issuer·period·metric·status를 명시 연결 |
| foundation DoD가 downstream renderer 완료를 요구 | u167/u168 등록: typed boundary·buffer·ledger로 foundation 완료, u169/u172의 reader 수용은 후속 통합 |
| 모든 무효 digest를 hard 실패로 기대 | [u172](../u172-real-event-semantic-acceptance-and-cutover/design-brief.md): 표현 실패의 국소 제외와 unsupported claim의 original hard finding을 분리 |

공통 EventAssetImpact 선언을 u169로 옮기고 u171은 matcher만 구현하여 역방향 의존을 제거한 사항도 부모 통합에서 반영했다. 새로운 source 확보, 사람 점수 또는 runtime 합격을 문서에서 생성하지 않았다.

## 문서 검증

7개 유닛의 단계 수 8/8/9/8/8/9/7과 세 등록 문서의 단일 등록, 필수 계획 항목, 상대 링크·anchor, 의존 그래프, 미결 placeholder, 새 문서와 기존 diff의 whitespace를 검증한다. 실행 결과와 파일 목록은 작업 workflow의 verification.json에 보관한다.

이번 변경은 aidlc-docs와 docs의 Markdown뿐이다. 구현 테스트·provider 호출·viewport·production acceptance는 수행하지 않았다. MkDocs의 docs_dir는 site_docs이며 이 변경은 사이트 출력에 포함되지 않으므로 build를 실행하지 않았다.
