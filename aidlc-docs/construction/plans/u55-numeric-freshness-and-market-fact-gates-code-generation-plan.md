# Code Generation Plan: `u55 numeric-freshness-and-market-fact-gates`

**Date**: 2026-05-13
**Unit**: u55 numeric-freshness-and-market-fact-gates
**Stage**: Code Generation
**Status**: 📋 Planned (re-tightened 2026-05-13 to u51 precision)
**Source**: 2026-05-13 10-subagent evaluation of generated market briefings (deduplicated against u51 reader-format, u52 carryover, u53 coverage), supplemented by `archive/us-equity/2026/05/2026-05-11.md` and `archive/crypto/2026/05/2026-05-11.md` date-token corruption + KOSPI repetition.
**Estimated Effort**: ~6-8 h
**Dependencies**:
- u25 summary-fidelity-and-content-trust (numeric invention avoidance / first-viewport trust).
- u32 trust-traceability-deep-dive (`briefing/numeric_self_check.py` substring-presence gate — *kept as-is, sibling-augmented*).
- u46 stooq-price-primary (Decimal close values shipped through `raw_metadata`).
- u49 deterministic-market-anchor (`briefing/market_anchor.py` ATH / 52w / MTD / YTD anchor data — conflict source-of-truth for direction/extremum gates).
- u50 lightweight-charts-embed (history reuse).

---

## Deduplication Boundary

Excluded because already owned elsewhere:
- **u51**: visual emphasis of numbers (bold wrap), TL;DR block, anchor table, glossing dedupe, "여부" ratio.
- **u52**: previous-day carryover row reconciliation.
- **u53**: adding new KRX/sector adapters.
- **u54**: source-status severity + observed-vs-target run KPI semantics.
- **u56**: compliance / advisory language gate.
- **u57**: segment narrative scope + intraday time-state reconciliation.

This unit owns **whether a (numeric, date, direction) claim in the published markdown is true, source-backed, fresh, and corruption-free**.

`figures_presence` (u32: "number appears as a substring of a candidate item") and the new `figures_verified` (u55: "core market fact equals source-backed value within tolerance") are two **distinct, append-only KPI columns** on the quality page — neither replaces the other.

---

## Persona evidence

> 10-subagent quality 리뷰 (2026-05-13 session) + 사용자 직접 회고:
> - subagent #2 (factual integrity): "domestic KOSPI level prose 가 본문에 등장하지만 structured index source 가 0 items — 발명 risk."
> - subagent #4 (date hygiene): "crypto first-viewport `5/65/7` 토큰 — month 65 는 impossible 인데 publish 통과."
> - subagent #6 (anchor consistency): "본문이 'BTC ATH 갱신' 인데 anchor metadata 의 `ath_distance_pct` 가 `-1.4%` — 정면 충돌."
> - subagent #8 (freshness): "최신 archive 가 2026-05-11 인데 quality 페이지가 target_date 2026-05-09 표시 — 어느 쪽이 stale 인지 reader 가 알 수 없음."
> - subagent #10 (KPI semantics): "`figures_presence` 100% 인데 source 가 0 items — gate 가 substring match 만 본다."

---

## Definition of Done

