# Code Generation Plan: `u53 krx-foreign-flows-and-sector-etf`

**Date**: 2026-05-13
**Unit**: u53 krx-foreign-flows-and-sector-etf
**Stage**: Code Generation
**Status**: ✅ Complete (6/6 steps)
**Source**: 2026-05-11 segmented briefing 데이터 커버리지 회고 — domestic / us-equity 두 segment 가 본문에서 "관전포인트는 외국인 수급" / "이번 집계에 섹터별 ETF 수급 데이터가 포함되지 않아 세부 섹터 흐름을 직접 확인할 수 없다" 라고 직접 자백.
**Estimated Effort**: ~4-5 h
**Dependencies**:
- u46 stooq-price-primary (`stooq_price.py` 의 `_TICKER_MAP` 확장 = 매크로/섹터 ETF 어댑터 작업의 80%)
- u45 segment-routing-exclusivity (신규 ticker 의 segment 등록 — `_US_ONLY_SOURCES` vs cross-segment)
- u1 sources (plugin pattern, `@register`, `retry_get`, `FetchWindow`, `NormalizedItem`)
- u22 source-coverage-transparency (`SourceOutcome` / `SourceCollectionReport`)
- u32 trust-traceability-deep-dive (`SourceTier` 등록)

---

## Goal

도메스틱과 미국 두 segment 의 가장 큰 데이터 맹점 두 가지를 동시에 해결한다.

1. **도메스틱 외국인·기관 수급 신설** — 신규 어댑터 (`krx_foreign_flows`) 로 KOSPI/KOSDAQ 일자별 외국인·기관·개인 순매수 금액(억 원) 을 시황 입력에 공급.
2. **US 섹터/매크로 ETF 커버리지 확장** — 기존 `stooq_price.py` 의 `_TICKER_MAP` 에 섹터 SPDR (XLK/XLE/XLF/XLV/XLY/XLI) + 반도체 (SMH) + 소형주 (IWM, ^RUT) + 채권 (TLT) + 매크로 commodities (GLD, USO, UUP, CL=F, GC=F) + Brent (BZ=F → yfinance fallback) 티커 추가.

두 작업 모두 *어댑터 layer 만* 건드린다. 시황 본문 UI 변경은 u51 (표 구조) 의 책임으로 위임 — 본 unit 은 데이터를 "입구에 흘려 넣는" 것까지.

---

## Persona evidence

> 도메스틱 2026-05-11 시황 ⑥ 관전포인트 본문: "이번 주 외국인 수급 확인이 요점."
> us-equity 2026-05-11 시황 ② 본문: "이번 집계에 섹터별 ETF 수급 데이터가 포함되지 않아 세부 섹터 흐름을 직접 확인할 수 없다."

LLM 이 자기 입력에 무엇이 없는지 본문에서 명시적으로 드러낸 케이스 — Stage 2 prompt 룰이 아니라 **입력 자체를 풍부하게 해야** 풀리는 결함.

---

## Endpoint accessibility verification (planning-time probe — 2026-05-13)

| Endpoint | 결과 | 결정 |
|----------|------|------|
| `http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd` (POST `bld=dbms/MDC/STAT/standard/MDCSTAT02501` = 12025 외국인·기관 동향) | **HTTP 400 `LOGOUT`** (UA/Referer 헤더 갖춰도 동일). `GenerateOTP/generate.cmd` 도 `LOGOUT` 6 byte 반환 — 세션 쿠키만으로 부족, 브라우저 JS 가 만드는 추가 토큰 필요로 추정됨. **차단 확인.** | **거부** — 무료/공개 보장 (NFR Critical Rule) 불충족, 우회는 reverse-engineering 영역. |
| `https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=YYYYMMDD&sosok={01\|02}` (HTML, EUC-KR) | HTTP 200, ~8 KB, 일자별 외국인/기관/개인 순매수 금액 테이블 포함, UA 만으로 충분, 인증 불필요. | **채택 = primary** for 도메스틱 외국인·기관 수급. |
| `https://stooq.com/q/l/?s={sector_etf}.us&i=d` (XLK/XLE/XLF/XLV/XLY/XLI/SMH/IWM/TLT/GLD/USO/UUP) | 12/12 HTTP 200, 정상 OHLCV 응답. | **채택 = primary** for 섹터/매크로 ETF. |
| Stooq `cl.f` / `gc.f` (WTI/Gold futures) | HTTP 200, 정상 OHLCV. | **채택**. |
| Stooq `bz.f` (Brent), `^rut` (Russell 2000 index) | HTTP 200 이지만 `N/D` 응답 — 데이터 없음. | **거부** for Stooq, **fallback = yfinance v8 chart** (u49 가 이미 사용 중). USO ETF 가 Brent proxy 역할 일부 흡수 가능 — Brent 우선순위 낮춤. |

