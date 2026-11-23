# DART 신탁계약 해지 결정 후속 교차검수

검수 범위는 u173/u184의 명시적 private source profile 구현·자격·현재 원문 준비·기사 미리보기다. 부모 단위의 운영/사람 인수 완료를 뜻하지 않는다.

| 기준 | 근거 | 판정 |
|---|---|---|
| FR-001/002 공식 원문 | 정확한 회사/접수/날짜/form/version/표 ownership, 실제 최신목록N/Y+XML3GET | Pass: 현재 원문1건 |
| FR-017 품질 추적 | XML32bindings/context5slots29refs/945자, 원문·문맥 hash 분리, source-slot replay1sample5fields | Pass |
| FR-023/024 사건 근거 | 결정/예정과 미기재 보존, global fact proof/core-only gate 유지, 실제 뉴스 단신41refs 검수 | Pass 범위 한정; DART/상세 기사 양성0 |
| NFR-002 비용 | 기존 무료 API·키·CLI runner만 사용, raw2GET, 기사model3, 개별준비3GET/model0 | Pass |
| NFR-003 신뢰성 | 필드/단위/날짜/소유권/최신성/양식 불일치 fail closed, fallback 없음 | 최종8316tests PASS/1skip |
| NFR-005 유지보수 | 별도 parser/profile/자격, 기존 CB 파일/다른7개 source 행 보존 | 독립 검수 Pass |
| NFR-006/007/008 경계 | 기존 요청/시간/바이트/ZIP/XML/secret guards,0700/0600·recipient encryption1day | 실제 캡처·재생 Pass |
| FR-021 운영 | exactCI45150453547, 전용preview/preparation pin, repository/env 전체 일치·checkout/clock 결속 | Pass; production 전환0 |
| 사람·운영 수용 | human0/12, externalrecallnull, viewport/성능/genuine scheduled 수용 | Pending |

## 실제 관측

기사 run45143245424: 모델3/단신1/상세0/source_limited, 일반 지원 DART 양식0·첨부추가 변형1/30건. DART HTTP0/native0이며 기사 양성이 아니다. 기사41refs와15개 문서가 같은 실행 원천 context와 일치하고 core_only/brief_ready 판정이 정확하다.

개별 준비 run45152929626: fresh discovery N/latest Y/XML,3GET/1.410751초/model0. 원문1건 enriched/native1,5slots29refs32XMLbindings/945자, actual-clock 재생 Pass. 이 기술적 성공으로 canonical runtime_qualified나 activation_ready를 승격하지 않는다. 알려진 접수번호를 일반 기사 입력에 주입하지 않았다.

## 검수와 수정

TU 날짜 속성 누락 L1, context/XML hash 혼용 M1을 수정했다. 캡처 도구는 repo 변수 전체 pagination/중복·exact equality, routed DART와 prepared item의 완전한 연결, codex-runtime 환경 override 차단을 보강했다. 코드/자격/운영 도구의 독립 잔여 C/H/M/L0. 실제 원문 검수 결과는 [준비 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-trust-termination-20261123/preparation-result.json)에 별도로 기록한다.

[설계](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-trust-termination-20261123/design.md), [세션](../sessions/2026-11-23-dart-trust-termination.md).
