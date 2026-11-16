# DART 현재 응답과 실제 수신 시각 검증

사용자의 “진행해줘”로 u173 Step4/u184 Step5의 [후속 계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-qualification-20261116/plan.md)을 수행한다. 기존 전달 승인을 적용하며 production/preview pin은 보존한다.

## 구현과 검사

기존 수동 probe에 명시적 --qualify 모드를 추가했다. 회사/접수일로 좁힌 list.json의 한 페이지가 완전하고 동일 공시가 유일한지 확인한 뒤 기존 adapter의 date_precision 정규화와 document.xml·versioned parser·C2 refs·29XML locator를 결속한다. 실제 UTC 수신 시각은 마지막 byte 직후 기록하고 원문의 접수일/date precision과 구분한다. 후속 정정/철회 표지는 private 원본과 공개 closed status에 보존한다. 검수했던 과거 공시의 현재 응답이며 오늘 사건·최신 발행조건을 뜻하지 않는다.

최대2GET, 요청 전체8초/공유20초, redirect/retry0·각500KiB·기존 ZIP/XML 안전 한도를 적용했다. private0700/0600·exclusive/no-follow와 recipient preflight·ciphertext1일을 유지한다. 새 private 수동 workflow는 전용 REVIEWED_DART_QUALIFICATION_SHA만 사용한다. 기존 secret 하나 외 추가 secret/API/모델/게시/알림/ledger/cursor는 없다. 비용 영향은 기존 무료 OpenDART2calls와 수동 Actions job1회다.

집중144PASS/1.97초, Ruff/format870 및 source+script mypy371PASS를 확인했다. 독립 QA·exact CI·실제 source 실행 결과는 확인 후 아래에 갱신한다. 이 구현만으로 source/runtime matrix를 승격하지 않는다. 약관의 이번 공개 열람은 timeout이었고 기존 제한된 사실 추출/private 보관 범위를 확대하지 않았다.

## 수용 상태

현재 local2/8·runtime0·DARTblocked·human0/12·v3예약0·운영 미완료를 유지한다. actual 결과와 독립 검수 전에 후속 단계나 source qualification을 완료로 표시하지 않는다. N184의 live HTML-only/ZIP 금지는 변경하지 않는다.
