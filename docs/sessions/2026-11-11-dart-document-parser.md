# 2026-11-11 — DART 정정공시 parser·필수 field 검증

사용자의 “진행시켜” 지시로 기존 u173 Step4/u184 Step5의 DART 후속을 수행했다. [설계/NFR](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-parser-20261111/design.md), [실행 계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-parser-20261111/plan.md), [count/hash 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-parser-20261111/evidence.json).

## 구현과 실제 원문 대조

기존 source의 오프라인 helper `sources/_dart_document.py`를 추가했다. 새 source 등록·HTTP/LLM·source capability·운영 pin·게시/알림은 변경하지 않았다. 기존 목록 item과 ZIP/응답 hash를 받아 FORMULA6.4/20260723·ACODE11324 및 목록의 정확한 기재정정 상태만 지원한다. 회사/공시번호/viewer/날짜와 단일 XML member/digest를 결속한다.

정정 표의4열/rowspan/colspan을 bounded grid로 읽고, 정정 후 price/shares/ratio/floor를 현재 발행 차수의 ACODE와 대조한다. 정정 전 값·다른 차수의 채무·단위 혼동·누락/중복·지원하지 않는 변경 행은 거절한다. 원문의 예정 상태를 완료로 바꾸지 않으며 board/payment/maturity/original-submission/correction 날짜를 분리한다. 작은 source-owned field projection만599자로 전달해 evidence_budget_limited=true를 명시한다.

보관 ZIP/XML digest를 대조하고 실제 원문에서5필수 slot·25refs(1/3/4/16/1)·29XML binding을 C2 factory로 재생했다. 모든 XML path/attribute를 표준 locator로 다시 찾아 정규화된 값과 동일한지 확인했다. 독립 QA가 기존 map_source_slot_context 결과와 같은 context임을 확인했다. publication은 date, occurred/announced는 unknown이며 listing title/summary와 입력 item은 보존한다.

이것은 새 원문 수집이나 독립 목록 API 재생이 아니다. 목록 title/summary/url/date는 과거 source 녹화에서 재구성했고 회사코드는 XML에서 입력했다. 원래 HTTP의 정확한 수신 순간이 없어 명시한 고정 오프라인 replay clock을 사용했다. 따라서 source/runtime 자격이나 사람 corpus를 승격하지 않는다. 실제 XML·정규화 capture는 ignored0700/0600에만 있으며 공개 fixture는 별도 합성 예시다.

## 검증

신규72개, 기존 DART/slot/model/checker/probe/plugin/enrichment를 합친 **203PASS/3.35초**, 독립120PASS/2.12초·잔여C/H/M0. Ruff/format861·mypy364·무료 API/SDK 금지 검사 PASS다. 독립 검수에서 발견한 Medium4건(UTF16/comment 우회, XML path index, NUL ZIP member, 목록 correction modifier 결속)을 모두 수정하고 각각 음성 회귀를 추가했다. ZIP500KiB·single exact member·안전XML·20knodes/depth256·raw/error/repr/credential 경계를 검증했다.

strictdocs도 PASS다. 최종 코드의 전체 CI 결과는 아래에 기록했다. 문서 갱신으로 같은 전체 테스트를 다시 실행하지 않는다.

## 남은 수용

ops matrix는 local2/8 verified·runtime0·DARTblocked/activationfalse 그대로다. 이 parser는 live HTML enrichment를 우회하지 않으며 N184의 기존 ZIP 금지/HTTP budget을 바꾸지 않는다. 현재 listing과 live 수신·권리/접근/clock·versioned parser 범위를 연결한 별도 qualification, 실제 source preparation 경로 및 u172 사람12건/화면/성능/운영 검수가 남는다. u173 Step4/u184 Step5 전체 완료나 운영 전환을 선언하지 않는다.


## 정적 XML import 규칙 보완

최초 통합2a0db03a의 CI42980639029는7,978PASS/1knownskip 및 저장소 XML import 검사1건 실패였다. 파서는 defusedxml만 사용했지만 타입 전용 stdlib Element import도 금지하는 기존 규칙에 걸렸다. 해당 import를 내부 Protocol로 대체했고 규칙은 유지했다. 독립 AST 대조에서 기존8개 함수의 파싱/field/refs 알고리즘이 그대로이며 원문29개 binding·5slot/context hash도 동일하다. XML safety2와신규parser72를 합친74PASS, 통합집중304PASS·독립 타입 delta C/H/M0이며 후속 전체 CI도 통과했다.


## 최종 코드 CI와 전달

최종 코드 `90dc6d2a36143781cb18fbde559b38ca3f95e4e9`의 [CI42982852064](https://github.com/murphyGo/investo/actions/runs/42982852064)가 성공했다. Python3.11.9에서 **7,979PASS/1knownskip·801.80초**, Node39PASS, Ruff/format869·mypy370, 무료 API/SDK·asset/image·Material/Calendar 정책 검사와 strictdocs가 모두 통과했다. 앞선 XML 타입 import 실패 기록은 보존한다.

별도 macro source 변경 `505f5c1e`와 함께 통합한 집중 검사도304PASS/4.27초다. 별도 작업의 source 등록과 state/audit 기록을 보존했고, 타입 Protocol 변경에 대한 독립 검수도 잔여C/H/M0이다. 공개 파일에는 합성 fixture와 count/hash만 있으며 원문 capture는 private 경로에 유지했다.

오프라인 subplan6/6을 완료하고 코드를 main에 전달했다. 다음 단계는 현재 목록·실제 수신 clock과 원문을 함께 수집해 live source 연결 및 권리/접근/field qualification을 검증하는 것이다. local2/8·runtime0·DARTblocked·human0/12·v3예약0 및 운영 전환 미완료 상태는 그대로다.
