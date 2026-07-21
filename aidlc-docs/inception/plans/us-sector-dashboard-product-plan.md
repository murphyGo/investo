# Product Plan: 미국 섹터 동향 대시보드

**Date**: 2026-07-18<br>
**Stage**: Product discovery approved / Phase 0 source viability<br>
**Status**: Approved on 2026-07-18 — public source gate blocked, private validation path selected<br>
**Owner**: Investo planner

---

## 1. Executive Summary

Investo의 기존 `us-equity` 데일리 시황에 의존하지 않고도 사용자가 미국 증시의
주도 섹터와 부진 섹터를 10초 안에 파악할 수 있는 일일 EOD 대시보드를 추가한다.

첫 버전의 관찰 범위는 미국 전체 상장 종목이 아니라 **S&P 500의 11개 섹터를
대표하는 Select Sector SPDR ETF**로 고정한다. State Street가 공개한 11개
섹터 ETF는 XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU다.
벤치마크는 SPY를 사용한다.

대시보드는 다음 두 질문에 순서대로 답한다.

1. **어디가 강하고 약한가?** — 상대수익률과 모멘텀 가속도를 이용한
   `주도 / 둔화 / 회복 / 부진` 상태
2. **왜 그런가?** — 거래강도, 변동성, 실적 이벤트, 뉴스 관심도, 근거가 연결된
   내러티브

MVP는 `가격 모멘텀 + 거래강도 + 실현 변동성 + 뉴스/내러티브`에 집중한다.
실제 ETF 자금 유입·유출과 섹터 실적 집계는 데이터 사용권과 소스 안정성을
확인한 뒤 2단계로 추가한다. 거래량을 자금 유입으로 오인시키는 프록시는 만들지
않는다.

---

## 2. Problem and User Job

### 2.1 현재 문제

- 현재 `us-equity` 시황의 `③ 섹터/수급 동향`은 일일 서술형 결과라 11개 섹터를
  동일 기준으로 비교하기 어렵다.
- 일부 섹터 ETF만 수집되고, 가격 소스가 0건인 날에는 섹터 비교가 사실상
  불가능하다.
- 가격, 거래량, 변동성, 실적, 관심도, 뉴스가 각기 다른 문맥에 흩어져 있어
  “현재 주도 섹터”와 “주도력이 꺾이는 섹터”를 한 화면에서 볼 수 없다.
- 거래대금과 실제 펀드 자금흐름을 구분하지 않으면 독자가 잘못된 결론을 내릴
  수 있다.

### 2.2 Primary user job

> 매일 미국 장 마감 후 11개 섹터의 상대 강도와 변화 방향을 한 화면에서 보고,
> 상위·하위 섹터의 움직임을 설명하는 수치와 뉴스 근거를 2분 안에 확인한다.

### 2.3 Success moments

- 10초: 주도/부진 섹터와 전일 대비 상태 변화를 식별한다.
- 30초: 가격 움직임이 거래강도와 변동성으로 확인되는지 본다.
- 2분: 상·하위 섹터의 실적 일정, 뉴스, 내러티브와 출처를 확인한다.
- 필요 시: 섹터 상세 페이지에서 최근 상태 변화와 근거 이력을 본다.

---

## 3. Scope Decisions

### 3.1 Recommended defaults

| Decision | Recommended default | Rationale |
| --- | --- | --- |
| Market scope | S&P 500 11-sector ETF proxy | 공식적이고 고정된 11개 비교 집합. 미국 전체 상장종목이라고 과장하지 않음 |
| Frequency | 미국 정규장 마감 기준 일 1회 | Investo의 KST 아침 파이프라인과 맞고 무료 EOD 데이터로 구현 가능 |
| Benchmark | SPY | 섹터의 절대수익률과 시장 대비 상대수익률을 분리 |
| Primary state | 주도 / 둔화 / 회복 / 부진 | “강한가”뿐 아니라 “방향이 개선되는가”까지 표현 |
| Delivery | 기존 MkDocs 정적 사이트 | 신규 서버·DB·월 비용 없이 기존 Pages/아카이브 계약 재사용 |
| Narrative | 수치 계산은 결정적, LLM은 근거 요약만 | 숫자·순위 환각을 차단하고 기존 Claude Code CLI 패턴 재사용 |
| Advice boundary | 관찰형 정보만 제공 | 매수/매도, 목표가, 포트폴리오 추천은 범위 밖 |

### 3.2 Approved product decisions

2026-07-18에 다음 제품 결정을 확정했다.

1. 최종 공개 표면은 기존 GitHub Pages를 목표로 한다.
2. 공개 사용권 또는 런타임 안정성이 확보되기 전에는 private fixture/artifact로만
   계산과 화면을 검증한다.
3. 첫 출시 범위는 가격·상대강도·거래강도·실현변동성·뉴스 근거 중심의 core
   radar다.
4. 실제 ETF flow와 실적 actual 집계는 Phase 2로 분리한다.
5. Telegram 요약은 웹 대시보드가 안정화 게이트를 통과한 뒤 별도 단계로 추가한다.

### 3.3 Sector universe

| Ticker | Korean label | English label |
| --- | --- | --- |
| XLC | 커뮤니케이션 서비스 | Communication Services |
| XLY | 경기소비재 | Consumer Discretionary |
| XLP | 필수소비재 | Consumer Staples |
| XLE | 에너지 | Energy |
| XLF | 금융 | Financials |
| XLV | 헬스케어 | Health Care |
| XLI | 산업재 | Industrials |
| XLB | 소재 | Materials |
| XLRE | 부동산 | Real Estate |
| XLK | 정보기술 | Information Technology |
| XLU | 유틸리티 | Utilities |

**Public label requirement**: 모든 화면에 `S&P 500 11개 섹터 ETF 프록시`를
표시한다. “미국 증시 전체 섹터” 또는 “미국 시장 자금 전체”라고 표현하지 않는다.

### 3.4 Non-goals for MVP

