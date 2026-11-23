# 기사 생성 연결과 비공개 품질 검수

사용자 “진행시켜”를 DART 준비 다음의 기사 품질 검수 진행으로 적용한다. 기존 u184/u185/u186/u172의 제한된 후속이며 필요한 코드 전달, 정확한 CI와 전용 preview pin/workflow 갱신 및 국내 article_v2 비게시 실행 1회를 포함한다.

## Stage Decision

Functional Design/NFR Requirements는 아래 계약으로 완료한다. 기존 FR-001/002/017/021/023/024, NFR-002/003/005/006/007/008 및 공통 preparation·native context·private preview·Codex auth owner를 재사용한다. 신규 provider, 유료 API, 공개 게시 경로는 없다. 사람의 사전 annotation과 최종 평가는 AI 검수로 대체하지 않는다.

- 최신 main의 별도 계약조건 정정 v2 및 retry feedback을 보존하고 검수된 schedule branch를 통합한다. parser는 price/schedule/terms 간 자동 fallback 없이 각 계약을 유지한다.
- 기사 preview의 schedule 선택은 dart body·official body·schema3/article_v2를 요구한다. trusted code checkout의 qualification과 slot matrix를 수집 전에 검증하고 같은 matrix를 공통 preparation에 전달한다.
- Codex wrapper/workflow가 DART 선택값을 실제 전달하도록 연결한다. 기본 off/price를 유지하고 이번 수동 실행만 schedule을 선택한다.
- record-model-io 모드에서 routed input/native context를 256KiB, DART preparation 응답 bytes를 총192KiB, 모델 녹화를 기존1MiB, edition128KiB, Markdown256KiB 이내로 private 보관한다. 전체 암호화2MiB/12파일 한도를 유지하고 넘치면 자르지 않고 차단한다. DART 외 collector 전체 HTTP를 기록하지 않는다. token/header/auth 자료를 기록하지 않는다.
- source snapshot을 모델 호출 전에 기록하고 동일 native context를 생성기에 전달한다. 현재 관측창에 없는 과거 공시는 재삽입하지 않는다. 성공·quiet·source-limited·실패를 결과대로 기록한다.
- 기존 article 전역5call/최대1회 수정·auth lock/refresh/cleanup 예산을 유지한다. 모델 응답을 수동 수정해 성공으로 세지 않는다. 암호문은 즉시 확보하고 같은 실행의 입력·refs·모델IO·최종 문서를 독립 대조한다.
- 전용 REVIEWED_EVENT_PREVIEW_SHA만 정확한 CI 성공 코드로 바꾼다. production/DART 진단 pin·일정·게시·알림·ledger/cursor는 보존한다. 다른 작업의 갱신을 되돌리지 않는다.

## 단계

- [x] 1. 준비 결과와 기사/운영 수용 계약, 최신 main·private 설정을 조사한다.
- [x] 2. parser branch 통합, preview profile 전달과 bounded private evidence를 구현·검수한다.
- [x] 3. 정확한 CI 통과 후 전용 preview에 반영하고 현재 날짜 국내 비게시 실행 1회의 암호문을 즉시 확보한다.
- [x] 4. 실제 결과의 사실·근거·내용·봉인/실패 원인을 독립 검수하고 발견된 결함은 범위 내 수리한다.
- [x] 5. 검수 가능한 자료와 운영 전환 잔여 조건을 기록한다.

## 완료와 잔여 구분

이 실행의 technical/AI 품질 판정과 human corpus12, 시장별4/2일, viewport·성능·운영/예약 인수를 분리한다. 독립 공식 목록의 사전 human annotation이 없으면 external recall과 human 점수를 미확인으로 유지한다. 운영 전환은 그 수용 조건이 충족되어야 하며 현재 실행 성공만으로 활성화하지 않는다.

## 실제 결과에 따른 수리 확장

첫 run45122245131은 봉인·출처 대조에 성공했지만 core-only 단일 사실을 detailed_ready로 판정하는 Medium1을 발견했다. B185의 단순 완결 사건=brief 규칙에 따라 이 판정을 수리하고, 정확한 새 코드 CI 뒤 같은 날짜 국내 preview를 1회 재실행한다. 첫 원본·모델 응답은 보존하며 재실행을 별도 사람 corpus 표본으로 세지 않는다.

- impact만으로 상세 자격을 부여하지 않고 packet에 닫힌 detail_basis를 기록한다. context_only와 단일 text-action/설명 근거 없는 core_only는 brief 상한이다.
- 명시적으로 배정된 background/comparison/meaning/followup refs, 중복 summary 외 source body, 숫자/복수 fact는 기존 상세 검토 자격을 유지한다. 이 자격은 의미 검수 합격을 대신하지 않는다. summary 형식·글자 수·문장 수로 일괄 차단하지 않는다.
- writer/reviewer는 핵심 주체·행위·대상·상태 및 업종 소개 반복을 why 설명으로 인정하지 않는다. 실제 비교·영향 범위·절차·조건을 근거로 답해야 한다.
- 새 policy hash와 terminal packet 재구성으로 판정 근거를 결속한다. 기존 packet의 default 직렬화/hash는 읽기 호환을 유지한다.
- 원run의 같은 근거·fact IDs에서 core_only/expected_detail=false로 재생하고, synthetic 핵심 반복 거절·조건 있는 summary·숫자 비교·본문·context-only 보존을 검증한다.

최종: 수정본5d9885d2/CI45123784115 통과, 실제45125524648에서3calls·core_only/brief_ready·detailed0 봉인 및 독립C/H/M/L0. 하위계획5/5를 완료하며 상위 unit·source/사람/운영 수용은 완료로 변경하지 않는다.
