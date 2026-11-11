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
| 실제 입력의 한계 | reconstructed listing/corp_code·명시 fixed offline clock | 새 capture/runtime 인수 아님 |
| live source/runtime | HTTP0·ops matrix 불변·local2/runtime0·DARTblocked | 별도 수용 대기 |
| 사람/viewport/성능/운영 | human0/12·v3예약0·기존 gate 유지 | 미완료 |

정확한 source SHA의 CI는 전달 이후 증거대로 갱신한다. scope 밖 archive·다른 dirty 작업·기존 runtime/workflow·source registry는 보존한다.
