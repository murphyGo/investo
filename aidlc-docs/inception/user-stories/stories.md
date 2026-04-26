# User Stories: Investo

**Date**: 2026-04-26
**Format**: INVEST + 체크리스트 acceptance criteria (Q3=B)
**Breakdown**: Feature-Based, US-ID ↔ FR-ID 1:1 + 운영성 NFR 별도 (Q4=A, Q6=C)
**AC depth**: 표준 — 정상 + 주요 실패 + NFR 연결 (Q5=B)

---

## Personas Reference
- **P1 Operator-User**: 본인 (운영자 + 1차 사용자)
- **P2 Public Reader**: 지인/익명 사이트 방문자 (옵션 텔레그램 구독)

전체 페르소나 정의는 `personas.md` 참조.

---

## Daily Operator Journey (narrative — Q7=B)

평일 KST 07:00. 운영자가 출근 준비 중 모바일에서 텔레그램 알림을 받는다 (US-004). 요약을 30초 훑고, 흥미로운 부분이 있으면 본문 링크를 눌러 GitHub Pages에서 전체 시황을 본다 (US-003). 만약 알림이 오지 않았다면 1:1 chat으로 실패 메시지가 도착해 있을 것이다 (US-007) — GitHub Actions 로그를 열어 원인을 확인하고 수동 재실행하거나 코드 수정 후 다시 트리거한다 (US-005). 새 무료 데이터 소스를 발견하면 plugin 모듈 1개를 추가해 다음 실행에 반영한다 (US-008). 비용은 월 0을 유지한다 (US-009).

---

## US-001 (← FR-001): 매일 시장 데이터를 자동 수집한다

**As a** Operator-User,
**I want** 매일 정해진 시각에 무료 공개 소스에서 미국 주식·크립토(+ 코스피) 관련 뉴스·시세·거시 지표·연준 이벤트·실적 캘린더를 수집받기를,
**So that** 직접 뉴스를 뒤지지 않고 시황 작성 재료가 자동으로 준비되도록.

**Personas**: P1
**Acceptance Criteria**:
- [ ] 무료 API/RSS만 사용 (월 $0 — NFR-002 연결)
- [ ] 카테고리별 소스 1개 이상: 주가/지수, 크립토 시세, 거시 지표, 연준 캘린더, 주요 기업 뉴스, 실적 캘린더
- [ ] 신규 소스 추가는 단일 모듈 추가로 가능 (plugin/registry 구조 — NFR-005 연결, US-008 별도)
- [ ] 단일 소스 실패 시 다른 소스 수집은 계속 진행 (graceful degradation — NFR-003 연결)
- [ ] 각 소스 응답을 구조화 모델(pydantic)로 검증, 실패 시 로그만 남기고 해당 항목 제외

**INVEST**: Independent (수집 단계만 검증) · Negotiable (소스 조합 협상 가능) · Valuable (재료 없으면 시황 작성 불가) · Estimable · Small (단일 단계) · Testable (mock 데이터로 단위 테스트)

---

## US-002 (← FR-002): AI가 한국어 데일리 시황을 작성한다

**As a** Operator-User / Public Reader,
**I want** 수집된 데이터로부터 일관된 7섹션 한국어 시황을 자동 생성받기를,
**So that** 빠르게 훑어보고 핵심을 파악할 수 있도록.

**Personas**: P1, P2
**Acceptance Criteria**:
- [ ] LLM 호출은 **Claude Code CLI**로 수행 (Anthropic API key 직접 호출 금지 — NFR-002 연결)
- [ ] 출력 섹션 순서 고정: ①요약 ②전일 핵심 이슈 ③섹터/수급 동향 ④지표·이벤트 ⑤주요 종목 ⑥오늘의 관전 포인트 ⑦면책조항
- [ ] 한국어로 작성, 영문 종목명/티커는 원문 유지
- [ ] **면책조항 자동 삽입** — "투자 자문이 아닌 정보 제공" + 손실 책임 면책 (NFR-004 연결)
- [ ] LLM 호출 실패 시 retry (지수 backoff), 최종 실패 시 빈/저품질 시황 게시 금지 (NFR-003 연결)
- [ ] 시황 본문에 시크릿/PII가 포함되지 않도록 출력 검증 (FR-004 공개 채널 안전)

**INVEST**: Independent (수집 결과를 입력으로) · Valuable (핵심 가치 — 본 도구의 존재 이유) · Testable (record/replay fixture로 LLM 호출 재현)

---

## US-003 (← FR-003): GitHub Pages에 시황을 정적 게시한다

