# Project Requirements: Investo

*Generated via interactive refinement on 2026-04-25*

## 1. Overview

### Problem Statement
매일 아침 국내 증시, 미국 증시, 크립토의 동향을 따로 파악하기 위해 직접 뉴스를 찾고 분석하는 작업은 시간이 많이 들고 일관성이 없다. **자동화된 데일리 시황 생성기**가 있으면 매일 일관된 형식으로 (a) 전일 핵심 이슈, (b) 섹터·수급 동향, (c) 주요 지표·연준 이벤트, (d) 주요 종목/실적 이슈, (e) 시장 방향성과 관전 포인트를 받아볼 수 있어 의사결정에 도움이 된다.

### Target Users
- **1차 사용자**: 본인 (개인 투자자, 한국 거주, 국내 증시 + 미국 주식 + 크립토 관심)
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
  - [x] 무료 API/RSS만 사용한다 (월 $0)
  - [x] 소스 카테고리: 주가/지수, 크립토 시세, 거시 지표(FRED 등), 연준 캘린더, 주요 기업 뉴스, 실적 캘린더
  - [x] 신규 소스 추가/제거가 코드 변경 1곳으로 가능 (plugin/registry 구조)
  - [x] 단일 소스 실패 시 다른 소스 수집은 계속 진행 (graceful degradation)
  - [x] 시장별 거래일 기준을 적용한다: 국내 증시는 KST, 미국 증시는 America/New_York, 크립토는 UTC 기준으로 `target_date` 데이터를 필터링한다.
- **Priority**: Must-have

### FR-008: 세그먼트별 시황 생성
- **Description**: 단일 통합 시황 대신 국내 증시, 미국 증시, 크립토를 각각 독립 세그먼트로 생성한다. 한 소스군의 강한 이슈가 다른 자산군의 시황을 압도하지 않도록 입력 분리, 최소 커버리지, 섹션별 품질 기준을 둔다.
- **User Story**: As a 본인, I want 국내/미국/크립토 시황을 분리해서 받기를, so that 각 시장의 핵심 흐름을 빠르게 비교하고 한쪽 시장 뉴스에 전체 브리핑이 끌려가지 않도록.
- **Acceptance Criteria**:
  - [x] 매 실행마다 `domestic-equity`, `us-equity`, `crypto` 세그먼트를 생성한다.
  - [x] 각 세그먼트는 독립 제목과 ①~⑥ 본문 섹션을 가진다. ⑦ 면책조항은 기존처럼 코드가 공통 삽입한다.
  - [x] 세그먼트별 입력은 source/category/ticker/news provenance 기반으로 분리한다.
  - [x] 특정 세그먼트의 핵심 소스가 부족하면 다른 세그먼트 뉴스로 대체하지 않고 "데이터 부족"을 명시한다.
  - [x] 텔레그램 메시지는 세 세그먼트의 짧은 요약과 각 상세 링크를 포함한다.
- **Priority**: Must-have (post-MVP correction)

### FR-002: AI 시황 작성
- **Description**: 수집된 데이터를 입력으로, **Claude Code CLI**(GitHub Actions에서 setup token 인증)를 호출해 한국어 시황을 생성한다.
- **User Story**: As a 본인, I want 일관된 형식의 한국어 시황을, so that 빠르게 훑어보고 핵심을 파악할 수 있도록.
- **Acceptance Criteria**:
  - [x] LLM 호출은 Claude Code CLI를 통해 수행 (Anthropic API key 직접 호출 금지)
  - [x] 출력은 정해진 섹션 템플릿 준수: ①요약 ②전일 핵심 이슈 ③섹터/수급 동향 ④지표·이벤트 ⑤주요 종목 ⑥오늘의 관전 포인트 ⑦면책조항
  - [x] 한국어로 작성, 영문 종목명/티커는 원문 유지
  - [x] 면책조항 자동 삽입 ("투자 자문이 아닌 정보 제공" 명시) — NFR-004 참조
  - [x] LLM 호출 실패 시 retry (최대 N회), 최종 실패 시 빈 시황 게시 금지 → 알림
- **Priority**: Must-have

### FR-003: 정적 웹 게시
- **Description**: 생성된 시황을 GitHub Pages 정적 사이트에 게시한다. 모든 과거 시황은 이력으로 보관·열람 가능.
- **User Story**: As a 열람자, I want 오늘 시황과 과거 시황을 웹에서 볼 수 있기를, so that 시점별 시장 흐름을 추적할 수 있도록.
- **Acceptance Criteria**:
  - [x] 시황은 markdown 파일로 git repo에 저장 (신규 세그먼트 실행 예: `archive/us-equity/2026/04/2026-04-25.md`; 과거 단일 시황은 `archive/2026/04/2026-04-25.md` 유지)
  - [x] 정적 사이트 생성기로 빌드 → GitHub Pages 배포
  - [x] 날짜별 인덱스, 최신 시황 홈 노출
  - [x] 검색 또는 최소한 날짜/연도별 탐색 가능
- **Priority**: Must-have

### FR-004: 텔레그램 시황 채널 알림
- **Description**: 시황 생성 직후 **공개 Telegram 채널/그룹**으로 요약을 전송한다. 운영자 본인과 공유 받은 Public Reader가 동일 채널에 join하여 푸시를 수신한다.
- **User Story**: As a 운영자/Public Reader, I want 텔레그램 채널 푸시로 시황 요약을 받기를, so that 웹사이트를 열지 않아도 핵심을 알 수 있도록.
- **Acceptance Criteria**:
  - [x] Telegram Bot API 사용 (Bot 토큰은 GitHub Secrets — `TELEGRAM_BOT_TOKEN`)
  - [x] 발송 대상: **공개 Telegram 채널 또는 그룹** (`TELEGRAM_BRIEFING_CHANNEL_ID` 시크릿). 누구나 채널 링크로 join 가능.
  - [x] 메시지에 국내 증시, 미국 증시, 크립토 상세 URL 링크를 모두 포함
  - [x] 텔레그램 메시지 길이 제한(4096자) 준수 — 초과 시 요약 + 링크
  - [x] 텔레그램 발송 실패는 시황 게시 자체를 막지 않음 (게시는 성공, 알림만 실패)
  - [x] 공개 채널이므로 시크릿/PII가 메시지에 포함되지 않도록 검증
  - [x] 운영자 실패 알림(FR-007)과는 **별도 chat**을 사용 — 공개 채널에 노이즈 주입 금지
