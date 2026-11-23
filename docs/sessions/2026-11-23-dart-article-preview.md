# 2026-11-23 — DART 기사 미리보기 연결과 실제 검수

사용자 “진행시켜”에 따라 일정 정정 공통 준비 다음 단계인 국내 `article_v2` 비게시 실행과 실제 근거 대조를 진행한다. `dev-investo`의 독립 검수와 기존 u173/u184/u172 수용 계약을 적용한다. 사람의 사전 annotation·최종 인수는 AI 검수로 대체하지 않는다.

## 구현과 전달

최신 main의 계약조건 정정 v2와 retry feedback을 보존하면서 검수된 일정 정정 parser를 통합했다. `price/v1`, `price/v2`, `schedule/v1`은 각각 명시적 자격 파일을 사용하며 parser 사이 자동 fallback은 없다. schedule preview는 DART body·official body·schema3/article_v2를 요구하고 수집 전에 조합을 검증한다.

Codex wrapper와 전용 private workflow에 DART profile을 연결했다. 선택한 routed source와 native context, DART 공통 준비의 HTTP 응답, 모델 입출력, 생성 초안과 최종 Markdown을 기존 recipient-encrypted artifact 안에 제한된 크기로 보관한다. 입력 snapshot은 모델 실행 전에 기록하며 실제 모델에 같은 context를 전달한다. collector 전체 HTTP를 재현하거나 외부 뉴스 recall을 입증하는 자료는 아니다.

독립 검수에서 발견한 decoded credential echo와 원래 DART 입력 보존 문제를 수정했다. 관련330개 테스트·전체 Ruff/format883파일·mypy373 source가 통과했고 독립 코드 검수 잔여 C/H/M/L0이다. 전달본은 `codex/dart-article-preview-20261123`의 `0e3f389d5abc8678d2268d73c5ff6976ee275de3`이며 공유 dirty 작업을 보존하기 위해 격리 checkout에서 전달한다.

## 실제 검증 기준

현재 날짜 국내 입력으로 한 번 실행하고, 같은 run의 원문→준비 결과→native context→모델 응답→최종 문서를 대조한다. 과거 10월 표본을 현재 입력에 넣지 않는다. quiet/source_limited는 정상 뉴스가 충분한 날의 기사 성공으로 합산하지 않는다. `edition.json`은 finalizer 전 초안이며 최종 결과는 `preview.md`와 manifest hash로 확인한다.

전용 preview pin/workflow만 변경한다. 기존 auth queue·refresh·cleanup 및 전역 모델5call 예산을 유지하며 다른 작업의 production/DART pin·예약을 보존한다. publication·notification·production ledger/cursor 변경은 없다.

## 진행 상태