**As a** Public Reader / Operator-User,
**I want** 매일 시황과 과거 시황을 웹에서 인증 없이 열람할 수 있기를,
**So that** 시점별 시장 흐름을 추적할 수 있도록.

**Personas**: P1, P2
**Acceptance Criteria**:
- [ ] 시황은 markdown 파일로 git repo에 저장 (예: `archive/2026/04/2026-04-26.md`)
- [ ] 정적 사이트 생성기(MkDocs Material)로 빌드 → GitHub Pages 배포
- [ ] 최신 시황이 홈에 노출되며 날짜/연도별 인덱스로 과거 시황 탐색 가능
- [ ] 모바일에서 가독성 보장 (반응형 테마)
- [ ] 빌드 실패 시 기존 사이트는 유지되며 운영자에게 알림 (FR-007)
- [ ] 사이트는 인증 없이 누구나 열람 (NFR-007 — 시크릿 외 모두 공개)

**INVEST**: Independent (US-002 산출물 사용) · Valuable (열람 채널의 핵심) · Small · Testable (빌드 산출물 점검)

---

## US-004 (← FR-004): 공개 텔레그램 채널로 시황 요약이 푸시된다

**As a** Operator-User / Public Reader,
**I want** 텔레그램 채널에서 매일 시황 요약 푸시를 받기를,
**So that** 사이트를 열지 않아도 모바일에서 핵심을 파악하고, 원하면 링크로 전체 시황을 볼 수 있도록.

**Personas**: P1, P2
**Acceptance Criteria**:
- [ ] Telegram Bot API 사용 (`TELEGRAM_BOT_TOKEN` 시크릿)
- [ ] 발송 대상: **공개 채널 또는 그룹** (`TELEGRAM_BRIEFING_CHANNEL_ID`) — 누구나 join 가능
- [ ] 메시지에 GitHub Pages 시황 URL 포함 (전체 시황 열람용)
- [ ] 메시지 길이 4096자 한도 준수 — 초과 시 요약 + 링크
- [ ] 텔레그램 발송 실패해도 시황 게시 자체는 성공 (NFR-003 연결)
- [ ] 메시지 본문에 시크릿/PII 미포함 검증 (공개 채널 노출 안전)
- [ ] 운영 실패 알림(US-007)과는 **다른 chat** 사용 → 일반 구독자 노이즈 방지

**INVEST**: Independent (US-002 산출물을 입력으로 요약) · Valuable (모바일 접근성) · Testable (Bot API mock)

---

## US-005 (← FR-005): GitHub Actions cron으로 자동 실행된다

**As a** Operator-User,
**I want** 매일 같은 시각에 파이프라인이 자동 실행되기를,
**So that** 수동 트리거 없이 시황이 정기적으로 게시되도록.

**Personas**: P1
**Acceptance Criteria**:
- [ ] GitHub Actions `schedule` cron 트리거 사용
- [ ] 평일: 한국시간 오전 7시 (UTC 22:00 전일)
- [ ] 주말: 토요일 한국시간 오전 9시 1회
- [ ] `workflow_dispatch`로 수동 트리거도 지원 (디버깅/재실행용)
- [ ] 단일 job 실행 시간 ≤ 10분 (NFR-001 연결)
- [ ] 실행 시각/지속시간을 GitHub Actions 로그로 확인 가능

**INVEST**: Independent (인프라 설정) · Valuable (자동화의 트리거) · Small · Testable (workflow_dispatch로 즉시 검증)

---

## US-006 (← FR-006): 모든 시황을 영구 보관한다

**As a** Operator-User / Public Reader,
**I want** 과거 시황을 모두 영구 보관·열람할 수 있기를,
**So that** 시점별 시장 분석을 회고할 수 있도록.

**Personas**: P1, P2
**Acceptance Criteria**:
- [ ] 시황은 git commit으로 저장 (영구, diff 가능)
- [ ] 폴더 구조: `archive/YYYY/MM/YYYY-MM-DD.md`
- [ ] GitHub Pages 인덱스에서 연도/월/날짜로 탐색 가능
- [ ] 저장 용량이 문제 될 정도(수년 후)면 별도 archival 정책 검토 (현재 Out of Scope)
- [ ] 동일 날짜 재생성 시 기존 파일 덮어쓰기 정책 명시 (default: 덮어쓰기 + 이전 버전은 git history)

**INVEST**: Independent (저장 방식만) · Valuable (회고/검색) · Testable (파일 시스템 검증)

---

## US-007 (← FR-007): 파이프라인 실패 시 운영자 1:1 chat으로 알림 받는다