- **Priority**: Must-have

### FR-005: 스케줄 실행
- **Description**: GitHub Actions cron으로 매일 자동 실행한다.
- **User Story**: As a 본인, I want 매일 같은 시각에 자동 실행되기를, so that 수동 트리거가 필요 없도록.
- **Acceptance Criteria**:
  - [x] GitHub Actions `schedule` cron 트리거
  - [x] 평일: 미국장 마감 후 충분한 데이터 확보 시각 (예: 한국시간 평일 오전 7시 = UTC 22:00)
  - [x] 주말: 토요일 1회 (주간 리뷰)
  - [x] 수동 트리거(`workflow_dispatch`)도 지원
  - [x] 실행 시간 ≤ 10분 (NFR-001)
- **Priority**: Must-have

### FR-006: 영구 이력 보관
- **Description**: 생성된 모든 시황을 영구 보관한다.
- **User Story**: As a 본인, I want 과거 시황을 모두 보관하기를, so that 시점별 시장 분석을 회고할 수 있도록.
- **Acceptance Criteria**:
  - [x] 시황은 git commit으로 영구 저장
  - [x] 폴더 구조: 신규 세그먼트 시황은 `archive/{segment}/YYYY/MM/YYYY-MM-DD.md`; 과거 단일 시황은 `archive/YYYY/MM/YYYY-MM-DD.md` 읽기 가능
  - [x] 저장 용량 문제 발생 시 (수년 후) 별도 archival 정책 검토 — 현재는 Out of Scope
- **Priority**: Must-have

### FR-009: Reader-facing 출력 포맷 (u51 tldr-block-and-number-bold-inversion)
- **Description**: 시황의 가독성·액션성을 강제한다. (1) 본문 § 시작 전에 `## 한눈에 보기` TL;DR 3-bullet 블록을 emit 하고, (2) 시장 anchor 정보를 prose blockquote 가 아닌 markdown 표로 렌더하며, (3) §②/③/④/⑥ sub-heading 은 `### Title` (H3) 로 작성하고, (4) 본문 prose 안의 숫자 토큰 (`+11.51%`, `$81,154.06`, `4.42%`) 은 `**...**` 로 강조하며, (5) §⑥ "관전 포인트" bullet 의 관찰형 종결 어미 (`~여부 / ~필요가 있다 / ~관건이다 / ~주목할 필요`) 비율을 40% 이하로 유지하고 (위반 시 WARNING flag, blocking 아님), (6) 같은 segment 내 같은 용어의 풀어쓰기 글로싱은 첫 1회만 표기하고 2번째 이후는 base 용어만 남긴다.
- **User Story**: As a 시황 reader, I want 페이지를 열자마자 매그니튜드·방향성·액션을 한눈에 보기를, so that 본문을 전부 읽지 않고도 그날의 핵심을 빠르게 잡을 수 있도록.
- **Acceptance Criteria**:
  - [x] 모든 segmented 시황 상단에 `## 한눈에 보기` H2 + 정확히 3 bullet 블록이 워터마크/세그먼트-네비/anchor 다음, ① 요약 헤더 직전에 배치
  - [x] 시장 anchor 라인이 4-컬럼 markdown 표 (`| 종목 | 종가 | 변동 | 비고 |`) 로 렌더 — 우선순위 ranking 은 u49 와 동일, 최대 5행
  - [x] §②/③/④/⑥ 의 sub-heading 이 `### Title` (H3) 로 작성됨; 기존 `**Title** — body` 패턴 부재
  - [x] 본문 prose 의 숫자 토큰 (`[+-]?\d+\.\d+%`, `\$[\d,]+(?:\.\d+)?`, `\d+\.\d+%`) 이 `**...**` 로 wrap; 표 cell / 코드 블록 / 링크 URL 내부 미적용; 이미 wrap 된 토큰 idempotent
  - [x] §⑥ bullet 의 관찰형 종결 어미 비율 ≤ 40% 검증 (위반 시 publisher WARN 로그 + segment / ratio / count 구조화 extra; *blocking 아님* — generation 변동성 흡수)
  - [x] 같은 segment 내 같은 base 용어의 글로싱 (`base(풀어쓰기)`) 은 첫 1회만 풀어쓰기 표기; 2번째 이후 출현은 `base` 만 남김 (u40 의 `> **용어 가이드**` callout 은 그대로 유지)
  - [x] 면책조항 (NFR-004 R5) 은 reader-format chain 후에도 verbatim 보존; `publisher.verify_disclaimer` 가 chain 다음 단계에서 정상 통과
- **Priority**: Should-have (reader UX KPI — NFR-001 reliability/quality 보강)