- [x] **Typed core-fact verification**: 사전 정의된 `CoreFact` (10개 enum 값) 만 verify; 자유 prose claim extraction 시도 안 함. 각 `CoreFact` 의 source-backed Decimal 값이 stage-2 markdown 본문의 keyword-scoped window (anchor token ± WINDOW chars) 내에 tolerance 안에서 나타나면 verified, 아니면 unverified/conflict.
- [x] **Sibling helper, not extension**: 신규 모듈 `src/investo/briefing/numeric_verify.py` (u32 `numeric_self_check.find_unverified` 와 **별 surface**). u32 substring presence gate 는 변경 없음.
- [x] **KPI 분리**: `figures_presence` (u32 기존) + `figures_verified` (u55 신규) 가 `briefing/quality_eval.py` + `quality_history.py` 양쪽에 append-only column 으로 등록 (기존 history JSONL backward-compat).
- [x] **Conflict action enum**: `NumericGateAction = Literal["pass", "warn", "downgrade", "block"]` — anchor conflict (예: ATH 거짓) → `block`, unverified core fact → `downgrade` (`> 확인 필요` callout 본문 상단 삽입), non-core unverified → `warn` (operator alert only).
- [x] **Date corruption gate**: `r"\d{1,2}/\d{1,2}(?:/\d{1,2})?"` 매치 후 month ≤ 12 / day ≤ 31 / sanity check 실패 시 `block`. u51 `reader_format` 이 잡지 못하는 이유 명시 (post-format 시점 + regex scope 차이 — 본 unit 은 publish gate **직전** 별도 pass).
- [x] **무료 calendar**: 신규 정적 데이터 모듈 `src/investo/models/market_calendar.py` 에 KRX 2026 휴장일 + NYSE 2026 휴장일 hand-rolled list (KRX 공지 / NYSE 공지 URL 을 코멘트로 박음); 크립토는 24/7 (no holiday). **유료 API (tradingeconomics, pandas-market-calendars) 금지** — NFR-002 + 무료 룰 R10 보강.
- [x] **Per-segment freshness → publisher contract change**: orchestrator 가 segment 별 `SegmentResult(segment, status: Literal["fresh","stale","failed"], briefing: SegmentBriefing | None)` 를 publisher 에 전달; publisher 는 `fresh` 만 archive/Telegram 발행, `stale` 은 quality 페이지 라인 + operator alert (공개 채널 무발송, FR-007 경유).
- [x] **Per-segment isolation**: 한 segment 의 stale/failed 가 다른 segment 의 발행을 막지 않음 (graceful degradation).
- [x] **Tolerance 상수 박음**: 표로 (price/pct/yield/BTC) 절대 vs 상대 tolerance 명시; Decimal 비교; 발명 방지.
- [x] **R13 secret hygiene**: date corruption 테스트 fixture 에 secret 없음; 모든 WARNING / structured extra 가 secret-shaped substring 미포함.
- [x] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +44-56 신규 테스트), `mkdocs build --strict` ✅.

---

## Core data contracts

### `CoreFact` 10개 (Literal enum, `src/investo/models/core_fact.py`)

| id | CoreFact value | 의미 | 추출 keyword token (본문 매칭) | 1차 source-of-truth |
|----|----------------|------|----------------------------|---------------------|
| 1  | `kospi_close`  | 코스피 종가 | "코스피", "KOSPI"            | stooq-price `^kospi` close (Tier A) |
| 2  | `kosdaq_close` | 코스닥 종가 | "코스닥", "KOSDAQ"           | stooq-price `^kosdaq` close |
| 3  | `spx_close`    | S&P 500 종가 | "S&P 500", "스탠더드"        | stooq-price `^spx` close + yfinance fallback |
| 4  | `ndx_close`    | 나스닥 종가  | "나스닥", "NASDAQ"           | stooq-price `^ndq` close |
| 5  | `dji_close`    | 다우 종가    | "다우", "DOW"                | stooq-price `^dji` close |
| 6  | `btc_usd`      | BTC 가격     | "BTC", "비트코인"            | stooq-price `btc.v` close |
| 7  | `eth_usd`      | ETH 가격     | "ETH", "이더리움"            | stooq-price `eth.v` close |
| 8  | `usd_krw`      | 달러/원 환율 | "달러/원", "원화"            | (Phase-2, DEBT-D55-A 후보 — MVP `warn` 처리) |
| 9  | `us10y_yield`  | 미 10년물 금리 | "10년물", "10Y"            | (Phase-2, DEBT-D55-A) |
| 10 | `vix`          | VIX 지수    | "VIX", "변동성"              | stooq-price `vix` (Stooq N/D 다발 — D46-A 후보) |

