# DART 일정 정정 공통 준비 — 범위 검수

u173 Step4/u184 Step5의 기존 FR-001/017/024 및 NFR-002/003/005/006/007/008 계약을 기준으로 검수한다. 전체 event-v3 활성화 판정과 이 하위 준비 경로의 검증을 분리한다.

| 계약 | 확인 근거 | 판정 |
| --- | --- | --- |
| 명시적 parser 선택, 자동 fallback 금지 | `price`/`schedule` profile, typed version, 교차 양식 차단 테스트 | PASS |
| 수집 전 권한 검증 | profile·matrix hash·parser·fixture·source SHA·rights 불일치 HTTP 0 | PASS |
| 원문 근거 일치 | 실제 보관본 파일 5개, 필수 항목 5개·참조 22개·XML binding 76개 독립 재구성 | PASS |
| 기존 가격 정정 경로 보존 | 원래 자격 파일 2개 byte 일치, 다른 source 7행 의미 일치, 기본 `price` | PASS |
| 제한된 source 접근 | 공통 owner, 20초/6요청/GET 8초/동시 2/500KiB 및 1,200자 projection | PASS |
| credential·원문 격리 | credential 단계 한정, ignored 0700/0600, recipient 암호문 및 1일 artifact | PASS |
| 검증 코드의 정확성 | Python 3.11.9 focused 235 PASS, Ruff/format/mypy PASS, remote 19개 파일 일치 | PASS |
| 실제 수집과 결과 재생 | 동일 run의 collection→latest list→XML→native clock/hash/refs | PASS |
| 운영 영향 제한 | 전용 진단 pin만 변경, 다른 설정·모델·게시·알림·ledger/cursor 보존 | PASS |

독립 source 및 qualification/driver 검수는 C0/H0/M0/L0이다. driver 검수에서 찾은 일정 profile의 가격 trace 수용 가능성과 오래된 private HEAD 참조는 수정 후 재검수했다.

정확한 [CI 45056435819](https://github.com/murphyGo/investo/actions/runs/45056435819)는 8,147PASS/1skip·Node39·정적/정책/docs 통과다. 실제45059739620은 4GET/200·2.039706초, 일정 정정1건의5slot/22refs/76XML·661자/native1을 확보했다. 암호문21,466bytes와 private5파일을 독립 재생해 C0/H0/M0/L0을 확인했다. 원래 과거공시는 최신목록 missing으로 XML 없이 차단했다. 실행 전후 변수는 같으며 다른 작업의 production pin 갱신은 보존했다. 하위계획5/5만 완료한다. canonical local 3/8·runtime 0·activation false·human 0/12·genuine v3 scheduled accepted 0은 유지한다. 이 결과만으로 u173/u184 전체 또는 source 활성화를 완료로 표시하지 않는다.

[계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-runtime-20261123/plan.md) · [세션](../sessions/2026-11-23-dart-schedule-runtime.md) · [자격 근거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-runtime-20261123/qualification-evidence.json)