- 실시간/장중 대시보드
- 미국 전체 종목의 완전한 breadth 계산
- 유료 실시간 시세, 유료 컨센서스, 유료 fund-flow 데이터
- 거래량을 “자금 유입/유출”로 명명
- 종목 추천, 섹터 비중 추천, 목표가, 자동매매
- 사용자 계정, 개인 포트폴리오, 별도 웹 서버/DB

---

## 4. Reader Experience

### 4.1 Latest dashboard

Target path: `site_docs/sectors/index.md`

```text
┌──────────────── 미국 섹터 레이더 · 2026-07-17 ET 마감 ────────────────┐
│ 데이터 상태: 부분 · 가격 10/11 · 뉴스 8/11 · 마지막 갱신 07:18 KST │
├───────────────────────────────────────────────────────────────────────┤
│ [주도] XLK +2.1%p  거래 1.4x │ [회복] XLF -0.3%p ↑ │ ... 11 tiles │
├────────────────── 상대강도 × 가속도 4분면 ────────────────────────────┤
│ 회복                         │ 주도                                  │
│                XLF →         │                 XLK →                 │
│ ─────────────────────────────┼────────────────────────────────────── │
│ 부진                         │ 둔화                                  │
├───────────────────────────────────────────────────────────────────────┤
│ 섹터  상태  1D  5D  21D  SPY대비  거래강도  20D변동성  관심도  근거 │
├───────────────────────────────────────────────────────────────────────┤
│ 오늘의 주도 내러티브 3개 │ 약세 내러티브 3개 │ 주요 실적 일정       │
└───────────────────────────────────────────────────────────────────────┘
```

색상만으로 상태를 구분하지 않는다. 상태 텍스트, 아이콘, 표 셀을 함께 사용한다.

### 4.2 Sector detail page

Target path: `site_docs/sectors/{ticker-lower}.md`

- 현재 상태와 전일/5거래일 전 상태
- ETF와 SPY의 정규화 가격 비교 차트
- 1D/5D/21D/63D 가격수익률 및 SPY 대비 초과수익률
- 거래량, 거래대금, 20일 기준 거래강도
- 20일 실현변동성, 20일 최대낙폭
- 해당 섹터로 분류된 뉴스와 실적 일정
- 최근 20거래일 내러티브/상태 변화 이력
- 지표 정의, 기준 시각, 출처, 데이터 제한

### 4.3 Navigation

`mkdocs.yml` 최상위 nav에 `미국 섹터`를 추가한다. 기존 `미국 증시` 시황에서는
대시보드로, 대시보드에서는 당일 `us-equity` 시황으로 상호 링크한다.

---

## 5. Metric Contract

### 5.1 Primary regime: relative strength × acceleration

수치 기준은 모든 섹터에 동일하게 적용하며 LLM이 계산하지 않는다.

```text
relative_strength_21d = sector_return_21d - spy_return_21d
recent_relative_5d    = sector_return_5d - spy_return_5d
prior_relative_5d     = return(t-10, t-5)_sector - return(t-10, t-5)_spy
acceleration_5d       = recent_relative_5d - prior_relative_5d
```

| State | Rule | Reader meaning |
| --- | --- | --- |
| 주도 | `relative_strength_21d > 0` and `acceleration_5d > 0` | 시장보다 강하고 최근 더 강해짐 |
| 둔화 | `relative_strength_21d > 0` and `acceleration_5d <= 0` | 아직 강하지만 주도력이 약해짐 |
| 회복 | `relative_strength_21d <= 0` and `acceleration_5d > 0` | 아직 시장보다 약하지만 개선 중 |
| 부진 | `relative_strength_21d <= 0` and `acceleration_5d <= 0` | 시장보다 약하고 개선 신호도 부족 |
| 데이터 부족 | 필요한 거래일 또는 SPY 기준이 없음 | 상태를 추정하지 않음 |

임계값 0 근처의 일일 출렁임을 줄이기 위해 구현 단계에서 `±0.10%p` 중립 밴드를
검증한다. 밴드 폭은 fixture/replay 데이터로 민감도 테스트한 뒤 고정하며, 기획
단계에서 임의 확정하지 않는다.

### 5.2 MVP metrics

| Family | Metric | Definition / label rule | Score use |
| --- | --- | --- | --- |
| Price | 1D/5D/21D/63D price return | 조정주가 소스가 아니면 반드시 `가격수익률`로 표기 | 5D/21D/63D 순위 |
| Relative | excess return vs SPY | 동일 기간 섹터 가격수익률 - SPY 가격수익률 | primary |
| Volume | volume ratio 20D | 당일 거래량 / 최근 20거래일 중앙값 | confirmation only |
| Liquidity | dollar volume | close × volume; `거래대금`으로 표기 | display only |
| Volatility | realized volatility 20D | 일간 로그수익률 표준편차 × √252 | display/risk context |
| Drawdown | max drawdown 20D | 20일 구간 고점 대비 최대 하락 | display/risk context |
| Attention | news attention | Investo 수집물 중 섹터 태그 기사 수, 20일 중앙값 대비 배수, 고유 소스 수 | display only |
| Narrative | evidence-backed themes | 섹터별 입력 근거 2개 이상 또는 S-tier 1개가 있는 최대 3개 테마 | no numeric score |
| Earnings | event pulse | 섹터로 매핑된 당일/향후 5일 실적 예정 건수와 주요 기업 | no score in MVP |

`관심도`는 전체 인터넷/검색 관심도가 아니라 **Investo 수집 뉴스 내 관심도**라고
표기한다. Google Trends 또는 커뮤니티 소스가 붙기 전에는 범위를 넓혀 말하지
않는다.

### 5.3 Ranking

한 개의 불투명한 종합점수보다 상태와 원 지표를 우선한다. 표 정렬용
`relative_rank_v1`만 제공한다.

```text
relative_rank_v1 =
    0.20 * percentile(excess_return_5d) +
    0.50 * percentile(excess_return_21d) +
    0.30 * percentile(excess_return_63d)
```

