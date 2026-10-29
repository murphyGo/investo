# 추가 데이터 확장 후보 연구

조사일: 2026-10-28 KST. 범위: 코인 이벤트, KRX 옵션 만기, 청산, 거래소 순유입과 인접한 무료 데이터. 사용자의 연구 요청에 따른 후보 평가이며 구현·활성화 승인은 포함하지 않는다.

## 결론

**우선 설계할 후보는 KRX 공식 규칙 기반 만기 달력과 Coin Metrics BTC·ETH 거래소 순유입이다.** 기존 DEBT-067의 “만기 규칙 공식 근거 미확보”, DEBT-072의 “무료 무키 순유입 소스 미확정”을 재검토할 직접 근거를 확보했다. 둘 다 공개 운영 자격은 별도 검증이 필요하다.

코인 일정은 Deribit 옵션 만기와 Ethereum Foundation 공지를 별개 후보로 검토한다. 시장 전체 이벤트를 포괄하는 무료 달력은 확인하지 못했다. CoinMarketCal 무료 키만 등록하면 공개 사용이 가능하다는 기존 가정은 현재 약관과 맞지 않는다.

공개 운영에 곧바로 승격할 `ship-now` 후보는 이번 연구에서 확정하지 않았다. `defer`는 설계·자격검증 가치가 있는 후보, `reject`는 현재의 무료 공개 서비스 용도에서 제외할 후보를 뜻한다. 12개 제공자/경로를 검토했고 로컬 직접 HTTP 요청은 10회였다. [검증 메타데이터](probe-summary.json)에 상태·시각·응답 해시·필드 검증을 기록했다.

## 기존 기능과 중복

| 영역 | 현재 구현 | 추가 가치 |
| --- | --- | --- |
| 예정 일정 | u35/u43의 FOMC, FRED, Nasdaq 실적, Treasury 경매 | 국내 파생 만기와 crypto 일정은 별도 공백 |
| 크립토 상태 | u66/u74의 F&G, dominance, market cap, Bybit→OKX funding/OI | 청산·거래소 흐름은 대체되지 않음 |
| DeFi | `defillama_market_structure.py`의 TVL·stablecoin supply | 공급량/TVL 변화를 거래소 순유입으로 해석할 수 없음 |
| 인사이트 | u182 일정·u183 crypto typed projection 및 공개 권한 체계 | 새 수집 성공이 공개 current/history 저장 허용을 자동으로 뜻하지 않음 |
| 기사 근거 | 현재 별도 세션의 u173/u184 작업 | EF 공지를 연결하려면 해당 evidence 계약과 조율 필요 |

## 후보별 판정

| 후보 | 무료·구조·인증 | 실측 또는 공식 근거 | 판정과 남은 조건 |
| --- | --- | --- | --- |
| KRX 공식 규칙 기반 만기 | 공식 HTML/PDF, 키 없음, 로컬 계산 가능 | 상품 HTML 200, PDF에서 휴장 조정 확인 | **defer / 최우선 설계**. 공식 휴장일·특례·적용 연도를 검증하고 계산 일정으로 표시 |
| Coin Metrics Community 순유입·활동 | 무료 무키 JSON, 일별 | BTC/ETH 유입·유출 및 활동 데이터 200 | **defer / 우선 설계**. 비상업 조건·출처·변경 표시, 잠정값 처리와 공개 이력 정책 확정 |
| Deribit 옵션 만기 | 무키 public JSON | BTC 옵션 목록 200, 880행·11개 만기 timestamp | **defer**. 일정 표시·파생값·Git 저장 권한과 GHA 경로 검증 |
| Ethereum Foundation 공지 | 무키 RSS | 200, defusedxml로 644항목 파싱 | **defer**. 본문/요약 사용 범위, 일정 변경·취소 처리 및 기존 기사 세션과 통합 |
| CoinMarketCal | 무료 키, 3천 회/월, Free는 내부 사용 | 공식 약관상 공개 표시는 Pro/Elite | **reject / 무료 공개 서비스**. 키 발급만으로 해결되지 않음 |
| CoinGecko events | 과거 무키 JSON | `/api/v3/events` 404 | **reject / 현재 경로** |
| DeFiLlama unlocks | Pro 키 경로 | 공개 `/emissions` 402, 공식 Pro 문서 | **reject / 무료 운영** |
| Bybit allLiquidation | public WebSocket, 종목별 이벤트 | 공식 문서에 500ms 전달 | **defer / 별도 상시 수집 구조 필요**. 일일 cron 조회로 24h를 복원할 수 없음 |
| Binance forceOrder | public WebSocket snapshot | 공식 COIN-M 문서에 1초 구간 최신 주문만 전달 | **reject / 누락 없는 24h 총액 대체 용도**. 관측된 표본으로는 별도 용도 가능 |
| CoinGlass | 키 필요, 가격표의 API 플랜은 유료 | Hobbyist부터 유료, 개인/상업 이용 구분 | **reject / 무료 운영** |
| CryptoQuant | Basic 무료 키에 일별 market data, on-chain은 유료 | 공식 API 페이지에 청산 포함; 가격표에 personal use | **reject / 현재 무료 공개 배포**. 개인 연구 청산 후보로는 재검증 가치; netflow는 무료 범위 아님 |
| Glassnode | Professional + API add-on | 공식 API 안내 | **reject / 무료 운영** |

