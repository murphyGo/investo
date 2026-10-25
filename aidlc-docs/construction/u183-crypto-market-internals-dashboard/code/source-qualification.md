# u183 원천·권리·시간 매핑

2026-10-25 · source5개, metric7slot/9definition(파생2개는Bybit·OKX별 정의). 원천 응답·실제 운영·재배포 허용을 구별한다.

| 제공자 | typed field/의미 | clock·범위 | 공개 Git/분석 이력 |
| --- | --- | --- | --- |
| CoinGecko global | data.market_cap_percentage.btc %, total_market_cap.usd | data.updated_at. 제공자 추적 자산 범위이며 누락 시 unknown; window.end를 원천 갱신시각으로 쓰지 않음 |2정의 차단. 공개 current JSON·Git 영구 보관/재배포 범위 미확인 |
| DeFiLlama | named positive row의 circulating.peggedUSD 공급단위 합, chains.tvl 합 | 원천 update timestamp가 없으므로 실제 기존 HTTP 요청의 start/end 수집구간. legacy published_at/window와 별개 |2정의 차단. 공개 API 응답 접근을 데이터 재배포/영구 Git 보관 허용으로 확대하지 않음 |
| Bybit linear BTCUSDT | fundingRate fraction, openInterestValue USD명목 | response.time; intervalHour와 nextFundingTime으로 확인한 적용 구간. current indicative만, 임의8h 고정0 |2정의 차단. API/Service Data 재포장·재배포 범위 확인 전 |
| OKX BTC-USD-SWAP | fundingRate fraction/current_period, oiUsd USD명목 | response ts. prevFundingTime~fundingTime을 nextFundingTime 차이와 대조해 일치할 때만 current cycle. 부족/변경이면funding만 억제. settState=settled라도fundingRate를settFundingRate로 바꾸지 않음 |2정의 차단. public endpoint도 제3자 display/redistribution 제한 적용 |
| Alternative.me | integer0..100 Fear & Greed index, provider timestamp | BTC 중심 제공자 지수. 자체 위험등급/매매판단 생성0 |1정의 허용. 값 직후·이력표 앞·그래프 앞 source notice, JSON definition attribution. 동일 지표 서비스로 위장하지 않음 |

정의별 기본 permission은 **1allow/8blocked**다. 허용된 분석 이력은 FNG만이다. blocked 지표의 원 응답 숫자는 current/history/HTML에 넣지 않는다. 로컬 전체7카드와 이력 QA는 example.invalid 허용 증거가 붙은 합성 fixture이며 실제 권리 승인으로 쓰지 않는다.

## 근거와 해석

- [Alternative.me API rules](https://alternative.me/crypto/fear-and-greed-index/)의 전체 Fear & Greed data에 대한 출처 표기·인접 attribution 조건을 적용한다. 원천을 흉내내는 서비스가 아니며 current·lazy history·JSON 모두 출처를 보존한다.
- [CoinGecko API terms](https://www.coingecko.com/en/api_terms), [라이선스 구분](https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses). 화면 표시와 별도의 raw/current JSON 및 영구 Git 재배포 권한이 같다고 추론하지 않는다.
- [DeFiLlama terms](https://enterprise.defillama.com/terms). 공개 API/오픈 코드 라이선스를 데이터 전체의 재배포 허가로 확대하지 않는 보수적 판정이다.
- [Bybit API terms](https://www.bybit.com/en/help-center/article/API-Terms), [tickers schema](https://bybit-exchange.github.io/docs/v5/market/tickers). clock은 market observation이 아닌 provider response로 표시한다.
- [OKX API agreement](https://www.okx.com/help/okx-api-agreement), [공식 public API schema](https://www.okx.com/docs-v5/en/). fundingRate는 current forecast이며 마지막 정산율은 별도 필드다. source docs의 cycle 차이와 실제 previous boundary를 함께 검사하는 제한적 구현이다.

DeFi positive/named row 선택과 기존 legacy title/metadata는 유지한다. 새 Decimal decode로 원 숫자 자릿수를 유지하며 TVL/공급을 netflow로 부르지 않는다. 다른 peg currency를USD로 바꾸거나 coin/contracts OI를가격으로USD 변환하지 않는다. row중복/상한/수치 실패는typed value만억제한다.

모든7기존 endpoint의 개발 조회는HTTP200이었다. 실제 응답을offline adapter replay해2+2+2+2+1typed metric을 확인했다. 원body는/private/tmp에만 두고 새 rawfixture를공개repo에복사하지 않았다. [response hash와요청수](source-probes.json). GHA/IP 접근, production collector admission/Pages/5회 scheduled의 증거는 아니다. 기존 Demo/key/source/fallback/runtime 설정은 변경하지 않았다.
