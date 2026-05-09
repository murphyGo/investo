# Code Generation Plan: `u50 lightweight-charts-embed`

**Date**: 2026-05-10
**Unit**: u50 lightweight-charts-embed
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 사용자 직접 (TradingView 계정 + 차팅 라이브러리 사용 의사). 결정론적 anchor (u49) 의 visual 보완.
**Estimated Effort**: ~3-4 h
**Dependencies**:
- u46 stooq-price-primary (가격 history JSON 데이터 source).
- u49 deterministic-market-anchor (anchor 수치 — 차트의 ATH 마커 + 52주 범위 음영 source).
- u24 visual-provenance-and-layout (정적 SVG 카드와 visual harmony — JS 차트는 progressive enhancement, SVG fallback 보존).

---

## Goal

TradingView **Lightweight Charts** (MIT 라이센스, 오픈소스) 라이브러리를 자가 호스팅으로 GitHub Pages 정적 사이트에 임베드해, 시황 페이지에 인터랙티브 일봉 K-line + ATH 수평선 + 52주 범위 음영 차트를 띄운다. 데이터는 Stooq 에서 우리 측이 fetch 한 1년치 history JSON 을 `data-history` HTML attribute 로 주입; TradingView 의 paid 데이터 API 는 사용하지 않는다 (무료 only). 정적 SVG (u24) 와 공존: SVG 는 fallback (JS 비활성 / 메일 클라이언트 임베드 시), JS 차트는 progressive enhancement.

---

## Persona evidence

> 사용자 (2026-05-09 회고): "TradingView 계정 + 차팅 라이브러리 사용 가능."

추가 결정론적 narrative (u49) 의 visual 보완. 사용자가 TradingView 계정 보유 → Charting Library (full version, free for non-commercial) 등록 가능; 단 MVP 는 더 가벼운 Lightweight Charts (UMD bundle ~60KB) 로 시작.

라이센스 정리:
- **Lightweight Charts**: MIT, 자가 호스팅 가능, 자유 사용.
- **Charting Library** (full version): non-commercial 무료, 등록 필요. 별 unit 으로 격상 검토.
- **TradingView UDF/REST 데이터 API**: 유료 (별도 결제 필요 — 우리는 안 씀).
- **데이터 source**: 우리 측 Stooq fetch → JSON 변환.

---

## Definition of Done

- [ ] 자가 호스팅 라이브러리 번들: `site_docs/assets/lightweight-charts.standalone.production.js` (Lightweight Charts UMD ~60KB; CDN 의존 차단으로 R10 외부 의존 invariant 보존).
- [ ] MIT 라이센스 파일: `site_docs/assets/lightweight-charts.LICENSE.txt` — 라이브러리 원본 LICENSE 파일 byte-equal 첨부.
- [ ] 시황 markdown 에 차트 placeholder div 삽입 (publisher 가 가격 history JSON 을 `data-history` HTML attribute 로 주입):
  ```html
  <div class="investo-chart"
       id="chart-^GSPC"
       data-ticker="^GSPC"
       data-history='[{"t":"2025-05-10","o":..., "h":..., "l":..., "c":..., "v":...}, ...]'
       data-ath="5820.40"
       data-52w-high="5820.40"
       data-52w-low="4521.30"></div>
  ```
- [ ] mkdocs Material `extra_javascript` 등록: `lightweight-charts.standalone.production.js` + `assets/investo-chart-init.js` (우리의 init 스크립트).
- [ ] `site_docs/assets/investo-chart-init.js` (~80-150 LOC):
  - DOMContentLoaded 시 `.investo-chart` div 모두 scan.
  - `data-history` JSON.parse → `LightweightCharts.createChart(div, {...})` → `addCandlestickSeries()` + `setData(history)`.
  - ATH 수평선 마커: `addLineSeries()` with single-point data at `data-ath` value, line style `LightweightCharts.LineStyle.Dashed`.
  - 52주 범위 음영: `addAreaSeries()` with `data-52w-low` to `data-52w-high` band (또는 `priceLines`).
  - 차트 spec: 일봉 candlestick, 1년 history (~252 row), light/dark theme 자동 (mkdocs Material 의 `[data-md-color-scheme]` 감지).
  - 에러 fallback: JSON.parse 실패 / data-history 미존재 → div 자체 hidden + console.warn (사용자 시야에서 깔끔히 숨김 — SVG 카드가 fallback 으로 남음).