- 각 percentile은 당일 가용한 11개 섹터의 횡단면 순위다.
- 한 기간이 없으면 나머지 가중치를 재정규화하되 최소 2개 기간이 있어야 한다.
- 거래량, 변동성, 관심도는 강세/약세의 “좋음 점수”로 합산하지 않는다.
- 실제 fund flow와 실적 모멘텀이 안정적으로 추가되기 전 `종합 건강점수`라는
  이름을 사용하지 않는다.

### 5.4 Flow terminology

| Available fact | Allowed label | Forbidden label |
| --- | --- | --- |
| ETF exchange volume | 거래량 | 자금 유입 |
| close × volume | 거래대금 | 순매수, fund flow |
| signed price × volume heuristic | 가격·거래량 압력 프록시 | 실제 자금 흐름 |
| change in shares outstanding × NAV | ETF 설정/환매 기반 추정 순유입 | 미국 섹터 전체 자금 |

MVP에서는 실제 shares-outstanding 시계열의 공개 사용권이 확정되지 않으면 flow
카드를 `미지원`으로 표시하고 점수에서 제외한다.

---

## 6. News, Narrative, and Earnings Contract

### 6.1 Sector tagging

태그 신뢰도는 다음 우선순위를 사용한다.

1. 공식 ETF holdings 또는 승인된 ticker-to-sector registry의 정확한 ticker 매치
2. SEC CIK/SIC와 프로젝트 소유 SIC-to-sector crosswalk
3. 섹터 고유 기업명/산업 키워드의 결정적 매치
4. LLM 분류는 보조 후보만 생성하고, 공개 집계에는 신뢰도 기준을 통과한 항목만 반영

하나의 뉴스가 복수 섹터에 걸칠 수 있으나, 전체 기사 수를 각 섹터에 무제한
중복시키지 않는다. primary sector 1개, related sectors 최대 2개로 제한한다.

### 6.2 Narrative generation

- 입력: 결정적으로 계산된 지표 + 섹터로 라우팅된 뉴스/실적/공시 근거
- 출력: 상위/하위 섹터별 최대 3개 한글 테마, 각 테마에 근거 링크
- 금지: 근거 없는 인과, 목표가, 가격 예측, 매매 권유, LLM 산술
- fallback: LLM 실패 시 `수치상 움직임은 확인되나 설명 근거가 제한적입니다`와
  원 지표/기사 목록만 게시
- validation: 테마에 연결된 근거 id가 실제 입력에 없으면 해당 테마를 폐기

### 6.3 Earnings scope

MVP의 Nasdaq earnings calendar는 **예정/forecast 이벤트** 용도만 사용한다.
현재 Nasdaq 공개 캘린더는 역사적 보고일 기반 알고리즘과 외부 데이터 제공자를
사용하므로, 이를 “실적 발표 확정” 또는 “실적 서프라이즈”로 확대 해석하지 않는다.

실적 모멘텀은 Phase 2에서 다음이 갖춰진 뒤 추가한다.

- 섹터 구성 종목과 가중치의 합법적·안정적 source of truth
- SEC Company Facts의 분기 매출/EPS YoY 정규화
- 보고기간/회계연도 정렬과 restatement 처리
- consensus가 없을 때 beat/miss 또는 surprise를 만들지 않는 계약

---

## 7. Data Source Evaluation

### 7.1 Current local evidence

- 현재 `stooq-price`는 XLK/XLE/XLF/XLV/XLY/XLI 6개 섹터만 포함하며 5개
  섹터와 SPY가 빠져 있다.
- 2026-07-01~07-14의 저장된 미국 시황 여러 건에서 `stooq-price`와
  `yfinance-price`가 0건으로 기록됐다.
- 2026-07-18 live probe에서 Stooq snapshot endpoint는 기존 XLK를 포함한
  테스트 심볼들에 HTTP 404를 반환했다.
- Yahoo history helper는 이미 코드에 GitHub Actions 공유 IP의 HTTP 429 위험을
  명시하고 있다.

따라서 현재 가격 어댑터에 ticker 5개를 추가하는 것만으로는 MVP가 성립하지 않는다.

### 7.2 Candidate disposition

