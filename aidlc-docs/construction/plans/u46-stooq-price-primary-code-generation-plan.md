# Code Generation Plan: `u46 stooq-price-primary`

**Date**: 2026-05-10
**Unit**: u46 stooq-price-primary
**Stage**: Code Generation
**Status**: 📋 Planned (R10: Stooq is unauth public CSV — fixture session can be recorded immediately, no credential blocker)
**Source**: 2026-05-09 cron yfinance HTTP 429 IP-level block (사용자 직접 회고 + GHA log evidence)
**Estimated Effort**: ~3-4 h
**Dependencies**:
- u45 segment-routing-exclusivity (라우팅 fix 후 stooq 신규 source 등록이 깔끔; us-equity / crypto 양쪽 single-source 등록 가능).
- u1 sources (plugin pattern, `@register`, `retry_get`).
- u22 source-coverage-transparency (`SourceOutcome` / `SourceCollectionReport` 상속).
- u32 trust-traceability-deep-dive (`SourceTier` 등록).

---

## Goal

GHA shared runner IP에서 사실상 차단된 yfinance v8 endpoint를 보완하기 위해 **Stooq primary 가격 어댑터를 신규 등록**하고, 기존 `yfinance-price` 어댑터는 *제거하지 않고* secondary fallback 으로 강등한다. 둘 다 같은 segment allow-list 에 등록되므로 둘 중 하나라도 응답하면 가격 데이터가 시황에 들어간다 (orchestrator-level fallback 도입은 별 unit; 이 unit 은 단순히 source coverage 를 늘려서 confidence 를 회복).

---

## Persona evidence

> 사용자 (2026-05-09 cron 회고): "어제 미국 지수가 사상 최고가 경신했는데 시황에 안 나옴."

오늘 GHA log 분석:
```
GET https://query1.finance.yahoo.com/v8/finance/chart/^IXIC?... HTTP/1.1 429 Too Many Requests
GET https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?... HTTP/1.1 429 Too Many Requests
... (모든 11 ticker × 3 retry = 33 요청 전부 429)
```

GHA shared runner IP (AWS US-east) 가 Yahoo Finance 에 rate-limit 차단 — 이것은 코드 fix 로 우회 불가. 대체 무료 가격 source 평가:

- **Stooq** (`https://stooq.com/q/l/?s={ticker}&i=d`): 무제한 무료 CSV, 인증 불필요, 글로벌 지수·주식·crypto 커버. **PRIMARY 권장**.
- Twelve Data: 800 req/day, key 필요 (무료) — SECONDARY 후보.
- yfinance: 가끔 작동 → fallback 으로 강등.

---

## Definition of Done

- [ ] 신규 어댑터 `src/investo/sources/stooq_price.py` 등록 — `@register("stooq-price", segments=("us-equity","crypto"))`, `category="price"`.
- [ ] Stooq endpoint: `https://stooq.com/q/l/?s={ticker}&i=d&f=sd2t2ohlcv` (CSV; 인증 불필요; identity encoding per u11).
- [ ] Default ticker symbol mapping (12 default tickers — yfinance 어댑터의 ticker list 와 동일):
  - 지수: `^GSPC → ^spx`, `^IXIC → ^ndq`, `^DJI → ^dji`, `^RUT → ^rut`
  - 빅테크: `AAPL → aapl.us`, `MSFT → msft.us`, `NVDA → nvda.us`, `GOOGL → googl.us`, `META → meta.us`, `AMZN → amzn.us`, `TSLA → tsla.us`
  - 크립토: `BTC-USD → btcusd`, `ETH-USD → ethusd`
  - 매핑은 `_TICKER_MAP: Mapping[str, str]` 모듈 상수로 — 향후 watchlist 통합 시 동일 매핑 재사용.
