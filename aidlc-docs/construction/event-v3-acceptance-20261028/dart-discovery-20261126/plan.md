# DART 지원 양식의 bounded discovery

사용자 2026-11-26 “진행시켜”에 따른 u173 Step4/u184 Step5 후속. 직전 run45143245424의 일반 최신30건에서 지원공시가 탈락한 gap을 해결한다. 기반은 검수된 3caca98a, public main bccedf9a의 소스 변경은 기존 terms/schedule 통합으로 이 기반에 이미 포함되며 새 archive는 현재 baseline을 실행 때 읽는다. 공유 dirty tree를 변경하지 않는다.

## Stage Decision

Functional Design 및 NFR Requirements: Required. 조회 범위와 요청 예산을 바꾸므로 [설계](design.md)에 상태·실패·비용·범위 의미를 코드 전에 고정했다. FR-001/002/023/024, NFR-002/003/005/006/007/008, R10/R13, 기존 공통 준비와 private article_v2 계약을 재사용한다. 기존 진행 지시가 구현·검증·전용 비게시 진단까지 포함하며 production cutover 인수는 별도다.

## 단계

- [x] 1. 일반 fetch 경로와 현재 main/private pins를 확인하고 FD/NFR을 고정한다.
- [x] 2. sources 소유의 별도 discovery adapter를 명시적 preview profile에 연결하고 합성 회귀를 검증한다.
- [ ] 3. 독립 코드 검수와 exact-code quality를 완료한다.
- [ ] 4. 현재 날짜의 비게시 실행과 암호화 캡처로 실제 발견·준비·기사 결과를 검증한다.
- [ ] 5. 독립 실제 검수 및 세션·상태·남은 인수 조건을 기록한다.

원문은 ignored0700/0600만 사용한다. canonical qualification, human0/12·외부recallnull, 상세기사/viewport/성능/예약 수용과 운영 활성화를 자동 승격하지 않는다.