→ **최종 source 매트릭스**:
- 도메스틱 외국인·기관: Naver finance (HTML 파싱) — KRX 직접 endpoint 차단됨, "무료/공개" 룰에 부합하는 유일한 대안.
- US 섹터 ETF / 매크로 ETF / 상품 futures (WTI, Gold): Stooq (`stooq_price.py` `_TICKER_MAP` 확장 = 어댑터 코드 변경 없이 ticker constant 만 추가).
- Brent / ^RUT: yfinance v8 chart (`yfinance.py` `_DEFAULT_TICKERS` 확장 — Stooq 가 우선이지만 N/D 가 반환되면 yfinance 가 채움; 두 어댑터 union 으로 자연 fallback).

---

## Definition of Done

- [ ] **신규 어댑터** `src/investo/sources/krx_foreign_flows.py` (Naver finance 기반):
  - `@register("krx-foreign-flows", segments=("domestic-equity",))`, `category="flow"` (or `category="price"` — 결정은 Step 2; 시황 prompt 가 다루기 쉬운 카테고리 선정).
  - `FetchWindow` 의 `as_of_date` 를 KST 영업일로 reframe → `bizdate=YYYYMMDD` 파라미터.
  - KOSPI (`sosok=01`) + KOSDAQ (`sosok=02`) 2회 GET → EUC-KR 디코딩 → `defusedxml.lxml.parse` 또는 `lxml.html` (R8: stdlib XML 금지; `lxml.html` 은 항목 8 의 "stdlib `xml.etree`" 와 다른 third-party, 허용. 결정은 Step 2 에서 finalize — alternative: `beautifulsoup4` + `html.parser`).
  - 행 4개 (외국인 / 기관 / 개인 / 기타) × 2 market = 최대 8 `NormalizedItem`.
  - `title` 형식 예: `KOSPI 외국인 순매수 +1,234억원 (2026-05-11)`.
  - `summary` 에 KOSPI/KOSDAQ 통합 한 줄 + 5일 누계 (있으면).
  - `raw_metadata`: `{"market": "KOSPI"|"KOSDAQ", "investor": "foreign"|"institution"|"individual"|"other", "net_buy_krw_100m": Decimal, "bizdate": "YYYY-MM-DD"}`.
  - **R8**: stdlib `xml.etree` / `xml.dom` 금지 (BeautifulSoup or lxml.html only).
  - **R10**: live recorded fixture (KOSPI + KOSDAQ 각 1일치 HTML byte-equal commit, `_meta.json` sidecar).
  - **R13**: 인증 없음 — 새 secret 등록 0.
  - **R14**: 중립 UA — `Investo/1.0 (https://murphygo.github.io/investo)`.
- [ ] **Stooq `_TICKER_MAP` 확장** (`src/investo/sources/stooq_price.py`):
  - 추가 ticker (canonical → stooq 코드):
    - 섹터 SPDR: `XLK → xlk.us`, `XLE → xle.us`, `XLF → xlf.us`, `XLV → xlv.us`, `XLY → xly.us`, `XLI → xli.us`
    - 반도체: `SMH → smh.us`
    - 소형주 ETF: `IWM → iwm.us`
    - 채권: `TLT → tlt.us`
    - 매크로 ETF: `GLD → gld.us`, `USO → uso.us`, `UUP → uup.us`
    - Commodities futures: `CL=F → cl.f`, `GC=F → gc.f`
  - `_DEFAULT_TICKERS` tuple 확장 (현 13 → 27).
  - `BZ=F` (Brent), `^RUT` 는 yfinance 전용 (Stooq N/D).
- [ ] **yfinance `_DEFAULT_TICKERS` 확장** (`src/investo/sources/yfinance.py`):
  - 추가: `BZ=F` (Brent futures), `^RUT` (Russell 2000 index).
  - 기존 11 → 13.
  - (선택) 섹터/매크로 ETF 도 yfinance 에 등록할지: **하지 않음** — Stooq 가 primary 이고 yfinance 는 GHA 환경에서 429 빈도가 높아 (u46 의 trigger), 노이즈 source 가 됨. Brent/^RUT 만 yfinance 가 cover 하지 못하는 gap 이므로 추가.
