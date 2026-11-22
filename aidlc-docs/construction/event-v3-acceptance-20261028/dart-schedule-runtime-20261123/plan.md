# DART 일정 정정 — 공통 준비 연결과 실제 비게시 검증

사용자 “진행시켜”를 직전 제안(새 버전의 실제 수집 경로 연결·비게시 검증)에 대한 승인으로 적용한다. 기존 u173 Step4/u184 Step5를 이어가며, 검증에 필요한 정확한 코드 전달/CI와 전용 private 진단 설정을 포함한다. 공개 기사 전환·모델/알림 호출을 포함하지 않는다.

## Stage Decision

Functional Design/NFR Requirements: 아래 제한된 계약으로 완료. 기존 FR-001/017/024, NFR-002/003/005/006/007/008과 DART 공통 HTTP owner·자격표·암호문 보관 계약을 재사용한다. 별도 Infrastructure/NFR Design은 기존 private workflow의 명시적 profile 선택으로 흡수한다.

- `price` 기본값은 기존 가격 정정 v1의 policy/slot 파일을 사용한다. `schedule`은 별도 일정 정정 v1의 policy/slot 파일을 사용한다. 원문 실패를 다른 parser의 성공으로 바꾸는 fallback은 없다.
- typed transport/trace에 두 parser version만 허용하고, slot matrix의 canonical hash·source code·fixture·rights·parser 일치를 동일하게 검사한다. 요청 전 자격/프로필을 확인한다.
- 일정 정정용 별도 slot matrix는 보관된 실제 원문과 독립 source 검수를 근거로 해당 양식의5slot에만 한정한다. 기존 canonical8row/price policy를 덮어쓰지 않는다. 기존 public rights의 제한 추출 범위이며 새 원문 재배포 권한을 선언하지 않는다.
- `prepare_event_evidence`의 기존 latest-list→단일 XML/1,200자 native projection을 사용한다. 전체20초/최대6HTTP/GET8초/동시2/500KiB와 상태·회사·접수일·hash·차수 검사는 유지한다.
- 기존 수동 private workflow에 선택 입력을 추가하며 기본은 price다. 정확한 CI 성공 code만 전용 `REVIEWED_DART_PREPARATION_SHA`에 연결한다. 다른4개 reviewed pin·일정·production/preview는 보존한다.
- 현재31일 범위의 원래 대상/별도 최신후보를 최대2개 확인한다. 현재 원문이 달라졌거나 최신목록에서 사라지면 결과대로 차단한다. 즉시 암호문을 다운로드해 같은run의 clock/XML/native refs를 독립 재생한다. 원문은 ignored0700/0600, private artifact1일, 모델/게시/알림/ledger/cursor0.

## 단계

- [x] 1. 기존 설계·보관본·최신 remote/pin과 독립 checkout 경계를 확인한다.
- [x] 2. 명시적 parser/profile 선택과 shared preparation·probe·회귀를 구현한다.
- [ ] 3. 별도 source/transport 자격 및 private capture 재생을 검수하고 정확한 코드 CI를 통과한다.
- [ ] 4. 전용 진단의 profile/pin을 반영하고 실제 비게시 수집·암호문 보관·독립 검수를 마친다.
- [ ] 5. 실제 결과와 하위 완료/상위 잔여를 session/cross-check/state/audit에 기록한다.

## 수용 판정

오프라인/합성/actual shared-preparation을 각각 분리한다. 실제5slot/native 확보 시 이 명시적 profile의 준비 경로 성공만 기록하며, 전체 source readiness·기사12개/사람 검수·예약 발행·public activation을 완료로 올리지 않는다. production 설정을 바꾸지 않는다.