| Candidate | Disposition | Useful fields | Reason |
| --- | --- | --- | --- |
| Existing Stooq snapshot | **defer** | OHLCV snapshot | no-key/기존 계약 장점은 있으나 현재 live 404와 production 0건 반복. 복구 확인 전 핵심 source로 사용 금지 |
| Existing Yahoo chart/history | **defer** | 5D/1Y OHLCV | no-key지만 GHA 429 및 production 0건. fallback 이상으로 승격 금지 |
| State Street NAV History XLSX | **private validation only** | 11 ETF + SPY의 NAV, shares outstanding, AUM history | 2026-07-18에 12/12 접근, 최신일 2026-07-16, 최소 2,030행 확인. 공개 재배포는 약관상 허용되지 않으며 OHLCV가 아니므로 NAV 기반 regime fixture에만 사용 |
| State Street Product Data XLSX | **private validation only** | 11 ETF의 close, high, low, volume, NAV, shares outstanding, AUM, valuation, EPS growth | 공식·구조화·무키이며 2026-07-18 다운로드/열 확인 성공. 단일일 snapshot이고 사이트 약관이 복제·재배포를 제한하므로 공개 Pages source로 사용 금지 |
| State Street Daily Holdings XLSX | **defer** | ETF별 ticker/weight daily holdings | 뉴스 섹터 매핑에 매우 유용하나 동일한 공개 재배포/자동 사용권 검토 필요 |
| Alpha Vantage TIME_SERIES_DAILY | **reject for public MVP** | 무료 key로 최근 100개 일봉 OHLCV | 12 symbols/day는 무료 25 requests/day 안에 들지만 기본 약관은 개인·비상업 사용으로 제한하고 제3자 접근을 상업 사용으로 본다. 별도 서면 계약 없이는 공개 Pages에 사용하지 않음 |
| Twelve Data individual/free plans | **reject for public MVP** | 일봉 OHLCV | 공식 안내가 individual plan의 재배포와 제3자 공개 표시를 허용하지 않음 |
| Finnhub stock candles | **reject for public MVP** | split-adjusted daily OHLCV | 2026-07-19 공식 문서 기준 stock candles는 Premium-only이고 market-data 요금제 라이선스도 Personal Use다. 공개/상업 사용의 서면 승인 근거가 없으므로 무과금 public Pages gate 전에 탈락 |
| Alpaca Market Data API | **reject for public MVP under current terms** | 무료 Basic의 US 주식·ETF 2016년 이후 daily OHLCV, multi-symbol, corporate-action adjustment | 기술·비용 조건은 유력하지만 Alpaca 공식 지원이 API 데이터 재배포 불가를 명시하고 현재 고객 계약도 서면 동의 없는 복제·배포를 금지한다. Investo 공개 derived-display 서면 권한 전에는 사용하지 않음 |
| Financial Modeling Prep | **reject for public MVP under current terms** | 무료 Basic의 5년 end-of-day OHLCV, 250 calls/day | 공식 가격표가 Basic을 Individual use로 분류하고 FMP 데이터 표시·재배포에는 별도 Data Display and Licensing Agreement가 필요하다고 명시한다. 일반 약관도 별도 계약 없는 제3자 접근 앱/다중 사용자 표시를 금지하므로 공개 derived-display 계약 전에는 사용하지 않음 |
| Tiingo EOD API | **reject for public MVP** | 무료 Starter의 광범위한 raw/adjusted 일봉 OHLCV, dividend, split factor | 무료 500 symbols/month, 50 requests/hour, 1,000/day는 기술적으로 충분하지만 모든 표준 tier가 Internal Use Only다. 약관은 공개 분석/표시를 금지하고 display redistribution은 월 USD 250부터라 무과금 public Pages gate를 통과하지 못함 |
| Marketstack EOD API | **reject for public MVP under current terms** | 무료 1년 batch raw/adjusted 일봉 OHLCV, dividend, split factor, 100 requests/month | 다중 ticker 1회 호출로 기술·호출량 조건은 충족하지만 Commercial Use는 유료 Basic부터 제공된다. 현재 연결된 APILayer Freeware 계약도 테스트·평가만 허용하며 무료 공개 derived-display 권한을 부여하지 않음 |
| Massive Stocks API (구 Polygon.io) | **reject for public MVP under current terms** | 무료 Stocks Basic의 2년 all-US EOD OHLCV/VWAP, 5 calls/minute | 기술적으로 12개 ETF 수집은 가능하지만 Individual use다. Market Data Terms가 다른 최종사용자용 앱과 원데이터 또는 파생 차트·분석·리서치의 제3자 표시/배포를 서면 동의 없이 금지하므로 공개 radar에 사용할 수 없음 |
| EODHD EOD API | **reject for public MVP under current terms** | 무료 Starter의 1년 single-symbol 일봉 OHLCV와 adjusted close, 20 calls/day | 12개 ETF/SPY 요청은 기술적으로 가능하지만 Personal use다. 약관은 비전문 사용자의 원본·재포장 정보 표시와 재배포를 금지하고 전문 사용에는 사전 서면 승인을 요구하므로 공개 radar에 사용할 수 없음 |
| Tradier Market Data API | **reject for public MVP under current terms** | 개인 brokerage 계정의 lifetime single-symbol 일봉 OHLCV, production 120/sandbox 60 requests/minute | 계정 보유자의 API 접근 자체는 무과금이지만 non-Partner 권한은 personal use다. public-release app은 Partner 승인이 필요하고 business integration의 무과금 공개 표시 권한이 문서화되지 않았다. attribution 안내만으로 공개 radar 권한을 추론하지 않음 |
| StockData.org EOD API | **reject for public MVP under current terms** | 무료 100 requests/day, single-symbol split-adjusted 일봉 OHLCV | 무료 tier는 EOD 이력이 1개월뿐이라 63거래일을 충족하지 못하고, 1년은 월 USD 29 Basic부터다. 약관도 personal, non-commercial use만 허용하며 공개 derived-display 권한을 부여하지 않음 |
| MarketData.app Historical Candles API | **reject for public MVP under current terms** | 무료 1년 single-symbol split-adjusted 일봉 OHLCV, 100 credits/day, 최소 24시간 지연 | 12개 ETF/SPY의 63일 수집은 기술적으로 가능하지만 모든 self-service plan이 Internal Use다. 공개/end-user 표시는 custom annual Commercial plan과 거래소 라이선스가 필요하므로 무과금 public radar에 사용할 수 없음 |
| Barchart OnDemand `getHistory` API | **reject for public MVP under current published terms** | stock/ETF 일봉 OHLCV, 날짜 범위, split/dividend 조정, JSON/XML/CSV | 무료 접근은 plan 가입 전 limited-request trial뿐이고 production은 usage-based 유료다. 일반 약관도 공개·배포에 Barchart와 관련 data provider의 사전 서면 동의를 요구하므로 무과금 public radar에 사용할 수 없음 |
| Databento Historical API / `EQUS.SUMMARY` | **reject for public MVP under current published evidence** | Nasdaq NLS+ 기반 consolidated US-equities EOD `ohlcv-1d`, multi-symbol, JSON/CSV/DBN | 기술·이력·호출량 조건은 유력하지만 historical bytes가 항상 과금된다. 무료분은 팀당 1회 $125이며 6개월 후 만료되고, `EQUS.SUMMARY`의 정확한 공개 파생표시 권한도 Data Catalog/License Manager 확인이 필요하므로 무과금 public radar에 사용할 수 없음 |
| Intrinio EOD Historical Stock Prices | **reject for public MVP under current published pricing and terms** | 50년+ 일봉 raw/adjusted OHLCV, dividend/split/factor, JSON API | 영구 무료 production tier가 없다. Individual은 월 USD 150이며 외부 표시·재배포가 금지되고, 공개 표시 권리는 월 USD 333부터 시작하는 Startup과 체결된 Order Form 범위에서만 제공되므로 무과금 public radar에 사용할 수 없음 |
| SimFin Daily Share Prices | **reject for public MVP under the current FREE/BASIC data license** | 무료 5년 일봉 OHLC, adjusted close, volume, API/bulk download | 비용·이력 조건은 유력하지만 FREE/BASIC은 personal research와 own use로 한정되고 타인 공유를 금지한다. 재가공 데이터도 같은 제한을 따르며 재배포는 별도 Redistribution/Enterprise 라이선스가 필요하다. `interpretations` 예외가 공개 수치형 radar 산출물을 허용한다고 명시되지 않아 권리를 추론하지 않음 |
| Nasdaq market-data APIs | **reject for no-cost MVP** | licensed OHLCV/history | 공식 API는 trial/credential 및 주문 계약 기반이고 derived data의 외부 배포도 주문서 또는 사전 승인이 필요함 |
| SEC EDGAR Company Facts / Submissions | **ship-now** | 공시·실적 actual, SIC, filing lineage | 공식, JSON, 무키, real-time update, 기존 adapter 존재. 전 섹터 확대 시 bulk/frames 사용과 runtime 설계가 필요 |
| Nasdaq Earnings Calendar | **ship-now (schedule only)** | 예정일, report time, EPS forecast, 기업명 | 기존 adapter 재사용. 실제 실적/서프라이즈 점수에는 사용 금지 |
| Existing US news feeds | **ship-now** | 기사 제목/요약/URL/시각 | 기존 수집 corpus로 뉴스 관심도와 근거 내러티브 시작 가능. 섹터별 coverage 공개 필요 |
| Cboe VVIX/SKEW | **ship-now (market context only)** | 시장 전체 tail/volatility context | 기존 공식 adapter. 섹터별 변동성은 ETF 일봉에서 직접 계산; Cboe 역사 데이터 구매 의존 금지 |
| FINRA daily short-sale volume | **defer to Phase 2** | security별 off-exchange short volume | 공식·구조화·비상업 무료. 단, 전체 거래/short interest가 아니므로 관심/포지셔닝 보조 지표로만 사용 |
| SEC Form N-PORT datasets | **defer** | 월별 펀드 holdings | 공식·구조화지만 분기 배포, 400MB+ 규모라 일일 flow 요구와 맞지 않음 |
| Google Trends API alpha | **defer** | 검색 관심도 | 공식 API가 제한된 alpha tester에게만 제공됨 |
| Reddit API/scraping | **reject for MVP** | 커뮤니티 관심도/내러티브 | OAuth/등록/약관/콘텐츠 권리/삭제 요구 부담. 무인 scraping은 사용하지 않음 |