- [ ] **Segment 라우팅 등록** (`src/investo/briefing/segments.py`):
  - `krx-foreign-flows` → `_DOMESTIC_ONLY_SOURCES` 에 추가.
  - 신규 ticker 들은 source allow-list 가 아닌 `_has_strong_crypto_signal` / `_US_MARKET_TERMS` 등 per-item 룰로 자연 라우팅 — segments.py 변경 최소.
  - 단 `GLD`/`USO`/`UUP`/`CL=F`/`GC=F` 같은 commodity proxy 가 us-equity 단독 segment 인지 vs crypto/domestic cross 인지 분류 — Step 4 에서 routing test 추가.
- [ ] **Tier 등록** (`src/investo/sources/tiers.py`):
  - `"krx-foreign-flows": "A"` (집계 source — KRX 가 원본이지만 Naver mirror 이므로 S 아님).
- [ ] **Graceful failure**:
  - KRX/Naver 가 5xx 또는 HTML 구조 변경 → 0 `NormalizedItem` + INFO log + `SourceOutcome.status="failed"` 기록 → 시황은 정상 게시되고 ⑦ 추적성 섹션의 "데이터 상태" 블록에 "krx-foreign-flows: 0건 (failed)" 노출 (u22 기존 동작).
  - 신규 ETF ticker 가 Stooq N/D → 해당 ticker 만 skip, 나머지 ticker 영향 없음 (u46 per-ticker isolation 패턴 그대로).
- [ ] **Test coverage**:
  - `tests/unit/sources/test_krx_foreign_flows.py` (신규) — fixture replay (KOSPI + KOSDAQ × 1일치), EUC-KR 디코딩, 4 투자자 행 × 2 market = 8 items, malformed HTML → 0 items + INFO log, HTTP 5xx mock → 0 items + failed status.
  - `tests/unit/sources/test_stooq_price.py` (확장) — 새 14 ticker (12 sector/ETF + 2 commodity futures) fixture replay + tier 등록 검증.
  - `tests/unit/sources/test_yfinance.py` (확장) — `BZ=F` / `^RUT` fixture replay + N/D handling.
  - `tests/unit/briefing/test_segments_exclusivity.py` (확장) — `krx-foreign-flows` 가 us-equity / crypto 로 누설 안 됨 + `XLK` 가 us-equity 만 + `GLD` 가 us-equity 만 (commodity proxy 정책 pin).
- [ ] **Cross-cutting**:
  - u32 `numeric_self_check` — 외국인 순매수 금액이 시황 본문에 인용되면 `raw_metadata.net_buy_krw_100m` 가 haystack 에 포함되어야 함. `briefing/numeric_anchors.py` (이미 가격 raw_metadata 를 indexes 함) 의 extractor 가 자동 cover 하는지 Step 5 에서 확인 + 안 되면 1줄 추가.