**Adapter contract** (Step 1 작업): source adapter 가 emit 하는 `Item.raw_metadata` 에 신규 typed field `"core_facts": dict[CoreFact, str]` (Decimal-as-string) 추가. lookup 은 `Item.raw_metadata["core_facts"]["spx_close"]` → `Decimal` 변환. 모든 CoreFact 가 항상 emit 되지 않음 — 빈 dict 허용; 없는 CoreFact 는 본문에 등장 시 `unverified` 로 분류.

### `NumericGateAction` enum

```python
NumericGateAction = Literal["pass", "warn", "downgrade", "block"]
```

| 상황                                  | Action      | 효과                                                    |
|---------------------------------------|-------------|---------------------------------------------------------|
| Core fact ↔ source value within tol   | `pass`      | (no-op)                                                 |
| Anchor metadata 와 정면 충돌 (ATH 거짓 등) | `block`     | publish 거부; segment 전체 stale 처리 + operator alert |
| Core fact 본문 등장하지만 source 값 부재/불일치 (tol 초과) | `downgrade` | 본문 상단 `> ⚠️ 확인 필요: {fact} 수치는 별도 확인이 필요합니다.` callout 삽입 + WARN |
| Non-core 숫자 (figures_presence 가 잡지 못함) | `warn`      | operator alert; reader 변경 없음                        |
| Date corruption (impossible month/day) | `block`     | publish 거부; operator alert                            |

### Tolerance 상수 (`src/investo/briefing/numeric_verify.py`)

| 종류                  | Tolerance         | 비고                              |
|-----------------------|-------------------|-----------------------------------|
| Index close (KOSPI/SPX/NDX/DJI/KOSDAQ) | 절대 ±0.01 Decimal | 종가는 보통 소수 둘째 자리 publish |
| Percent move (`+0.85%`)               | 절대 ±0.05 pp     | LLM 반올림 흡수                   |
| Yield (`4.42%` 10Y 등)                | 절대 ±1 bp (0.01) | 인용 정밀도 한계                   |
| BTC                                    | 절대 ±$1          | 분 단위 변동 흡수                  |
| ETH                                    | 절대 ±$0.5        | 분 단위 변동 흡수                  |
| FX (USD/KRW)                           | 절대 ±0.10 원     | (Phase-2)                         |

Decimal 비교; 모든 source 값 → Decimal-as-string 직렬화 (NFR-003 재현성).

### Keyword scoped window

본문 prose 에서 `CoreFact` keyword 토큰 ± **WINDOW = 40 chars** 내에 등장하는 `[+-]?\d[\d,]*(?:\.\d+)?` 매치만 verify 후보. 윈도우 밖은 본 unit 무관 (u32 substring gate 가 이미 다룸). 다중 매치 시 가장 가까운 매치 채택.

### `SegmentResult` (publisher contract)

```python
class SegmentResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    segment: Segment  # Literal["domestic-equity","us-equity","crypto"]
    status: Literal["fresh", "stale", "failed"]
    briefing: SegmentBriefing | None  # None when status != "fresh"
    stale_reason: str | None  # human-readable, e.g. "latest archive 2026-05-09, calendar expects 2026-05-12"
```

기존 segmented briefing path 가 `dict[Segment, SegmentBriefing | None]` 으로 반환하던 자리에 추가. backward-compat: `status == "fresh"` 행만 archive/Telegram 으로; 나머지는 quality 페이지 + operator alert.

---

## Steps

### Step 1 — CoreFact + adapter contract (typed lookup framing)

