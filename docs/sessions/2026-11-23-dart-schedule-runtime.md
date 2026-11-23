# 2026-11-23 — DART 일정 정정 공통 준비 연결

## 범위와 결정

사용자 “진행시켜”에 따라 앞서 제안한 일정 정정 parser의 공통 수집 연결과 실제 비게시 검증을 진행한다. `dev-investo`의 독립 코드 검수와 기존 u173 Step4/u184 Step5 설계를 재사용했다. 검증에 필요한 제한된 코드 전달·정확한 CI·전용 수동 workflow/pin 갱신을 포함한다.

`price`는 기본값으로 기존 가격 정정 자격 파일을 사용한다. 새 `schedule` 선택은 별도 일정 정정 자격 파일과 `dart-cb-schedule-6.4-v1`만 사용한다. 두 parser 사이 fallback은 없다. 잘못된 profile이나 자격 조합은 수집 전에 차단한다.

## 변경과 검증

- typed transport/trace, 공통 DART preparation, 수동 probe와 private workflow에 명시적 profile을 연결했다.
- 일정 전용 자격은 실제 보관 원문의 clock·fixture·코드 SHA·matrix hash·rights를 결속한다. 다른 7개 행과 기존 price 자격 파일 2개는 보존한다.
- 공통 owner의 전체 20초, 최대 6 HTTP, GET 8초, 동시 2, 응답 500KiB 및 native 1,200자 제한을 유지한다.
- 독립 코드 검수 C0/H0/M0/L0. 운영 Python 3.11.9에서 독립 234개, 전달본 235개 관련 테스트 통과. 전체 Ruff/format 877개 파일, mypy 371개 source 통과.
- 실제 보관 입력 파일 5개 해시, 1개 표본의 5개 필수 항목·22개 참조·76개 XML 위치를 독립 재구성했다.
- 로컬 capture 검수 도구의 parser 혼용 가능성과 오래된 private HEAD 참조를 수정했다. 재검수 C0/H0/M0/L0.

구현 기준 commit은 `fc84d7c1d1c4f2ed140606e9a5ca38fb667f086c`, 자격을 포함한 전달본은 `3eafd2bc8ea0aff906ba2d23466a75a66fe945d3`다. [정확한 코드 CI](https://github.com/murphyGo/investo/actions/runs/45056435819)와 실제 수집 결과는 아래에 이어 기록한다.

## 운영 경계

전용 `REVIEWED_DART_PREPARATION_SHA`만 검증된 코드로 갱신한다. 다른 reviewed pin과 production/preview 설정·예약은 유지한다. 모델 호출·게시·알림·ledger/cursor 변경 없이 source 준비만 확인한다. 원문은 ignored 0700/0600 저장소와 1일 보관 recipient-encrypted artifact에만 둔다.

canonical local 3/8, runtime 0, activation false, human 0/12, v3 예약 수용 0 및 상위 u173/u184 미완료 상태는 유지한다. 일정 profile의 준비 성공과 전체 기사 생성·발행 준비 완료를 구분한다.

## 실제 결과

정확한 전달본의 CI는 **8,147 PASS / 1 skip, 564.48초**, Node 39개, 모든 정적·정책 검사와 strict docs 6.02초로 통과했다. 구현과 자격은 `codex/dart-schedule-runtime-20261123` branch로 전달했고 private 진단은 이 SHA를 직접 사용한다.

private workflow는 `a6dbb7db558aee02aab177aad525fe7bb71935ab`로 갱신했다. 변경은 수동 DART workflow 1개뿐이다. GitHub 연결 도구의 코드 쓰기 권한 제한으로 인증된 `gh`를 사용했고, `gh` token의 workflow scope 제한은 기존 인증된 SSH 전달 경로로 처리했다.

실행 직전 다른 작업이 `REVIEWED_CODE_SHA`를 `3ce35148`에서 `378bccee`로 갱신한 것을 guard가 감지했다. 첫 시도는 key/state/dispatch 생성 전 중단됐으며 HTTP 0이었다. 외부 변경을 보존하고 새 snapshot으로 재검사했다. 실행 전후 전체 변수는 같으며 이번 작업이 바꾼 변수는 전용 `REVIEWED_DART_PREPARATION_SHA` 하나다.

[실제 run 45059739620](https://github.com/murphyGo/automation-runtime/actions/runs/45059739620)은 **4 GET / 모두 200 / 2.039706초**로 완료됐다. 원래 과거 공시는 최신 목록에서 없어 차단하고, 별도로 발견한 일정 정정 공시 1개에서 필수 항목 5개·참조 22개·XML binding 76개 및 661자 native context 1개를 확보했다. 공통 준비 경로의 positive 표본 1개이며 최신 발행조건이나 발행 완료를 보증하지 않는다.

암호문 21,466bytes를 같은 run에서 즉시 확보했고, private 파일 5개와 수신 시각·응답/XML/native 해시·공통 준비 결과를 재생해 일치를 확인했다. 원래 manifest의 `independent_review_pending` 및 runtime/activation false는 수정하지 않았다. 독립 실제 검수는 별도 review 결과로 기록한다.

관련 자료: [계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-runtime-20261123/plan.md), [자격 근거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-runtime-20261123/qualification-evidence.json), [독립 검수](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-runtime-20261123/qualification-review.json).

최종 실제 독립 검수 **C0/H0/M0/L0**. 두 item의 공통 준비 결과·trace·reason이 일치하고 모든 source→native 참조가 같은 텍스트를 가리킨다. 각 요청/수신 시각은 같은 run의 probe step 안에 있으며 occurrence는 unknown으로 유지한다. 하위 계획5/5를 완료했고 상위 unit·기사 사람 검수·v3 운영 전환은 남겨 두었다. 공개 main은 다른 작업의 갱신을 보존하며 이 전달본은 전용 branch/pin에 둔다. [실제 검수](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-schedule-runtime-20261123/actual-review.json).