- [ ] Per-ticker isolation: 한 ticker 가 4xx/5xx 또는 빈 CSV 응답일 때 나머지 ticker 응답 영향 없음 (yfinance 어댑터 패턴 그대로 차용; `await asyncio.gather(..., return_exceptions=True)` + per-future try/except).
- [ ] `NormalizedItem` 출력 shape: title `"^GSPC 5,820.40 (+0.12%)"` 형식; `summary` 에 일/주/월/YTD 변화율 (CSV 가 일봉만 주므로 일변화율만; 추가 timeframe 은 u49 anchor 에서 계산); `category="price"`; `published_at` = CSV `Date,Time` 컬럼 KST→UTC 변환; `raw_metadata` 에 ticker / open / high / low / close / volume.
- [ ] `segments.py::_US_ONLY_SOURCES` 에 `"stooq-price"` 등록 (지수·빅테크) + `_CRYPTO_ONLY_SOURCES` 에도 등록 (BTC-USD / ETH-USD). u45 의 새 source 분류 체계 위에 깔끔히 얹힘.
- [ ] `yfinance-price` 어댑터는 변경 없이 보존 — segment allow-list 에 둘 다 등록된 채 공존. orchestrator 가 두 source 의 union 을 받아 candidate stream 에 흘림 (별도 fallback 로직 없음; 둘 다 fail 해도 u22 reason code 가 quiet vs failed 구분).
- [ ] `sources/tiers.py` 에 `"stooq-price": "A"` 등록 (가격 source 는 regulator-of-record 가 아니므로 A; SEC EDGAR 같은 S 등급은 아님).
- [ ] `_internal/redaction.py::SECRET_ENV_VARS`: 변경 없음 (Stooq 인증 없음).
- [ ] R10 record/replay fixture:
  - 12 ticker happy-path CSV 응답 1세트 녹화 (`tests/fixtures/sources/stooq_price/{ticker_safe}.csv`)
  - empty-window 응답 1건 (Stooq 가 unknown ticker 에 대해 빈 CSV header 만 반환하는 케이스)
  - HTTP 5xx mock (fixture 는 fabricated 가 아닌 실제 5xx response body 의 truncated trace; 또는 transport-layer mock — fixture 폴더에 두지 않고 unit test 안에서 monkeypatch).
  - **R10 invariant**: live recording 의 byte-equal 보존; `.meta.json` sidecar 에 `recorded_at` + URL (인증 없으므로 redaction 불필요).
- [ ] 회귀 테스트 (`tests/unit/sources/test_stooq_price.py`):
  - 12 ticker fixture replay → 12 `NormalizedItem` 생성, `category="price"`, `raw_metadata` shape 검증.
  - 빈 CSV → 0 items, 예외 없음.
  - HTTP 5xx (mocked) → 0 items, INFO log, source health `failed` 기록.
  - 잘못된 CSV row (필수 컬럼 결손) → 해당 ticker 만 skip, 나머지는 통과 (per-ticker isolation pin).
  - tier 등록 확인: `SourceOutcome.tier == "A"`.
- [ ] segment 라우팅 회귀 (u45 와 contract):
  - stooq-price 의 `^GSPC` row → us-equity 만, crypto 없음.
  - stooq-price 의 `BTC-USD` row → crypto 만, us-equity 없음 (단 동일 source 가 양쪽 segment 에 등록되었으므로 — segment routing 은 source 만이 아니라 ticker 도 고려해야 함; per-row routing 은 u45 의 `_has_strong_crypto_signal` ticker regex 에 `BTC` 포함 → 자연스럽게 처리됨; 그래도 명시적 테스트 1건 추가).