- [x] 신규 모듈 `src/investo/models/core_fact.py`: `CoreFact: Literal[...]` (10개) + `CORE_FACT_KEYWORDS: dict[CoreFact, tuple[str, ...]]` (한국어/영문 토큰).
- [x] 신규 모듈 `src/investo/models/market_calendar.py`: KRX 2026 휴장일 list + NYSE 2026 휴장일 list (정적 tuple, source URL 코멘트). 함수 `next_expected_trading_day(segment, now: datetime) -> date` + `is_holiday(segment, day: date) -> bool`. 크립토는 항상 24/7.
- [x] 신규 어댑터 contract field: stooq-price 어댑터 (u46) 와 yfinance 어댑터 (u49) 가 emit 하는 `Item.raw_metadata` 에 `"core_facts": {CoreFact: Decimal-as-string}` key 추가 — ticker → CoreFact mapping table (`^spx` → `spx_close`, `btc.v` → `btc_usd`, ...) `src/investo/sources/_core_fact_map.py` 에 박음.
- [x] 단위 테스트 `tests/unit/models/test_core_fact.py` (예상 8-10 tests): enum 값 / keyword 매핑 / market_calendar holiday lookup / segment-specific calendar 정답성.
- [x] 영향 파일: `src/investo/models/core_fact.py` (신규), `src/investo/models/market_calendar.py` (신규), `src/investo/sources/_core_fact_map.py` (신규), `src/investo/sources/stooq_price.py` (raw_metadata field 1줄 추가), `src/investo/sources/yfinance.py` (동일), `tests/unit/models/test_core_fact.py` (신규), `tests/unit/sources/test_stooq_price.py` (+2-3 tests), `tests/unit/sources/test_yfinance.py` (+2-3 tests).

### Step 2 — Numeric verification engine (sibling to u32)

- [x] 신규 모듈 `src/investo/briefing/numeric_verify.py`:
  - `verify_core_facts(text: str, items: Sequence[Item], anchors: Sequence[MarketAnchor]) -> CoreFactVerificationReport`.
  - `CoreFactVerificationReport` (frozen pydantic, `extra="forbid"`): `verified: tuple[CoreFact, ...]`, `unverified: tuple[CoreFact, ...]`, `conflicts: tuple[ConflictDetail, ...]`, `actions: dict[CoreFact, NumericGateAction]`.
  - `ConflictDetail`: `fact: CoreFact`, `body_value: Decimal`, `source_value: Decimal`, `delta: Decimal`, `source_ticker: str`.
  - Lookup 절차: (1) `Item.raw_metadata["core_facts"]` aggregate 로 `dict[CoreFact, Decimal]` 빌드; (2) 본문에서 각 CoreFact keyword ± 40 char window 내 첫 Decimal 매치 추출; (3) tolerance 비교; (4) anchor 와 cross-check (예: 본문 "ATH 갱신" 매치 ↔ `MarketAnchor.is_ath`).
  - Pure (no I/O); idempotent; Decimal-as-string round-trip.
- [x] u32 `numeric_self_check.py` 무수정. quality KPI 양 surface 공존.
- [x] 단위 테스트 `tests/unit/briefing/test_numeric_verify.py` (예상 18-22 tests):
  - source-backed → `verified`, action `pass`.
  - source 부재 → `unverified`, action `downgrade`.
  - source 와 tol 초과 → `conflict`, action `block` (anchor 충돌 케이스) vs `downgrade` (단순 mismatch).
  - keyword window edge: 40 char 경계 / 다중 매치 / 한국어/영문 토큰 양쪽.
  - non-core 숫자 (예: 종목 PER) → action `warn`.
  - Decimal tolerance: ±0.01 / ±0.05pp / ±1bp / ±$1 / ±$0.5 boundary.
- [x] 영향 파일: `src/investo/briefing/numeric_verify.py` (신규), `tests/unit/briefing/test_numeric_verify.py` (신규).

### Step 3 — Date corruption + direction sanity gates

- [x] 신규 모듈 `src/investo/briefing/date_corruption.py` (또는 `numeric_verify.py` 내부 함수):
  - `find_corrupt_date_tokens(text: str) -> tuple[CorruptDate, ...]`: regex `r"\b(\d{1,2})/(\d{1,2})(?:/(\d{1,2}))?\b"` 매치 → month > 12 or day > 31 or all zero or duplicate-segment (`5/65/7` like) → `block`.
  - Why u51 `reader_format.wrap_numbers_bold` 가 잡지 못하는가? u51 은 *post-format* layer (regex `[+-]?\d+\.\d+%` / `\$[\d,]+`) — 슬래시-구분 date 토큰 패턴 미커버. 본 unit 은 publish gate 직전 별도 pass.