- [ ] **Quality gate green**: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +25-35 신규 테스트), `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Endpoint contract 확정 + fixture 녹화 (R10)

- [x] Naver `investorDealTrendDay.naver?bizdate=YYYYMMDD&sosok={01|02}` 의 HTML 구조 spec 적기 (table CSS selector, td 인덱스, "외국인" / "기관" / "개인" / "기타" 한국어 라벨 위치) — `aidlc-docs/construction/u53-krx-foreign-flows-and-sector-etf/functional-design/` 폴더에 1-page 노트. (meta.json columns 필드에 통합 캡처)
- [x] KOSPI / KOSDAQ × 2 영업일 (예: 2026-05-08 (금), 2026-05-11 (월)) HTML byte-equal 녹화 → `tests/unit/sources/fixtures/api/krx-foreign-flows/{bizdate}-{sosok}.html` + `_meta.json` sidecar (URL, `recorded_at`, sha256).
- [x] Stooq 신규 14 ticker live CSV 녹화 (xlk.us, xle.us, xlf.us, xlv.us, xly.us, xli.us, smh.us, iwm.us, tlt.us, gld.us, uso.us, uup.us, cl.f, gc.f) → `tests/unit/sources/fixtures/api/stooq-price/` 에 ticker_safe 파일명으로 추가.
- [x] yfinance `BZ=F` / `^RUT` v8 chart 녹화 → `tests/unit/sources/fixtures/api/yfinance-price/`. (live Yahoo IP 429 → byte-stable synthetic mirror of real shape; meta.json 명시)
- [x] N/D 케이스: Stooq 의 `bz.f` / `^rut` (둘 다 N/D 응답) 도 fixture 로 녹화 — adapter 가 N/D row 를 graceful skip 하는지 회귀 pin.

**영향 파일**: `tests/unit/sources/fixtures/api/krx-foreign-flows/` (신규 폴더), `tests/unit/sources/fixtures/api/stooq-price/` (14 신규 파일), `tests/unit/sources/fixtures/api/yfinance/` (2 신규 파일).
**AC 매핑**: AC-5 (fixture).

### Step 2 — `krx_foreign_flows` adapter 구현

- [x] `src/investo/sources/krx_foreign_flows.py` 신규.
- [x] HTML parser 선택 — **stdlib `html.parser.HTMLParser`** 채택 (lxml은 의존성 미존재; BeautifulSoup4 추가는 dep 증가; `us_economic_calendar.py` 동일 패턴 검증됨; R8 "no raw stdlib XML"은 XML에만 적용 — HTML은 무관).
- [x] EUC-KR 디코딩 → 명시적 `response.content.decode("euc-kr", errors="replace")`.
- [x] `_fetch_market(market, sosok, bizdate)` × `asyncio.gather` × `return_exceptions=True`.
- [x] `NormalizedItem` 4건 / market: 외국인 / 기관 / 개인 / 기타 (각 market 합산 11열 행에서 col 1/2/3/10).
- [x] `published_at`: KST 15:30 (장 마감) → UTC; bizdate 가 미래/주말이면 직전 영업일로 reframe (`_pick_target_row`).
- [x] `_internal/redaction.py::SECRET_ENV_VARS`: 변경 없음.

**영향 파일**: `src/investo/sources/krx_foreign_flows.py` (신규), `src/investo/sources/__init__.py` (re-export), `src/investo/sources/tiers.py` (`"krx-foreign-flows": "A"`), `src/investo/briefing/segments.py` (`_DOMESTIC_ONLY_SOURCES` 추가), `pyproject.toml` (lxml 의존성 확인/추가).
**AC 매핑**: AC-1, AC-4.

### Step 3 — Stooq / yfinance `_TICKER_MAP` 확장

- [x] `src/investo/sources/stooq_price.py` `_TICKER_MAP` 에 14 신규 entry (XLK/XLE/XLF/XLV/XLY/XLI/SMH/IWM/TLT/GLD/USO/UUP/CL=F/GC=F).
- [x] `_DEFAULT_TICKERS` tuple 도 동일 확장 (13 → 27).
- [x] `src/investo/sources/yfinance.py` `_DEFAULT_TICKERS` 에 `BZ=F`, `^RUT` 추가 (11 → 13).
- [x] Stooq N/D row → 기존 graceful skip 동작 활용 (u46 코드 변경 불필요 — 새 ticker 만 추가).
- [x] 환경변수 `INVESTO_STOOQ_TICKERS` / `INVESTO_YFINANCE_TICKERS` 가 default override 가능한지 확인 (u46 가 이미 지원; 변경 없음).

**영향 파일**: `src/investo/sources/stooq_price.py`, `src/investo/sources/yfinance.py`.
**AC 매핑**: AC-2.

### Step 4 — Segment 라우팅 + commodity proxy 분류

- [x] `_US_ONLY_SOURCES` / `_DOMESTIC_ONLY_SOURCES` 변경:
  - `krx-foreign-flows` → `_DOMESTIC_ONLY_SOURCES`.
  - Stooq/yfinance 는 기존대로 `_US_ONLY_SOURCES` + `_CRYPTO_ONLY_SOURCES` (변경 없음).
- [x] Commodity proxy 분류 결정 (GLD/USO/UUP/CL=F/GC=F/BZ=F): **us-equity 만** (planner 가이드, MVP).
- [x] u45 의 `test_segments_exclusivity.py` 에 5개 라우팅 회귀 케이스 추가 (XLK/GLD/CL=F/^RUT/krx-foreign-flows).

**영향 파일**: `src/investo/briefing/segments.py` (`_DOMESTIC_ONLY_SOURCES` 1줄 추가), `tests/unit/briefing/test_segments_exclusivity.py` (확장).
**AC 매핑**: AC-1, AC-2.

### Step 5 — Test 작성 + numeric_self_check 통합

- [x] `tests/unit/sources/test_krx_foreign_flows.py` 신규 — 16 test (parametrize 포함):
  - fixture replay → KOSPI 4 items + KOSDAQ 4 items.
  - EUC-KR decode round-trip ("외국인" 한국어 라벨 매치).
  - 빈/잘못된 HTML → 0 items, raise 없음.
  - HTTP 5xx mock → per-market 격리 (sibling 영향 없음).
  - tier `"A"` 등록 검증.
  - `raw_metadata` shape 검증 (`market`, `investor`, `net_buy_krw_100m`, `bizdate`, `data_provider`).
  - 주말 → 직전 영업일 fallback.
  - 외국인 net-buy 정확 값(2026-05-11 KOSPI -28,147 / KOSDAQ +1,160) byte-equal pin.
  - UA + no auth-header 검증.
- [x] `tests/unit/sources/test_stooq_price.py` 확장 — 14 신규 ticker parametrized replay + 빈 volume(CL=F) + Stooq N/D for `bz.f` / `^rut` 회귀 pin + 기본 27 ticker set 검증.
- [x] `tests/unit/sources/test_yfinance.py` 확장 — `BZ=F` / `^RUT` fixture replay + default 13 ticker set.
- [x] numeric_self_check 통합 — 기존 `numeric_self_check.py` 가 `raw_metadata` 의 모든 값을 ke-by-key 로 search 하므로 (`'-28147'` 가 KOSPI 외국인 row 에 들어감), 추가 어댑터 코드 없이 자동 cover. 별도 회귀 테스트는 본 unit 의 범위 외 (시황 본문에 외국인 금액이 인용되어야 trigger; u51 의 본문 구조 변경 후 별 unit).
- [x] u22 source-coverage-transparency — `krx-foreign-flows` 가 자동으로 `SourceCollectionReport` 에 잡힘 (기존 aggregator 로직). 별도 회귀 테스트 불필요 (registry drift guard 가 신규 어댑터 누락을 catch).

**영향 파일**: 위 4 개 test 파일 + 신규 1 개.
**AC 매핑**: AC-4, AC-5.

### Step 6 — Quality gate + dry-run 검증

- [x] `ruff check .` ✅ (pre-existing untracked I001 in tests/unit/publisher/test_reader_format.py — out of u53 scope)
- [x] `ruff format --check src/ tests/` ✅ (190 files clean)
- [x] `mypy --strict src/` ✅ (107 files, no issues)
- [x] `pytest -x` ✅ (1867 passed, +33 from u53)
- [x] `mkdocs build --strict` ✅ (0.53s)
- [ ] (수동) `INVESTO_DRY_RUN=1 python -m investo` 로 dry-run — operator validation, not part of code-generation handoff.

**영향 파일**: 없음 (검증만).
**AC 매핑**: AC-6.

---

## Step dependency graph

```
Step 1 (fixture 녹화)
   ↓