- [ ] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +18-25 신규 테스트), `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Stooq fixture 녹화 (R10)

- [ ] 개발자 머신에서 `curl 'https://stooq.com/q/l/?s=^spx&i=d&f=sd2t2ohlcv'` 등 12 ticker 각각 수동 호출.
- [ ] 응답 byte 그대로 `tests/fixtures/sources/stooq_price/{ticker_safe}.csv` 에 저장 (파일명: `^GSPC` → `_GSPC.csv`, `BTC-USD` → `BTC-USD.csv`).
- [ ] `tests/fixtures/sources/stooq_price/_meta.json` 에 `recorded_at: "2026-05-10"` + ticker → URL 매핑 + sha256 hash 기록.
- [ ] 빈 CSV 케이스: `s=zzzznonexistent&i=d` 호출 → `Symbol,Date,Time,Open,High,Low,Close,Volume\nzzzznonexistent,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n` 식 응답 — 그대로 저장.

### Step 2 — Adapter 구현

- [ ] `src/investo/sources/stooq_price.py`:
  - `_TICKER_MAP` 상수.
  - `async def fetch(window, *, http) -> list[NormalizedItem]` — `asyncio.gather(*[_fetch_one(t, mapped, http) for t, mapped in _TICKER_MAP.items()], return_exceptions=True)` + 결과 필터링.
  - `_parse_csv_row(row: str) -> tuple[Decimal, Decimal, Decimal, Decimal, int] | None` — `csv.reader` (stdlib OK; XML 아님이므로 `defusedxml` 무관) 사용, decimal 파싱 실패 시 `None`.
  - 변화율 계산: 일봉만 주므로 `(close - prev_close) / prev_close * 100` 은 별도 prev_close fetch 없이 — Stooq 의 `range=5d` 에 해당하는 multi-row 응답을 받으려면 endpoint URL 에 `&d1=YYYYMMDD&d2=YYYYMMDD` 추가 (또는 `i=d&n=5` — 정확한 파라미터는 fixture 녹화 시 확인). MVP 는 1일치만 — 변화율은 u49 anchor 에서 계산.
  - `retry_get` 사용 (u11 identity-encoding); UA `Investo/1.0 (https://murphygo.github.io/investo)`.
- [ ] `src/investo/sources/__init__.py` 에 re-export.
- [ ] `src/investo/briefing/segments.py` `_US_ONLY_SOURCES` + `_CRYPTO_ONLY_SOURCES` 에 등록.
- [ ] `src/investo/sources/tiers.py` 에 `"stooq-price": "A"` 등록.

### Step 3 — 회귀 테스트

- [ ] `tests/unit/sources/test_stooq_price.py` — fixture replay + 빈 CSV + HTTP 5xx mock + per-ticker isolation + tier 등록.
- [ ] `tests/unit/briefing/test_segments_exclusivity.py` (u45 와 cross-cutting) 에 stooq-price 의 `^GSPC` / `BTC-USD` 라우팅 케이스 추가.

### Step 4 — 검증

- [ ] 전체 quality gate green.
- [ ] (수동) GHA dry-run: `INVESTO_DRY_RUN=1` + Stooq endpoint 실제 호출 → 12 ticker 응답 받는지 직접 확인.

---

## Project rule compliance

- **Anthropic SDK ban**: 무관.
- **모듈 경계**: `sources/stooq_price.py` 신규; aggregator → orchestrator path 변경 없음.
- **R8 (no raw stdlib XML)**: Stooq CSV 응답이므로 `csv.reader` (stdlib) 사용 가능; XML 아님.
- **R10 (record/replay fixtures, no fabrication)**: 강제. 12 ticker 모두 live-recorded byte-equal fixture. 5xx mock 은 transport-layer (fabricated payload 아님 — payload 가 아예 없는 transport error simulation).
- **R13**: 신규 secret 없음 (Stooq 인증 없음). `SECRET_ENV_VARS` 변경 없음.
- **R14 (fair-access UA)**: Stooq 는 명시적 UA 정책 없음; 중립 UA 로 충분.
- **무료 API only**: Stooq 무료 무제한; SEC fair-access policy 무관.
- **Disclaimer enforcement**: 무관 (가격 데이터; publisher gate 변경 없음).

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅
- [ ] `uv run pytest -q` ✅ (예상 +18-25 신규 테스트)
- [ ] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **결정론적 시장 anchor 계산** (ATH / 52주 / MTD / YTD / 거래량 z-score) — u49 deterministic-market-anchor.
- **TradingView Lightweight Charts 임베드** — u50.
- **`yfinance-price` 어댑터 제거** — 보수적으로 보존; 가끔 working day 가 있으므로 union 으로 두면 confidence 가 더 높아짐.
- **Twelve Data 어댑터** — Stooq 가 충분하면 secondary 후보로만 둠. 별 unit.
- **Multi-day price history** — Stooq endpoint 가 multi-row CSV 도 지원하지만 MVP 는 1일치. u49 가 history 를 필요로 하므로 그 unit 의 Step 1 에서 endpoint URL 확장 (또는 별 history adapter) 결정.
- **Intraday tick** — Stooq 무료 tier 는 일봉만; intraday 는 별도 paid source — out of scope (무료 only 룰).

---

## Open questions

- **Stooq endpoint 파라미터 정밀도**: `i=d` (daily) 는 확실하지만 `n=N` (last N rows) vs `d1/d2` (date range) 중 multi-day history 를 원할 때 어느 쪽이 stable 한지는 fixture 녹화 시 확인.
- **변화율 source-of-truth**: stooq CSV 한 row 만 받으면 변화율은 어댑터가 못 계산. u49 anchor 가 prev_close 를 가져야 함 — Stooq endpoint 에서 multi-row 받을지, 아니면 archive/_meta 의 어제 close 를 lookup 할지는 u49 의 Open question.
- **Symbol mapping 충돌**: `^IXIC → ^ndq` 가 정확한 stooq 코드인지 (또는 `^nasdaq`) — fixture 녹화 시 검증. 매핑이 틀리면 fixture 녹화 자체에서 발견.
- **DEBT 후보**: yfinance-price 어댑터는 영구히 fallback 으로 둘 것인지 vs 일정 기간 (예: 3개월) 0건이 지속되면 제거할 것인지 — implementation closeout 시점 DEBT 로 등록 검토.