### FR-010: Source-Status Severity & Quality KPI Truthfulness (u54 source-status-severity-and-quality-kpi)
- **Description**: 시황의 데이터 상태 라벨과 quality KPI 가 실제 수집 신뢰도를 반영하도록 강제한다. (1) `CoverageStatus` 를 4-tier (`정상 / 부분 / 제한 / 실패`) 로 격상하고, (2) segment 별 core source set 을 frozen constant 로 박아 결정 트리를 기반으로 deterministic 하게 severity 를 산출하며, (3) 핵심 가격 소스의 `latest_item_at` 이 segment market-close window 보다 오래되면 severity 를 강제로 `limited` 이상으로 다운그레이드하고, (4) source count 를 `targeted / succeeded / zero / failed / body-used` 5-tuple 로 분리해 first-viewport 에 surface 하며, (5) `site_docs/quality.md` 가 분모-zero KPI 를 `0.0%` 대신 `n/a` 로 표기하고 신규 KPI (`failed_sources`, `zero_item_sources`, `core_missing_segments`, `segments_limited_or_worse`) 를 노출하며, (6) 같은 URL 이 한 segment 내 ≥ 3 distinct ticker/entity claim 에 attribute 되면 WARN flag (non-blocking) 를 발화하고, (7) `OperatorAlerter` 가 동일 segment 의 severity ≥ `limited` 가 ≥ 2 연속 run 일 때만 발화하며, (8) 같은 (date, segment) 의 `append_quality_snapshot` 은 worst severity 를 keep (last-write-wins 금지).
- **User Story**: As a 시황 reader / 운영자, I want 데이터 상태 라벨이 핵심 가격 소스 실패·0건·stale 을 숨기지 않고, quality 페이지가 실제 수집 위험을 설명하기를, so that 데이터 신뢰도 오판 없이 본문을 읽고, 플레이키 소스로 인한 알림 spam 없이 진짜 regression 만 받을 수 있도록.
- **Acceptance Criteria**:
  - [x] Source count 가 `targeted / succeeded / zero / failed / body-used` 5-tuple 로 분리되어 first-viewport coverage 라인에 렌더
  - [x] Reader-facing status 라벨이 4-tier (`정상 / 부분 / 제한 / 실패`); legacy `insufficient` → `failed` 단일 마이그레이션, 병행 enum 없음
  - [x] Segment 별 core source frozen constant (`SEGMENT_CORE_SOURCES`) 기반 결정 트리로 severity 산출; 핵심 소스 failed/zero/stale 시 `정상` 불가
  - [x] `site_docs/quality.md` 가 분모-zero 시 `n/a` 표기 + 신규 KPI (`failed_sources`, `zero_item_sources`, `core_missing_segments`, `segments_limited_or_worse`) 노출
  - [x] Trace/collapsed diagnostics 가 failed / zero / excluded 소스를 sanitized 메시지 (R13 chokepoint) 로 노출
  - [x] 동일 URL 이 한 segment briefing 안에서 ≥ N=3 distinct ticker/entity claim 에 attribute 되면 `reader.citation_cardinality_exceeded` WARN 발화 (structured extra: url_hash sha1[:12] + claim_count + segment); *non-blocking*
  - [x] `OperatorAlerter` 는 동일 segment 의 severity ≥ `limited` 가 ≥ 2 연속 run 일 때만 발화 (1st bad run = INFO log only); 회복 시 카운터 reset; FR-007 hard-failure 경로는 영향 없음
  - [x] `append_quality_snapshot` 이 같은 (date, segment) 에 대해 worst severity 를 keep — 후속 upgrade 시도는 dropped + 명시적 로그
- **Priority**: Should-have (NFR-001 reliability/quality + NFR-003 graceful-degradation 보강)

### FR-011: Numeric / Date / Freshness Gate (u55 numeric-freshness-and-market-fact-gates)
- **Description**: 시황 publish 직전 (1) 사전 정의된 10-element `CoreFact` enum 에 한해 source-backed Decimal 값과 본문 prose 의 keyword-scoped window (anchor token ± 40 chars) 내 Decimal 매치를 tolerance 안에서 비교하여 verified/unverified/conflict 로 분류하고 (`pass / warn / downgrade / block` 4-tier `NumericGateAction` 에 매핑), (2) `r"\d{1,2}/\d{1,2}(?:/\d{1,2})?"` 슬래시-date 토큰의 month ≤ 12 / day ≤ 31 sanity 를 검증해 `5/65/7` 류 corruption 을 `block` 처리하고, (3) 본문 "강세 / 약세 / ATH 갱신 / 52w 최고" claim 을 `MarketAnchor.pct` / `is_ath` / `pct_from_52w_high` 와 cross-check 하며, (4) 각 segment 마다 `next_expected_trading_day` 와 `latest_archive_date` 를 비교해 stale segment 는 공개 채널 무발송 + quality 페이지 라인 + operator alert (FR-007) 만 발화한다. (5) `figures_presence` (u32 substring presence) 와 distinct 한 `figures_verified` (u55 source-backed core-fact 검증) KPI 를 quality 페이지 + sparkline 에 append-only column 으로 노출.
- **User Story**: As a 시황 reader / 운영자, I want 본문의 핵심 수치 / 날짜 / 방향 claim 이 source-backed Decimal / static calendar / deterministic anchor 와 충돌하면 publish 가 막히거나 명시적 callout 이 붙기를, so that hallucinated 가격 · 잘못된 날짜 토큰 · 방향 정반대 prose 가 reader-facing 채널로 새지 않도록.
- **Acceptance Criteria**:
  - [x] Typed core-fact verification: 사전 정의된 `CoreFact` (10개 enum 값) 만 verify; 자유 prose claim extraction 시도 안 함.
  - [x] Sibling helper, not extension: 신규 모듈 `src/investo/briefing/numeric_verify.py` (u32 `numeric_self_check.find_unverified` 와 별 surface, u32 무수정).
  - [x] KPI 분리: `figures_presence` (u32 기존) + `figures_verified` (u55 신규) 가 `briefing/quality_eval.py` + `quality_history.py` 양쪽에 append-only column.
  - [x] `NumericGateAction = Literal["pass", "warn", "downgrade", "block"]` enum.
  - [x] Date corruption gate: month > 12 / day > 31 / all-zero → `block`; 코드 블록 내부 무영향.
  - [x] 무료 calendar: `src/investo/models/market_calendar.py` hand-rolled KRX 2026 + NYSE 2026 휴장일 (유료 API 금지, NFR-002).
  - [x] Per-segment freshness → publisher 호출 시 `SegmentResult(status: Literal["fresh","stale","failed"])` 분기. `fresh` 만 archive + Telegram 공개; `stale` / `failed` 는 quality 라인 + operator alert.
  - [x] Per-segment isolation: 한 segment 의 stale/failed 가 다른 segment 발행을 막지 않음.
  - [x] Tolerance 상수 박음: price/pct/yield/BTC/ETH 절대 Decimal tolerance 명시; idempotent.
  - [x] R13 secret hygiene: date corruption fixture / WARNING / operator alert payload 가 secret-shaped substring 미포함.
