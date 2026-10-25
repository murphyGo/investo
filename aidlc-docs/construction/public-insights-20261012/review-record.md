# 설계 검토 기록

작성일: 2026-10-12. 역할: main agent의 문서·현행 코드 대조. 별도 에이전트 검토와 제품 테스트를 수행했다고 주장하지 않는다.

## 검토와 반영

| 검토 항목 | 발견한 문제 / 결정 | 최종 반영 |
| --- | --- | --- |
| 유닛·story 번호 | 원격 등록은 u179, US-010은 이미 섹터 화면 소유 | u180–u183, US-011–013, FR-026–029를 별도 등록 |
| 시황 실패와 데이터 화면 | 기존 collector는 재사용 가능하지만 게시가 LLM 결과에 묶여 있음 | collection 1회·LLM 전 독립 dashboard phase·typed 결과·기존 시황 status 보존 |
| Pages 결과 신호 | production workflow는 briefing publication_committed만 확인 | 별도 insights 확정 신호와 Pages OR 조건·실패 후 기존 exit code 재발급·확정 SHA 사용 |
| H.10 시각·주기 | 현행 adapter는 source_date와 NY12:00 convention. 일별 관측과 주간 공표는 별개 | 관측 convention을 공표시각으로 표시하지 않음; 주간 공표/연방휴일 이월로 freshness 판단 |
| 금리 휴일 | NYSE 휴장과 NY Fed 휴일·SOFR/EFFR의 특정 공표 예외가 다름 | 지표별 publication calendar와 미지원 연도 unknown·비교 억제 |
| 일정 precision | FRED/Fed/auction의 UTC 자정은 date-level placeholder | 현지 날짜·기간을 보존하고 exact만 KST 변환; 발표 완료/actual join 제외 |
| source 권리 | 현재 snapshot도 Git commit에 남으며 rolling 파일 상한이 과거 commit을 없애지 않음 | current에도 display+public_git_history 허가 필요; 분석 이력 허용은 추가 축 |
| fallback provenance | producing OKX와 실제 caller Bybit의 outcome이 다를 수 있음 | collector-bound origin과 producing source 분리, 기존 fallback만 허용, S31 추가 |
| 비교·가격 의미 | CPI 지수, 펀딩 주기, venue OI, 공급/TVL은 서로 다른 의미 | 지수→YoY/주기→24h 평균/TVL→netflow 추론0; provider/contract 전환 비교0 |
| DEBT-079 | 기존 문구와 달리 현재 FRED calendar/BLS에 explicit macro_event_key 있음 | debt 전체 해결을 주장하지 않으며 upcoming-only u182에 불필요한 repair 의존성 추가0 |
| 기존 운영과 상태 | 새 문서로 기존 u145/v3/source pin·gate를 바꾸면 안 됨 | 기존 9개 문서는 append-only, source/코드/배포 변경0, 신규 단계는 Draft/Planned |

## 확인한 문서 검사

- 첫 전체 검증: 52개 문서, local link 123개, 기존 9개 파일의 원 내용 보존, 구현 Step 31개 미완료, whitespace·conflict·fence·placeholder·유닛/등록 참조 오류0.
- `git diff --check`: PASS. 신규 파일도 별도 whitespace/conflict 검사를 수행했다.
- 계획·Functional Design·NFR·공통 계약의 필수 링크와 구현 단계 수를 대조했다.
- 새 production Python·test·source registry·workflow 파일 변경0. `docs/`와 `aidlc-docs/`의 설계 문서만 추가/등록했다.
- 모든 문서는 public `site_docs/` 밖이다. 문서 작업 때문에 제품 full pytest/MkDocs/viewport/운영 수용을 실행하지 않았다.

최종 검사 결과는 [design-validation.json](design-validation.json)에 기록한다. 숫자·clock·source·CAS·Pages의 실제 구현 수용은 각 code-generation plan과 [수용 시나리오](acceptance-scenarios.md)의 후속 작업이다.

## 현재 상태

설계 초안과 등록 검토는 완료했다. 산출물 승인·구현·원격 delivery·공개 카드 qualification·private runtime activation·실제 viewport·5회 예약 관찰은 미실행으로 구별한다. 이번 요청에서 구현 단계에 진입하지 않았다.