## KRX 만기 달력

[공식 KOSPI 200 상품 명세](https://global.krx.co.kr/contents/GLB/02/0201/0201040202/GLB0201040202.jsp)와 [KRX 야간시장 안내서](https://global.krx.co.kr/contents/GLB/02/0201/0201041003/Guide_to_Night_Session_in_KRX_Derivatives_Market.pdf)의 인쇄 58–59쪽에서 월물·위클리 만기 규칙을 확인했다. 월물은 둘째 목요일이고 휴장이면 앞당긴다. 월요일 위클리는 휴장이면 뒤로, 목요일 위클리는 앞으로 조정한다. 월물과 겹치는 둘째 목요일 위클리는 상장하지 않는다. PDF는 2025년 안내이며 규정 우선 원칙을 명시하므로 현재 상품 안내와 함께 사용한다.

이는 DEBT-067에 적힌 “공식 규칙을 확인하지 못해 계산 방식도 불가”라는 당시 장애를 해소한다. **거래소가 배포한 일정 API를 확보했다는 뜻은 아니다.** 제한된 규칙과 검증된 휴장일로 Investo가 날짜를 계산하는 구현 제안이다.

첫 범위는 **KOSPI 200 월물 옵션 최종거래일**로 한정한다. 위클리는 휴장 조정 방향·월물 중복·예외 검증 후 확장한다. `models/market_calendar.py`의 현 휴장 목록은 2026년만 포함하므로 다른 해에 그대로 적용하면 안 된다. 연도별 공식 휴장일과 특례 근거가 없으면 해당 연도 일정은 생성하지 않는다. 최종거래일과 최종결제일도 분리한다.

후속 설계: u43 확장, 제안 source name `krx-option-expiry`, `sources/krx_option_expiry.py`, domestic-only/calendar, `scheduled_at`은 검증된 날짜·시간 정밀도만 표현. 규칙 출처, 규칙 버전, 휴장 캘린더 버전, 계산 여부를 보존한다. 검증 항목은 둘째 목요일, 연말 경계, 연속 휴장, 미지원 연도, 월물·위클리 중복, 조정 방향 및 정상 빈 일정이다. 웹페이지 전체 재게시나 매일 스크래핑은 필요하지 않은 설계다.

## Coin Metrics 거래소 순유입

Community의 [공식 카탈로그](https://community-api.coinmetrics.io/v4/catalog/asset-metrics)를 직접 조회해 32개 metric 중 `FlowInExNtv`, `FlowOutExNtv`, `FlowInExUSD`, `FlowOutExUSD`의 BTC/ETH 일별 지원을 확인했다. 같은 무키 host의 `/v4/timeseries/asset-metrics` 호출에서 2026-10-26·27 관측일, 두 자산의 네 필드를 실제 수신했다. HTTP 200, 네 행 모두 유한한 비음수 Decimal 파싱과 같은 자산·날짜의 뺄셈을 검증했다. 금액 원문은 보고서/공개 fixture에 복사하지 않았다.

카탈로그 설명상 이 흐름은 제공자가 식별한 거래소 주소를 대상으로 하고 거래소 간 이동을 제외한다. 전체 거래소의 완전한 자금 흐름이나 매수·매도 체결량으로 표시하면 안 된다. 다음 식은 **Investo 계산값**이다.

`순유입(asset, day, unit) = 유입(asset, day, unit) - 유출(asset, day, unit)`

BTC/ETH native 단위를 합산하지 않으며 한쪽 값 누락은 0으로 대체하지 않는다. 일별 관측을 실시간 또는 임의의 최근 24시간으로 표시하지 않는다. 이번 응답의 모든 flow 필드에는 `status=flash`와 별도 `status-time`이 있었다. 따라서 확정값으로 게시해서는 안 되며 잠정 표시/공개 억제 정책을 설계해야 한다. 수집 시각, 관측일, 상태 갱신 시각을 구분하고, 공급자 수정으로 과거값이 변할 때 이력 처리도 고정해야 한다. [공식 API 문서](https://docs.coinmetrics.io/api/v4/)는 reviewable metric과 `flash/reviewed/revised` 상태를 다룬다.

비용·사용 조건: [공식 Community 안내](https://github.com/coinmetrics/product-docs/blob/master/docs/access-our-data/api/README.md)는 무키·비상업적 사용을 설명하고, [공식 데이터 저장소](https://github.com/coinmetrics/data)는 CC BY-NC 4.0을 명시한다. 상업용 표시권을 추론하지 않는다. Investo의 공개 사이트/Telegram/Git 이력에 적용할 비상업성·출처·라이선스 링크·변경 표시를 자격 문서에 고정한 후 공개한다. Community 안내의 rate limit은 10회/6초이며 일일 한 번의 BTC/ETH batch 요청으로 설계할 수 있다. 현재 공개 데이터 안내는 [Talos Community 페이지](https://www.talos.com/our-solutions/data/community-resources)로 이동한다.

이 결과로 DEBT-072의 남은 장애는 “무료 소스 발견”에서 **사용 조건과 잠정값·시간·공개 이력 자격검증**으로 좁혀진다. 접근 성공 1회를 운영 안정성 증거로 세지 않는다. 비용/의미 제약 때문에 기존 CryptoQuant·Glassnode 평가를 뒤집는 것도 아니다.

후속 설계: 제안 `coinmetrics-exchange-flows` / `sources/coinmetrics_exchange_flows.py`, crypto-only/macro. 첫 범위는 BTC/ETH의 native 유입·유출과 계산 순유입으로 제한한다. `AdrActCnt`, `TxCnt`, `FeeTotNtv`도 실제 200으로 확인했지만 별도 추가 지표로 취급한다. 무료 범위 변경, 빈 값, mismatched day, 잠정/수정 상태, 429/timeout, 잘못된 Decimal, 제공자 라벨 변경을 검증한다. API 키나 자동 유료 fallback은 필요 없다.

## 코인 일정의 두 가지 대안

**Deribit 옵션 만기:** [현재 공식 API](https://docs.deribit.com/api-reference/market-data/public-get_instruments)는 `expiration_timestamp`, `kind`, `state`, 통화 필드를 제공하며 약 1분 cache, 1회/초 제한을 설명한다. 실측은 BTC-settled 옵션에 한정했다. `currency`는 derivatives의 settlement 통화 기준이므로 BTC 기초자산 전체를 조회했다고 주장하면 안 된다. 기본 목록에 거래 불가능 상태도 포함될 수 있어 future expiry와 상태를 함께 필터링한다. 행사가·콜/풋별 880행을 만기별로 중복 제거해야 한다. 11개 timestamp는 검증 전 후보 개수다. OI나 청산·가격 영향은 이 목록에서 계산하지 않는다. 공개 표시/보관 권한은 [API usage policy](https://docs.deribit.com/articles/api-usage-policy)만으로 확정하지 못했으며, 공개 자격검증을 남긴다.

**Ethereum Foundation 공지:** [공식 RSS](https://blog.ethereum.org/en/feed.xml)는 무키 XML이며 실제 파싱에 성공했다. `pubDate`는 글 발행일이고 upgrade 시행일과 다르다. 최신 공지를 통한 연기·취소 처리도 필수다. 실제 [2026-10-22 Hoodi 연기 공지](https://blog.ethereum.org/2026/10/22/glamsterdam-hoodi-delay)는 앞서 제시한 10월 26일 일정을 철회하고 새 날짜가 없다고 명시한다. 테스트넷 사건을 메인넷 일정으로 바꾸거나 과거 공지만 보고 예정일을 계속 표시해서는 안 된다. 첫 단계는 crypto 공식 뉴스 근거 수집, 일정 승격은 명시된 시행일·network·후속 정정 연결이 검증된 건에 한정한다. blog 콘텐츠 라이선스는 별도 확인이 필요하며 다른 ethereum 사이트의 라이선스를 전용하지 않는다.

이 둘은 각각 거래소 파생 일정과 특정 프로토콜 공지다. 토큰 언락·상장·모든 코인의 업그레이드를 포괄하는 달력을 대체하지 않는다.

## 청산 및 제외 후보의 근거

- [Bybit 공식 allLiquidation](https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation)은 500ms 스트림이다. 문서상 `S=Buy`는 long 청산이고 `p`는 bankruptcy price다. 일반 주문 방향이나 체결가로 오독하지 않는다. 재연결·누락 구간·저장·중복·단위 검증을 갖춘 상시 collector가 필요하며 현재 일일 실행에 몇 초 구독을 추가해서 24h 총액을 만들 수 없다. 실제 스트림/24h 수집 검증은 하지 않았다.
- [Binance 공식 COIN-M 스트림 문서](https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-coin-m-futures/api/ws-streams)는 1초 구간 최신 청산 snapshot만 전달한다고 명시한다. 전 이벤트 합계로 사용하기에 불충분하다. 다른 상품 API에 이 결론을 무조건 확장하지 않는다.
- [CryptoQuant API 안내](https://www.cryptoquant.com/apis)는 Basic 무료 market data에 일별 청산이 포함되고, on-chain은 Professional 이상이라고 설명한다. [가격표](https://www.cryptoquant.com/pricing)의 개인 사용 조건 때문에 공개 Investo용 무료 대안으로 승격하지 않았다. 키·API 실측·거래소별 범위·일별 기준도 미검증이다.
- [CoinGlass 가격표](https://www.coinglass.com/pricing)는 유료 API 플랜, [Glassnode API 안내](https://docs.glassnode.com/basic-api/api)는 Professional 및 API add-on을 요구한다.
- [CoinMarketCal 약관](https://coinmarketcal.com/api-terms-of-service)은 Free/Standard를 내부 사용으로 제한하고 Pro/Elite에 공개 표시를 부여한다. [무료 플랜](https://coinmarketcal.com/developer)은 7일 전망·상위 100코인·24시간 지연·출처 필드 미제공이며 [rate limit](https://coinmarketcal.com/developer/docs/rate-limits)은 3천 회/월·1회/초다. 무료 키 등록만을 DEBT-067 해결 조건으로 둘 수 없다.
- CoinGecko 기존 events는 직접 조회 404였다. [DeFiLlama 공식 Pro 문서](https://github.com/DefiLlama/api-docs/blob/main/llms-pro.txt)는 emissions를 Pro 경로에 두며 공개 주소 직접 조회도 402였다. 기존 TVL 수집 경로의 무료 여부와 구분한다.

## 후속 작업 경계

1. **KRX 월물 만기:** u43의 기존 공백을 재개한다. 공식 휴장일/규칙 버전과 날짜 계산 Functional Design을 먼저 작성한다.
2. **Coin Metrics 순유입:** DEBT-072 해결 후보로 제한된 source qualification 및 FD/NFR을 작성한다. 무료 API·비상업 라이선스·잠정값·수정 이력·공개 표시를 하나의 계약으로 다룬다.
3. **Deribit 만기:** 공개 사용 범위를 확인한 뒤 crypto 일정용 adapter를 설계한다.
4. **EF 공지:** u173/u184 담당 세션의 공식 근거 범위와 중복 대조 후 추가한다.
5. **24h 청산:** 현 일일 cron 구조에서는 우선순위를 낮춘다. 상시 collector는 별도 운영비·저장·복구 설계를 요구한다.

모든 신규 adapter는 `sources/__init__.py` 등록, `_internal/source_specs.py`의 tier·window·item/outcome routing, `sources/_registry.py` plugin 계약, `sources/tiers.py` 파생 값, `sources/aggregator.py` 실패 진단을 대조한다. 일정 소스는 `briefing/segments.py::LOOKAHEAD_AWARE_SOURCES`와 필터/빈 일정 진단을 함께 등록한다. u182/u183 dashboard 연결은 별도 typed model·projection·공개 권한 정의를 추가해야 한다. 기존 source registry를 복제하지 않는다.

수용 검증은 `test_registry.py`, `test_plugin_contract.py`, `test_source_specs.py`, `test_tiers.py`, 후보별 record/replay·오류 fixtures, `scripts/check_no_paid_apis.py`로 연결한다. 수집기 구현만으로 debt나 운영 인수를 완료 처리하지 않는다. 로컬 소스 응답은 GHA 접근성·예약 운영 관찰을 대신하지 않는다.

## 검증 및 변경 범위

로컬 직접 HTTP 10회 중 7회 200, 1회 400(카탈로그에 지원하지 않는 `assets` 파라미터를 넣은 조사 오류), 1회 402, 1회 404. 카탈로그는 파라미터를 제거한 공식 경로로 재조회해 200과 metric별 자산 지원을 확인했다. 원 응답은 `.tmp/data-expansion-research-20261028/`에만 저장했고 본 폴더에는 값이 아닌 검증 메타데이터를 남겼다. 문서 조사 요청은 이 10회와 별도다.

연구 문서와 메타데이터만 추가했다. 유닛 번호 등록·기술 부채 상태 변경·production 코드·배포는 수행하지 않았다. 별도 세션에서 변경 중인 state/audit/TECH-DEBT와 구현 파일은 이 연구에서 편집하지 않았다. 새 문서 링크·JSON·공백·placeholder를 확인하며, 사이트에 포함되지 않는 AIDLC 연구 자료이므로 MkDocs나 전체 pytest를 실행할 필요는 없다.