- **Priority**: Should-have (NFR-001 quality 보강 + NFR-003 재현성).

### FR-012: Compliance language enforcement + segment-aware disclaimer (u56 compliance-language-and-observational-tags)
- **Description**: 시황의 advisory wording / quantified outcome / Korean retail-coded language 를 publish 게이트에서 차단한다. (1) `src/investo/models/compliance_phrases.py` 의 단일 source 가 briefing prompt + publisher gate 양쪽 import 대상. (2) `publisher/compliance_language.py` 의 `scan_compliance(markdown, segment) -> ComplianceReport` 가 P0 phrase 발견 시 `ComplianceLanguageError` raise (orchestrator 가 publish 차단); P1 hit 은 WARN + structured extra; 6-token-window context-aware classifier 가 `진입/청산/목표가/편입` 의 quotative / fact-pattern 사용을 INFO 로 demote. (3) `briefing/disclaimer.py` 에 `DISCLAIMER_CRYPTO` (가상자산이용자보호법 2024-07-19 시행 §10·§19 reference) 분리; `append_disclaimer(markdown, segment)` + `verify_disclaimer(briefing_md, segment, *, legacy)` 시그니처 확장; 기존 1-arg call 은 default 인자로 byte-compat. (4) `publisher/reader_format.py::emit_first_viewport_disclaimer` 가 `## 한눈에 보기` 직전에 segment-aware short disclaimer blockquote 를 1줄 emit; `verify_short_disclaimer_first_viewport` 가 *additive* gate. (5) ActionTag 5종 (`[관망] [변동성↑] [강세] [약세] [혼조]`) → 4종 observation 라벨 (`[상승 관찰] [하락 관찰] [혼재] [변동성 확대]`) + `[데이터부족]` 마이그레이션. `LEGACY_TAG_ALIASES` 가 LLM cutover 동안 legacy 입력을 normalise. (6) `check_sentence_ending_diversity` + `check_filler_phrase_density` — 본문 surface 종결 어미 dominance > 60% / filler 빈도 > 8.0/1000 chars → WARN-only.
- **User Story**: As a 시황 reader, I want 자동 생성된 시황이 advisory wording / quantified outcome / retail 토착어 / 단방향 stance 라벨 / 단일 종결 어미 일색의 자동 생성물 시그니처를 피하기를, so that 한국 자본시장법 §17 / 가상자산이용자보호법 §10·§19 와 거리상 안전하고 reader UX 가 retail 자동물처럼 보이지 않도록.
- **Acceptance Criteria**:
  - [x] Stage-2 segment-aware prompt forbids direct trading-action instructions and uses observation/check language.
  - [x] ActionTag 5종 → 4종 마이그레이션 + alias map backward-compat parser (legacy tag 정상 normalise; archive 재렌더 안 함).
  - [x] `publisher/compliance_language.py` 신규 gate: P0 phrase 발견 시 `ComplianceLanguageError` (orchestrator publish 차단); P1 phrase 발견 시 WARN + structured extra (segment / phrase / count / line_no).
  - [x] P0 banned phrase 세 카테고리: (a) Action instruction (대칭 buy/sell, 16 phrases), (b) Quantified outcome promise (regex), (c) Korean retail-coded crypto-only (5 phrases, segment="crypto" 만 active).
  - [x] Context-aware 6-token-window classifier 가 `진입 / 청산 / 편입` symmetric, `목표가` left-only (quotative) demote.
  - [x] First-viewport short disclaimer (segment-aware) 가 `## 한눈에 보기` H2 직전에 1줄 blockquote 로 emit; `verify_short_disclaimer_first_viewport` 가 *추가* gate.
  - [x] `briefing/disclaimer.py` 에 `DISCLAIMER_CRYPTO` 신규 상수 (가상자산이용자보호법 §10·§19 reference + 24h 거래 / 비제도권 / 변동성 / 원금 전액 손실 명시).
  - [x] `append_disclaimer(markdown, segment)` + `verify_disclaimer(briefing_md, segment, *, legacy)` 시그니처 확장; default 인자로 기존 1-arg call site 무파괴.
  - [x] Archive backward-compat (legacy=True flag) — weekly digest 가 pre-cutoff archive 의 equity-only footer 도 통과.
  - [x] 종결 어미 다양성 cap ≤ 60% (`check_sentence_ending_diversity` → `tone.sentence_ending_dominance` WARN).
  - [x] Filler phrase family (`여부 / 전망 / 우려 / 가능성 / 작용`) per-1000-chars 빈도 ≤ 8.0 (`check_filler_phrase_density` → `tone.filler_density` WARN).
  - [x] 회귀 핀: 면책 footer 누락 → `verify_disclaimer` fail; first-viewport 누락 → 신규 gate fail; crypto + us-equity 면책 mismatch → `verify_disclaimer(segment="crypto")` fail.
  - [x] R13 secret hygiene: scan WARN extra 가 LLM output text 만 carry (segment / phrase / line_no); raw_metadata 미포함.
- **Priority**: Must-have (Rule 2 disclaimer enforcement 강화 — 기존 footer + 신규 first-viewport + segment 분기).

