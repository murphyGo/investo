# S0 Decision Record: 미국 섹터 대시보드 가격·히스토리 소스

**Date**: 2026-07-18<br>
**Status**: Complete for planning — public gate blocked, private validation viable<br>
**Scope**: read-only source/terms/response spike; no production adapter or public artifact

---

## 1. Decision

현재 검증한 후보 중 **공개 GitHub Pages에 표시할 권한과 안정적인 11개 섹터 ETF
및 SPY OHLCV를 동시에 만족하는 무상 소스는 없다**.

따라서 다음 두 경로를 분리한다.

1. **Public path — blocked**
   - 기존 Pages를 최종 목표로 유지한다.
   - 공개 파생 표시 권한과 12심볼 OHLCV 안정성이 확인되기 전에는 public
     collector/publisher를 구현하거나 raw/derived market data를 게시하지 않는다.
2. **Private validation path — proceed**
   - State Street NAV History XLSX를 private fixture로 사용해 상대강도, 가속도,
     regime, NAV 기반 실현변동성·낙폭, coverage/UI 계약을 검증한다.
   - exchange volume, 거래대금, actual flow는 이 fixture에서 만들지 않는다.
   - 다운로드 원본과 계산 결과를 public archive/Pages에 넣지 않는다.

이 결정은 제품 범위를 축소하지 않는다. 공개 가능한 가격 source를 확보하면 같은
도메인 계약에 OHLCV 입력을 연결하고 Pages 경로를 연다.

### 1.1 2026-07-22 amendment — limited public sibling

u140 Step 0 iterations 1-25가 strict gate를 만족하는 후보 없이 종료된 뒤, 제품은
`u145 sector-dashboard-public-hf-limited-radar`를 별도 경로로 선택했다. 이 결정은
u140을 통과 처리하거나 위의 strict 판단을 수정하지 않는다.

유지하는 gate:
- 영구 무료 기본 사용 경로
- 공개 파생 표시와 배포를 허용하는 명시적 권리
- ≤36시간 freshness 목표와 bounded GitHub Actions 실행
- 필수 attribution, raw-payload 비보존, secret 비노출

u145에서만 완화하는 gate:
- exact 12-symbol coverage: HF catalog의 SPY + 10개 sector ETF를 사용하고 XLRE는
  `unavailable`로 표시
- consolidated-volume semantics: post-2022 OHLCV를 `IEX venue sample`로 표시하고
  IEX volume을 rank/regime/composite score에서 제외

필수 공개 계약:
- 열한 섹터 카드를 항상 렌더하고 XLRE를 대체·추정·자동 누락하지 않는다.
- 가격 기반 수익률/상대강도/가속도/실현변동성/낙폭은 IEX 샘플이라는 라벨과 함께
  제공한다.
- `거래량`, `거래강도`, `자금 유입/유출`, `미국시장 전체`라는 무수식 표현을 금지한다.
- HF Data Library CC BY 4.0 attribution과 IEX 고정 attribution을 화면 및 provenance에
  남긴다.
- 첫 valid snapshot 전 source 실패는 게시를 막고, 이후 실패는 last-good snapshot의
  원래 `as_of`를 유지한 채 stale 경고를 강제한다.

외부 prerequisite:
- HF는 다운로드/API 사용에 계정, 정확한 등록 정보, 이메일 인증을 요구한다.
- API key는 30일마다 만료된다.
- Investo는 operator-owned key 없이는 payload probe, fixture 기록, 5-run GHA 검증,
  scheduled collection을 시작하지 않는다.

---

## 2. Acceptance Gate Result

| Gate | Public Pages | Private fixture |
| --- | --- | --- |
| 11 sectors + SPY | State Street는 충족하나 공개 사용권 미충족 | **충족: 12/12** |
| 최근 21거래일 이상 | State Street NAV는 충족하나 OHLCV가 아님 | **충족: 최소 2,030행** |
| OHLCV | **미충족** | 미충족; NAV-only 계약으로 제한 |
| weekday freshness ≤36h | 단발 확인만 수행; 연속성 미검증 | 최신 `2026-07-16`, spike 시점 기준 정상 범위 |
| public derived display right | **미충족** | 적용 안 함; private evaluation only |
| GitHub Actions 5-run stability | **미검증** | production integration을 만들지 않으므로 적용 안 함 |

**S0 outcome**: public MVP construction exit gate는 실패했다. private domain/UI
validation을 시작할 최소 입력 계약은 확보했다.

---

## 3. Live Response Evidence

### 3.1 State Street NAV History

검증한 파일 패턴:

```text
https://www.ssga.com/library-content/products/fund-data/etfs/us/
navhist-us-en-{ticker-lower}.xlsx
```

2026-07-18에 `XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU,
SPY`를 병렬 요청했고 12/12가 HTTP 성공으로 내려왔다.

| Group | Rows | Latest | Earliest |
| --- | ---: | --- | --- |
| XLC | 2,030 | 2026-07-16 | 2018-06-18 |
| XLRE | 2,708 | 2026-07-16 | 2015-10-07 |
| 나머지 9개 섹터 ETF + SPY | 각 5,694 | 2026-07-16 | 2003-12-01 |

공통 열은 다음 네 개다.

```text
Date | NAV | Shares Outstanding | Total Net Assets
```

