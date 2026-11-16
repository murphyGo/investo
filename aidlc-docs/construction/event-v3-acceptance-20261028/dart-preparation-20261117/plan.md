# DART shared preparation·관측 최신성 연결

사용자의 “진행해줘”를 u173 Step4/u184 Step5의 다음 구현·검수 승인으로 적용한다. 이전 commit/push/private probe 승인을 재사용한다. 운영 전환 전체나 사람 인수를 자동 승인하지 않는다.

## Stage Decision / 기능·NFR

Functional Design/NFR Requirements: Required. 기존 FR-001/017/024·NFR-002/003/005/008·R10/R13 및 u161 공유HTTP owner를 아래 계약으로 구체화한다. 기존 수동 원문 probe를 production fetcher로 재사용하지 않는다. 새 provider/키/SDK/LLM/공개 raw 저장소는 없다.

### 단일 수집 경로

prepare_event_evidence → enrich_event_evidence의 동일 owner 안에 DART 전용 typed 분기를 추가한다. HTML EnrichmentSource/SourceQualification4종은 그대로 두고, 별도 DartTransportQualification을 명시적으로 전달해야만 DART 요청이 가능하다. 현재 slot matrix canonical SHA와 DART row의 parser/version/fixture/source-code 승인 근거를 대조한다. 승인 fixture hash를 새 runtime context의 hash로 재사용하지 않는다.

EnrichmentQualification의 선택적 DART 필드는 없을 때 직렬화에서 제외해 기존 JSON/policy hash를 보존한다. preview source 선택·qualification hash·DART transport·slot matrix가 모두 맞아야 한다. default off/Fed-only preview/active capability false는 유지한다. 공통 경로에 코드를 연결해도 scheduling/production pin·게시·알림은 변경하지 않는다.

### 최신성·원문

기존 item의 숫자형 회사코드/공시번호/정확한 viewer/지원 report form으로 요청을 제한한다. 고정 list.json에 corp_code/접수일/last_reprt_at=Y/page1/100을 요청해 완전한 한 페이지와 target 유일성·회사/접수일·기존 adapter 정규화 identity를 대조한다. rm은 유·코·채·넥·공·연 조합만 비상태 표지로 허용하며 정/철/미지문자/누락·비string은 닫힌 실패다. 실패 시 원문 요청0회이며 다른 접수번호로 교체하거나 추가 페이지/URL을 따라가지 않는다.

통과 후 document.xml을 한 번 요청하고 기존 dart-cb-correction-6.4-v1의 ZIP/XML/회사/공시/정정후/current-series/단위/날짜 및5slot refs를 검증한다. published=date, occurred/announced=unknown, 마지막byte의 실제 수신UTC를 사용한다. 공개 계약은 두 endpoint의 atomic snapshot을 보장하지 않으므로 결과는 ‘목록 응답 시점의 관측 최신성 검사 통과’뿐이며 전 기간 최신/현재 발행 완료/영구 미정정의 증명이 아니다.

### 실패가 기사로 재유입되지 않는 경계

NormalizedItem에 source-neutral strict event_input_blocked flag를 추가하고 false는 직렬화에서 제외한다. 명시적 DART 경로를 선택하면 모든 DART 항목을 기본 차단하고 실제 검증에 성공한 항목만 해제한다. quota 밖/unsupported/예산·인증·조회·parser 실패도 원래 title/summary/url/raw_metadata를 보존한 채 차단한다. HTML fallback과 opt-in하지 않은 legacy 경로는 그대로다. generic event selector는 차단항목을 classifier 전에 제외하고 availability는 source_limited로 남긴다. 실제 자료가 부족한 실행을 news-rich나 사람 표본으로 세지 않는다.

### 실행 예산·보안

목록+ZIP 두 요청은 기존 전체run6HTTP/동시2/소스2items/공유20초 안에서 차감한다. DART는 redirect0/retry0, 전체GET8초·실제raw500KiB, ZIP 압축/총해제500KiB·single exact XML·20knodes/depth256·defusedxml/UTF8/credential echo 거절을 재사용한다. HTML parser의 일반 ZIP 금지는 유지하고, 이 예외는 DART typed 분기에만 적용한다. 소스5종×2후보를 수용하도록 bounded outcomes만8→10으로 조정하며 HTTP 상한은6 그대로다.

API key는 source HTTP owner가 기존 env에서 읽어 고정 endpoint에만 주입한다. key 포함 URL/exception/provider message/raw는 공개하지 않는다. 기존 canonical secret log filter를 HTTPX/httpcore emitting logger에 idempotent·thread-safe하게 설치해 transport 기록을 닫힌 marker로 바꾼다. 전역 log level은 바꾸지 않으며 취소 시 모든 task를 수거한다. 결과 trace는 allowlisted clock/hash/count/closed state만 갖는다. private 진단은 ignored0700/0600·recipient preflight/ciphertext1일을 사용한다.

### 실제 검증과 잔여

새 수동 private 진단은 동일 prepare_event_evidence를 호출하며 모델/게시/알림/ledger/cursor0이다. 기존 superseded 공시는 최신목록 검사에서 원문0회로 거절되는지 확인한다. 최신 지원 후보가 필요하면 별도 bounded collection을 기록해 원래 target을 몰래 치환하지 않는다. positive runtime body가 확보되지 않으면 runtime qualification0을 유지한다. local3/8·human0/12·상위 단계 미완료를 성공으로 바꾸지 않는다.

## 실행 계획

- [x] 1. 공통 HTTP owner·slot/transport·최신성·기사 차단·FD/NFR 계약을 확인하고 기록한다.
- [x] 2. backward-compatible typed policy/trace/차단 flag와 DART source helper·공유 HTTP 분기를 구현한다.
- [x] 3. prepare/preview 및 generic event selector·source_limited 경계를 연결한다.
- [x] 4. 혼합quota·secret/cancel·JSON/ZIP/parser·최신성·legacy hash·기사 재유입 회귀와 독립 QA를 통과한다.
- [ ] 5. exact CI 후 동일 경로의 비게시 실제 진단을 실행하고 원문/clock/trace를 독립 대조한다.
- [ ] 6. runtime 판정을 증거대로 기록하고 session/cross-check/state/audit 및 승인 범위를 전달한다.

## 공식 계약

[목록 API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)의 last_reprt_at·접수일·rm, [원본 ZIP](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003), [제한된 자료 추출 안내](https://opendart.fss.or.kr/intro/main.do)를 사용한다. 전체 raw 문서/이미지/서명/첨부의 공개 재배포 권리로 확대하지 않는다.


## Native field paragraph

원래 XML parser/오프라인 fixture hash는 그대로다. 생성된25줄의 field projection은 native passage6개 한도에서 일부가 탈락하므로, 별도 projection_version=dart-field-paragraph-v1이 LF만1:1 space로 바꿔 ≤1,200자/한 문단으로 구성한다. 새 EvidenceDocument/revision/native2 context를 만들고 각 ref는 원래 title/summary/detail source locator에 대응시켜25refs 원값을 다시 검증한다. 29XML binding은 원래 parser에서 결속한다. 정책 max_excerpt_chars와 transport max_projection_chars 중 작은 값을 넘으면 전체를 거절하고 잘라내지 않는다. 전체 문서 평탄화나 과거 fixture hash를 새 runtime hash로 재사용하지 않는다.