### FR-013: 세그먼트 narrative scope + time-state 일관성 (u57 segment-narrative-scope-and-time-reconciliation)
- **Description**: 같은 run 으로 생성된 3 segment briefing 의 narrative 결함 4종 (same-page time-state 모순, cross-market promotion 과잉, native-link 없는 글로벌 ticker, shared macro 중복) 을 종결한다. (1) `src/investo/models/bundle_context.py` 의 `BundleContext` + `MarketStateSummary` 가 Stage 2 *전*에 계산되어 3 segment prompt 에 same-object 로 inject 됨. (2) `src/investo/orchestrator/bundle_context.py::compute_bundle_context` 가 routed items 만으로 segment 의 close-state 를 결정 (자기 segment 는 `pending` 으로 force, anti-self-assert). (3) `src/investo/briefing/time_state.py::detect_time_state` 가 6 label catalogue regex 로 source title 의 time-state 를 결정론적으로 부여; ambiguous → LLM in-context disambiguation. (4) `src/investo/publisher/cross_segment_lint.py` 의 `lint_domestic_foreign_linkage` / `lint_native_fact_priority` / `lint_time_state_consistency` 가 post-Stage-2 publish-gate 에서 violation 을 WARN / REJECT 로 발화. (5) `cross_market_core_allowed` frozenset (`geopolitical_oil_macro`, `fed_policy_event`, `global_systemic_risk`) 가 prompt + lint 공통 single source of truth. (6) `src/investo/publisher/shared_macro.py::inject_shared_macro_block` 가 `## ⓪ 오늘의 매크로` H2 를 TL;DR 직후 / §① 직전 site 에 idempotent 하게 inject; 본문 재서술은 WARN-only.
- **User Story**: As a 시황 reader, I want 같은 페이지의 3 segment 가 서로 모순 없이 시간 상태를 정렬하고 (US 가 같은 날 +0.5% 마감했는데 도메스틱이 "US 하락 출발" 인용 금지), 외국 ticker 가 도메스틱 segment 에 등장할 때 환율/외인/연관종목 같은 도메스틱 hook 을 반드시 동반하며, 같은 매크로 fact 가 segment 마다 raw 재서술 없이 1회만 `## ⓪` 블록에 등장하기를, so that 같은 페이지의 narrative 일관성이 자동 검증되고 reader 신뢰가 회귀하지 않도록.
- **Acceptance Criteria**:
  - [x] BundleContext (same-run, per-segment market-state summary) 가 Stage 2 *전*에 계산되어 3 segment prompt 모두에 동일 객체로 inject 됨. 자기 segment 자신은 `pending` 으로 표시.
  - [x] Time-state label 6 종 (`pre-market / open / intraday / close / post-close / scheduled`) 이 source title regex catalogue 로 결정론적으로 부여; ambiguous → LLM in-context.
  - [x] 도메스틱 segment 본문의 모든 외국 ticker 출현은 같은 `\n\n` 단락 안에 도메스틱 ticker `\d{6}` 또는 linkage 키워드 ≥ 1 동반. 위반 시 publish-gate WARNING (워치리스트 subsection 안에서는 REJECT).
  - [x] 각 segment §② 의 첫 H3 primary noun 은 segment-native entity allowlist 매치 (domestic: KRX 6-digit / KOSPI / KOSDAQ / 외국인; us-equity: SPX/NDX/주요 ticker; crypto: BTC/ETH). 위반 시 WARN-tier diagnostic.
  - [x] Same-bundle time-state 모순 detect — us-equity `close_state = close` 인데 본문이 "하락 출발 / 상승 출발" wording 인용 시 REJECT-tier 발화.
  - [x] BundleContext `shared_macro_block` 이 non-null 이면 `## ⓪ 오늘의 매크로` H2 + 단일 paragraph 가 TL;DR 직후 1회만 inject (idempotent).
  - [x] Cross-market core-tier allow-list (`CROSS_MARKET_CORE_ALLOWED`) 가 module constant 로 노출, 단위 테스트로 핀; 신규 테마 추가는 후속 unit.
  - [x] R13 secret hygiene — lint WARNING extra 가 segment / kind / severity / numeric lengths 만 carry; raw_metadata / secret-shaped substring 미포함.
- **Priority**: Must-have (NFR-001 readability 회귀 방지 — same-page narrative 모순 / over-promotion / orphan global ticker / macro 중복 4종 시그니처 종결).

### FR-014: Macro actual priority + lineage (u59 macro-actual-priority-and-lineage)
- **Description**: 고중요도 매크로 이벤트를 일정 row 가 아니라 source-backed event object 로 승격한다. (1) CPI/PPI/NFP/PCE/GDP/FOMC 등 핵심 매크로 이벤트는 `macro_event_key`, `macro_event_status`, `macro_priority`, `release_period`, actual/prior/forecast/surprise 필드를 primitive-safe metadata 또는 typed `MacroPrint` 로 보유한다. (2) Stage 1 후보 선별 전 결정론적 priority scoring 을 수행해 P0/P1 macro 이벤트를 generic news/lookahead cap 보다 먼저 bounded reserve 한다. (3) P0 actual 은 `required_macro_actuals` 계약으로 Stage 1 `unassigned` 및 Stage 2 prompt cap 에서 보호되고, post-generation validator 가 최종 markdown 언급/출처를 확인한다. (4) macro actual source health 는 price/news core 와 분리된 severity 축으로 계산되며, macro claim 이 있는데 actual source 가 missing/zero/failed/stale 이면 `limited` 이상으로 downgrade 한다. (5) operator-only lineage artifact 가 source collection → segment routing → Stage 1 candidate → classification → Stage 2 prompt → final body 의 drop 지점을 진단한다. (6) release-day unresolved macro 이벤트는 `scheduled / unresolved / confirmed / stale` lifecycle 로 carryover 된다.
- **User Story**: As a 시황 reader / 운영자, I want PPI 같은 핵심 매크로 발표가 일정에만 잡히고 실제 발표치/우선순위/최종 본문에서 누락되는 일이 없기를, so that 시장을 움직인 공식 macro actual 이 시황의 중심 사건으로 반영되고 누락 시 원인을 즉시 추적할 수 있도록.
- **Acceptance Criteria**:
  - [x] Macro metadata contract: schedule/actual items carry event key, label, status, priority, release period, and source identity with primitive-safe values.
  - [x] PPI schedule identity: `fred-economic-calendar` release id `46` fixture/test pins scheduled date, label, source, and `us-equity` routing.
  - [x] PPI actual source path: `fred-macro` or approved official actual adapter emits PPI actual/prior/observation date/source URL without secret leakage.
  - [x] Forecast discipline: "예상치 상회/하회" wording is forbidden unless an approved forecast/consensus field is present.
  - [x] Priority-aware selection: `_select_llm_candidate_items(items, target_date=...)` reserves bounded P0/P1 macro events before generic caps while preserving existing crypto-policy priority behavior.
  - [x] Required macro Stage 1/Stage 2 contract: P0 actuals cannot be omitted, classified `unassigned`, or dropped by Stage 2 caps without retry/fail/downgrade.
  - [x] Post-generation validation: final markdown is checked for required macro label/event/source mention; omission emits `MACRO_REQUIRED_OMITTED`.
  - [x] Macro severity: `MACRO_ACTUAL_MISSING`, `MACRO_ACTUAL_ZERO`, `MACRO_ACTUAL_FAILED`, `MACRO_ACTUAL_STALE`, `MACRO_FORECAST_UNVERIFIED` reason codes feed coverage and quality diagnostics.
  - [x] Lineage: `archive/_meta/run_traces/{target_date}/{segment}.json` diagnoses `missing_at_source`, `dropped_by_segment_routing`, `dropped_by_stage1_candidate_cap`, `dropped_by_stage1_classification`, `dropped_by_stage2_prompt_cap`, `llm_omitted`, or `published`.
  - [x] Carryover lifecycle: macro events persist as `scheduled / unresolved / confirmed / stale` and can carry release-day unresolved events into the next run.
  - [x] Quality KPI: `macro_actual_missing_segments` and `required_macro_omitted` are available to operator diagnostics or quality history.
  - [x] R10 fixtures and R13 secret hygiene cover new macro schedule/actual/lineage surfaces.