### 7.3 Mandatory source spike

구현 유닛 등록 전에 0.5~1일의 read-only/fixture spike를 수행한다.

Decision record:
[us-sector-dashboard-s0-source-decision.md](us-sector-dashboard-s0-source-decision.md)

1. 공개 Pages에 파생 EOD 수치를 표시할 수 있는 가격 source의 약관 확인
2. GitHub Actions에서 11 ETF + SPY를 5일 연속 또는 replay-equivalent로 수집
3. 최근 63거래일 이상 OHLCV 확보 여부 확인
4. 전체 요청 수, wall-clock, rate limit, failure mode 측정
5. raw response를 공개 저장하지 않고 계산 결과만 저장해도 되는지 확인
6. 하나의 source가 실패할 때 dashboard가 partial/insufficient로 정직하게 퇴화하는지 설계

**Public exit gate**: 가격 source가 공개 파생 표시 권한, `10/11 sectors + SPY`, 최근
21거래일 이상 OHLCV, weekday freshness 36시간 이하를 모두 만족하지 못하면 public
MVP construction과 Pages publish integration을 시작하지 않는다.

**Private validation gate**: 공개 게이트가 막혀도 11개 섹터 + SPY의 동일 기준 시계열이
있으면 regime/순위/화면 계약을 private fixture로 검증할 수 있다. 이때 NAV는 반드시
`NAV 기반`으로 표기하고, exchange volume·거래대금·실제 flow 카드는 숨긴다. private
결과를 public archive나 Pages에 복사하지 않는다.

---

## 8. Architecture Proposal

### 8.1 Component boundary

새 기능은 기존 시황 prompt에 표를 더 넣는 방식이 아니라 독립 도메인 컴포넌트로
둔다.

```text
sources ───────────────┐
                      v
                orchestrator
                 /         \
                v           v
       sector_dashboard   briefing
                |           |
                └─────┬─────┘
                      v
                  publisher
                      |
                      v
              MkDocs / GitHub Pages

models = all components' shared leaf
```

Rules:

- `sector_dashboard`는 `models`만 import하며 `sources`, `briefing`, `publisher`를
  import하지 않는다.
- `orchestrator`가 `NormalizedItem`, OHLC history, previous sector snapshots를
  주입한다.
- `publisher`는 완성된 `SectorDashboardSnapshot`만 받아 markdown/JSON을 쓴다.
- 섹터 숫자 계산은 pure/deterministic 함수다.
- LLM 내러티브 실패는 숫자 대시보드 게시를 막지 않는다.

### 8.2 Proposed package surfaces

```text
src/investo/models/sector.py
src/investo/sector_dashboard/
  universe.py          # 11 sectors + benchmark registry
  metrics.py           # returns, relative strength, volume, volatility
  regime.py            # 주도/둔화/회복/부진
  evidence.py          # news/earnings sector tagging + confidence
  narrative.py         # evidence-bound narrative contract
  history.py           # prior public snapshot loading/validation
src/investo/publisher/sector_pages.py
site_docs/sectors/index.md
site_docs/sectors/{ticker}.md
site_docs/assets/sector-dashboard.js
```

정확한 파일 구조는 Application Design 단계에서 확정한다. 위 목록은 책임 경계를
고정하기 위한 제안이며 구현 지시가 아니다.

### 8.3 Canonical artifacts

```text
archive/_meta/sectors/YYYY/YYYY-MM-DD.json
site_docs/sectors/index.md
site_docs/sectors/{ticker}.md
```

`SectorDashboardSnapshot`의 최소 계약:

