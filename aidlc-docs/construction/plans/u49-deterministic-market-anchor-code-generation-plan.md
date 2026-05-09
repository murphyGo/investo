# Code Generation Plan: `u49 deterministic-market-anchor`

**Date**: 2026-05-10
**Unit**: u49 deterministic-market-anchor
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 2026-05-09 cron 미국 시황 quality 회고 (사용자 직접 통찰). 가격 데이터에서 결정론적으로 도출되는 시장 사실을 시황 헤더에 박아 LLM 환각 risk 제거.
**Estimated Effort**: ~3-4 h
**Dependencies**:
- u46 stooq-price-primary (가격 데이터 안정화 후 anchor 계산이 의미 있음).
- u22 source-coverage-transparency (`SourceOutcome` integration).
- u32 trust-traceability-deep-dive (`numeric_self_check` 모듈과 contract — anchor 의 수치는 자동으로 numeric self-check pass).
- u25 summary-fidelity (Stage 2 prompt 룰 확장).

---

## Goal

가격 데이터로부터 결정론적으로 도출되는 시장 사실 (ATH 경신 / 52주 고저 거리 / MTD / YTD / 거래량 z-score) 을 별도 모듈에서 계산해, 시황 헤더에 `> **시장 anchor**: ...` 한 줄로 박는다. Stage 2 LLM 은 이 anchor 를 인용해야 하며, 추가 수치 발명은 prompt rule 로 금지. 이로써 사용자 회고의 "어제 미국 지수가 사상 최고가 경신했는데 시황에 안 나옴" 문제를 LLM 환각 risk 0 으로 해소한다.

---

## Persona evidence

> 사용자 (2026-05-09 cron 회고): "꼭 헤드라인 없어도 가격/차트 데이터만으로 ATH 경신 같은 건 결정론적으로 도출 가능."

이 통찰의 핵심: LLM 이 "가격이 ATH 다" 라고 출력하는 것은 환각 risk 가 있지만, 코드가 `close == max(history)` 를 검증해 헤더에 박은 사실을 LLM 이 *인용* 하는 것은 환각 risk 0. Anchor 헤더는 시황의 narrative spine 이 된다.

---

## Definition of Done

- [ ] 신규 모듈 `src/investo/briefing/market_anchor.py`:
  - `MarketAnchor` (frozen pydantic v2 + `slots=True` + `extra="forbid"`):
    - `ticker: str`
    - `close: Decimal`
    - `prev_close: Decimal | None`
    - `pct: Decimal | None` (= `(close - prev_close) / prev_close * 100`, prev_close 없으면 `None`)
    - `is_ath: bool` (close >= history max)
    - `pct_from_52w_high: Decimal | None` (음수 또는 0; ATH 면 0)
    - `pct_from_52w_low: Decimal | None` (양수 또는 0)
    - `mtd_pct: Decimal | None` (월초 종가 대비)
    - `ytd_pct: Decimal | None` (연초 종가 대비)
    - `volume_z_score: Decimal | None` (last 60 거래일 평균/표준편차 기준)
  - `compute_market_anchors(price_items: Sequence[NormalizedItem], history_window_days: int = 252) -> tuple[MarketAnchor, ...]`
- [ ] 가격 history source 결정 (Open Question 후 확정 — Step 1):
  - **Option A**: `archive/_meta/price_history.jsonl` 에 매일 가격 close 를 append → 시계열 누적. 첫 N 일은 ATH/52주 계산 불가 → graceful 'insufficient history' 처리.
  - **Option B**: Stooq endpoint multi-row CSV (`d1=YYYY-MM-DD&d2=YYYY-MM-DD`) 매일 1년치 fetch → ATH/52주 계산 즉시 가능, 단 Stooq fetch 부하 증가.
  - **권장**: Option B (즉시 calculable + Stooq 무제한); Option A 는 fallback (Stooq fail 시 archive 시계열에서).
- [ ] 시황 헤더 변경 (`briefing/pipeline.py`): 시황 markdown 의 `> **기준 시각**: ...` watermark (u25) 바로 아래에 `> **시장 anchor**: ^GSPC 5,820.40 ATH 경신, ^IXIC 18,420.10 (-0.3% from 52w high), AAPL +12.5% MTD` 형식의 한 줄 추가.
  - 렌더 함수 `render_market_anchor_line(anchors: Sequence[MarketAnchor]) -> str` — anchor 가 비어있으면 빈 문자열 반환 (헤더 라인 자체 생략).
  - 표시 우선순위: 지수 (^GSPC, ^IXIC, ^DJI) → 빅테크 (AAPL, MSFT, NVDA, ...) → 크립토 (BTC-USD, ETH-USD); 한 줄에 최대 5 ticker, 나머지는 omitted (또는 다음 줄 — UI 결정).
