# DART 현재 응답·실제 수신 clock 검증

u173 Step4/u184 Step5의 후속 substep. 사용자의 2026-11-16 “진행해줘”를 현재 목록 응답과 원문을 다시 수집해 검증하는 승인으로 적용한다. 기존 커밋·푸시·private probe 승인을 재사용한다.

## Stage Decision

Functional Design/NFR Requirements: Required. 아래 계약으로 기존 parser 설계를 확장한다. FR-001/017/024, NFR-002/003/005/008, R10/R13 및 기존 private probe/암호화 계약을 재사용한다. 신규 provider/secret/production HTTP 권한은 없다. N184의 live HTML-only/ZIP 금지는 그대로다.

## 계약

검수한 과거 정정공시20261027000337을 회사01230255/접수일20261027로 공식 list.json에서 새로 조회한다. 이것은 현재 시점의 과거 공시 응답이며 오늘의 새 사건이나 최신 정정 여부의 증명이 아니다. 한 페이지100건·total_page1·정확한 회사/접수일/공시번호의 유일한 행만 허용한다. 목록 내용은 XML이나 이전 capture에서 채우지 않는다. 기존 adapter의 date_precision 정규화 후 document.xml을 한 번 요청하고 기존 versioned parser와 C2 refs/XML locator를 검증한다.

수집은 최대2GET/list+document, redirect0/retry0, 각 raw500KiB·8초, 전체20초 공유다. 원문 ZIP의 압축/해제500KiB·16member/단일 exact member·20knodes/depth256·defusedxml·UTF8·credential echo 거절은 기존 parser를 따른다. request 시작/최종 byte 수신 UTC와 monotonic 경과를 기록한다. received는 관측 수신 시각이며 publication/event 시각으로 승격하지 않는다. published=date, occurred/announced=unknown을 보존한다.

키는 기존 private GHA secret owner에서만 주입하고 HTTP 로그를 억제한다. provider message/error/URL을 공개하지 않는다. private 파일은 ignored0700/0600·exclusive/no-follow, 원문/목록/정규화 payload는 ciphertext1일만 업로드한다. 공개 영수증은 count/hash/clock/닫힌 code만 담는다. 별도 수동 workflow와 REVIEWED_DART_QUALIFICATION_SHA만 사용해 기존 production/preview pin을 보존한다. 무료 기존 API2calls 외 모델/게시/알림/ledger/cursor0이다.

성공한 진단만으로 production runtime_verified나 activation_ready를 선언하지 않는다. source matrix 결정은 실제 raw/hash/동일 parser/필수5slot/fixture/권리 범위를 독립 검토한 뒤 별도 기록한다. 실패·외부 다운로드 오류는 실패로 남기고 오래된 capture로 대체하지 않는다. 상위 u173/u184 및 사람/화면/성능/운영 수용은 별개다.

## 실행

- [x] 1. 이전 설계·원문·공식 API/추출 범위·운영 pin을 확인하고 이 계약을 기록한다.
- [x] 2. 기존 probe에 명시적인 qualification 모드와 실제 clock/목록 결속·private 결과를 구현한다.
- [x] 3. 합성 양성 및 pagination/identity/secret/HTTP/clock/refs/보안 음성 회귀와 독립 QA를 통과한다.
- [x] 4. exact code CI를 확인하고 별도 private 수동 workflow·전용 pin을 전달한다.
- [x] 5. 실제2GET probe의 암호문을 즉시 회수하고 새 목록/원문/수신 clock/5slot/29XML 근거를 검수한다.
- [ ] 6. 증거대로 qualification 판정·session/cross-check/state/audit를 기록하고 전달한다.

## 공식 근거

2026-11-16 재확인: [목록 API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001), [원본 ZIP API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003), [원문에서 필요한 자료 추출 안내](https://opendart.fss.or.kr/intro/main.do). [약관](https://opendart.fss.or.kr/intro/terms.do)은 이번 공개 fetch에서 timeout으로 재열람하지 못했다. 기존 제한된 사실 추출/private 보관 범위를 유지하며 전체 문서·이미지·서명·첨부 재배포 허가로 확대하지 않는다.


## 자격표의 출처 메타데이터 보완

실제 loader가 빈 DART evidence_domains 때문에 후보를 거절해, 공개 viewer dart.fss.or.kr만 canonical source metadata에 등록했다. 기존 domain guard를 완화하지 않았다. 이 메타데이터는 출처 집계/자격표 locator 검증에 쓰이며 live body source/selector/EnrichmentSource에는 DART를 추가하지 않았다. 정적/집중 검사와 독립 검수 후 local3/runtime0의 자격표 및 이 보완에 대해 별도 exact CI를 확인한다. 새 HTTP 재실행은 필요 없으며 실제6ac의 parser/runner bytes는 그대로다.