- schema version, target date, US-market as-of timestamp
- benchmark ticker and source provenance
- 11 fixed sector records
- raw metric values, coverage status, missing reasons
- regime and relative rank inputs/outputs
- news/earnings evidence references
- narrative text + referenced evidence ids
- source outcomes and freshness

Provider raw payload, API key, proprietary holdings dump는 공개 artifact에 저장하지 않는다.

### 8.4 Pipeline behavior

```text
collect
  -> build/reconcile sector history
  -> compute sector metrics and regimes
  -> tag news/earnings evidence
  -> generate optional evidence-bound narrative
  -> publish canonical snapshot + latest/detail pages atomically
  -> existing briefing publish continues independently
```

- sector dashboard failure는 기존 시황을 실패시키지 않는다.
- 실패 시 pipeline은 `PARTIAL`, operator alert를 남기고 마지막 정상 dashboard를
  덮어쓰지 않는다.
- partial data가 허용 기준을 넘으면 해당 섹터에 누락 badge를 표시하고 게시한다.
- insufficient이면 새 latest page를 승격하지 않고 `last successful as-of`를 유지한다.

### 8.5 Coverage policy

| Status | Minimum condition | Publish behavior |
| --- | --- | --- |
| normal | 11/11 sectors + SPY, required 21D history, freshness ≤36h | full rank/regime publish |
| partial | 8~10 sectors + SPY, or optional news/earnings gaps | available sectors only; missing badges; no fake rank |
| insufficient | <8 sectors, SPY missing, or required history absent | preserve prior latest; publish operator diagnostics only |

초기 bootstrap 중 21D history가 없으면 별도 `warming_up` 상태를 사용한다. 이
기간에는 1D/5D만 보여주고 4분면/정식 순위를 숨긴다.

---

## 9. MVP and Roadmap

### Phase 0 — Data viability and product contract

- 가격/history source spike 및 공개 사용권 결정
- 11-sector universe와 지표 명세 고정
- 공개 Pages 목표 + private validation fallback 결정
- fixture 11-sector sample로 화면/상태 민감도 검토

### Phase 1 — Core sector radar MVP

- 11 sector + SPY EOD OHLCV/history
- relative-strength/acceleration regime
- 1D/5D/21D/63D table
- volume ratio, dollar volume, realized vol, max drawdown
- heatmap + 4-quadrant + detail pages
- canonical daily JSON history and coverage badge
- existing news corpus의 sector tagging과 evidence list
- LLM 없이도 완성되는 deterministic dashboard

### Phase 1.5 — Evidence narrative and web stabilization

- 상위/하위 섹터의 근거 연결 내러티브
- 당일/5일 실적 일정 pulse
- 당일 `us-equity` 시황과 상호 링크
- public source gate가 열리면 Pages에서 coverage/freshness/mobile/link 안정성 관찰

### Phase 1.75 — Telegram after web stability

- 웹 대시보드가 연속 10회 예정 실행에서 `insufficient` 없이 게시되고 같은 원인의
  실패가 반복되지 않은 뒤 시작
- 상위 2/하위 2, 상태 변화, dashboard link만 선택적으로 노출
- Telegram 실패는 웹 게시 성공을 되돌리지 않음

### Phase 2 — Flow, earnings, and attention depth

- 허용된 shares-outstanding/NAV source 기반 ETF 설정·환매 추정 flow
- SEC actual 기반 revenue/EPS YoY sector pulse
- FINRA short-sale volume 보조 지표
- Google Trends 정식 접근 가능 시 검색 관심도
- 신뢰 가능한 holdings registry 기반 constituent breadth

### Phase 3 — Retrospective and alerts

- 1주/1개월 sector rotation 회고
- 상태 전환 알림: `부진 -> 회복`, `주도 -> 둔화`
- false transition rate와 narrative 후행 검증
- 사용자 watchlist와 sector regime의 관계 표시

---

## 10. Candidate Construction Slices

아래 slice 중 source gate와 private validation은 2026-07-18에 AIDLC unit으로 등록했다.
`u138`은 기존 시황 가격 endpoint의 운영 복구이며 공개 섹터 OHLCV source gate를
대체하지 않는다.

| Slice | Scope | Depends on | Deliverable |
| --- | --- | --- | --- |
| S0 data-source spike / `u140` | price/history source, terms, GHA reachability, fixtures | none | source decision record; blocked until a source clears every public gate |
| S0-P private validation / `u139` | NAV fixture schema, regime math, local/private render contract | S0 public gate blocked | no public artifacts; validates domain/UI assumptions only |
| S1 sector domain contract | universe, models, metric/regime pure functions | S0 | deterministic snapshot contract |
| S2 sector data pipeline | selected OHLCV/history acquisition, canonical history, coverage | S0, S1 | 11-sector computed snapshot |
| S3 sector evidence layer | news/earnings tagging, evidence-bound narrative | S1 | per-sector evidence and optional narrative |
| S4 sector publisher | latest/detail pages, heatmap/quadrant/table, mobile/accessibility | S1, S2 | MkDocs dashboard |
| S5 orchestrator/ops integration | partial failure, atomic publish, nav, telemetry, alerts | S2, S3, S4 | daily production integration |
| S6 flow/fundamentals | licensed flow + SEC actual aggregation | Phase 1 stable | Phase 2 enrichment |

Public construction order after the source gate clears:

```text
S0 -> S1 -> S2 -> S4 -> S3 -> S5
                         |
                         └-> S6 after MVP observation
```

S0가 통과하기 전 S1 이후의 production unit을 등록하지 않는다.
그 전에는 `u139`만 별도 private validation unit으로 construction할 수 있다.
Application Design 결과는
[us-sector-dashboard-application-design-plan.md](us-sector-dashboard-application-design-plan.md)에 기록한다.

---

## 11. Acceptance Criteria for MVP

### Product