- [ ] Stage 2 prompt 룰 확장 (`briefing/prompts.py::STAGE2_SYSTEM`):
  - "시장 anchor 헤더에 명시된 사실 (ATH 경신, 52주 거리, MTD/YTD, 거래량 z-score) 은 ① 요약과 ② 전일 핵심 이슈에서 그대로 인용해야 함."
  - "anchor 헤더에 없는 수치를 발명하지 말 것 — anchor 에 명시된 % 와 가격만 사용 가능. 다른 수치는 Stage 1 candidate 의 `summary` / `raw_metadata` 에서 인용."
  - u25 의 numeric integrity 룰의 자연스러운 연장 — anchor 는 `numeric_self_check` 의 haystack 에 포함되므로 자동으로 검증됨 (anchor 수치는 항상 verified).
- [ ] 회귀 테스트 (`tests/unit/briefing/test_market_anchor.py`):
  - **A1**: 단순 ATH 케이스 — close=100, history max=99 → `is_ath=True`, `pct_from_52w_high=Decimal(0)`.
  - **A2**: 52주 저가 근접 — close=85, 52w_high=110, 52w_low=84 → `pct_from_52w_high≈-22.7`, `pct_from_52w_low≈+1.2`.
  - **A3**: 첫 거래일 (history 1 row) — `is_ath=True` (단일 점이 자기 자신의 max), `prev_close=None`, `pct=None`.
  - **A4**: 휴장일 (price_items 에 해당 ticker 부재) → 그 ticker 의 anchor 는 결과 tuple 에 포함되지 않음 (skip, 예외 없음).
  - **A5**: history insufficient (< 20 거래일) — MTD/YTD/52주 모두 `None` (graceful).
  - **A6**: 거래량 z-score — `volume = mean + 2σ` → `z=2.0` (Decimal); 평균 없으면 `None`.
  - **A7**: anchor 라인 렌더 — 5 anchor 입력 → 한 줄 string, ATH 마크 표시, 줄바꿈 없음.
  - **A8**: 빈 anchor → 빈 문자열 (헤더 라인 생략).
- [ ] 통합 테스트 (`tests/unit/briefing/test_pipeline.py` 확장):
  - 시황 generate → 헤더에 `> **시장 anchor**:` 라인 존재.
  - anchor 가 빈 경우 → 라인 자체 생략, watermark 만 존재.
  - Stage 2 user prompt 에 anchor block 이 주입되는지 (prompts.py 의 `format_market_anchor_section` helper 호출 검증).
