# u181 Frontend components

설계 2026-10-12 · 구현 검증 2026-10-25 · 사용자 후속 진행 지시로 설계 채택. 로컬 7/8 완료, 운영 Step8 pending.


Component tree: InsightsHeader(질문/판정시점) → PrimaryMetricGrid(2Y/10Y/spread/FX) → MaturityPanel(SVG4point + 동일 숫자 표) → MoneyMarketPanel → MonthlyFactsPanel → ComparisonPanel(optional history) → RelatedLinks → SourceMethodFooter.

입력은 ValidatedInsightModule 과 compatible history 만 사용한다. source envelope·raw_metadata·LLM text 는 props 가 아니다. local state 는 표시 탭/current-vs-history 선택만 있고 server fetching/새 fact 계산은 없다. JS chart 가 실패해도 표/카드 의미가 남는다.

모바일 primary2columns 또는 확대시 1column, 각 카드에 날짜·단위·상태를 표시한다. 화면 전체 horizontal overflow 를 숨겨 문제를 감추지 않는다. tooltip 만으로 unit/source 를 전달하지 않는다. 기존 insights CSS scope 와 u176 tokens 를 사용하며 Material theme toggle 를 그대로 소비한다.

첫 navigation 은 `대시보드: 모음·미국 분야별·매크로 환경`이며 기존 `/sectors/` URL 은 그대로다. calendar/crypto 를 구현하기 전에 링크하지 않는다. API 없음. 필요 시 same-origin `/insights/_data/macro/history.json`만 사용자 확장 후 읽고 latest manifest identity 를 검증한다.


Source/권리/시점 선택은 CSS/JS 의 책임이 아니다. 상태별 한국어 내용, 숫자 단위·출처·면책은 HTML 에 제공하며 [C7](../../public-insights-20261012/contracts.md)의 실제 렌더 수용을 통과해야 한다.
