# DART 자기주식 신탁계약 해지 결정 지원

사용자 “진행시켜”에 따라 기사 공급의 실제 부족을 해소하는 u173 Step4/u184 Step5 후속이다. 직전 실제 run45125524648의 DART25건에는 기존 CB 정정 지원 양식이 없었다. 현재 관측된 자기주식 취득 신탁계약 해지 결정2건의 원문과 계약을 먼저 확인하고 해당 양식에만 bounded 지원을 추가한다. 과거 공시를 현재 뉴스로 주입하지 않는다.

## Stage Decision

- Functional Design/NFR Requirements: Required, 실제 원문 확인 뒤 아래 닫힌 범위를 구체화한다. 기존 FR-001/002/017/021/023/024, NFR-002/003/005/006/007/008과 u184 공통 준비·private retention·인수 계약을 재사용한다.
- 새 provider/키/유료 API 없이 공식 OpenDART list.json/document.xml과 기존 secret owner를 사용한다. GitHub connector에 dispatch 기능이 없어 기존 인증된 gh 경로로 수동 진단을 실행한다.
- 기존 검수된 raw probe로 현재 공시2건을 각각1GET/8초·전체20초·압축/해제500KiB·defusedxml/credential-echo 거절 경계 안에서 암호화해 즉시 확보한다. 원문은 ignored0700/0600만 사용한다.
- 원문 확인 전 parser/rights/runtime qualification을 승격하지 않는다. 공식 양식·버전·고정 행/필드·issuer·계약금액/상대방/해지목적/일자/방법과 결정·실행 상태를 대조하고 합리적인 closed schema를 고정한다.
- 별도 parser/profile 및 전용 qualification으로 기존 price/schedule/terms 계약을 보존한다. 자동 parser fallback이나 제목만으로 기사 생성하는 우회는 없다. 적합한 candidate가 quota 전에 식별되는지도 함께 검증한다.
- 기존 공통 HTTP6회/20초/동시2/응답500KiB·native1200자 및 article 전역5call/최대1회수정 예산을 유지한다. source/Stage1/packet의 원문·조건·날짜·상태 refs를 보존한다.
- 현재 정확한 CI 코드에 대한 source qualification·공통 준비·비게시 article_v2를 검증한다. 별도 preview pin/workflow 조정은 이 검증에 필요한 범위만 수행한다. production/main·다른 pin·예약·게시/알림/ledger/cursor는 보존한다.
- 사람 사전 annotation·5/5·corpus12, viewport/성능, genuine 예약 인수를 AI 검수로 대체하지 않는다. quiet/source_limited/brief는 정상 상세 양성으로 합산하지 않는다.

## 단계

- [x] 1. 현재 공시2건을 기존 비공개 probe로 검사했다. sample1 원문 확보·구조 확인, sample2는 기존 안전 검사 차단으로 원문 미보관·원인 불명이다. 재요청/검사 완화 없이 양성1건 범위로 한정한다.
- [x] 2. 실제 구조에 맞춰 versioned parser/5slot/native/선정·자격 계약을 구체화한다.
- [ ] 3. 격리 checkout에 구현하고 실제 원문 재생·회귀·독립 코드 검수를 완료한다.
- [ ] 4. exact CI 뒤 실제 source preparation·비게시 기사 생성과 즉시 캡처를 검증한다.
- [ ] 5. 독립 실제 검수·상태/세션/교차검수 기록과 남은 인수 조건을 전달한다.

공식 근거: [공시 검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001), [공시 원본](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003). 원문 검증 결과에 따라 불확실한 세부 지원은 닫힌 상태로 남긴다.
