# DART parser 검수 — 코드 PASS / source·운영 PARTIAL

[세션](../sessions/2026-11-11-dart-document-parser.md), [설계/NFR](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-parser-20261111/design.md), [증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-parser-20261111/evidence.json).

| 계약 | 확인한 증거 | 판정 |
| --- | --- | --- |
| 지원 양식·목록 상태 | 6.4/20260723·11324·기재정정 exact | 통과 |
| 정정 후/current series | grid·body codes·unit/날짜·소유자·중복/누락 음성 | 통과 |
| source locator | listing/viewer/rcept_no/XML member/digest·회사 결속 | 통과 |
| typed context | 기존 factory·5slot/25refs·29XML roundtrip·599자 | 오프라인 통과 |
| 의미/clock | 예정≠완료, published=date·occurred/announced=unknown | 통과 |
| 보안/자원 | 500KiB·16member 외 단일 양식·20knodes/depth256·defusedxml·NUL/encoding/secret/repr | 통과 |
| 회귀/독립 검수 | 집중203·독립120 PASS·M4건 수정·잔여C/H/M0 | 통과 |
| 최종 코드 전체 CI | 90dc6d2a·CI42982852064·7,979PASS/1knownskip·Node39·정적/정책/docs | 통과 |
| 실제 입력의 한계 | reconstructed listing/corp_code·명시 fixed offline clock | 새 capture/runtime 인수 아님 |
| live source/runtime | HTTP0·ops matrix 불변·local2/runtime0·DARTblocked | 별도 수용 대기 |
| 사람/viewport/성능/운영 | human0/12·v3예약0·기존 gate 유지 | 미완료 |

최종 코드90dc6d2a의 [전체 CI](https://github.com/murphyGo/investo/actions/runs/42982852064)는 Python3.11.9·7,979PASS/1knownskip·801.80초다. Ruff/format869·mypy370·Node39와 모든 정책/strictdocs가 통과했다. scope 밖 archive·다른 dirty 작업·기존 runtime/workflow·source registry는 보존한다.

최초 CI42980639029의 유일 실패는 타입 전용 stdlib XML import guard였다. Protocol 대체와 XML safety2 PASS·기존 알고리즘 AST 불변을 확인했다. 최초7,978PASS/1skip을 새 코드의 full PASS로 치환하지 않고 후속 exactCI가 통과했음을 별도로 기록한다.

macro source505f5c1e를 보존한 통합집중304PASS/4.27초, 타입 변경의 독립 검수C/H/M0을 확인했다. 오프라인 subplan만6/6이며 u173 Step4/u184 Step5 전체와 source/runtime/사람/운영 인수는 미완료다.