**As a** Operator-User,
**I want** 파이프라인 실패 시 별도 1:1 텔레그램 chat으로 즉시 알림 받기를,
**So that** 빠르게 조치하고 일반 구독자에게 노이즈가 가지 않도록.

**Personas**: P1
**Acceptance Criteria**:
- [ ] 실패 발생 시 `TELEGRAM_OPERATOR_CHAT_ID`로 알림 발송
- [ ] 메시지에 실패 단계 + 에러 메시지(또는 stack trace 요약) 포함
- [ ] **공개 시황 채널(US-004)에는 실패 메시지 발송 금지**
- [ ] GitHub Actions 기본 실패 알림(이메일)도 함께 활성
- [ ] 알림 발송 자체가 실패하면 GitHub Actions 로그에 명시적 마킹

**INVEST**: Independent (실패 처리만) · Valuable (운영 안정성) · Small · Testable (의도적 실패 주입)

---

## US-008 (← NFR-005): 새 데이터 소스를 단일 모듈 추가로 통합한다

**As a** Operator-User,
**I want** 새 무료 데이터 소스를 단일 plugin 모듈 추가로 통합할 수 있기를,
**So that** 시황 품질 개선이 코드 1곳 변경으로 가능하도록.

**Personas**: P1
**Acceptance Criteria**:
- [ ] 새 소스 통합 = (1) 모듈 파일 1개 추가 + (2) registry 한 줄 등록 (이상 변경 없음)
- [ ] 각 소스는 공통 인터페이스 (예: `fetch() -> list[NormalizedItem]`)를 구현
- [ ] 소스의 timeout/retry 정책은 공통 베이스에서 제공
- [ ] 단일 소스 실패는 전체 파이프라인을 죽이지 않음 (US-001 graceful degradation 연결)
- [ ] 신규 소스 추가 PR 예시·체크리스트 README/CONTRIBUTING에 기술

**INVEST**: Independent (구조적 요구) · Valuable (확장성/유지보수) · Estimable · Small (인터페이스 정의 + 1개 reference 구현) · Testable (interface conformance test)

---

## US-009 (← NFR-002): 운영비를 월 $0으로 유지한다

**As a** Operator-User,
**I want** 모든 LLM 호출과 데이터 호출이 무료 한도 내로만 운영되기를,
**So that** Claude Code 구독 외에는 추가 비용이 발생하지 않도록.

**Personas**: P1
**Acceptance Criteria**:
- [ ] LLM은 **Claude Code CLI**(GitHub Secrets `CLAUDE_CODE_OAUTH_TOKEN`)로만 호출 — Anthropic API key 직접 호출 금지
- [ ] 데이터 소스는 모두 무료 tier — 유료 호출이 발생할 수 있는 소스는 등록 금지
- [ ] GitHub Actions 무료 한도 내 (public repo면 무제한)
- [ ] 비용 위험 발견 시(예: 유료 API key 등록 시도) CI lint/grep 등으로 차단 검토
- [ ] 외부 LLM/API 호출 추가 시 PR 설명에 비용 영향 명시 의무

**INVEST**: Independent (정책 준수 검증) · Valuable (지속 가능성의 핵심 제약) · Small (정책 + 검증) · Testable (lint rule, README 게이트)

---

## Story ↔ FR/NFR Traceability

| Story | Source | NFR Tied via AC |
|-------|--------|-----------------|
| US-001 | FR-001 | NFR-002, NFR-003 |
| US-002 | FR-002 | NFR-002, NFR-003, NFR-004 |
| US-003 | FR-003 | NFR-007 |
| US-004 | FR-004 | NFR-003, NFR-007 |
| US-005 | FR-005 | NFR-001 |
| US-006 | FR-006 | — |
| US-007 | FR-007 | NFR-003 |
| US-008 | NFR-005 | (별도 스토리화) |
| US-009 | NFR-002 | (별도 스토리화) |

NFR-006(Testing) 및 NFR-007(Security)은 별도 스토리화하지 않고 각 스토리의 AC와 코드 표준에 흡수.

## Story ↔ Persona Map

| Story | P1 Operator | P2 Public Reader |
|-------|:-----------:|:----------------:|
| US-001 | ✅ | — |
| US-002 | ✅ | ✅ (소비) |
| US-003 | ✅ | ✅ |
| US-004 | ✅ | ✅ (옵션 구독) |
| US-005 | ✅ | — |
| US-006 | ✅ | ✅ |
| US-007 | ✅ | — |
| US-008 | ✅ | — |
| US-009 | ✅ | — |
