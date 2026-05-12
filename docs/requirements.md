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
  - [ ] 무료 API/RSS만 사용한다 (월 $0)
  - [ ] 소스 카테고리: 주가/지수, 크립토 시세, 거시 지표(FRED 등), 연준 캘린더, 주요 기업 뉴스, 실적 캘린더
  - [ ] 신규 소스 추가/제거가 코드 변경 1곳으로 가능 (plugin/registry 구조)
  - [ ] 단일 소스 실패 시 다른 소스 수집은 계속 진행 (graceful degradation)
  - [ ] 시장별 거래일 기준을 적용한다: 국내 증시는 KST, 미국 증시는 America/New_York, 크립토는 UTC 기준으로 `target_date` 데이터를 필터링한다.
- **Priority**: Must-have

### FR-008: 세그먼트별 시황 생성
- **Description**: 단일 통합 시황 대신 국내 증시, 미국 증시, 크립토를 각각 독립 세그먼트로 생성한다. 한 소스군의 강한 이슈가 다른 자산군의 시황을 압도하지 않도록 입력 분리, 최소 커버리지, 섹션별 품질 기준을 둔다.
- **User Story**: As a 본인, I want 국내/미국/크립토 시황을 분리해서 받기를, so that 각 시장의 핵심 흐름을 빠르게 비교하고 한쪽 시장 뉴스에 전체 브리핑이 끌려가지 않도록.
- **Acceptance Criteria**:
  - [ ] 매 실행마다 `domestic-equity`, `us-equity`, `crypto` 세그먼트를 생성한다.
  - [ ] 각 세그먼트는 독립 제목과 ①~⑥ 본문 섹션을 가진다. ⑦ 면책조항은 기존처럼 코드가 공통 삽입한다.
  - [ ] 세그먼트별 입력은 source/category/ticker/news provenance 기반으로 분리한다.
  - [ ] 특정 세그먼트의 핵심 소스가 부족하면 다른 세그먼트 뉴스로 대체하지 않고 "데이터 부족"을 명시한다.
  - [ ] 텔레그램 메시지는 세 세그먼트의 짧은 요약과 각 상세 링크를 포함한다.
- **Priority**: Must-have (post-MVP correction)

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
  - [ ] 시황은 markdown 파일로 git repo에 저장 (신규 세그먼트 실행 예: `archive/us-equity/2026/04/2026-04-25.md`; 과거 단일 시황은 `archive/2026/04/2026-04-25.md` 유지)
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
  - [ ] 메시지에 국내 증시, 미국 증시, 크립토 상세 URL 링크를 모두 포함
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
  - [ ] 폴더 구조: 신규 세그먼트 시황은 `archive/{segment}/YYYY/MM/YYYY-MM-DD.md`; 과거 단일 시황은 `archive/YYYY/MM/YYYY-MM-DD.md` 읽기 가능
  - [ ] 저장 용량 문제 발생 시 (수년 후) 별도 archival 정책 검토 — 현재는 Out of Scope
- **Priority**: Must-have

### FR-009: Reader-facing 출력 포맷 (u51 tldr-block-and-number-bold-inversion)
- **Description**: 시황의 가독성·액션성을 강제한다. (1) 본문 § 시작 전에 `## 한눈에 보기` TL;DR 3-bullet 블록을 emit 하고, (2) 시장 anchor 정보를 prose blockquote 가 아닌 markdown 표로 렌더하며, (3) §②/③/④/⑥ sub-heading 은 `### Title` (H3) 로 작성하고, (4) 본문 prose 안의 숫자 토큰 (`+11.51%`, `$81,154.06`, `4.42%`) 은 `**...**` 로 강조하며, (5) §⑥ "관전 포인트" bullet 의 관찰형 종결 어미 (`~여부 / ~필요가 있다 / ~관건이다 / ~주목할 필요`) 비율을 40% 이하로 유지하고 (위반 시 WARNING flag, blocking 아님), (6) 같은 segment 내 같은 용어의 풀어쓰기 글로싱은 첫 1회만 표기하고 2번째 이후는 base 용어만 남긴다.
- **User Story**: As a 시황 reader, I want 페이지를 열자마자 매그니튜드·방향성·액션을 한눈에 보기를, so that 본문을 전부 읽지 않고도 그날의 핵심을 빠르게 잡을 수 있도록.
- **Acceptance Criteria**:
  - [ ] 모든 segmented 시황 상단에 `## 한눈에 보기` H2 + 정확히 3 bullet 블록이 워터마크/세그먼트-네비/anchor 다음, ① 요약 헤더 직전에 배치
  - [ ] 시장 anchor 라인이 4-컬럼 markdown 표 (`| 종목 | 종가 | 변동 | 비고 |`) 로 렌더 — 우선순위 ranking 은 u49 와 동일, 최대 5행
  - [ ] §②/③/④/⑥ 의 sub-heading 이 `### Title` (H3) 로 작성됨; 기존 `**Title** — body` 패턴 부재
  - [ ] 본문 prose 의 숫자 토큰 (`[+-]?\d+\.\d+%`, `\$[\d,]+(?:\.\d+)?`, `\d+\.\d+%`) 이 `**...**` 로 wrap; 표 cell / 코드 블록 / 링크 URL 내부 미적용; 이미 wrap 된 토큰 idempotent
  - [ ] §⑥ bullet 의 관찰형 종결 어미 비율 ≤ 40% 검증 (위반 시 publisher WARN 로그 + segment / ratio / count 구조화 extra; *blocking 아님* — generation 변동성 흡수)
  - [ ] 같은 segment 내 같은 base 용어의 글로싱 (`base(풀어쓰기)`) 은 첫 1회만 풀어쓰기 표기; 2번째 이후 출현은 `base` 만 남김 (u40 의 `> **용어 가이드**` callout 은 그대로 유지)
  - [ ] 면책조항 (NFR-004 R5) 은 reader-format chain 후에도 verbatim 보존; `publisher.verify_disclaimer` 가 chain 다음 단계에서 정상 통과
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
- **시황 출력 포맷 디테일** — 섹션은 정해졌으나 각 섹션 길이/스타일 가이드 필요
- **Claude Code CLI 호출 패턴** — `-p` 비대화형 모드, prompt 입력 방식, output 파싱 전략 (구현 시 결정)
- **GitHub Pages 사이트 디자인** — MkDocs Material 기본 테마 사용 가정
