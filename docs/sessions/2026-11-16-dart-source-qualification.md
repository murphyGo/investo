# DART 현재 응답과 실제 수신 시각 검증

사용자의 “진행해줘”로 u173 Step4/u184 Step5의 [후속 계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-qualification-20261116/plan.md)을 수행한다. 기존 전달 승인을 적용하며 production/preview pin은 보존한다.

## 구현과 검사

기존 수동 probe에 명시적 --qualify 모드를 추가했다. 회사/접수일로 좁힌 list.json의 한 페이지가 완전하고 동일 공시가 유일한지 확인한 뒤 기존 adapter의 date_precision 정규화와 document.xml·versioned parser·C2 refs·29XML locator를 결속한다. 실제 UTC 수신 시각은 마지막 byte 직후 기록하고 원문의 접수일/date precision과 구분한다. 후속 정정/철회 표지는 private 원본과 공개 closed status에 보존한다. 검수했던 과거 공시의 현재 응답이며 오늘 사건·최신 발행조건을 뜻하지 않는다.

최대2GET, 요청 전체8초/공유20초, redirect/retry0·각500KiB·기존 ZIP/XML 안전 한도를 적용했다. private0700/0600·exclusive/no-follow와 recipient preflight·ciphertext1일을 유지한다. 새 private 수동 workflow는 전용 REVIEWED_DART_QUALIFICATION_SHA만 사용한다. 기존 secret 하나 외 추가 secret/API/모델/게시/알림/ledger/cursor는 없다. 비용 영향은 기존 무료 OpenDART2calls와 수동 Actions job1회다.

집중144PASS/1.97초, Ruff/format870 및 source+script mypy371PASS를 확인했다. 독립 QA는142PASS/2.01초와 XML safety2PASS/0.39초, 잔여C/H/M/L0으로 승인했다. 실패 영수증의 elapsed 누락과 Ruff 줄 길이 지적을 해결했다. exact CI43892236864와 실제 source 실행 결과는 확인 후 아래에 갱신한다. 이 구현만으로 source/runtime matrix를 승격하지 않는다. 약관의 이번 공개 열람은 timeout이었고 기존 제한된 사실 추출/private 보관 범위를 확대하지 않았다.

## 수용 상태

최종 local3/8·runtime0·DART 과거 지원 양식만 qualified·human0/12·v3예약0·운영 미완료다. metadata/ops 최종 CI와 운영 인수는 별도로 확인한다. N184의 live HTML-only/ZIP 금지는 변경하지 않는다.


## exact CI와 실제 응답

코드6ac349fe의 [CI43892236864](https://github.com/murphyGo/investo/actions/runs/43892236864)가 Python3.11.9에서8,018PASS/1knownskip/779.41초, Node39·Ruff/format870·mypy370 및 모든 정책/strictdocs PASS다. script를 추가한 로컬 strict mypy371도 통과했다. private a3e95003에는 검수한 수동 workflow1개만 추가했고, 전용 pin만6ac349fe로 등록했다.

11월17일 KST의 비공개 run43894860556은 목록·원문2GET 모두 HTTP200으로1.571763초에 검증을 마쳤다. 새 목록은590bytes/2행이며 원문은ZIP13,524/XML79,039bytes다. 실제 최종 byte 수신은 목록2026-11-16T15:18:30.282299Z, 원문15:18:31.089899Z다. 원문 digest는 보관본과 같지만 새 clock을 반영한 context SHA444f3da8…를 사용했다. 로컬 재생에서5slot/25refs·29XML/599자를 대조했다. 암호문·manifest·목록·원문·parser hash와 비공개 보관 경계는 [증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-qualification-20261116/evidence.json)에 기록한다.

현재 목록의 target rm에는 후속 정정 표지(superseded)가 있다. 따라서 과거 정정문의 당시 발행 계획만 검증하며 최신 조건·현재 발행 완료·미철회 상태를 판정하지 않는다. 추가 공시나 URL을 따라가지 않았다. 독립 source 검수와 local qualification 결정은 아래 판정으로 마쳤다. 원래 진단의 source/runtime/activation false 영수증은 변경하지 않는다.


## 제한된 local qualification 판정

원문·목록·수신 clock·새 context·29XML locator의 독립 readback은C/H/M0으로 승인됐다. 실제 loader에서 확인한 DART 공개 viewer domain 누락을 canonical metadata1행으로 보완했다. body source/selector/EnrichmentSource는 그대로라 수집 권한은 늘지 않는다. 후보의 URL 범위 오류도 실제 loader 검사 전에 수정했고, guard를 우회하지 않았다.

검수한 DART1행만 자격표에 반영해 **local3/8 verified·5blocked, runtime0/activationfalse**로 판정했다. 다른7행과 기존Fed2 sample은 완전히 보존했다. 새 matrix hash로3sample/10fieldslot을 실제 loader와 private CLI에서 재생했다. DART의 상태는 역사적 정정문의 한 지원 양식에만 한정되며 superseded 표지를 최신 조건이나 발행 완료로 바꾸지 않는다. 원래 진단의 false 영수증은 보존하고 이 오프라인 판정을 별도 기록한다.

qualification 통합 집중162PASS/2.65초·Ruff/mypy371, 관련 독립23PASS/1.00초·C/H/M0을 확인했다. 자격표·viewer metadata·미활성 경계 회귀의 최종 exact CI는 아직 확인 중이다. u173 Step4/u184 Step5 전체, production source preparation 연결·나머지5source·사람12건/화면/성능/실제 기사/운영 전환은 계속 미완료다.
