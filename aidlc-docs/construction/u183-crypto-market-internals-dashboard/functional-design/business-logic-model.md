# u183 크립토 시장 내부 — Business logic

작성일: 2026-10-12 · u183 · 상태: 2026-10-25 사용자 후속 “진행시켜” 지시로 설계 채택. 로컬 구현·검증을 진행하며 운영 활성화는 별도다.

## 목표와 사용자

시장 규모·USD 연동 공급·체인 TVL·BTC 거래소 파생상품을 제공자/계약/주기/조회시점에 맞게 읽을 수 있는 공개 내부 지표 화면을 만든다.

사용자: P1 운영자/개인 투자자, P2 인증 없는 공개 독자. US-013 와 FR-029/026; 기존 FR-003/011/013/018 를 구현할 후속 기준이다. 기술 단계와 public 데이터/화면/운영 수용은 구별한다.

## 책임과 선행 조건

u180 typed gate/history/receipt, u181/u182 사용자 순서 전달, u66/u74 기존 crypto indicator 의미와 u164 source-vs-query time 재사용. 소스별 public display/retention 은 activation prerequisite 이며 코드 fixture 작업의 가짜 승인으로 만들지 않는다.

구현 범위: 기존 sources/defillama_market_structure.py/coingecko_global_market.py/bybit_derivatives.py/okx_derivatives.py/alternative_fng.py 의 opt-in envelope; models/insights.py 의 crypto7slot definition; orchestrator/insights_projection.py crypto precedence/selection; publisher/insights/crypto.py; crypto/index.md 와 _data/crypto; 공통 history/filter/nav·qualification·tests.

제외 범위: crypto price/Demo 키 활성화, 추가 ETH/SOL 파생상품, 거래소별 liquidation/netflow, ETF 실제 fund flow, TVL 기반 유입 단정, 펀딩 연율·24h 평균·시장 종합 위험점수, provider 바뀐 OI 이력 연결, 새 paid/historical endpoints.

## 데이터 흐름과 행동


1. DeFiLlama 응답의 USD-linked peggedUSD 공급 합계와 chain TVL 합계를 기존 parser 와 같은 정의로 읽는다. 집계된 USD 평가액과 순자금 유입·네트워크 거래활동을 구별한다.
2. CoinGecko global 의 USD total market cap/BTC dominance 와 provider updated_at 를 읽는다. Alternative.me 의 index/timestamp 는 별도 일별 보조 카드다.
3. Bybit BTCUSDT perpetual 또는 OKX BTC-USD-SWAP funding/OI 의 provider·instrument·notional unit·response time·applicable cycle 을 원 응답에서 확인한다. funding current/indicative/settled 의미가 미확인이면 값을 카드에 쓰지 않는다.
4. u66 의 기존 선택 규칙을 바꾸지 않는다. 같은 run 의 정상 Bybit 우선, 유효한 OKX fallback; 각 metric 의 정확한 provider/instrument 를 노출한다. 응답에 없는 사실을 fallback source_name 만으로 부여하지 않는다.
5. 검증/permission 을 통과한 7slots 를 시장 규모·공급/활동 참고·파생상품 세 panel 과 보조심리로 구성한다. first current-only 표시와 source 별 상태가 기본이다.
6. 같은 provider/contract/definition/sample policy 의 D 와 D−7 기록이 있으면 7 일 관찰 변화, 최대 30 개 일별 표본 그래프를 제공한다. 원천 시각이 없는 DeFi value 는 source updated unknown·collection interval 관찰로 표시한다.


## 실패와 대체

[공통 계약](../../public-insights-20261012/contracts.md)의 C2–C7 을 적용한다. available 숫자·일정에 없는 time/period/단위/원천을 발명하지 않는다. 해당 source 실패·미확인·key 없음은 해당 card/module 의 명시된 상태와 유효 last-good 로 표현하며 정상 sibling 을 유지한다. 권리가 미확인/철회된 숫자는 current/history 에 포함하지 않는다. LLM text 또는 다른 source 의 유사 제목으로 채우지 않는다.

## 수용 시나리오

[시나리오 목록](../../public-insights-20261012/acceptance-scenarios.md)과 [실행 계획](../../plans/u183-crypto-market-internals-dashboard-code-generation-plan.md)의 numbered AC 를 함께 따른다. 현재 문서 작성은 제품 test/pass 결과가 아니다.
