# u183 Domain entities

작성일: 2026-10-12 · u183 · 상태: 2026-10-25 사용자 후속 “진행시켜” 지시로 설계 채택. 로컬 구현·검증을 진행하며 운영 활성화는 별도다.

| Entity | 필드/관계 | 불변 조건 |
| --- | --- | --- |
| CryptoMetricDefinition | metric_id, provider/aggregation, scope/instrument, unit, sample_policy | 7slot; 정의 변경은 다른 이력 series |
| FundingObservation | fraction, funding_basis, applicable cycle, source response/collection time | source-confirmed settled 와 indicative 구별, 연율/24h 평균 생성 0 |
| OpenInterestObservation | USDnotional, provider, instrument, time basis | 거래소·계약별 snapshot; global aggregate 아님 |
| CryptoPanelView | market size, supply/TVL, derivatives, optional FNG | 같은 수집 run 이 같은 원천시간을 뜻하지 않음 |
| DailyCollectionSample | UTC day, confirmed capture window, compatible definition | 해당 날 마지막 published sample; 일봉 close/avg 아님 |

공유 DTO 선언은 `src/investo/models/insights.py`와 공통 foundation 이 소유한다. source envelope → validated module → public manifest/receipt 관계는 [C1–C6](../../public-insights-20261012/contracts.md)에 고정한다. serializer 의 기본 bytes, Decimal/clock/기간·closed enum 검증을 유지한다. public writer 는 source raw item 이나 LLM draft 를 받지 않는다.