- [ ] 최신 화면에서 11개 고정 섹터와 SPY 기준 시각을 확인할 수 있다.
- [ ] 사용자는 상태 텍스트만으로 주도/둔화/회복/부진을 구분할 수 있다.
- [ ] 상위/하위 섹터에 원 지표와 근거 링크가 함께 보인다.
- [ ] `미국 전체`가 아닌 `S&P 500 11개 섹터 ETF 프록시` 범위가 명시된다.
- [ ] 거래량/거래대금이 실제 자금 유입으로 표시되지 않는다.

### Data integrity

- [ ] 모든 수익률·상대강도·변동성·순위는 deterministic code가 계산한다.
- [ ] 데이터가 부족한 섹터는 추정값 대신 missing reason을 표시한다.
- [ ] 가격 source와 benchmark의 as-of date가 다르면 regime 계산을 차단한다.
- [ ] 순위와 4분면은 canonical snapshot 한 개에서 렌더링된다.
- [ ] LLM narrative의 모든 공개 테마가 실제 evidence id를 참조한다.

### Reliability / operations

- [ ] 섹터 기능 실패가 기존 시황 publish를 막지 않고 pipeline `PARTIAL`로 노출된다.
- [ ] insufficient run은 마지막 정상 latest page를 덮어쓰지 않는다.
- [ ] 동일 입력 재실행은 byte-stable canonical JSON을 만든다.
- [ ] 신규 stage 포함 전체 일일 pipeline이 기존 10분 한도를 지킨다.
- [ ] GitHub Actions 로그에 sector coverage, source, duration, as-of가 남는다.

### Public surface / compliance

- [ ] 390px mobile과 desktop에서 핵심 표/타일이 겹치지 않는다.
- [ ] 색상 외 상태 텍스트/아이콘을 제공한다.
- [ ] provider raw payload와 secret이 public artifact에 포함되지 않는다.
- [ ] 데이터 사용권과 attribution 요구를 source별로 문서화한다.
- [ ] 투자 권유가 아니라 관찰형 정보라는 기존 면책 경계를 유지한다.

---

## 12. NFR Targets

| NFR | Target |
| --- | --- |
| Cost | 월 $0, 유료 API/유료 key 의존 없음 |
| Freshness | 평일 미국 장 마감 후 36시간 이내 |
| Coverage | normal 11/11, partial publish minimum 8/11 + SPY |
| Incremental runtime | sector collect/compute/publish 합계 목표 ≤2분; 전체 pipeline ≤10분 |
| Determinism | 동일 source payload와 prior snapshot이면 동일 metric/regime JSON |
| Availability | sector failure가 기존 briefing availability를 낮추지 않음 |
| Accessibility | 색상 비의존, mobile-first, 표에 텍스트 상태 제공 |
| Provenance | 모든 공개 narrative와 non-derived fact에 source/evidence 연결 |
| Security | secret/raw licensed payload/public metadata 분리 |

---

## 13. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| 기존 가격 source 0건/404/429 | dashboard 핵심 지표 불가 | S0를 mandatory gate로 두고 GHA reachability를 먼저 검증 |
| EOD 데이터 공개 재배포 조건 | public Pages 법적/계약 위험 | source 약관 확인; raw payload 비공개; 필요 시 private artifact mode |
| ETF proxy를 미국 전체 섹터로 오해 | 과도한 일반화 | 모든 표면에 S&P 500 proxy label 고정 |
| 거래량을 fund flow로 오해 | 잘못된 수급 판단 | 용어 계약과 score 제외; 실제 shares/NAV 확보 전 flow 미지원 |
| 관심도 corpus 편향 | 뉴스가 많은 source/섹터가 과대평가 | `Investo 수집 뉴스 내`, 고유 source 수, coverage badge 표시 |
| LLM 인과 환각 | 신뢰 저하 | metric 계산 금지, evidence id gate, deterministic fallback |
| 섹터 holdings drift | 뉴스/실적 오분류 | versioned registry, source date, unmatched/uncertain bucket |
| 장기 history bootstrap | 첫 21일 동안 regime 불가 | 허용된 100-bar source 또는 one-time bootstrap; warming_up 상태 |
| 파이프라인 10분 예산 초과 | 기존 시황 영향 | 별도 stage timing, bounded concurrency, cache/snapshot reuse |

---

## 14. Approved Decisions and Remaining Gate

### Approved on 2026-07-18

- 기존 Pages 공개 목표, 필요 시 private fixture/artifact 검증
- core radar 우선
- 실제 flow와 실적 actual은 Phase 2
- Telegram은 웹 안정화 후 추가

### Remaining gate, not a product-scope decision

공개 Pages에 쓸 가격 source가 아직 확정되지 않았다. 새 무료 key의 허용 여부는
제품 기능 결정이 아니라 source별 사용권·표시권·GHA 안정성 검증 결과로 결정한다.
별도 서면 권한 없이 개인용 API 데이터를 공개하지 않는다.

---

## 15. Primary Source Notes

- State Street sector ETF universe:
  <https://www.ssga.com/us/en/institutional/capabilities/equities/sector-investing/select-sector-etfs>
- State Street downloadable product data:
  <https://www.ssga.com/library-content/products/fund-data/etfs/us/spdr-product-data-us-en.xlsx>
- State Street NAV history file pattern:
  <https://www.ssga.com/library-content/products/fund-data/etfs/us/navhist-us-en-xlk.xlsx>
- State Street terms and conditions:
  <https://www.ssga.com/us/en/footer/terms-and-conditions>
- SEC EDGAR data APIs:
  <https://www.sec.gov/search-filings/edgar-application-programming-interfaces>
- SEC Form N-PORT data sets:
  <https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets>
- Nasdaq earnings calendar:
  <https://www.nasdaq.com/market-activity/earnings>
- FINRA short-sale volume:
  <https://www.finra.org/finra-data/browse-catalog/short-sale-volume>
- Alpha Vantage API documentation and limits:
  <https://www.alphavantage.co/documentation/>
  <https://www.alphavantage.co/support/>
  <https://www.alphavantage.co/terms_of_service/>
- Twelve Data personal/commercial use:
  <https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage>