- [x] `verify_direction_against_anchor(text: str, anchors: Sequence[MarketAnchor]) -> tuple[DirectionConflict, ...]`:
  - 본문에 `[강세]` / `[약세]` / "상승 마감" / "하락 마감" 토큰이 등장하면 segment 대표 anchor 의 `change_pct` 부호와 cross-check.
  - "ATH 갱신" / "52w 최고" 토큰 ↔ `MarketAnchor.is_ath` / `ath_distance_pct == 0`.
  - 충돌 시 action `block`.
- [x] 단위 테스트 `tests/unit/briefing/test_date_corruption.py` (예상 10-12 tests): `5/65/7` 류 corruption / 정상 날짜 / month 13 / day 32 / 한국어 날짜 ("5월 11일") 무영향 / 코드 블록 내부 무영향.
- [x] 단위 테스트 `tests/unit/briefing/test_direction_sanity.py` (예상 8-10 tests): 강세 ↔ 양수 / 약세 ↔ 음수 / ATH 거짓 / 52w 최고 거짓 / anchor 부재 시 skip.
- [x] 영향 파일: `src/investo/briefing/date_corruption.py` (신규), `tests/unit/briefing/test_date_corruption.py` (신규), `tests/unit/briefing/test_direction_sanity.py` (신규).

### Step 4 — Per-segment freshness gate + `SegmentResult` contract

- [x] 신규 모델 `src/investo/models/segment_result.py`: `SegmentResult` pydantic (frozen, slots, `extra="forbid"`, `status: Literal["fresh","stale","failed"]`).
- [x] orchestrator `_run_segmented_briefing` 의 segment 별 반환 타입을 `dict[Segment, SegmentBriefing | None]` → `dict[Segment, SegmentResult]` 로 마이그레이션. 기존 호출자 (publisher / notifier / quality) 가 `result.briefing if result.status == "fresh" else None` 패턴으로 접근.
- [x] 신규 함수 `briefing/freshness.py::evaluate_segment_freshness(segment, latest_archive_date, target_date, calendar=market_calendar) -> SegmentResult.status`:
  - latest archive ≥ `next_expected_trading_day(segment, now)` − 1 → `fresh`.
  - 아니면 `stale` + `stale_reason` 채움.
  - 크립토: 항상 `fresh` 기대 (24/7) — latest archive 가 어제보다 오래되면 stale.
- [x] Publisher 변경: `briefing/quality_eval.py` 및 publisher path 가 `SegmentResult.status` 분기. `fresh` 만 archive markdown 작성 + Telegram 공개 채널 (FR-004). `stale` / `failed` 는 quality 페이지 freshness 라인 + operator alert (FR-007) — 공개 채널 무발송.
- [x] 단위 테스트 `tests/unit/briefing/test_freshness.py` (예상 10-12 tests): KRX 휴장 day-after / NYSE 휴장 / 크립토 토요일 fresh / domestic stale 시 us-equity/crypto 발행 영행 (per-segment isolation).
- [x] 통합 테스트 `tests/integration/test_pipeline_partial_freshness.py` (예상 4-6 tests): 3 segment 중 1개만 stale 인 케이스 → 2개 publish + 1개 quality 라인.
- [x] 영향 파일: `src/investo/models/segment_result.py` (신규), `src/investo/briefing/freshness.py` (신규), `src/investo/briefing/pipeline.py` (signature 마이그레이션), `src/investo/orchestrator/pipeline.py` (return type 마이그레이션 + publisher 호출 분기), `src/investo/publisher/` (분기 1-2 함수), `tests/unit/briefing/test_freshness.py` (신규), `tests/integration/test_pipeline_partial_freshness.py` (신규).

### Step 5 — KPI separation (`figures_verified`) + quality page + operator alert

- [x] `briefing/quality_eval.py`:
  - `QualityKPIs.figures_verified: float | None` 신규 column (1.0 = 모든 core fact verified, 0.0 = 전부 unverified/conflict; non-core 숫자는 분모에 미포함).
  - `figures_presence` (u32 기존) 보존 — backward-compat.
  - `score_quality` payload 직렬화 `figures_verified` 추가.
