# DART 기사 미리보기 연결 교차검수

범위는 u173/u184/u185/u186/u172의 제한된 후속이다. 실제 preview를 통해 준비·분류·작성·의미 검수·봉인 연결과 자동 readiness를 점검하며 전체 운영 전환 수용을 대신하지 않는다.

| 계약 | 검증 근거 | 판정 |
| --- | --- | --- |
| 명시적 DART profile과 trusted qualification | 잘못된 profile·schema·parser 조합 수집 전 거절, 같은 slot matrix 전달 | PASS |
| 제한된 private 근거 보관 | source256KiB·DART192KiB·모델1MiB·draft128KiB·Markdown256KiB·전체2MiB, credential/decoded echo 차단 | PASS |
| 정확한 실행 연결 | code0e3f389d/CI45120572446 → private64981a4f/run45122245131 | PASS |
| 같은 실행의 근거 | routed113/native37/분류전송14, 모델3회, 6파일·참조·최종 Markdown hash | PASS |
| DART 현재 자료 처리 | 28개 전체 차단, 지원양식0·selected unsupported2·HTTP0·공통 준비 exact replay | PASS, 기사 양성 아님 |
| 최초 실제 기사 정확성 | 사건1/claim1/문장1, unsupported 관측0·finalizer 손실0 | PASS, source_limited |
| 최초 상세 준비도 | core-only 사건이 detailed_ready로 승격됨 | Medium1 발견, 새 정책으로 수리 |
| 새 core-only 정책 | 명시적 detail_basis·brief 상한·writer/reviewer why 구분·policyhash/terminal 재구성 | 독립 C/H/M/L0 |
| 기존 입력·호환성 보존 | 실제 원본의 facts/passages/refs/legacy hash 보존, 예전 판정 재봉인 거절 | PASS |
| 회귀 | 관련3,352PASS/84.73초·별도 terminal 위조 테스트·독립58PASS/1.41초 | PASS |
| 새 정확한 CI/실제 producer | code5d9885d2/CI45123784115: 8,238PASS/1skip·Node39·정적/정책/docs; run45125524648 모델3회·core_only/brief_ready·detailed0 | PASS, 독립 실제 C/H/M/L0·terminal PASS |

단순 문장 길이나 summary 형식으로 상세 여부를 정하지 않는다. 실제 비교·조건·설명 refs·별도 본문은 상세 검토 자격을 유지하지만 의미 검수의 합격을 대신하지 않는다. 원래 producer output을 수정하거나 원래 run을 새 정책의 성공으로 재집계하지 않는다.

사람 사전 annotation·점수 및 external recall은 미확인이다. human0/12, canonical local3/8·runtime0·activationfalse, 수용된 v3 예약0을 유지한다. 최종 actual HTML의 두 viewport·성능·정확한 release/cursor/source 인수와 실제 예약 관찰도 남아 있다. 로컬 나란히 검수 HTML은 사전 annotation이나 viewport 수용 증거가 아니다.

[계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/plan.md), [전체 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/evidence.json), [최초 실제 검수](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/actual-review-original.json), [수리 검수](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/readiness-fix-review.json).

수정 후 실제 검수는 [actual-review-rerun.json](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/actual-review-rerun.json)에 기록한다. 새run의 참고 가격2개도 captured input과 일치한다. 하위계획5/5 완료, 상위 unit 상태 불변.
