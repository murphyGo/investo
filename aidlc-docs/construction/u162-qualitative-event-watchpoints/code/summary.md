# u162 정성 사건 관전 포인트

u152 `82c4e072`의 관측값 계약 위에 사건 관전 포인트를 추가한다. 협상 재개, 법안 의결, 서비스 출시처럼 가격 수치가 없는 사건도 검증된 출처의 실제 상태와 후속 확인 항목으로 표시한다. 현재 상태는 EventFact 원문이며 생성된 조건문이나 today_watch 자유문장을 사건으로 재분류하지 않는다.

`NumericWatchpoint | EventWatchpoint`는 kind discriminator로 구분한다. 사건은 현재 상태·사건/보도 시점의 정밀도·출처·다음 확인·검증된 의미를 표시한다. 같은 사건의 예정 fact가 있으면 다음 확인에 사용하고, 없으면 사건 종류별 닫힌 관찰 문구를 사용한다. 출처/의미/현재 상태가 적합하지 않으면 카드를 제외한다. 단독 예정 사건은 기존 일정 소유권에 남긴다.

기존 숫자 resolver/fallback의 전체 결과를 먼저 고정한다. 유효 사건이 있으면 사건 1개+정량 1개, 정량이 없으면 사건 최대 2개를 보여준다. 유효 사건 카드가 없으면 기존 정량 최대 6개/fallback 최대 2개와 제한 문구 계약을 유지한다. public WatchpointRenderResult 제약은 그대로이며 kind별 시도/표시/제한 사유는 private CompanionOutcome에 보관한다. 정량 attempted는 raw 문장 수가 아니라 검증된 numeric baseline 카드 수로 정의한다.

B8 bounded repair 안에서 사건 생존 여부를 반영해 카드·요약을 함께 정리하고 reindex한다. 전부 제거되면 같은 고정 정량 결과를 복원한다. 반복 최종화에서도 전체 정량 결과를 유지하도록, 사건 시도가 있었던 결과의 Briefing.today_watch에 numeric-only baseline을 보관하며, 사건이 전부 제거된 경우도 포함한다. 다음 pass는 canonical 숫자 카드/제한 문구 또는 기존 mixed 마커가 있을 때만 이를 기존 숫자 renderer에 돌려준다. 이 필드는 사건 생성기에 전달하지 않으며 봉인 이후 수정은 없다.

생성 단계는 region index가 비어 있으므로 기존 watchpoint 소유자의 정확한 원문 구간으로 숫자 검사를 먼저 수행한다. mixed cap으로 버릴 문장의 hard finding도 보존한다. 사건 카드의 마커·전체 내용·출처·시점을 편집 전과 terminal survivor 기준으로 각각 검증한다. 수치/entity/compliance/면책조항/partial sibling 검사는 유지한다.

반복 검증에서 발견한 용어 풀이 중복 제거의 숫자 접미사 충돌은 기존 event 전용 cosmetic 보존 경로에서 바로잡았다. canonical 채널 기준선과 사건 카드만 해당 편집으로부터 보호하며 신뢰성 검사는 전체 내용을 계속 확인한다. off/빈 선택 경로 및 기존 알림 DTO schema는 유지한다.

새 I/O·LLM·비용·활성화는 없다. 전체 gate, 독립 review/cross-check, 원격 전달 증거는 validation.json과 해당 보고서에 기록한다. 예정 shadow·실제 LLM 의미 평가·운영 활성화·게시/알림/Pages 검증 및 DEBT-090은 별도 상태다.

교차 리뷰는 사건의 detail_limited 상태와 실제 출처 링크 누락을 구분하도록 보완했다. 확인된 링크·fact·meaning이 온전하면 제한된 사건도 카드를 만들 수 있다. 실제 링크가 누락되면 source_locator_missing으로 제외하며 사건 자체가 제거됐다고 잘못 계수하지 않는다. HTML raw/숨김 컨테이너 안의 canonical 카드도 terminal 표시로 인정하지 않는다.