- [x] `briefing/quality_history.py` `QualitySnapshot` 에 `figures_verified: float | None` (append-only column; None 허용으로 기존 JSONL backward-compat).
- [x] `visuals/quality_sparkline.py` 의 `_FIELDS` 튜플에 `("figures_verified", "수치 검증", "#7e22ce")` 추가 — 신규 색.
- [x] Operator alert (FR-007 / `notifier/operator_alerter.py`) 에 신규 알림 타입: `numeric_block` / `numeric_downgrade` / `segment_stale` — structured `extra={"segment": ..., "fact": ..., "delta": ...}` (R13 검증: secret-shaped substring 미포함).
- [x] 단위 테스트 `tests/unit/briefing/test_quality_eval_figures_verified.py` (예상 6-8 tests): 1.0 / 0.5 / 0.0 / None backward-compat.
- [x] 단위 테스트 `tests/unit/notifier/test_operator_alerter_numeric.py` (예상 4-6 tests): alert payload / R13 secret hygiene.
- [x] 영향 파일: `src/investo/briefing/quality_eval.py` (수정), `src/investo/briefing/quality_history.py` (수정), `src/investo/visuals/quality_sparkline.py` (수정), `src/investo/notifier/operator_alerter.py` (수정), 위 테스트 2개 (신규).

### Step 6 — Orchestrator wire-through + canary

- [x] `src/investo/orchestrator/pipeline.py` publish path 에 호출 chain:
  1. `verify_core_facts(...)` → `CoreFactVerificationReport`.
  2. `find_corrupt_date_tokens(...)`.
  3. `verify_direction_against_anchor(...)`.
  4. Action 적용: `block` → segment status `failed`; `downgrade` → 본문 상단 `> ⚠️ 확인 필요` callout 삽입; `warn` → operator alert; `pass` → no-op.
  5. `evaluate_segment_freshness(...)` → segment status `stale` 여부.
- [x] dry-run 에서도 같은 chain 호출 — 텍스트 변형만 (callout 삽입), 외부 효과 없음.
- [x] 회귀 카나리: 의도적 위반 fixture 3종 (`5/65/7` date / ATH 거짓 / KOSPI 부재) 주입 → block / WARN 발화 + caplog.
- [x] 영향 파일: `src/investo/orchestrator/pipeline.py` (수정), `tests/integration/test_numeric_gates_canary.py` (신규, 예상 6-8 tests).

### Step 7 — Requirements + audit + quality gate

- [x] `docs/requirements.md` 에 **FR-011** 추가 (u51=FR-009, u54=FR-010 점유):
  - "FR-011: Numeric/Date/Freshness Gate — Core market fact verification, date corruption block, direction sanity, per-segment freshness."
  - AC: 본 plan DoD 의 9 항목 그대로 인용.
  - Priority: Should-have (NFR-001 quality 보강 + NFR-003 재현성).
- [x] `docs/DESIGN.md` 의 briefing pipeline 다이어그램에 `numeric_verify` + `freshness` 노드 추가.
- [x] `aidlc-docs/audit.md` 최상단에 본 unit 의 *re-tightening* entry append.
- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (예상 +44-56 신규 테스트; 현재 1694 → ~1738-1750)
- [x] `uv run mkdocs build --strict` ✅
- [x] (수동) 2026-05-11 us-equity + crypto + domestic-equity briefing 재생성 시뮬레이션 → `5/65/7` 류 corruption 차단 / KOSPI prose vs zero source → `downgrade` callout 시각 확인.

---

## Step Dependency Graph

```
Step 1 (CoreFact + calendar + adapter contract) ──┐
                                                   ├──> Step 6 (orchestrator wire-through) ──> Step 7 (gate)
Step 2 (numeric_verify engine) ───────────────────┤                              ↑
                                                   │                              │
Step 3 (date corruption + direction sanity) ──────┤                              │
                                                   │                              │
Step 4 (freshness + SegmentResult) ───────────────┤                              │
                                                   │                              │
Step 5 (figures_verified KPI + operator alert) ───┘                              │
                                                                                  │
                                                                                  │
(Step 7 의 `docs/requirements.md` + audit + DESIGN 갱신은 Step 6 와 병렬 가능) ────┘
```