- **Priority**: Must-have (FR-001/FR-002/FR-008 신뢰성 보강 — official macro actual 과 priority 를 놓치지 않는 시황 중심성 회복).

### FR-015: Shared macro evidence hardening (u60 shared-macro-evidence-hardening)
- **Description**: `## ⓪ 오늘의 매크로` shared macro block 의 evidence selection 을 source-backed deterministic contract 로 강화한다. (1) UST/oil/FOMC shared macro matcher 는 title substring 만으로 evidence 를 확정하지 않고 key-specific predicate 로 검증한다. (2) `UST` 는 ASCII word-boundary + rate/yield/curve/tenor context 가 있어야 하며, `customers` / `trust` / `custody` / `dust` 같은 substring false positive 는 거부한다. (3) representative evidence 는 first-match order 가 아니라 source/category/title specificity rank 로 선택한다. (4) `ust_yield` reader-facing shared macro 는 valid UST candidate 가 2개 이상 routed segment 에 있고, 그중 최소 1개가 canonical U.S. rates source (`treasury-rates` 또는 `fred-macro`) 일 때만 생성된다. (5) `fred-macro` 는 ranking positive evidence 일 뿐 crypto fan-out 이나 routing 변경을 만들지 않는다. (6) false-positive 후보 또는 non-canonical-only UST 후보만 두 segment 이상에 있어도 `shared_macro_block` 은 생성되지 않는다. (7) reader-facing layout 과 injection idempotency 는 u57 behavior 를 유지한다.
- **User Story**: As a 시황 reader, I want `미 국채 수익률` 행이 실제 국채금리/UST/FRED/Treasury evidence 만 보여주기를, so that 보안/버그바운티 같은 unrelated headline 이 매크로 fact 로 표시되어 전체 시황 신뢰를 훼손하지 않도록.
- **Acceptance Criteria**:
  - [x] `customers`, `trust`, `custody`, `dust` 는 `ust_yield` 로 매칭되지 않는다.
  - [x] `UST stablecoin collapse`, `UST depeg`, `UST custody product` 는 rate/yield/curve/tenor context 없이 `ust_yield` 로 매칭되지 않는다.
  - [x] `UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp`, `DGS10 4.46`, `10Y Treasury yield`, `미 국채 10년물 수익률` 은 `ust_yield` 로 매칭된다.
  - [x] `한국 국채 10년물 금리` 는 `미 국채 수익률` 로 렌더되지 않는다.
  - [x] false-positive news 와 real UST macro item 이 같은 segment 에 함께 있을 때 real macro item 이 representative evidence 로 선택된다.
  - [x] `ust_yield` shared macro 는 valid UST candidate 가 2개 이상 routed segment 에 있고, 그중 최소 1개가 `treasury-rates` 또는 `fred-macro` 일 때만 생성된다.
  - [x] `fred-macro` 단독으로는 shared macro block 또는 crypto fan-out 을 만들지 않는다.
  - [x] false-positive title 만 여러 segment 에 존재하면 `## ⓪ 오늘의 매크로` 에 `미 국채 수익률` 행이 생성되지 않는다.
  - [x] `treasury-rates` fan-out 으로 us-equity + crypto 에 real UST evidence 가 있을 때 shared macro block 은 기존처럼 생성된다.
  - [x] oil/FOMC shared macro happy path 와 `inject_shared_macro_block()` idempotency 는 회귀하지 않으며, oil/FOMC boundary false positive 는 거부된다.
  - [x] R13 secret hygiene — matcher/ranking diagnostics (`candidate_accepted`, `candidate_rejected`, `key_suppressed`, `representative_selected`) 는 raw_metadata 를 로깅하지 않고 title preview 도 bounded length 로 제한한다.
- **Priority**: Must-have (FR-008/u57 회귀 방지 — deterministic shared macro evidence 가 독자 신뢰의 첫 화면 표면에 직접 노출됨).

