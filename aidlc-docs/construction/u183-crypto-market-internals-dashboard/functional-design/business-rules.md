# u183 Business rules

작성일: 2026-10-12 · u183 · 상태: 2026-10-25 사용자 후속 “진행시켜” 지시로 설계 채택. 로컬 구현·검증을 진행하며 운영 활성화는 별도다.

- R183.1:crypto slots=btc_dominance/market_cap_usd/usd_stablecoin_supply/chain_tvl_sum/btc_funding/btc_oi_usd/fear_greed_index. marketcap/supply/TVL/OI finite≥0, dominance/FNG0..100, FNG integer. funding 은 finite fraction 이며 percent 표시는×100.
- R183.2:USD-linked stablecoin 공급만 peggedUSD 로 합산하고 다른 peg currency 를 USD 처럼 처리하지 않는다. TVL 합계는 chain coverage/중복·평가가격 영향을 명시한다. 증가를 netflow 로 주장 0.
- R183.3:funding basis 는 indicative_for_cycle 또는 source-confirmed_settled, applied cycle start/end·instrument 를 가진다. fundingTime/nextFundingTime 만 지나갔다고 settled 로 변경 0. 주기 길이는 8h 로 고정하지 않음.
- R183.4:OI 는 USD notional 이며 native contracts/coinOI 와 단위가 다르다. provider/instrument/sourceUpdated/collectionClock 를 표시한다. Bybit 와 OKX 값을 합산하거나 전체시장 OI 라고 표시 0.
- R183.5:provider response ts 와 market observation timestamp 는 다른 역할일 수 있다. 응답 clock 이라고 source 가 정의한 ts 는 source_response 로 표시한다. synthetic window.end_utc·now_utc 는 실제 sourceUpdated 가 아니다.
- R183.6:기존 Bybit fallback 중복 응답은 same provider/instrument/metric/timestamp/value 가 모두 같은 경우만 dedupe. 다른 sample 은 선택 정책에 따라 현재값 하나를 택하며 합계 0.
- R183.7:definition_id 에 instrument/provider/aggregation/sample/funding_basis 를 넣는다. 변경 전후 이력·7 일변화 연결 0. retained raw 또는 새로운 historical endpoint 로 빈 구간 복구 0.
- R183.8:public display 미확인 card 는 unavailable 이며 scope/정밀도 정의가 미확인인 숫자를 예쁜 UI 로 정상 처리하지 않는다. Fear & Greed 는 제공자 index 로 표시하고 자체 위험 등급화 0.

[공통 C1–C7](../../public-insights-20261012/contracts.md)이 숫자·시간·권리·상태·보관·게시의 기본 계약이다. 여기서 정의한 source/metric/event 의미를 다른 module 에서 재정의하지 않는다. 충돌하는 raw metadata 는 검증 실패이며 임의 보정을 하지 않는다.