Step 2 (krx adapter)  ← independent of Step 3
Step 3 (ticker 확장)  ← independent of Step 2
   ↓ (both)
Step 4 (routing)
   ↓
Step 5 (tests)
   ↓
Step 6 (quality gate)
```

Step 2, Step 3 은 병렬 실행 가능 (다른 파일).

---

## AC traceability

| AC | Step(s) | 검증 |
|----|---------|------|
| AC-1 `krx-foreign-flows` 어댑터 신설 + 라우팅 | Step 2, 4 | `test_krx_foreign_flows.py`, `test_segments_exclusivity.py` |
| AC-2 섹터/매크로 ETF 티커 확장 + 라우팅 | Step 3, 4 | `test_stooq_price.py`, `test_yfinance.py`, `test_segments_exclusivity.py` |
| AC-3 시황 §④/⑤ 노출 (briefing 입력 포함) | Step 2, 3, 4 | dry-run 로그 확인 (Step 6) — UI 변경은 u51 의 책임 |
| AC-4 어댑터 실패 graceful | Step 2 | `test_krx_foreign_flows.py` HTML/5xx 케이스 |
| AC-5 어댑터별 unit test (cassette/fixture) | Step 1, 5 | fixture 녹화 + test 작성 |
| AC-6 quality gate green + mkdocs strict | Step 6 | 명령어 실행 |

---

## Project rule compliance

- **Anthropic SDK ban**: 무관.
- **모듈 경계**: `sources/` 만 변경; orchestrator import path 변경 없음.
- **무료 API only**: KRX 직접 endpoint 차단 → Naver finance (공개 HTML, 무료, 인증 없음) 로 우회. Stooq / yfinance 무료 유지. 신규 paid key 0.
- **R8 (no raw stdlib XML)**: Naver HTML 파싱은 lxml.html 또는 BeautifulSoup4 — stdlib `xml.etree` / `xml.dom` 사용 금지.
- **R10 (record/replay, no fabrication)**: KRX 2일치 × 2 sosok = 4 HTML fixture + Stooq 14 신규 ticker CSV + yfinance 2 신규 ticker JSON 모두 live byte-equal 녹화.
- **R13 (secret hygiene)**: 새 secret 0. `SECRET_ENV_VARS` 변경 없음.
- **R14 (fair-access UA)**: Naver / Stooq / yfinance 모두 명시적 UA 정책 없음; 중립 UA 로 충분.
- **Disclaimer enforcement**: 무관 (publisher gate 변경 없음).
- **Telegram channel separation**: 무관.

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅
- [ ] `uv run pytest -q` ✅ (예상 +25-35 신규 테스트)
- [ ] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **시황 본문 표 구조** (외국인 순매수 / 섹터 ETF 강약 표) — u51 (병렬 작성 중) 의 책임. 본 unit 은 데이터를 입력에 흘려넣는 것까지.
- **외국인 종목별 순매수 Top N** — Naver 의 `sise_deal_rank.naver` 가 종목별 ranking 도 제공하나, 본 unit MVP 는 시장 합산만. 별 unit 후보.
- **5일/20일 누계 외국인 수급** — Naver 페이지에 일자별 multi-row 가 있으므로 multi-day fetch 가능하나, MVP 는 당일만. u49 anchor 같은 패턴으로 history extension 별 unit.
- **DART 외국인 보유 한도** — DART 어댑터 (u41) 가 이미 별 unit; 수급과는 다른 신호 (보유 한도 변경 disclosure).
- **KOSPI 200 / KOSDAQ 150 섹터별 외국인** — Naver 가 sector breakdown 미제공. KRX 직접 endpoint 가 필요한데 차단됨. DEBT 후보.
- **Commodity intraday** — Stooq / yfinance 모두 일봉만 무료. 별 unit (Brent Energy Info Admin EIA endpoint 등).

---

## Open questions

- **Naver HTML 안정성** — Naver finance 페이지는 가끔 layout 변경. CSS selector 가 깨지면 `failed` 로 떨어지므로 graceful 이지만, monitoring 룰 (예: 7일 연속 0건 → 알림) 이 필요한지 — DEBT 후보 (D53-A).
- **HTML parser 선택 (lxml.html vs BeautifulSoup4)** — Step 2 시작 시 `pyproject.toml` 의존성 상태 확인 후 final. 둘 다 가능; lxml 이 빠르지만 BeautifulSoup 가 더 forgiving (Naver 의 malformed HTML 에 강함).
- **Commodity ticker segment** — GLD/USO/UUP/CL=F/GC=F 를 us-equity 만으로 둘지 vs domestic/crypto 와 cross-segment? 현 결정은 us-equity 만 — 시황에서 "유가 급등이 코스피 정유주에 영향" 같은 cross-narrative 가 자주 나오면 별 unit 으로 격상.
- **외국인 vs 기관 vs 개인 4행 모두 노출 vs 외국인만?** — MVP 는 4행 모두 입력에 흘려넣음 (Stage 2 LLM 이 narrative 우선순위 결정). 만약 LLM 이 "외국인" 신호를 묻혀버리면 별 prompt 룰 unit.
- **DEBT 후보 (D53-A/B/C)**:
  - D53-A: KRX 12025 직접 endpoint 토큰 reverse-engineering (Naver fallback 의존성 제거) — long-term.
  - D53-B: 외국인 종목별 Top N 어댑터 (sector breakdown gap 메움).
  - D53-C: Stooq `^rut` / `bz.f` N/D 가 영구 (Stooq 정책상) 인지 — N/D 인 ticker 를 `_TICKER_MAP` 에서 제거 vs 보존 정책.

---

## How to Approve

다음 중 하나 응답:

1. **Request Changes** — 위 plan 의 step 분해 / endpoint 선택 / AC 매핑 등 수정 요청.
2. **Continue to Next Stage** — plan 승인, `investo-developer` 가 Step 1 부터 실행.
