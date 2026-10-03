# u161 독립 코드 리뷰

Baseline `79b9f039`. qualification, evidence/model/helper, 실제 생성 통합 테스트를 분리하고 parent가 adapter/collection/CLI를 소유했다. 두 번째 wave에서 다른 작성자가 qualification, helper와 parent 통합을 교차 검토한다. Parent는 실제 통합 테스트를 독립적으로 읽었다.

실제 feed parse→CollectStage→GenerateStage→기존 producer→finalizer를 사용하며 정상 gate는 대체하지 않았다. char400–421의 특정 사실과 독립 금지 문자열을 관측하고, synthetic empty history와 source publication/event time 차이를 명시했다. 본문 보강 실패/성공은 원 item와 source outcome에서 독립적으로 확인한다. 통합9개 PASS, 이 테스트 packet에서 미해결 결함은 없다.

검토와 교정은 구현 wave 1회와 독립 review wave 1회 안에서 진행했다. 다음 P2를 같은 review wave에서 수정하고 원재현을 재검한다.

| 발견 | 교정과 검증 |
|---|---|
| 요청의 read-gap만8초여서 느린 streaming이20초까지 이어짐 | 전체 요청 예산도 min(8초, 잔여 aggregate)으로 제한. slow-stream/cancellation 회귀. |
| 잘못된 HTML marked declaration의 AssertionError가 보강 전체로 누출 | 해당 parser 오류를 selector unavailable로 격리. 원기사와 정상 sibling 보존. |
| 범위 밖의 최신 URL2개가 source quota를 선점 | qualification/selector/URL 적격성을 먼저 적용하고 실제 요청 후보를 source당 최신2개 선정. 부적격 진단도 남는 슬롯 안으로 제한. |
| 증거화 불가능한 기사 URL 하나가 정상 feed sibling까지 탈락 | 여섯 adapter의 entry-local ValueError만 격리. off bytes 유지, active 정상 sibling 유지. FOMC partial parse loss도 정확히 기록. 독립 실제 aggregator23개 PASS. |
| streaming에서 이미 풀린 gzip 본문을 Response 재구성 시 다시 해제 | decoded representation에서만 encoding/wire length를 제거. 정상 gzip의 내용/MIME/request 보존과 decoded size cap을 검증. |

source qualification은 독립 검토에서 미해결 P1/P2가 없었다. helper 교정 후 identity 포함81개, gzip·feed·통합104개가 통과했다. 전체 회귀5888개(464.69초)와 정적·정책·문서 gate가 통과했다. shared retry는 별도 작성자가45개 테스트와 identity/gzip/exact-cap/손상압축 네 경로를 확인했다. 최종 결과는 `code/validation.json`에 기록한다.

현재 운영 body activation은 false다. 공개 rights/hash 기록은 원문 공개가 아니며 source qualification은 실행 활성화와 구분한다.

독립 helper 검토자는 malformed HTML 원재현과 교정된 quota/identity81개(1.84초)를 확인했다. gzip 교정 후 원 검토자의 추가 실행은 결과 없이 중단돼 통과로 계산하지 않았다. gzip closure는 다른 독립 검토자의45개 테스트·별도 네 streamed 재현과 부모 전체5888개에 근거한다. 미해결 P1/P2는0개다.