정확한 전달본의 [CI45120572446](https://github.com/murphyGo/investo/actions/runs/45120572446)와 실제 private 실행 결과를 이어 기록한다. 읽기 전용 cutover checker의 기존 인수 원장은 blocked이며 source/cursor/release와 시장별 human readiness는 false, 수용된 v3 예약 실행은 0이다. 현재 코드 CI 통과와 이 원장의 인수 상태를 구분한다.

[계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/plan.md), [독립 코드 검수](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/source-review.json), [사전 검수 범위](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/pre-run-review-basis.json).

## 최초 실제 결과와 발견된 결함

[정확한 코드 CI45120572446](https://github.com/murphyGo/investo/actions/runs/45120572446)는 8,229PASS/1skip·811.63초, Node39·Ruff/format883·mypy373·strictdocs9.05초로 통과했다. 전용 preview pin은 `0e3f389d`로, private workflow는 `64981a4f`로 갱신했다. workflow 변경은 1파일17줄 추가이며 기존 `queue: max`를 보존했다.

[실제 run45122245131](https://github.com/murphyGo/automation-runtime/actions/runs/45122245131)은 모델3회와 봉인에 성공했다. 수집252·routed113·native context37·분류 전송14·사건/기사1이며 최종 Markdown은2,524bytes다. 현재 DART28건에는 지원 CB 일정 정정 양식이 없어 전체 차단됐고, 선택된2건의 parser_unsupported/HTTP0 결과를 공통 준비 경로로 정확히 재생했다. 따라서 이 실행을 DART 기사 생성의 양성 증거로 세지 않는다.

암호문59,051bytes/6파일을 만료 전에 즉시 확보했다. 원문 근거·모델3회·최종 문장의 사실·날짜·접수 상태·출처는 일치하며 finalizer 손실은0이다. 다만 핵심 사실1개/문장1개만으로 `detailed_ready`를 주는 자동 품질 판정 Medium1이 확인됐다. `source_limited`는 적절하며 원래 manifest를 고치지 않고 별도 검수 기록에 결함을 남겼다.

## 상세 판정 수리

`5d9885d2bebc7ea1a9b9d51b4c5d7df4338c708d`는 근거의 `detail_basis`를 기록하고 설명 근거 없는 core-only text action을 단신으로 제한한다. 의미가 있는 비교·조건·본문 자료는 기존 상세 검토 자격을 유지하며 글 길이나 summary 형식으로 일괄 판정하지 않는다. writer/reviewer는 핵심 사실·업종 소개 반복을 why로 세지 않도록 보완했다. 새 정책 hash와 terminal 재구성으로 예전 상세 판정의 재사용을 막는다.

원래 packet의 해시·읽기 호환과 사실·passage·refs를 보존하면서 같은 실제 입력이 `core_only`/expected_detail=false가 되는 것을 독립 재생했다. 관련3,352PASS/84.73초 및 별도 terminal 위조 회귀 통과, 독립58tests/1.41초·C/H/M/L0이다. 새 정확한 CI와 실제 재실행 결과는 이어 기록한다. 원본 실행은 새 정책의 성공 사례로 다시 집계하지 않는다.

## 수정 후 실제 재검증

[수정본 CI45123784115](https://github.com/murphyGo/investo/actions/runs/45123784115)는 **8,238PASS/1skip·828.54초**, Node39·Ruff/format884·mypy373·모든 정책 검사·strictdocs9.40초로 통과했다. 전용 preview pin을 정확히 `5d9885d2`로 갱신했으며 private workflow64981a4f와 다른 모든 변수는 유지했다.

[재실행45125524648](https://github.com/murphyGo/automation-runtime/actions/runs/45125524648)은 모델3회로 기사1편을 봉인했다. 새 수집258·routed119·native39·분류전송15이며, 실제 packet의 `core_only`/expected_detail=false → **brief_ready/brief_only·detailed0**가 확인됐다. what/when만 답하고 why는 빈 답·missing으로 남겼다. 이 실행의 source_limited 표시를 유지했으며 DART25개는 지원 양식이 없어 모두 차단·HTTP0이었다.

새 암호문60,850bytes/6파일은 즉시 확보했고 수신 파일과 최종 Markdown hash를 검증했다. 실행 로그의 실제 checkout SHA도5d9885d2와 일치한다. 실행 전후 전체 변수는 동일하며 publication·notification·production receipt/cursor는 모두false다. 원run의 오류 판정과 새run의 수정 결과를 각각 보존하고 사람/예약 표본은 늘리지 않는다.

## 남은 수용 조건

현재 날짜에서 지원되는 DART 기사 양성 표본, 나머지 source별 자격/실제 기사 근거, 사람의 사전 목록·최소12문서(시장별4/2일 이상)·5/5 검수, actual HTML 두 viewport·성능과 release/cursor/source 인수가 남아 있다. 해당 조건을 충족한 뒤에야 시장별 genuine 예약 관찰과 legacy cleanup을 진행한다. 기존 cutover 원장은 blocked이며 human0/12·canonical local3/8/runtime0·activationfalse·v3예약수용0을 유지했다. 현재 코드 CI 성공을 기존 인수 원장의 code_ready=true로 바꾸지 않았다.

공유 dirty source/HEAD/index와 다른 작업의 main·production pin을 보존했다. 최종 구현 branch는 `codex/dart-article-readiness-20261123`, 실제 preview pin은 정확한 CI를 통과한5d9885d2다. 로컬 원문/모델 기록과 나란히 보는 검수 HTML은 ignored0700/0600 경계에만 둔다. 원문을 포함한 UI의 실제 viewport 수용은 수행하지 않았다.

최종 독립 실제 검수 **C0/H0/M0/L0**, 직접 terminal 검증 PASS다. 근거/참조/사실·가격 참고값과 같은 run 입력이 일치하며 최종 문장 손실0이다. 이 하위 계획5/5만 완료했고 상위 단위의 인수 상태는 유지했다. [수정 후 실제 검수](../../aidlc-docs/construction/event-v3-acceptance-20261028/article-preview-20261123/actual-review-rerun.json).
