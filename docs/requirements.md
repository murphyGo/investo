# Project Requirements: Investo

*Generated via interactive refinement on 2026-04-25*

## 1. Overview

### Problem Statement
매일 아침 미국 주식·크립토(보조: 코스피)의 동향을 파악하기 위해 직접 뉴스를 찾고 분석하는 작업은 시간이 많이 들고 일관성이 없다. **자동화된 데일리 시황 생성기**가 있으면 매일 일관된 형식으로 (a) 전일 핵심 이슈, (b) 섹터·수급 동향, (c) 주요 지표·연준 이벤트, (d) 주요 종목/실적 이슈, (e) 시장 방향성과 관전 포인트를 받아볼 수 있어 의사결정에 도움이 된다.

### Target Users
- **1차 사용자**: 본인 (개인 투자자, 한국 거주, 미국 주식 + 크립토 + 코스피 관심)
- **2차 열람자**: 본인이 공유하는 지인 (인증 불필요, GitHub Pages public)
- **운영자**: 본인 1인 (코드/스크립트 직접 관리)

### Success Metrics
- 매일 정해진 시각에 시황이 자동 생성·게시됨 (실패율 ≤ 5%)
- 시황 품질: 전일 핵심 이슈 누락 없음, 섹터/종목 사실 오류 없음
- 본인이 매일 시황을 읽고 투자 판단에 참고함 (정성적)
- 월 운영비 0원 (Claude Code 구독 외)

## 2. Functional Requirements

### FR-001: 데이터 수집
- **Description**: 매일 정해진 시각에 미국 주식·크립토·(코스피) 관련 뉴스, 주요 지표, 연준 이벤트, 실적 캘린더, 시세를 수집한다.
- **User Story**: As a 본인, I want 무료 공개 소스에서 전일 시장 데이터를 자동 수집받기를, so that 직접 뉴스를 뒤지지 않아도 시황 작성 재료가 준비되도록.
- **Acceptance Criteria**:
  - [ ] 무료 API/RSS만 사용한다 (월 $0)
  - [ ] 소스 카테고리: 주가/지수, 크립토 시세, 거시 지표(FRED 등), 연준 캘린더, 주요 기업 뉴스, 실적 캘린더
  - [ ] 신규 소스 추가/제거가 코드 변경 1곳으로 가능 (plugin/registry 구조)
  - [ ] 단일 소스 실패 시 다른 소스 수집은 계속 진행 (graceful degradation)
- **Priority**: Must-have

### FR-002: AI 시황 작성
- **Description**: 수집된 데이터를 입력으로, **Claude Code CLI**(GitHub Actions에서 setup token 인증)를 호출해 한국어 시황을 생성한다.
- **User Story**: As a 본인, I want 일관된 형식의 한국어 시황을, so that 빠르게 훑어보고 핵심을 파악할 수 있도록.
- **Acceptance Criteria**:
  - [ ] LLM 호출은 Claude Code CLI를 통해 수행 (Anthropic API key 직접 호출 금지)
  - [ ] 출력은 정해진 섹션 템플릿 준수: ①요약 ②전일 핵심 이슈 ③섹터/수급 동향 ④지표·이벤트 ⑤주요 종목 ⑥오늘의 관전 포인트 ⑦면책조항
  - [ ] 한국어로 작성, 영문 종목명/티커는 원문 유지
  - [ ] 면책조항 자동 삽입 ("투자 자문이 아닌 정보 제공" 명시) — NFR-004 참조
  - [ ] LLM 호출 실패 시 retry (최대 N회), 최종 실패 시 빈 시황 게시 금지 → 알림
- **Priority**: Must-have

### FR-003: 정적 웹 게시
- **Description**: 생성된 시황을 GitHub Pages 정적 사이트에 게시한다. 모든 과거 시황은 이력으로 보관·열람 가능.
- **User Story**: As a 열람자, I want 오늘 시황과 과거 시황을 웹에서 볼 수 있기를, so that 시점별 시장 흐름을 추적할 수 있도록.
- **Acceptance Criteria**:
  - [ ] 시황은 markdown 파일로 git repo에 저장 (예: `archive/2026/04/2026-04-25.md`)
  - [ ] 정적 사이트 생성기로 빌드 → GitHub Pages 배포
  - [ ] 날짜별 인덱스, 최신 시황 홈 노출
  - [ ] 검색 또는 최소한 날짜/연도별 탐색 가능
- **Priority**: Must-have