Step 1 은 Step 2/3/4/5 의 contract 선행. Step 2-5 는 병렬 가능. Step 6 머지 후 Step 7.

---

## AC ↔ Step traceability

| DoD AC                                             | Step    | 영향 모듈                                                        |
|----------------------------------------------------|---------|------------------------------------------------------------------|
| Typed core-fact verification (10 enum)             | 1, 2    | `models/core_fact.py`, `briefing/numeric_verify.py`              |
| Sibling helper (not extension)                     | 2       | `briefing/numeric_verify.py` (u32 무수정)                         |
| KPI 분리 (`figures_presence` + `figures_verified`) | 5       | `briefing/quality_eval.py`, `quality_history.py`, `visuals/quality_sparkline.py` |
| `NumericGateAction` enum                           | 2, 6    | `briefing/numeric_verify.py`, `orchestrator/pipeline.py`         |
| Date corruption gate (`5/65/7` 류 block)            | 3, 6    | `briefing/date_corruption.py`, `orchestrator/pipeline.py`        |
| 무료 calendar (hand-rolled static)                 | 1       | `models/market_calendar.py`                                      |
| Per-segment freshness + `SegmentResult`            | 4, 6    | `models/segment_result.py`, `briefing/freshness.py`, `orchestrator/pipeline.py` |
| Per-segment isolation (graceful)                   | 4       | `orchestrator/pipeline.py`, `publisher/`                         |
| Tolerance 상수 (price/pct/yield/BTC/ETH)            | 2       | `briefing/numeric_verify.py`                                     |
| R13 secret hygiene in alerts                       | 5, 6    | `notifier/operator_alerter.py`, canary                           |

---

## NFR AC coverage map

- **NFR-001 (Performance / Quality KPI)**: `figures_verified` 신규 KPI 가 quality 페이지 + sparkline 에 노출 — DoD 전부 직접 달성.
- **NFR-002 (운영비 0원)**: 신규 외부 API 호출 0건. market_calendar 는 hand-rolled 정적 데이터 (KRX/NYSE 공지). 유료 API (tradingeconomics, pandas-market-calendars) **금지** 명시.
- **NFR-003 (재현성)**: 모든 helper pure (str / Sequence → 정적 모델). Decimal-as-string. idempotent test 포함.
- **NFR-004 (mypy strict)**: 신규 모듈 전부 strict.
- **NFR-005 (R13 secret hygiene)**: WARNING / structured extra / operator alert payload 가 secret-shaped substring 미포함 — Step 5/6 canary 핀.
- **R8 (no raw stdlib XML)**: 무관 — 본 unit 은 text + Decimal 처리만.
- **R10 (외부 의존성 최소)**: market_calendar / numeric_verify 가 외부 호출 0건. CoreFact / NumericGateAction / market_calendar 데이터는 `models/` 에 정적.

---

## Project rule compliance

