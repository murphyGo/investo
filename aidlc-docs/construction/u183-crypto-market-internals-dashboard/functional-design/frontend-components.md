# u183 Frontend components

작성일: 2026-10-12 · u183 · 상태: 2026-10-25 사용자 후속 “진행시켜” 지시로 설계 채택. 로컬 구현·검증을 진행하며 운영 활성화는 별도다.


Component tree: CryptoHeader(수집 구간/주기 안내) → MarketSizePanel → SupplyActivityReferencePanel → VenueDerivativesPanel → OptionalSentiment → CompatibleHistory → SourceMethodFooter.

props 는 ValidatedInsightMetric 과 source 별 time/status/qualification notices 다. 카드 자체에 provider/instrument 와 단위, applicable funding cycle·indicative/settled 를 보인다. update clock 가 없는 value 는 “원천 갱신시각 미상·수집 구간 관찰”로 표시한다.

display state 는 panel/history 확장만이며 ticker·venue 전환 selector 로 구현하지 않은 ETH/다른거래소를 약속하지 않는다. 원천별관측자료의 가용성을 전체시장건전성색상이나점수로 바꾸지 않는다. sourcefailed/stale/rightsblocked 는 선택된 provider 의정상 card 와구별된다.

noJS current7slots·source/기준일·범위·면책이 읽힌다. 사용자가 history 를 열 때만 `/insights/_data/crypto/history.json`을 읽고 manifest/moduleidentity 와 seriescompatibility 를검증한다. 교체된 provider/contract 구간은 선으로 이어 붙이지 않는다. u176 테마·focus token 과 u178 모바일 접근 규칙을재사용한다.


Source/권리/시점 선택은 CSS/JS 의 책임이 아니다. 상태별 한국어 내용, 숫자 단위·출처·면책은 HTML 에 제공하며 [C7](../../public-insights-20261012/contracts.md)의 실제 렌더 수용을 통과해야 한다.