- 전체 12파일 압축 크기: 약 2.9 MB
- 12개 병렬 다운로드: 각 요청 약 0.02~0.25초(현재 로컬 네트워크 1회 측정)
- API key/auth: 없음
- 중요한 누락: open, high, low, market close, exchange volume

State Street Product Data XLSX에는 최신 closing price, high, low, exchange volume가
있지만 단일일 snapshot이다. NAV history와 합쳐도 과거 OHLCV가 되지는 않는다.

### 3.2 Existing Stooq paths

2026-07-18 live probe:

| Path | XLK result | Decision |
| --- | --- | --- |
| `q/l/?s=xlk.us&i=d&h=1&f=sd2t2ohlcv` | HTTP 404 HTML | 핵심 source 사용 금지 |
| `q/d/l/?s=xlk.us&i=d&d1=...&d2=...` | HTTP 200 JavaScript verification page, CSV 아님 | 무인 history source 사용 금지 |

저장된 2026-07 미국 시황에서도 `stooq-price 0건`이 반복된다. 5개 누락 ETF를
mapping에 추가하는 것만으로 해결되는 문제가 아니다.

### 3.3 Existing Yahoo history

현재 helper는 약 1년 daily OHLCV 계약을 이미 갖고 있지만 코드와 운영 기록 모두
GitHub Actions 공유 IP의 HTTP 429를 명시한다. 최근 저장 시황에도
`yfinance-price 0건`이 반복되어 단독 primary로 승격하지 않는다.

---

## 4. Rights and Cost Evaluation

아래 판단은 법률 자문이 아니라 공개 제품에서 보수적으로 적용하는 source gate다.

| Candidate | Access/cost | Public-use finding | Disposition |
| --- | --- | --- | --- |
| State Street downloadable files | official, structured, no-key | 사이트 정보의 복제·배포를 제한하고 database 정보를 제3자에게 publish/redistribute하지 못하게 함 | **private fixture only** |
| Alpha Vantage free | API key, 25 requests/day; 12 symbols는 요청 예산 내 | 기본 약관은 개인·비상업 용도이며 타인이 정보에 접근하는 형태를 상업 사용으로 봄 | **reject public** |
| Twelve Data individual/free | API key, individual tier | 공식 안내가 재배포와 제3자 public display를 허용하지 않음 | **reject public** |
| Nasdaq market-data APIs | credential/order-form/trial | internal-use 기본, derived data 외부 배포는 order form 또는 사전 승인 필요 | **reject no-cost public** |
| Stooq | no-key path | 현재 endpoint가 CSV 계약을 충족하지 않음 | **defer until restored** |
| Yahoo chart | no-key, unofficial runtime dependency | GHA 429와 production zero 반복; 공개 사용권도 명시적으로 확보하지 않음 | **fallback/private experiment only** |

공식 근거:

- State Street terms:
  <https://www.ssga.com/us/en/footer/terms-and-conditions>
- Alpha Vantage limits and terms:
  <https://www.alphavantage.co/support/>
  <https://www.alphavantage.co/terms_of_service/>
- Twelve Data usage guidance:
  <https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage>
- Nasdaq Data Link terms:
  <https://data.nasdaq.com/terms>

---

## 5. Private Validation Contract

### Allowed calculations

```text
nav_return_1d / 5d / 21d / 63d
nav_excess_return_vs_spy
nav_relative_acceleration_5d
regime = 주도 / 둔화 / 회복 / 부진
nav_realized_volatility_20d
nav_max_drawdown_20d
```

### Required reader labels

- `가격수익률`이 아니라 `NAV 수익률`
- `시장 거래 변동성`이 아니라 `NAV 기준 실현변동성`
- 모든 화면에 `private validation`, `실제 시장 OHLCV 아님` 표시

### Forbidden in the private prototype

- exchange volume ratio와 dollar volume
- price × volume pressure
- shares outstanding 변화로 actual flow를 미리 공개하거나 score에 합산
- private fixture 또는 그 파생 일별 값을 `archive/`나 `site_docs/`에 저장
- 기존 daily pipeline/GitHub Pages publish와 연결

---

## 6. Next Bounded Planning Slice

다음 단계는 production adapter가 아니라 **private core-radar validation unit의
Application Design**이다.

포함:

1. 12심볼 NAV fixture parser와 canonical private input schema
2. deterministic return/relative-strength/acceleration/regime pure functions
3. missing/as-of/split discontinuity 검사
4. public UI와 동일한 정보 구조를 쓰는 로컬/private render fixture
5. NAV-only label 및 volume/flow 비노출 acceptance tests

제외:

- source 원본 repository commit
- GitHub Actions secret 또는 scheduled collection
- `site_docs/`, `archive/`, MkDocs nav 변경
- Telegram
- actual flow, SEC earnings actual, constituent breadth

Public collection/publisher construction unit은 다음 증거가 생긴 뒤 별도로 등록한다.

- 공급자 또는 거래소가 public derived display를 명시적으로 허용
- 11 sectors + SPY의 63거래일 OHLCV 제공
- GitHub Actions replay-equivalent 5회 또는 실제 예정 실행 5회 성공
- 요청 예산, attribution, raw retention, cache 정책 문서화

---

## 7. Planning Closeout

- [x] Product choices recorded
- [x] 12-symbol private fixture reachability verified
- [x] Field and history depth verified
- [x] Public-use constraints checked from primary provider terms
- [x] Public and private paths separated
- [x] No production code, public artifact, secret, or paid dependency added
- [ ] Public OHLCV source gate cleared