- Finnhub stock candles, pricing, and registration license boundary:
  <https://finnhub.io/docs/api/stock-candles>
  <https://finnhub.io/pricing>
  <https://finnhub.io/pricing-stock-api-market-data>
  <https://finnhub.io/register>
- Alpaca market-data plan, bars contract, and redistribution boundary:
  <https://docs.alpaca.markets/us/docs/about-market-data-api>
  <https://docs.alpaca.markets/us/reference/stockbars>
  <https://alpaca.markets/support/redistribute-alpaca-api>
  <https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf>
- Financial Modeling Prep pricing, terms, authentication, and EOD contracts:
  <https://site.financialmodelingprep.com/developer/docs/pricing>
  <https://site.financialmodelingprep.com/developer/docs/terms-of-service>
  <https://site.financialmodelingprep.com/developer/docs/quickstart>
  <https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full>
  <https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-non-split-adjusted>
  <https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-dividend-adjusted>
- Tiingo EOD contract, pricing, and redistribution boundary:
  <https://www.tiingo.com/documentation/end-of-day>
  <https://www.tiingo.com/pricing>
  <https://www.tiingo.com/products/end-of-day-stock-price-data>
  <https://app.tiingo.com/tos/>
- Marketstack/APILayer EOD, pricing, and free-license boundary:
  <https://docs.apilayer.com/marketstack/docs/api-endpoints-v2>
  <https://api.swaggerhub.com/apis/apilayer-863/MarketstackAPIv2/2.0.0/swagger.json>
  <https://marketstack.com/pricing/>
  <https://www.ideracorp.com/legal/APILayer>
  <https://www.ideracorp.com/~/media/IderaInc/Files/APILayer/Apilayer%20Master%20Software%20as%20a%20Service%20Subscription%20Agreement%20SaaS%20082523ns%20FORM>
- Massive Stocks pricing, aggregates, and public-display boundary:
  <https://massive.com/pricing?product=stocks>
  <https://massive.com/docs/rest/stocks/aggregates/custom-bars>
  <https://massive.com/legal/individuals-terms-of-service>
  <https://massive.com/legal/market-data-terms-of-service>
- EODHD EOD contract, personal pricing, terms, and US data-source boundary:
  <https://eodhd.com/financial-apis/api-for-historical-data-and-volumes>
  <https://eodhd.com/pricing>
  <https://eodhd.com/financial-apis/terms-conditions>
  <https://eodhd.com/financial-apis/our-data-sources-and-data-partners>
- Tradier history, auth, personal-use, attribution, and Partner boundary:
  <https://docs.tradier.com/reference/brokerage-api-markets-get-history>
  <https://docs.tradier.com/docs/historical-data>
  <https://docs.tradier.com/docs/historical>
  <https://docs.tradier.com/docs/rate-limiting>
  <https://docs.tradier.com/docs/faq>
  <https://docs.tradier.com/docs/authentication>
  <https://docs.tradier.com/docs/attribution-guidelines>
  <https://production.tradier.com/individuals/web>
  <https://production.tradier.com/businesses/fintechs>
  <https://api.tradier.com/v2/applications/agreements?key=api_agreement>
- StockData.org EOD contract, pricing, and personal-use boundary:
  <https://www.stockdata.org/documentation>
  <https://www.stockdata.org/pricing>
  <https://www.stockdata.org/tos>
- MarketData.app candles, free limits, Internal Use, and redistribution boundary:
  <https://www.marketdata.app/docs/api/stocks/candles/>
  <https://www.marketdata.app/docs/api/authentication/>
  <https://www.marketdata.app/docs/api/rate-limiting/>
  <https://www.marketdata.app/docs/account/free-accounts/>
  <https://www.marketdata.app/pricing/>
  <https://www.marketdata.app/terms/>
  <https://www.marketdata.app/docs/account/data-policies/data-redistribution/>
  <https://www.marketdata.app/terms/commercial-use-addendum/>
- Barchart OnDemand history, trial/production pricing, and publication boundary:
  <https://www.barchart.com/ondemand/api/getHistory>
  <https://www.barchart.com/ondemand/data>
  <https://www.barchart.com/solutions/services/ondemand>
  <https://www.barchart.com/ondemand>
  <https://www.barchart.com/ondemand/faq>
  <https://www.barchart.com/solutions/legal/terms>
  <https://www.barchart.com/solutions/exchange-fees>
- Databento consolidated EOD data, metered history, expiring credits, and dataset-specific licensing:
  <https://databento.com/docs/venues-and-datasets/equs-summary>
  <https://databento.com/docs/examples/equities/closing-prices>
  <https://databento.com/docs/api-reference-historical>
  <https://databento.com/pricing>
  <https://databento.com/docs/faqs/usage-pricing-and-data-credits>
  <https://databento.com/docs/quickstart>
  <https://databento.com/docs/portal>
  <https://databento.com/docs/knowledge-base>
- Intrinio EOD historical stock prices, plan pricing, and display boundary:
  <https://docs.intrinio.com/documentation/web_api/get_security_stock_prices_v2>
  <https://intrinio.com/access-methods>
  <https://help.intrinio.com/whats-an-api-call-and-how-are-they-counted>
  <https://intrinio.com/pricing>
  <https://about.intrinio.com/terms>
- SimFin free share prices, API access, and data-license boundary:
  <https://www.simfin.com/en/prices/>
  <https://www.simfin.com/en/commercial-license/>
  <https://www.simfin.com/en/fundamental-data-download/>
  <https://github.com/SimFin/simfin>
  <https://www.simfin.com/en/technical-updates-to-api-v3-and-bulk-download/>
- Nasdaq Data Link terms:
  <https://data.nasdaq.com/terms>
- Google Trends API alpha:
  <https://developers.google.com/search/blog/2025/07/trends-api>
- Reddit Data API terms:
  <https://redditinc.com/policies/data-api-terms>

---

## Stage Closeout

- [x] Continue to Next Stage

**Next stage**: use the S0 decision record to design a bounded private core-radar validation
unit. Do not register public collection/publish construction units until a price source clears
reachability, freshness, cost, and public-use constraints.