- **Anthropic SDK ban**: 무관 — gate 는 publish path post-LLM.
- **모듈 경계**: 신규 모델 (`CoreFact`, `NumericGateAction`, `SegmentResult`, `market_calendar`) 은 `models/` (공유 foundation). 검증 엔진 (`numeric_verify`, `date_corruption`, `freshness`) 은 `briefing/`. orchestrator 만 양쪽 import. publisher 는 `SegmentResult.status` 만 분기. notifier 는 operator alerter 만 신규 alert 추가. 4 unit 간 직접 import 없음.
- **무료 API only**: 위에서 명시 — market_calendar 정적 데이터, 유료 API 금지.
- **Disclaimer enforcement**: `downgrade` callout 은 본문 *상단* 삽입 — disclaimer 보존; `verify_disclaimer` 가 gate chain 이후에도 정상 통과 (단위 테스트 핀).
- **Telegram 채널 분리**: `stale` / `block` 케이스는 FR-007 operator chat 만 발송, FR-004 공개 채널 무발송. 단위 테스트로 핀.
- **R13**: date corruption fixture 에 secret 없음 (synthetic markdown 만); operator alert payload 의 모든 structured field 가 redaction layer 통과 확인.

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (예상 +44-56 신규 테스트)
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **u51 owns**: 숫자 bolding, TL;DR 블록, 앵커 표, glossing dedupe, "여부" 비율.
- **u53 owns**: 신규 데이터 source (KRX foreign flows / sector ETF).
- **u54 owns**: source-status severity, observed vs target run, zero-vs-failed source 구분.
- **u56 owns**: compliance / 자문성 어구 차단 (`[강세]/[약세]` softening, advisory language).
- **u57 owns**: segment narrative scope (us-equity 본문이 crypto 내용 majority 차지하는 문제), 동일 bundle 내 `장중/마감` state mismatch 화해.
- **Phase-2 (DEBT-D55-A 후보)**: USD/KRW 환율 + 미 10년물 금리 CoreFact 활성화 (현재 source 부재로 MVP 에서는 `warn` 만).
- **Phase-2**: regenerate path — `block` 시 LLM 재시도 (현재는 segment 발행만 거부 + operator alert; regenerate 는 별 unit).
- **KRX/NYSE 휴장일 자동 갱신**: 본 unit 은 2026 hand-rolled. 2027 갱신은 annual maintenance task (DEBT-D55-B 후보).

---

## Open questions

- **Tolerance 조정**: ±0.05pp percent move 가 LLM 반올림 (예: 0.847% → 0.85%) 흡수에 충분한가? Implementation 후 fixture 회귀로 검증; 위반 시 ±0.10pp 로 완화.
- **Keyword scoped window WINDOW = 40 chars**: 한국어 prose 의 키워드↔숫자 거리 분포 측정 후 30-60 사이 조정. 너무 좁으면 false-negative (verification 누락), 너무 넓으면 false-positive (다른 ticker 의 숫자 매치).
- **Anchor 충돌 시 `block` 가 정말 옳은가?** 사용자 회고에서 "false positive 가 너무 잦으면 발행 중단" 우려 시 `downgrade` 로 완화 + canary 로 모니터링. 본 plan 은 *block* 채택 (사실 무결성 우선).
- **`figures_verified` 분모**: core fact 중 본문에 등장한 것만 분모 vs 모든 10개 분모? **본문 등장만 분모** 채택 (안 쓴 CoreFact 를 penalty 로 잡으면 segment 마다 자연스러운 0 점 발생).
- **`SegmentResult` 마이그레이션 backward-compat**: 기존 archive markdown 파서 (u52 carryover) 가 `SegmentBriefing` 직접 접근하면 lookup 1줄 수정 필요. Step 4 implementation 시 cross-verify.
- **DEBT 후보** (Open Questions 외):
  - **D55-A**: USD/KRW + 10Y yield CoreFact 활성화 (FRED endpoint 후보, NFR-002 무료 확인 필요).
  - **D55-B**: market_calendar 2027 갱신 (annual maintenance).
  - **D55-C**: keyword scoped window 의 한국어 형태소 분석 (KoNLPy) 으로 정확도 향상 — 무료 룰 무위반, 의존 무게 trade-off (u51 의 동일 DEBT 후보와 평행).
  - **D55-D**: regenerate path — `block` 시 LLM 재시도.

---

## How to approve

본 plan 의 9 DoD AC 와 7 step 분해를 검토 후:

1. **Request Changes** — AC 조정 / CoreFact enum 10개 명단 변경 / tolerance 상수 재조정 / NumericGateAction 매핑 재분류 / step 분해 변경 / out-of-scope 항목 재분류.
2. **Continue to Next Stage** — developer 가 Step 1 부터 implementation 시작.

승인 시 `aidlc-state.md` 의 u55 행이 "📋 Planned (0/5)" → "📋 Planned (0/7)" 후 "⚙️ In Progress" 로 전이.
