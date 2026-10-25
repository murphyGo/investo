# u183 independent code review — initial

작성일: 2026-10-25. 별도 reviewer. 현재 확인한 미해결 **Critical 0 / High 0 / Medium 0**.

## 범위와 검토 방법

기존 code-review skill 및 protocol INDEX의 security-boundary/data-integrity/error-contract/memory/performance/resource-lifecycle/concurrency 관점을 해당 추가분에 적용했다. u183 FD business logic/rules, focused NFR, code-generation plan과 공통 C1–C7을 기준으로 검토했다. 동일 작업의 u180/u181/u182 전체를 다시 전수 검토한 것은 아니다.

검토한 u183 추가분:

- models/insights_crypto.py의7 slots/9 definitions, funding interval identity, bounded Decimal/exact 연산.
- models/insights.py의 applicable cycle, compact history clock, superseded_from, crypto coverage, None 생략을 통한 기존 canonical 보존.
- 기존5 crypto adapter의 동일 응답 opt-in envelope 변경과 DeFi 수집구간/원 JSON Decimal 재해석.
- orchestrator/crypto_insights.py 선택·중복·conflict·provider precedence·slot/source coverage, insights_projection.py의 typed gates/last-good/UTC collection day/history replacement·revision 분기.
- publisher/insights/crypto.py, store renderer/caps, 공용 lazy history reader, CSS/nav/hub 및 qualification9개/관련 tests·synthetic helpers.

초기 scope를 읽은 뒤 lead가 추가한 source별 clock-role negative gate와 공용 lazy reader의 표/그래프 인접 attribution 표시도 좁게 다시 읽었다. 자동화 전체 suite/static/browser/live source 실행은 lead 제공 증거와 reviewer 직접 실행을 아래에서 구분한다.

## Findings

재현 또는 코드 경로로 확정한 Critical/High/Medium finding은 없다. 확인하지 않은 가능성을 결함으로 등록하지 않았다. 아래 확인은 코드 수용 경계이며 production activation이나 실제 권리 허가를 의미하지 않는다.

## 확인한 correctness 경계

### 원천·숫자·시각

CoinGecko는 원 응답의 updated_at과 Decimal token을 사용한다. DeFi는 실제 요청 시작/응답 완료 구간을 사용하며 기존 window.end_utc를 sourceUpdated로 표시하지 않는다. 집계는 기존 positive/named-row 조건과 peggedUSD 범위를 유지하고 별도 precise decode의 Decimal을 precision256으로 합산한다. duplicate chain/asset identity와 bound 밖 숫자는 공개 집계로 정상화하지 않는다.

Bybit는 BTCUSDT/linear를 검증하고 source response time, fundingIntervalHour, nextFundingTime으로 명시 cycle을 결속한다. OKX는 BTC-USD-SWAP/SWAP 및 current_period를 검증하고 명시된 이전/현재/다음 경계를 대조하며, cycle 정보가 없거나 서로 다르면 funding만 억제한다. 둘 다 OI USD notional을 coin/contract 수량으로부터 만들어내지 않는다. current fundingRate를 settState 또는 시간 경과만으로 settled 값으로 바꾸지 않는다.