- [ ] 차트 위치: 시황 markdown 의 ⑤ 주요 종목 섹션 위 (또는 ② 전일 핵심 이슈 위 — UI 결정). 한 시황당 1-3 ticker 차트 (지수만 또는 anchor 의 top 3).
- [ ] **`og_card.py` 와 충돌 방지**: og:image 카드 (u29) 는 SVG primary + PNG twin 로 변경 없음. 차트는 페이지 내부 surface 만, 메타 surface 미관여.
- [ ] 정적 SVG 카드 (u24) 와 공존: SVG 는 매일 publish 시점에 그대로 생성·아카이브; JS 차트는 SVG 위에 *추가*. JS off / 메일 임베드 시 SVG 만 보임 (progressive enhancement 원칙).
- [ ] `publisher/site_index.py` 또는 `publisher/segment_pages.py` 에 placeholder div 삽입 헬퍼 추가:
  ```py
  def render_chart_placeholder(ticker: str, history: Sequence[dict], anchor: MarketAnchor) -> str: ...
  ```
- [ ] orchestrator publish path 에서 placeholder 삽입 — `data-history` 의 JSON 은 `json.dumps(separators=(",", ":"))` 로 minified + HTML-attribute-safe escape (apostrophe + ampersand + quote).
- [ ] 회귀 테스트:
  - **C1** (`tests/unit/publisher/test_chart_placeholder.py`): placeholder 함수가 `<div class="investo-chart" ...>` 정확한 attribute 셋트로 렌더.
  - **C2**: `data-history` JSON 이 valid 한 shape (`[{t,o,h,l,c,v}, ...]`).
  - **C3**: anchor 의 ATH/52w 값이 attribute 로 정확히 옮겨짐.
  - **C4**: ticker special chars (`^GSPC`, `BTC-USD`) 가 HTML-safe escape — `id="chart-^GSPC"` 가 valid HTML id 룰을 깨지 않도록 slug rule (e.g., `^` → `_`).
  - **C5** (정적): MIT 라이센스 파일 존재 + sha256 invariant — license 가 갱신될 때까지 byte-equal.
  - **C6** (정적): `lightweight-charts.standalone.production.js` 파일 존재 + 사이즈 합리 (50KB-100KB band).
  - **C7** (mkdocs build): `extra_javascript` 등록된 path 가 `mkdocs build --strict` 에서 fail 안 함.
