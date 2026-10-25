# 소스 범위와 qualification 판정

2026-10-12 origin/main 과 현재 primary 문서 대조. 2026-10-11 의 HTTP/coverage 관측은 날짜를 보존한 참고 자료다. 이 문서는 운영 permission manifest 나 신규 activation 승인이 아니다.

| 소스 / 원천 경로 | 사용 범위 | access·auth·cadence | 현재 판정 / 구현 조건 |
| --- | --- | --- | --- |
| Treasury / 기존 `treasury_rates.py` XML endpoint | 3M/2Y/10Y/30Y 와 두 스프레드 | 공개 XML, no-key, 일별 | 기존 조회 재사용. 공식 field/source-date·공개 표시 근거·fixture 를 실행계획 Step1 에서 고정 |
| NY Fed / 기존 `nyfed_reference_rates.py` `/api/rates/.../last/1.json` | SOFR/EFFR, 동일 effective date spread | no-key REST, 미국 금융 영업일 | 공개 배포 고지 조건이 문서화됨. 정확한 고지/정의와 runtime 검증 후 allow |
| BLS / 기존 `bls_macro_actuals.py` | CUSR0000SA0/CUSR0000SA0L1E 의 SA index, LNS14000000 의 percent | 기존 공개 JSON, no-key, 월별 | 공식 unit/SA/period 를 그대로 사용. CPI YoY·NFP 신규 증감값 생성 제외 |
| FRED / 기존 `fred_fx_close.py`, DEXKOUS | KRW/USD H.10 관측값 | 기존 FRED_API_KEY optional path; daily 관측, weekly 공표 | H.10 관측을 거래소 종가로 표현하지 않음. 원천/series 권리·주간 공표·FRED 고지 확인 후 현재값/허용 이력만 allow |
| Fed / 기존 `fomc_calendar.py`, calendar.json | FOMC·minutes·공식 주요 중앙은행 일정 | no-key JSON, 일정 변경시 | source date range 유지. feed 의 synthetic scheduled_at 를 exact time 으로 승격하지 않음 |
| FRED / 기존 `fred_economic_calendar.py`, release/dates | 고정 10 release ID 의 원천 현지 날짜 | FRED_API_KEY, 일정 변경시 | date-only. 실제 announcement timestamp·발표 완료 추론 금지 |
| BEA / 기존 `us_economic_calendar.py` | GDP/PCE 공식 날짜·parse 된 ET 시간 | no-key 기존 페이지 parser | 기존 접근만 재사용. 정확한 parse/timezone fixture 와 허용 field/source link 대조 |
| Fiscal Data / 기존 `treasury_auctions.py` | coupon 입찰 날짜·term/CUSIP | no-key structured endpoint, 일정 변경시 | date-only. 11:30/13:00 관행 시각을 값으로 넣지 않음 |
| DeFiLlama / 기존 chains·stablecoins | 체인 TVL 합계와 USD 연동 공급 | no-key JSON, 조회시점 | 무료 접근과 소스별 derived display/retention 을 구별. 공개 조건 미확인 카드 blocked. 상위체인 세부값은 첫 범위 밖 |
| CoinGecko global / 기존 `coingecko_global_market.py` | BTC dominance/total_market_cap.usd | 기존 global JSON, source updated_at | api/attribution·재배포/보관 조건 검증 후 선택 카드. price/Demo 활성화는 u164 owner |
| Bybit / 기존 `bybit_derivatives.py` | BTCUSDT perpetual funding/OI | no-key public ticker, 조회시점 | 계약·주기·response time·USD 환산을 기존 응답에서 검증. permission 미확인 blocked |
| OKX / 기존 `okx_derivatives.py` | BTC-USD-SWAP funding/OI | no-key public API, 조회시점 | ts/fundingTime/settlement 의미와 oiUsd 검증. Bybit 와 source 가 달라지면 역사 비교 단절 |
| Alternative.me / 기존 `alternative_fng.py` | FNG 0–100 일별 index | no-key JSON, daily source timestamp | 보조 카드. attribution·공개 표시와 보관 조건 확인 전 blocked |

원천 주소는 기존 adapter 에 선언된 literal endpoint 로 한정하며 source-specific parser 는 sources 안에 둔다. 신규 source_name, registry import, SourceSpec, tier, market window, segment allow-list, 추가 key 를 이번 네 유닛에 등록하지 않는다. envelopes 의 opt-in metadata 필드는 source routing 이 아니다.

## Primary references

- [Treasury XML feed](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed).
- [NY Fed API](https://markets.newyorkfed.org/static/docs/markets-api.html), [배포 고지 조건](https://www.newyorkfed.org/privacy/termsofuse.html). 일반 면책과 reference-rate 배포 고지는 별개다.
- [BLS copyright](https://www.bls.gov/opub/copyright-information.htm), [BLS API](https://www.bls.gov/developers/).
- [FRED terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html). API 접근은 third-party series 권리를 대체하지 않는다. 비보증 고지·사용 조건 링크를 지키며 키 값/요청 URL query 를 공개하지 않는다.
- [FOMC official calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm), [BEA schedule](https://www.bea.gov/news/schedule).
- [DeFiLlama API](https://api-docs.defillama.com/), [free/paid 범위](https://defillama.com/subscription).
- [OKX API fields 변경 안내](https://www.okx.com/docs-v5/log_en/), [CoinGecko API terms](https://www.coingecko.com/en/api_terms), [Alternative.me API](https://alternative.me/crypto/fear-and-greed-index/).

소스별 정확한 rate limit 을 이번 조회로 전부 새로 확정했다고 표시하지 않는다. 추가 request=0 이며 기존 client/retry/60 초 adapter 상한을 유지한다. 기존 소스에서도 새 운영 HTTP 경로를 추가하면 unit 범위 변경과 fixture·rights·cost·limit 자격검증이 필요하다.

현재 snapshot도 공개 Git 이력에 남으므로 display_allowed와 별도로 public_git_history_allowed가 확인돼야 숫자를 게시한다. 파일의 rolling retention 상한은 Git 과거 commit의 영구 보관을 제한하지 않는다. 단순 display-only/TTL-only 조건의 소스는 이번 정적 Git 게시 경로에서 blocked다.

## Defer / reject

BLS ICS 는 공식 structured 보강 후보지만 이번엔 신규 adapter 로 추가하지 않는다. [공식 안내](https://www.bls.gov/help/hlpiCAL.htm)가 제공하는 endpoint 의 실제 fixture 와 등록/routing 계획을 별도 source unit 에서 수행한다. Nasdaq earnings 의 신규 공개 재배포, 더 넓은 FRED third-party series, CoinGecko historical API 도 첫 범위에서 defer 다.

지표값을 title/뉴스 prose 에서 추출하는 화면, synthetic midnight 를 exact clock 으로 표시하는 방법, 거래량으로 fund flow 를 만드는 방법, 유료 liquidation/netflow 또는 surprise API 의존은 reject 다. DEBT-071/072 는 그대로 둔다.

DEBT-079 의 과거 설명과 현재 코드를 구별한다. 현재 FRED calendar 는 `us:PPI:period=...` 같은 explicit macro_event_key 를 만들고 BLS actual 도 같은 형식을 사용한다. 이 관측만으로 모든 release/quarter/revision join 과 carryover debt 가 해결됐다고 선언하지 않는다. u182 첫 버전은 actual join 을 하지 않으므로 이 debt 를 필수 repair 로 등록하지 않는다.