### FR-016: Watchlist relevance and impact center (u18/u28/u33/u73/u111)
- **Description**: 운영자가 비밀이 아닌 설정으로 관심 자산을 정의하면, 파이프라인이 세그먼트별 소스/본문/알림에서 관련성을 결정론적으로 매칭하고 독자에게 직접 관련 영향만 공개한다. 직접/연관/불확실/거절 매칭을 분리하고, 공개 표면과 진단 표면을 나눠 watchlist 영향이 과장되거나 원시 matcher 사유가 노출되지 않도록 한다.
- **User Story**: As a 본인, I want 내가 관심 있는 종목/자산이 그날 시황에서 어떤 영향을 받는지 별도 표면으로 확인하기를, so that 전체 시황을 읽기 전에 내 관심 대상과 직접 관련된 이슈를 빠르게 파악할 수 있도록.
- **Acceptance Criteria**:
  - [x] 비밀값이 아닌 watchlist 설정을 로드하고, 자산 alias/ticker 기반 매칭을 결정론적으로 수행한다.
  - [x] 세그먼트 본문 first-viewport, Telegram 요약, watchlist daily/index 페이지가 관심 자산 영향 요약을 노출한다.
  - [x] 매칭 결과는 Direct / Related / Uncertain / Rejected 계층으로 분리되며, 공개 카운트와 본문에는 Direct/Related 중심의 reader-safe 결과만 반영한다.
  - [x] Uncertain/Rejected 및 matcher reason code 는 R13-safe collapsed diagnostics 로 제한하고 공개 Telegram 메시지에는 노출하지 않는다.
  - [x] watchlist public projection 은 `[alias:...]`, `[boundary-term]`, source registry reason 같은 내부 matcher 사유를 독자 표면에서 제거한다.
  - [x] watchlist 페이지 생성은 archive/site publish 경로와 함께 원자적으로 처리되고, 실패 시 공개 시황 본문과 불일치하지 않는다.
- **Priority**: Should-have (reader relevance/product utility 확장)

### FR-017: Public quality, source traceability, and consistency dashboard (u22/u32/u54/u69/u96/u123)
- **Description**: 시황 독자와 운영자가 데이터 수집 상태, 출처 사용, 수치 검증, 품질 KPI 를 공개 표면에서 일관되게 확인할 수 있도록 품질/출처/추적성 대시보드와 publish-time consistency gate 를 제공한다. 내부 진단은 보존하되 reader-facing 문구는 안전하게 투영한다.
- **User Story**: As a 시황 reader / 운영자, I want 각 시황과 품질 페이지가 실제 수집·출처·본문 사용 상태를 일관되게 보여주기를, so that 데이터 부족이나 품질 저하를 숨긴 브리핑으로 오판하지 않도록.
- **Acceptance Criteria**:
  - [x] 각 run 은 source outcome, segment coverage, quality snapshot, quality history 를 append-only 또는 canonical artifact 로 남긴다.
  - [x] `site_docs/quality.md` 와 `site_docs/accuracy.md` 는 최근 품질 KPI, 실패/0건/제한 상태, 예측 정확도 또는 검증 지표를 공개한다.
  - [x] trace footer 또는 collapsed diagnostics 는 사용/제외/실패 소스를 redaction chokepoint 를 거쳐 표시한다.
  - [x] 품질 페이지, 세그먼트 markdown, index label, `quality_history.jsonl` 사이의 상태 불일치는 publish boundary 에서 차단하거나 명시적으로 진단한다.
  - [x] 본문에서 실제 사용된 known-source 링크와 verified figure 는 quality accounting 에 반영되어 `본문 사용 미집계/0` 같은 과소계상을 방지한다.
  - [x] reader-facing 품질 문구는 내부 reason code 를 그대로 노출하지 않고 public-quality projection 을 통해 안전한 표현으로 렌더한다.
- **Priority**: Should-have (trust/operability surface)

### FR-018: Visual briefing assets, charts, and provenance (u19/u24/u26/u50/u75/u86)
- **Description**: 브리핑은 텍스트만이 아니라 deterministic visual card, chart placeholder/sidecar, OG card, curated context asset 을 함께 생성·게시한다. 모든 시각 자산은 archive-relative 경로와 provenance/validation 계약을 가지며, 외부 이미지 또는 AI 이미지 정책은 비용·권리·보안 제약을 따른다.
- **User Story**: As a 시황 reader, I want 핵심 데이터와 관심 자산 흐름을 카드/차트/이미지로 빠르게 훑어보기를, so that 긴 본문을 읽기 전에도 시장 상태를 시각적으로 파악할 수 있도록.
- **Acceptance Criteria**:
  - [x] 데이터 신뢰도, 시장 스냅샷, 가격 스냅샷, watchlist relevance 등 deterministic SVG visual card 를 생성하고 세그먼트 markdown 에 상대 경로로 삽입한다.
  - [x] visual asset 은 archive 파일과 함께 stage 되며, asset path/provenance sidecar/dimension validation 이 publish 경로에서 검증된다.
  - [x] 외부 이미지 스크래핑은 기본 비활성화되고, curated local context asset 과 정책 파일을 통해 권리/출처/런타임 비용을 통제한다.
  - [x] chart history 는 inline 대용량 HTML 속성이 아니라 archive-local JSON sidecar 로 외부화하고, 독자가 expand 할 때 lazy-load 한다.
  - [x] chart/visual sidecar 는 deterministic schema, stable key order, target-date provenance, no-secret payload 를 유지한다.
  - [x] visual 생성 실패 또는 text-only fallback 시에도 시황 본문 publish 는 깨지지 않고 진단 가능한 상태를 남긴다.
- **Priority**: Should-have (reader UX + visual trust)

