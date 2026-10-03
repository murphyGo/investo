# u159 독립 코드 리뷰

2026-09-27, baseline `c3f2e5ef`. 세 구현 packet과 parent 통합을 분리하고 두 번째 wave에서 작성자와 다른 검토자가 교차 검토했다. 모델/공개 품질, terminal 검사, parent 연결에서 발견한 P2 8건을 수정하고 원래 재현으로 독립 확인했다. Replay 독립 검토도 완료했으며 미해결 P1/P2는 없다. 전체 회귀 결과는 아래에 확정한다.

| 발견 | 교정 및 검증 |
|---|---|
| 다른 시장의 수집 성공이 현재 시장의 실패를 성공한 0건으로 변환 | 수신 시장 source outcome 및 실제 라우팅된 source 범위로 관측 pool을 제한한다. 외부 시장만 성공한 회귀는 collected failed/null 및 selected unknown이다. |
| 모든 구분의 hard 차단에서 구분별 사유 소실 | finalization error에 immutable 구분별 issue map을 운반하고 해당 구분만 hard 상태로 다시 계산한다. 미생성 sibling에 hard 사유를 전파하지 않는다. |
| hard 이유와 qualified 상태가 모순되어 공개 100% 집계 가능 | 모델 상태 우선순위와 공개 parser를 검증하고 aggregate에서도 재검증한다. 변조한 model_copy도 제외한다. |
| 숨긴 정상 품질 표 또는 중복 표가 페이지 parity를 우회 | 주석·fence를 제외한 실제 보이는 사건 섹션이 정확히 하나이며 canonical 값과 같아야 한다. |
| 선택 후 모두 삭제된 사건을 '선정 사건 없음'으로 표시 | '설명 충족 사건 없음'으로 수정하고 selected/omitted 수는 보존한다. |
| 숨긴 정상 TL;DR이 보이는 삭제 사건 재노출을 은폐 | 실제·기대값에 같은 visible projection을 적용한다. 중복 TL;DR/요약 prefix와 재노출은 hard 차단한다. |
| completed 분류·prompt·생성 count 0과 유효 사건 1개가 공존 | known classified는 selected 이상, prompted는 selected와 동일, generated는 검증 payload와 동일해야 한다. 미관측 단계의 null은 유지한다. |
| 이전 hard receipt를 다시 검사할 때 모순된 terminal count 생성 | prior hard reason과 observed unsupported count를 effective hard 판정에 포함한다. terminal count는 null이고 기존 hard 증거는 유지한다. |

검토 범주: correctness, 공개 입력 검증, 데이터 정합성, 오류 계약, 자원 제한, privacy, finalizer 소유권. Parent 교정은 105개 통합 회귀에서 확인했고, 품질 모델/페이지 교정은 독립 35개, terminal 교정은 독립 45개 테스트를 통과했다. 생성 실패도 실제 관측한 stage만 보존한다. confirmed receipt를 메모리에 먼저 기록하여 private trace 저장 실패나 후속 알림 실패가 게시 성공을 없애지 않는다.

offline mutation helper를 `src` 밖의 `scripts`로 옮겨 기존 production writer/seal architecture 제한을 유지했다. 실제 원격 대신 로컬 bare Git으로 remote baseline과 dirty local metadata 무시를 검증했다. live source/provider 및 운영 게시·알림은 실행하지 않았다.

## 최종 검증

Replay 독립 통합 테스트 32개 통과(4.04초). records SHA와 실제 Git `c286f500`의 과거 출력 18편 해시가 전부 일치했다. 실제 생성→finalizer→HTML→DTO 경로에 safety gate 대체가 없고 기대값은 정적 fixture에서 읽는다. fixture validation/예외는 원문 대신 닫힌 코드만 출력한다. 최종 전체 5652개 회귀가 416.33초에 통과했다. Ruff/format638, mypy282, 정책 검사 4종, strict MkDocs/Material 검사 PASS. 사람 의미 검수는 코드 리뷰와 구분하며 pending 상태다.