- [ ] u32 의 `numeric_self_check` 와 cross-cutting 검증: anchor 가 헤더에 박은 수치는 자동으로 verified-haystack 에 포함되어야 함 (anchor 수치는 입력 candidate 의 `raw_metadata` 에서 도출되므로 자연스럽게 매치). Anti-regression test 1건.
- [ ] 모듈 경계 — `briefing/market_anchor.py` 는 `sources/`, `notifier/`, `publisher/`, `orchestrator/` 어느 것도 import 하지 않음 (입력 = `Sequence[NormalizedItem]`, 출력 = `tuple[MarketAnchor, ...]` + render string).
- [ ] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +20-28 신규 테스트), `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — History source 결정 + history loader 구현

- [ ] Option A vs B 결정 (메인 세션과 사전 합의 권장; 권장 = B). 결과를 plan 의 Open Question 클로저 항목에 기록.
- [ ] B 선택 시: u46 의 stooq adapter endpoint 를 `&d1=...&d2=...` multi-row 로 확장 (또는 별 fetch 함수). NormalizedItem 의 `raw_metadata.history` 에 `[{date, close, volume}, ...]` 1년치 stash. R10 fixture 도 multi-row 로 재녹화.
- [ ] A fallback: `archive/_meta/price_history.jsonl` reader (orchestrator publish 시점에 매일 1줄 append; u31 의 atomic append pattern 차용).

### Step 2 — `market_anchor.py` core

- [ ] `MarketAnchor` 모델.
- [ ] `compute_market_anchors(items, history_window_days=252)`:
  - 각 ticker 의 history 추출 (raw_metadata.history 또는 jsonl lookup).
  - history 길이별 graceful degrade: `< 20` → 52주/MTD/YTD/z-score 모두 `None`.
  - ATH 판정: `close >= max(history.close for history.date < today)` (= today 의 close 가 *과거* max 보다 크거나 같음).
  - 52주 high/low: `max/min(history[-252:].close)`; 거리 % 계산.
  - MTD: 월초 첫 영업일 종가 → `(close - mtd_open) / mtd_open * 100`.
  - YTD: 연초 첫 영업일 종가 → 동일.
  - Volume z-score: `(volume - mean(history[-60:].volume)) / std(history[-60:].volume)`.

### Step 3 — Renderer + Stage 2 prompt 통합

- [ ] `render_market_anchor_line(anchors) -> str` — Markdown blockquote 한 줄.
- [ ] `briefing/prompts.py::format_market_anchor_section(anchors) -> str` — Stage 2 user prompt 에 주입할 sectioned block ("시장 anchor:" 헤더 + 항목 list). u34 의 `format_recent_context_section` 패턴 차용.
- [ ] `STAGE2_SYSTEM` 에 anchor 인용 강제 룰 + 수치 발명 금지 룰 추가.
- [ ] `STAGE2_USER_TEMPLATE` 에 `{market_anchor_context}` placeholder 추가.

### Step 4 — `briefing/pipeline.py` 통합

- [ ] `generate_briefing(...)` 시그니처 확장: `market_anchors: tuple[MarketAnchor, ...] | None = None` (기본 `None` = 안 박음).
- [ ] `_render_market_anchor_block` 헬퍼 — 헤더 watermark 바로 아래에 anchor 라인 삽입.
- [ ] `orchestrator/pipeline.py` 가 publish 직전에 `compute_market_anchors(price_items)` 호출해 결과를 `generate_briefing` 에 전달.

### Step 5 — 회귀 테스트 + 검증

- [ ] `tests/unit/briefing/test_market_anchor.py` (A1-A8).
- [ ] `tests/unit/briefing/test_pipeline.py` 확장.
- [ ] u32 `numeric_self_check` cross-cutting 테스트.
- [ ] 전체 quality gate green.

---

## Project rule compliance

- **Anthropic SDK ban**: 무관 (anchor 는 결정론적 계산; LLM 호출 없음).
- **모듈 경계**: `briefing/market_anchor.py` 는 `briefing/` 안에서만 사용; `sources/` `notifier/` `publisher/` `orchestrator/` import 금지. `orchestrator/pipeline.py` 가 anchor 를 호출해 generate_briefing 에 전달하는 path 는 OK (orchestrator → briefing 은 허용).
- **R8 (no raw stdlib XML)**: 무관 (Decimal 산술만).
- **R10**: 신규 live API 호출 없음 (u46 의 fixture 재사용; multi-row 확장 시 그 unit 의 R10 가 커버).
- **R13**: 신규 secret 없음.
- **R14**: 무관.
- **무료 API only**: 무관.
- **Disclaimer enforcement**: anchor 라인은 publisher gate 통과 (markdown 본문 일부; disclaimer 검증과 충돌 없음).

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅
- [ ] `uv run pytest -q` ✅ (예상 +20-28 신규 테스트)
- [ ] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **차트 시각화** — u50 lightweight-charts-embed.
- **추가 metric** (RSI / 이동평균 / MACD / 볼린저 밴드) — 별 unit. MVP 는 ATH / 52주 / MTD / YTD / 거래량 z-score 5가지만.
- **Intraday anchor** — 일봉 close 기준만; intraday tick anchor 는 무료 source 부재로 별 wave.
- **Anchor 의 한국어 화법 자동 생성** — anchor 는 raw 수치 + 영어 ticker; 한국어 narrative 는 Stage 2 LLM 이 anchor 를 인용해 생성.

---

## Open questions

- **History source 선택 (Option A vs B)**: Step 1 첫 결정 사항. Option B (Stooq multi-row) 권장 이유: ATH/52주 즉시 calculable; 첫 발행부터 anchor 가 의미있음. Option A (archive 시계열 누적) 단점: 1년치 누적까지 anchor 가 무의미. Hybrid (B primary + A fallback) 도 가능.
- **Volume z-score 의 stooq 데이터 가용성**: Stooq CSV 의 volume 컬럼이 지수 (^GSPC 등) 에 대해 의미 있는 값을 주는지, 빅테크 ticker 만 의미 있는지 — fixture 녹화 시 검증. 지수에 volume 0 이 들어오면 z-score = `None`.
- **MTD/YTD 의 휴일 경계 처리**: 5/1 이 토요일 → 5/3(월) 이 첫 영업일. `mtd_open` 은 그 날 종가. 휴장일 lookup 은 history 의 첫 row 가 그 달의 데이터.
- **Anchor 라인의 위치**: u25 watermark 바로 아래 (현재 plan) vs 시황 ① 요약 안 — UI 결정. 권장 = watermark 바로 아래 (헤더 영역에 모두 모임). u29 hero 카드와의 visual harmony 도 고려.
- **DEBT 후보**: history JSONL append (Option A fallback) 의 atomic-write 는 u31 의 pattern 차용. 1년 후 파일 크기 ~50KB / ticker → 12 ticker × 50KB = 600KB. 압축 필요 시점 도래 시 DEBT 등록.