### FR-019: Archive discovery, periodic retrospectives, and forecast accuracy (u16/u20/u29/u34/u58)
- **Description**: 공개 사이트는 최신 시황만 보여주는 것이 아니라 세그먼트별 archive, weekly/monthly retrospective, calendar/search/navigation, forecast/accuracy surface 를 제공한다. 과거 시황과 예측 기록은 독자가 시장 흐름을 회고하고 품질을 추적할 수 있는 탐색 표면으로 유지된다.
- **User Story**: As a 시황 reader, I want 일별/주별/월별 시황과 예측 정확도를 웹에서 탐색하기를, so that 특정 시점의 판단과 이후 결과를 비교해 볼 수 있도록.
- **Acceptance Criteria**:
  - [x] Home/About/Archive navigation 은 segmented product 를 기준으로 최신 domestic/us/crypto 링크와 과거 archive 접근 경로를 제공한다.
  - [x] 날짜/연도/세그먼트별 archive index 와 검색 기능을 통해 과거 브리핑을 탐색할 수 있다.
  - [x] weekly digest 와 monthly index 는 기존 archive 를 바탕으로 주차별/월간 회고 페이지를 생성한다.
  - [x] forecast log 는 예측 또는 관전 포인트의 후속 결과를 기록하고 accuracy dashboard 에 반영한다.
  - [x] archive path normalization 은 legacy 단일 브리핑과 신규 segmented briefing 경로를 모두 안전하게 처리한다.
  - [x] archive/site index 갱신은 publish transaction 과 함께 처리되어 latest/index/quality/watchlist/retrospective 표면이 같은 run 기준으로 맞춰진다.
- **Priority**: Should-have (public discovery + retrospective utility)

### FR-020: Event lookahead, recent-context, and unresolved carryover (u34/u35/u43/u52/u59)
- **Description**: 파이프라인은 당일 수집 결과만 사용하지 않고 임박 이벤트, 최근 브리핑 맥락, unresolved carryover 를 세그먼트별로 전달한다. 예정/미해결/확정/stale 상태를 구분해 같은 이벤트가 누락되거나 반복 과장되지 않도록 한다.
- **User Story**: As a 시황 reader, I want 오늘 끝난 이슈뿐 아니라 곧 다가올 이벤트와 전일 미해결 이슈의 이어짐을 보기를, so that 시장 흐름을 단절된 하루 단위가 아니라 연속된 맥락으로 이해할 수 있도록.
- **Acceptance Criteria**:
  - [x] lookahead item 은 forward-filter chokepoint 를 거쳐 세그먼트별 summary/Telegram context 에 전달된다.
  - [x] lookahead context 는 `now_utc` 와 함께 공급되어 임박 이벤트 태그가 시간 기준 없이 렌더되지 않는다.
  - [x] carryover model 은 topic/status/event type 을 검증하고, 세그먼트별로 isolated 되어 다른 시장의 미해결 이슈를 오염시키지 않는다.
  - [x] same-day rerun 에서 carryover block injection 은 idempotent 하게 동작한다.
  - [x] macro event lifecycle 은 `scheduled / unresolved / confirmed / stale` 상태로 이어지며 release-day unresolved event 를 다음 run 으로 carryover 할 수 있다.
  - [x] 데이터가 없는 lookahead/carryover 는 본문에 허위 이벤트를 만들지 않고 missing reason 또는 empty omission 으로 처리한다.
- **Priority**: Should-have (narrative continuity)

### FR-021: Operator observability, dry-run, retry budget, and operational digest (u17/u23/u31/u92)
- **Description**: 운영자는 cron/publish/notification/source-health 상태를 공개 독자 채널과 분리된 운영 표면에서 확인하고, dry-run 과 bounded retry 로 장애 대응을 할 수 있어야 한다. 알림은 중복/스팸을 줄이고 실패 원인을 추적 가능한 메시지와 artifact 로 남긴다.
- **User Story**: As a 운영자, I want 소스 상태, 알림 실패, retry 소진, dry-run 결과, 주간 운영 요약을 별도 운영 채널에서 확인하기를, so that 공개 독자에게 노이즈를 주지 않고 파이프라인 문제를 빠르게 진단할 수 있도록.
- **Acceptance Criteria**:
  - [x] source health 와 coverage history 는 run 별 성공/실패/0건/제한 상태를 기록하고 품질 KPI 또는 운영 진단에 사용된다.
  - [x] Telegram/public notification 은 bounded retry budget 을 사용하며 429 retry-after 를 존중하고 전역 retry budget 소진 시 중단한다.
  - [x] dry-run mode 는 공개 채널 발송과 boot/operator alert 를 실제 전송하지 않고, 운영자가 dry-run 상태를 식별할 수 있게 한다.
  - [x] boot alert dedup 은 같은 설정/부팅 문제로 반복 호출될 때 운영자 알림 스팸을 줄인다.
  - [x] weekly ops digest 는 최근 run/source/quality 상태를 운영자에게 요약한다.
  - [x] 운영자 알림 payload 와 로그는 secret-shaped substring 을 redaction chokepoint 로 보호하고 공개 채널과 분리한다.
- **Priority**: Should-have (operator reliability)

### FR-007: 운영자 실패 알림
- **Description**: 시황 생성 파이프라인 실패 시 **운영자 본인 1:1 chat**으로 알림한다. 공개 시황 채널(FR-004)과 분리하여 일반 구독자에게 노이즈를 주지 않는다.
- **User Story**: As a 운영자, I want 실패 시 별도 chat으로 즉시 알게 되기를, so that 빠르게 조치할 수 있고 일반 구독자가 노이즈를 보지 않도록.
- **Acceptance Criteria**:
  - [x] 파이프라인 실패 시 운영자 텔레그램 1:1 chat 알림 (`TELEGRAM_OPERATOR_CHAT_ID` 시크릿)
  - [x] GitHub Actions의 기본 실패 알림(이메일/배너)도 함께 활용
  - [x] 실패 사유(어느 단계? 어떤 에러? stack trace 요약) 메시지에 포함
  - [x] 공개 시황 채널(FR-004)에는 실패 메시지 발송 금지
  - [x] 알림 자체 실패 시 재시도 후 GitHub Actions 로그에라도 명시적으로 마킹
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
- **시황 출력 포맷 디테일** — 섹션은 정해졌으나 각 섹션 길이/스타일 가이드 필요
- **Claude Code CLI 호출 패턴** — `-p` 비대화형 모드, prompt 입력 방식, output 파싱 전략 (구현 시 결정)
- **GitHub Pages 사이트 디자인** — MkDocs Material 기본 테마 사용 가정