### FR-004: 텔레그램 시황 채널 알림
- **Description**: 시황 생성 직후 **공개 Telegram 채널/그룹**으로 요약을 전송한다. 운영자 본인과 공유 받은 Public Reader가 동일 채널에 join하여 푸시를 수신한다.
- **User Story**: As a 운영자/Public Reader, I want 텔레그램 채널 푸시로 시황 요약을 받기를, so that 웹사이트를 열지 않아도 핵심을 알 수 있도록.
- **Acceptance Criteria**:
  - [ ] Telegram Bot API 사용 (Bot 토큰은 GitHub Secrets — `TELEGRAM_BOT_TOKEN`)
  - [ ] 발송 대상: **공개 Telegram 채널 또는 그룹** (`TELEGRAM_BRIEFING_CHANNEL_ID` 시크릿). 누구나 채널 링크로 join 가능.
  - [ ] 메시지에 웹 URL 링크 포함 (전체 시황 열람용)
  - [ ] 텔레그램 메시지 길이 제한(4096자) 준수 — 초과 시 요약 + 링크
  - [ ] 텔레그램 발송 실패는 시황 게시 자체를 막지 않음 (게시는 성공, 알림만 실패)
  - [ ] 공개 채널이므로 시크릿/PII가 메시지에 포함되지 않도록 검증
  - [ ] 운영자 실패 알림(FR-007)과는 **별도 chat**을 사용 — 공개 채널에 노이즈 주입 금지
- **Priority**: Must-have

### FR-005: 스케줄 실행
- **Description**: GitHub Actions cron으로 매일 자동 실행한다.
- **User Story**: As a 본인, I want 매일 같은 시각에 자동 실행되기를, so that 수동 트리거가 필요 없도록.
- **Acceptance Criteria**:
  - [ ] GitHub Actions `schedule` cron 트리거
  - [ ] 평일: 미국장 마감 후 충분한 데이터 확보 시각 (예: 한국시간 평일 오전 7시 = UTC 22:00)
  - [ ] 주말: 토요일 1회 (주간 리뷰)
  - [ ] 수동 트리거(`workflow_dispatch`)도 지원
  - [ ] 실행 시간 ≤ 10분 (NFR-001)
- **Priority**: Must-have

### FR-006: 영구 이력 보관
- **Description**: 생성된 모든 시황을 영구 보관한다.
- **User Story**: As a 본인, I want 과거 시황을 모두 보관하기를, so that 시점별 시장 분석을 회고할 수 있도록.
- **Acceptance Criteria**:
  - [ ] 시황은 git commit으로 영구 저장
  - [ ] 폴더 구조: `archive/YYYY/MM/YYYY-MM-DD.md`
  - [ ] 저장 용량 문제 발생 시 (수년 후) 별도 archival 정책 검토 — 현재는 Out of Scope
- **Priority**: Must-have

### FR-007: 운영자 실패 알림
- **Description**: 시황 생성 파이프라인 실패 시 **운영자 본인 1:1 chat**으로 알림한다. 공개 시황 채널(FR-004)과 분리하여 일반 구독자에게 노이즈를 주지 않는다.
- **User Story**: As a 운영자, I want 실패 시 별도 chat으로 즉시 알게 되기를, so that 빠르게 조치할 수 있고 일반 구독자가 노이즈를 보지 않도록.
- **Acceptance Criteria**:
  - [ ] 파이프라인 실패 시 운영자 텔레그램 1:1 chat 알림 (`TELEGRAM_OPERATOR_CHAT_ID` 시크릿)
  - [ ] GitHub Actions의 기본 실패 알림(이메일/배너)도 함께 활용
  - [ ] 실패 사유(어느 단계? 어떤 에러? stack trace 요약) 메시지에 포함
  - [ ] 공개 시황 채널(FR-004)에는 실패 메시지 발송 금지
  - [ ] 알림 자체 실패 시 재시도 후 GitHub Actions 로그에라도 명시적으로 마킹
- **Priority**: Should-have

## 3. Non-Functional Requirements

### NFR-001: Performance
- 시황 생성 1회 실행 시간 ≤ 10분 (GitHub Actions 단일 job 실행)
- 데이터 수집 단계 동시 실행 (asyncio)으로 latency 단축

### NFR-002: Cost
- **목표 운영비: 월 $0**
- Claude Code 구독 외 추가 LLM API 비용 없음 → Claude Code CLI를 GitHub Actions에서 setup token으로 인증해 호출
- 모든 데이터 소스 무료 tier 한도 내 사용
- GitHub Actions 무료 한도 내 운영 (public repo면 무제한)

### NFR-003: Reliability
- 외부 API 호출은 timeout + retry (지수 backoff) 적용
- 단일 데이터 소스 실패가 전체 파이프라인을 죽이지 않음 (graceful degradation)
- 시황 생성 실패 시 빈/저품질 시황 게시 금지 (실패 알림만 발송)

### NFR-004: Compliance / Disclaimer
- 모든 시황에 면책조항 자동 삽입: 투자 자문이 아니며 정보 제공 목적이라는 명시 + 손실 책임 면책
- 시황은 한국어로 작성, 종목명/티커는 영문 원문

