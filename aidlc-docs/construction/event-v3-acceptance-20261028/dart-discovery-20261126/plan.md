# DART 지원 양식의 bounded discovery

사용자 2026-11-26 “진행시켜”에 따른 u173 Step4/u184 Step5 후속. 직전 run45143245424의 일반 최신30건에서 지원공시가 탈락한 gap을 해결한다. 기반은 검수된 3caca98a, public main bccedf9a에는 별도 terms/schedule 통합과 새 archive가 추가되어 있다. 이 작업은 직전 검수된 trust 전달본의 후속이며 별도 v2 통합을 재배포하거나 main을 병합하지 않는다. 현재 archive baseline은 실행 때 읽는다. 공유 dirty tree를 변경하지 않는다.

## Stage Decision

Functional Design 및 NFR Requirements: Required. 조회 범위와 요청 예산을 바꾸므로 [설계](design.md)에 상태·실패·비용·범위 의미를 코드 전에 고정했다. FR-001/002/023/024, NFR-002/003/005/006/007/008, R10/R13, 기존 공통 준비와 private article_v2 계약을 재사용한다. 기존 진행 지시가 구현·검증·전용 비게시 진단까지 포함하며 production cutover 인수는 별도다.

## 단계

- [x] 1. 일반 fetch 경로와 현재 main/private pins를 확인하고 FD/NFR을 고정한다.
- [x] 2. sources 소유의 별도 discovery adapter를 명시적 preview profile에 연결하고 합성 회귀를 검증한다.
- [x] 3. 독립 코드 검수와 exact-code quality를 완료한다.
- [x] 4. 현재 날짜의 비게시 실행과 암호화 캡처로 실제 발견·준비·기사 결과를 검증한다.
- [x] 5. 독립 실제 검수 및 세션·상태·남은 인수 조건을 기록한다.

원문은 ignored0700/0600만 사용한다. canonical qualification, human0/12·외부recallnull, 상세기사/viewport/성능/예약 수용과 운영 활성화를 자동 승격하지 않는다.


초기214daa2b/CI45809403700은8360PASS/1skip였다. 실제45811756622에서 비지원 공시의 전일 접수번호가 전체 페이지를 거절하는 구현 오류를 발견해39f75729로 수정했다. 관련100PASS 및 독립68PASS, 동일실제응답48→지원1 오프라인 재생이며 새 exact CI45812557093과 실제 후속 검증을 진행한다. 최초실행의 source failed/unknown·model1·기사0은 그대로 보존한다.


## 완료 범위

하위계획5/5. 최종39f75729/CI45812557093은8361PASS/1skip·JS39·Ruff889/mypy375·strictdocs9.12초 PASS다. 실제45814759782는당일B00148행에서지원1건발견/GET1·목록Y+XML GET2, 합계3GET/모델1이었다. discovery full은이B001조회범위만뜻한다. 새원문은정확한6.2/ADATE이지만날짜4개가YYYY.MM.DD이고주석328자로기존한국어날짜/240자주석계약밖이라parser_unsupported로차단했다. nativeDART0·선택DART0·기사0/source_limited,6파일62816bytes암호문즉시확보·독립실제C/H/M/L0이다. 지원후보발견양성1만인정하며본문/기사양성은0이다.

이후작업은 [원문표기·주석 gap](parser-gap.json)의별도bounded자격·완전한근거지원이다. 기존canonical local3/8/runtime0/activationfalse·human0/12·externalrecallnull·v3예약수용0과부모u173/u184/u172/u171을미완료로유지한다. [최종결과](corrected-result.json), [인계](handoff.json), [초기실패보존](initial-result.json).