공식 문서의 funding interval/nextFundingTime 및 funding 예측값과 settled 값의 구별·ts 역할을 대조했다. [Bybit tickers 문서](https://bybit-exchange.github.io/docs/v5/market/tickers), [OKX API guide](https://my.okx.com/docs-v5/). 이 대조는 문서 의미에 한정하며 API 재배포 권리를 승인한 것이 아니다.

최신 validation gate는 DeFi의 collection_window/source_updated_at=None, CoinGecko의 source_response 및 exact_at=source_updated_at, Bybit/OKX의 response clock/source_updated_at=None, Alternative.me의 지수 기준 timestamp 역할을 고정한다. source clock을 다른 clock 역할로 재명명한 negative 회귀를 직접 실행했다.

### 선택·이력·권리

같은 metric/provider 안에서 최신 source stamp를 선택하고 동일 시점의 완전히 같은 typed sample만 dedupe한다. origin은 운영 provenance로 따로 유지한다. 정상 Bybit 우선/유효 OKX fallback을 보존하며 standalone OKX 실패가 Bybit 경유 정상 OKX 관찰을 덮지 않는다. 같은 provider의 conflicting 최신 sample은 제외하고 유효 fallback으로 대체하거나 unavailable로 둔다.

funding duration/provider/instrument/definition/sample policy가 비교 키에 결속된다. crypto sample key는 source timestamp의 날짜 대신 UTC collection day이며, 같은 날 마지막 원격 확인 표본이라는 표시와 일치한다. 다른 clock의 당일 sample 교체는 superseded_from, 같은 clock의 값 수정은 revised_from으로 구별한다. last-good는 원 시각을 유지하고 새 이력/변화를 만들지 않는다. exact D/D-7가 없거나 provider/contract/interval이 달라지면 비교·이력 연결을 억제한다.

qualification9개 중 Alternative.me1개만 display/public-Git/retention이 허용되고 나머지8개는 차단되는 회귀를 실행했다. source runtime 성공과 권리 허가는 별도 축이며, fixture의 synthetic permission은 실제 source 권리 근거가 아니다. 권리 철회 시 current/last-good/history도 제거된다.

### 공개 출력·자원·호환

7 current slots는 JS 없이 읽을 수 있고 제공자/계약/단위/시각/주기·slot/source 상태를 구별한다. funding fraction×100 표시는 해당 cycle의 percent이며 연율·24h 평균·settled로 확대하지 않는다. 공급/TVL/OI/지수를 netflow·전체 시장 OI·자체 위험 등급으로 바꾸지 않는다.

lazy reader는 사용자 클릭 뒤 same-origin manifest 및 snapshot/current hash와 history SHA256을 대조하고, 같은 comparison identity의 최대30 rows만 생성한다. 정확한 원 Decimal 문자열 표와 optional Number 기반 SVG를 구별한다. DOM textContent/escape를 사용하고 optional SVG 실패에도 exact table을 유지한다. 당일 교체/같은 시점 수정, 원천 clock·funding cycle이 이력 표에 표시된다. 최신 JS에서 definition attribution이 표와 그래프 앞에 각각 인접하게 표시되는 것도 확인했다. 실제 attribution 조항 전체의 법적 수용과 구별한다.

current256KiB/history4MiB/private aggregate512KiB 및 crypto HTML100KiB/asset gzip20KiB gate를 읽고 관련 시험을 실행했다. 신규 clock/coverage/superseded 필드가 없으면 serializer가 생략하여 기존 v1 canonical을 유지하도록 구성되었다. 실제 최대 RSS/CPU/wall resource benchmark를 reviewer가 새로 실행한 것은 아니다.

source diff는 기존 requests/fallback/key 경로·off serialization을 보존한다. 새 SDK/LLM/Telegram/paid API 또는 source workflow는 없다. raw market body를 새 공개 fixture로 복사하는 작업도 reviewer 범위에서 수행하지 않았다. 공통 publisher/disclaimer/receipt 경계를 재사용하며 scoped publication과 세 모듈 coexistence의 local bare-Git integration을 실행했다.

## reviewer 직접 실행한 검증

처음 동일4개 test 파일을 실행하여 46 passed in 4.62s를 확인했다. clock-role 보강 뒤 다시 실행한 최종 결과는 다음과 같다.

```text
.venv/bin/python -m pytest tests/unit/orchestrator/test_crypto_insights_projection_u183.py tests/unit/publisher/test_crypto_insights_render_u183.py tests/unit/sources/test_crypto_insights_envelopes_u183.py tests/integration/test_crypto_insights_site_u183.py -q
47 passed in 4.89s
```

해당 실행은 synthetic/기존 recording offline replay와 임시 로컬 bare remote를 사용한다. source5종 on/off legacy JSON bytes·요청 수 parity와 Bybit→OKX fallback, Decimal/cycle negative, provider 우선순위/충돌·freshness/last-good·history/권리·caps·lazy HTML 구성 및 실제 로컬 원격 receipt 회귀가 포함된다.

이후 lead가 추가한 lazy attribution 두 곳은 read-only로 확인했다. 그 마지막 JS 보강 뒤 browser suite나 pytest를 reviewer가 별도 재실행했다고 주장하지 않는다.

## 검증하지 않은 운영 경계

lead가 전달한 실제7endpoint HTTP200/body typed9, source-probes와 runtime_probe_state, broader Ruff/format/mypy328/full4shard, UI16cases/lazy56rows/hash-snapshot negative는 lead의 별도 실행 증거다. reviewer는 이를 직접 실행한 것으로 계산하지 않는다.

실제 source의 법적 재배포 허가·production 활성화·private runtime pin·Pages/live identity·5회 scheduled observation 및 독립 browser viewport 수용은 이 보고서로 완료되지 않는다. reviewer는 source/test 수정, commit/push/activation을 하지 않았으며 이 보고서만 작성했다.