### NFR-005: Maintainability
- **Plugin 구조**: 새 데이터 소스를 단일 모듈 추가로 통합 가능
- **시황 포맷 템플릿화**: 섹션 정의·프롬프트가 코드와 분리 (예: `templates/briefing.md.j2` 또는 yaml)
- 코드 스타일: ruff (lint/format), mypy (type), pytest (unit)
- **Property-based testing 일부 적용** (NFR-006): 순수 함수와 직렬화 round-trip만

### NFR-006: Testing
- 핵심 비즈니스 로직 unit test
- **PBT 부분 적용**: 순수 함수(데이터 정규화, 섹터 분류, 포맷 변환)와 직렬화 round-trip에 hypothesis 사용
- LLM 호출은 record/replay fixture로 재현 가능 테스트

### NFR-007: Security (baseline 미적용)
- API 키/Bot 토큰은 모두 GitHub Secrets에 저장 (코드/로그에 노출 금지)
- public repo 운영 가정이므로 시크릿 외에는 모두 공개 가능
- 사용자 계정/PII 없음 → 별도 보안 강화 불필요 (Security extension SKIP)

## 4. Technical Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | 사용자 선호, 데이터/AI 생태계 |
| LLM Runtime | **Claude Code CLI (setup token via GitHub Secrets)** | Anthropic API 별도 요금 회피, 구독 활용 |
| HTTP Client | httpx | async + 모던, retry/timeout 친화적 |
| Validation | pydantic v2 | 외부 API 응답 데이터 모델링 |
| Web Generator | MkDocs Material | 정적 markdown 사이트, GitHub Pages 친화 |
| Hosting | GitHub Pages | 무료, GitHub Actions와 native 연동 |
| Notification | Telegram Bot API (raw HTTP) | 의존성 최소, 한국 친숙 |
| Scheduler | GitHub Actions cron | 무료, 사용자 요구 |
| Storage | Git repo (markdown files in `archive/`) | 영구 이력, 검색·diff 가능 |
| Secret Mgmt | GitHub Secrets | native, 코드와 분리 |
| Lint/Format | ruff | 단일 빠른 도구 |
| Type Check | mypy (strict) | 타입 안정성 |
| Test | pytest | 표준 |
| Property-Based Test | hypothesis (partial — pure func + serialization) | NFR-006 |
| Dep Mgmt | uv 또는 pip + requirements.txt | 빠른 install, lock file |

## 5. Constraints & Assumptions

### Constraints
- **LLM은 Claude Code CLI로만 호출** — Anthropic API key 사용 불가 (사용자 명시)
- 일 1회 배치 (실시간 시세/뉴스 아님)
- GitHub Actions 단일 job 실행 시간 한도
- 무료 데이터 소스의 rate limit 및 데이터 품질 한계
- public repo 운영 (GitHub Actions 무제한 활용 위해)

### Assumptions
- 본인이 Claude Max/Pro 구독자이며 Claude Code setup token 발급 가능
- 텔레그램 봇 1개 생성·운영 가능 (Bot Father로 토큰 발급)
- public GitHub repo로 운영 가능 (코드·시황 모두 공개)
- 한국시간 기준 미국장 마감 후 ~ 다음 새벽 사이 시점에 데이터 수집 가능

## 6. Out of Scope (MVP)

- 실시간 시황/주가/알람
- 사용자 계정·인증·구독 관리
- **포트폴리오 트래킹** (향후 확장)
- **기업 펀더멘털 심층 분석** (향후 확장)
- 모바일 네이티브 앱 (텔레그램으로 대체)
- 매수/매도 자동 실행 (절대 안 함)
- 유료 데이터 소스
- 한국어 외 언어 시황
- 다중 사용자/구독 관리

## 7. Open Questions

- **무료 데이터 소스 정확한 조합** — 후보: Alpha Vantage, Finnhub free, Yahoo Finance(yfinance), FRED, CoinGecko, NewsAPI free, FOMC RSS, SEC EDGAR. 구현 단계에서 PoC로 결정.
- **시황 작성 정확한 시각** — 한국시간 평일 오전 7시 기본, 주말 토요일 오전 9시 (가설)
- **텔레그램 발송 대상** — 본인 1:1 chat ID 또는 private 채널 (구현 시 결정)
- **시황 출력 포맷 디테일** — 섹션은 정해졌으나 각 섹션 길이/스타일 가이드 필요
- **Claude Code CLI 호출 패턴** — `-p` 비대화형 모드, prompt 입력 방식, output 파싱 전략 (구현 시 결정)
- **GitHub Pages 사이트 디자인** — MkDocs Material 기본 테마 사용 가정