- [ ] **JS 자체 단위 테스트는 작성하지 않음** — Python 프로젝트의 테스트 surface 가 아니므로 JS 동작은 (a) markdown placeholder 삽입 검증 + (b) data-history JSON shape 검증 + (c) license + bundle 파일 존재 검증으로 한정. 실제 JS 로직 검증은 수동 (mkdocs serve 후 browser 확인).
- [ ] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +12-18 신규 테스트), `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Lightweight Charts 라이브러리 자가 호스팅

- [ ] https://github.com/tradingview/lightweight-charts/releases 의 latest stable production UMD bundle 다운로드.
- [ ] `site_docs/assets/lightweight-charts.standalone.production.js` 에 byte-equal 저장.
- [ ] 동일 release 의 LICENSE 파일을 `site_docs/assets/lightweight-charts.LICENSE.txt` 에 byte-equal 저장.
- [ ] `_meta.json` (또는 directly in CONTRIBUTING runbook): bundle version + sha256 + 다운로드 URL + license 라벨 기록.

### Step 2 — `investo-chart-init.js` 구현

- [ ] `site_docs/assets/investo-chart-init.js` 작성:
  - `document.addEventListener("DOMContentLoaded", () => { ... })` 안에 `document.querySelectorAll(".investo-chart")` 루프.
  - 각 div 에 대해 history parse → chart 생성 → ATH/52w 마커 추가.
  - light/dark theme 감지: `document.documentElement.getAttribute("data-md-color-scheme")` watch + `MutationObserver` 로 변경 감지.
- [ ] 페이지 로드 후 console.log 로 `Investo charts initialised: N` 디버깅용.
- [ ] 사이즈 cap: 한 페이지에 차트 ≤ 5 (`querySelectorAll().slice(0, 5)`).

### Step 3 — Python publisher 헬퍼

- [ ] `src/investo/publisher/charts.py` (신규) — `render_chart_placeholder` 함수.
- [ ] HTML-safe id slug: `^GSPC` → `_GSPC`, `BTC-USD` → `BTC-USD` (이미 valid).
- [ ] `data-history` JSON.dumps + apostrophe escape (`json.dumps` default + `.replace("'", "&#39;")`).
- [ ] orchestrator publish path 에서 anchor list iteration → 각 anchor 에 대해 placeholder 삽입; 시황 markdown 의 정확한 위치 (UI 결정 — 권장: ⑤ 주요 종목 섹션 위 H2 직후).

### Step 4 — mkdocs 등록

- [ ] `mkdocs.yml` 의 `extra_javascript` block 에 두 path 추가:
  ```yaml
  extra_javascript:
    - assets/lightweight-charts.standalone.production.js
    - assets/investo-chart-init.js
  ```
- [ ] u24 의 `overrides/main.html` 변경 없음 (og:image meta 영향 없음).

### Step 5 — 회귀 테스트 + 수동 검증

- [ ] `tests/unit/publisher/test_chart_placeholder.py` (C1-C4).
- [ ] `tests/unit/publisher/test_chart_assets.py` (C5-C6 — 파일 존재 + sha256 invariant + 사이즈 band).
- [ ] mkdocs build 통과 확인.
- [ ] (수동) `mkdocs serve` 실행 → browser 에서 시황 페이지 열기 → 차트 렌더 확인. light/dark theme 토글.

---

## Project rule compliance

- **Anthropic SDK ban**: 무관.
- **모듈 경계**: `publisher/charts.py` 신규 (기존 `publisher/` 모듈 안). `orchestrator/pipeline.py` → `publisher/charts.render_chart_placeholder` 호출 path 는 OK. `briefing/` `notifier/` `sources/` 는 chart 모듈 import 금지.
- **R8 (no raw stdlib XML)**: 무관 (HTML attribute escape 만; XML parsing 아님).
- **R10**: 신규 live API 호출 없음. JS bundle 은 GitHub release 에서 한 번 다운로드 — 그 후 byte-equal 자가 호스팅. 외부 CDN 의존 차단.
- **R13**: 신규 secret 없음. `data-history` 는 가격 데이터 (public, secret 아님). `data-history` JSON 에 `raw_metadata` 의 secret-shaped substring 이 *섞여 들어오면* u27 redaction 이 차단해야 함 — anti-regression test 1건.
- **R14**: 무관.
- **무료 API only**: Lightweight Charts MIT, 자가 호스팅; TradingView 데이터 API 사용 안 함; 데이터는 Stooq (무료 무제한).
- **Disclaimer enforcement**: 시황 markdown 의 disclaimer 검증 path 변경 없음 — placeholder div 는 본문의 일부로 인라인됨.

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅
- [ ] `uv run pytest -q` ✅ (예상 +12-18 신규 테스트)
- [ ] `uv run mkdocs build --strict` ✅
- [ ] (수동) `mkdocs serve` browser 확인 — light/dark theme 차트 렌더.

---

## Out of scope

- **TradingView Charting Library (full version) 통합** — non-commercial 등록 필요; MVP 는 Lightweight Charts. 사용자가 full version 을 원하면 별 unit.
- **Intraday tick / real-time tick** — Stooq 무료 tier 는 일봉만; intraday 는 paid source 필요. 무료 룰에 막힘.
- **TradingView 데이터 API (UDF/REST)** — 유료. 영구 out of scope.
- **차트 인터랙션 (drawing tools / annotations)** — Lightweight Charts 의 기본 기능 (zoom / pan / crosshair) 만 활성화; drawing tools 는 Charting Library full version 영역.
- **Telegram 메시지 안 차트 임베드** — Telegram 은 SVG 만 지원; Lightweight Charts JS 는 안 보임. 메일/Telegram 은 SVG 카드 (u24/u26) 가 fallback; 변경 없음.

---

## Open questions

- **차트 위치 UI 결정**: ⑤ 주요 종목 섹션 위 vs ② 전일 핵심 이슈 위 vs 헤더 직후 — `mkdocs serve` 수동 비교 후 결정.
- **차트 갯수 cap**: MVP 는 페이지당 1 ticker (지수 ^GSPC) 만 vs top 3 (지수 + 빅테크 1 + 크립토 1) — 사용자 선호 확인. 권장: top 3 (다양성).
- **번들 사이즈 영향**: ~60KB JS + 매일 12 ticker × 1년치 × 6 컬럼 ≈ 200KB+ HTML attribute → 페이지당 ~260KB 추가. mkdocs Material 페이지 평균 사이즈 대비 25% 증가 — 허용 가능 판단; lazy-load 가 필요해지면 별 unit.
- **License 갱신 주기**: Lightweight Charts 신 release 가 나올 때 bundle + LICENSE 동시 갱신; runbook 에 분기 review 룰 등록 검토 (DEBT 후보).
- **DEBT 후보**: 차트 init JS 의 `MutationObserver` cleanup 누락 시 메모리 leak — single-page nav 인 mkdocs Material 에서 page-change 시 차트 re-init 룰 검토. Implementation closeout 시점에 DEBT 등록 검토.
