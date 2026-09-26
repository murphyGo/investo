# u159 사건 반영률과 최종 품질 검증

u158 원격 전달 `c3f2e5ef` 이후 순차 개발했다. 6개 구현 단계와 최종 검증·독립 리뷰를 완료했다. 운영 active는 false다.

## 구현

- 관측된 수집·수신 시장 라우팅·입력 후보·분류·선정·prompt·생성 단계의 hash-only receipt를 남긴다. `GenerationResult`와 생성 실패 예외 모두 실행한 단계만 운반한다. 현재 시장의 수집 전면 실패를 다른 시장의 성공으로 덮지 않는다. 성공한 0건과 실행되지 않은 단계를 구분한다.
- 실제 봉인 문서의 사건 본문, 필수 사실, 출처, 설명·반응 상태, summary/DTO와 사건 identity를 검사한다. URL/marker만 남은 블록은 설명 완료가 아니다. 구조 누락은 기존 containment가 처리하며 미지원 사실은 기존 hard gate를 유지한다. 모든 구분이 차단되어 bundle이 만들어지지 않아도 실제 구분별 차단 사유를 보존한다.
- `EventCoverage`는 단계별 unknown을 null로 유지한다. selected가 0/null이면 반영률은 null이다. detail_limited는 terminal 분자에는 포함하고 qualified 분자에는 제외한다. public history에는 counts/status/closed codes만 저장하며 receipts 원문과 stage IDs는 제외한다.
- 품질 페이지와 이력은 `terminal` 기준을 명시하고 봉인 문서에서 계산한 expected 값과 대조한다. 원격 게시 집계는 같은 시점의 `PublishReceipt.remote_confirmed`로 확인된 구분만 포함하고 제외 구분을 별도로 표시한다. 알림만 실패해도 게시 집계를 되돌리지 않는다.
- active 경로는 원격 main을 한 번 고정 SHA로 읽어 7일 receipt를 공급하고, 봉인된 survivor의 hash-only ledger를 archive와 같은 E11 transaction에 넣는다. CAS baseline이 없으면 쓰기 전에 게시를 거부한다. pending/outcome_unknown 상태는 공개 성공이나 다음 실행의 baseline이 아니다. 기본 off 및 dry-run의 metadata 비갱신 경계를 보존한다.
- 비게시 replay는 합성 기록 응답을 실제 기존 생성·finalizer·HTML/DTO로 검증한다. 의도적 문서 변조는 scripts의 오프라인 fixture helper 안에만 둔다. 과거 18편의 발행본 inventory는 입력 replay와 구분한다.

## 평가 범위

합성 fixture의 must_include/required facts/forbidden claims는 AI가 작성한 회귀 기대값이다. 구조 검사와 회귀 통과를 실제 원문의 의미 정확성이나 사람 검토 5/5로 대신하지 않는다. 사람의 의미 수용 검토, scheduled shadow 5회, 운영 active 첫 3회 게시/알림/Pages는 별도 운영 증거다. 이 코드 작업은 해당 운영 활성화를 수행하지 않는다.

## 검증

전체 5,652개 회귀가 416.33초에 통과했다. 12개 그룹/25개 replay 변형과 독립 통합 테스트 32개, preview/architecture 17개도 통과했다. 두 wave 안에서 독립 리뷰 P2 8건을 교정·재확인했고 미해결 P1/P2는 없다. Ruff/format638, mypy282, 정책 검사 4종, strict MkDocs7.84s 및 Material 계약 검사 모두 통과했다.

NF3 1,000개 입력의 선정·stage receipt·v2 parsing·renderer·terminal gate 최종 p95는 126.662ms(한도 200ms)였다. 실제 LLM 서비스, 운영 end-to-end p95, 공개 게시/알림은 측정하지 않았다. 자세한 수치와 AC-159.4의 사람 의미 수용 pending 상태는 `validation.json` 및 cross-check에 기록했다.
