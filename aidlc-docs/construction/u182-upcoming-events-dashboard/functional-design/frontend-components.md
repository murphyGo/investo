# u182 Frontend components

작성일: 2026-10-12 · u182 · 상태: 2026-10-25 사용자 후속 진행 지시로 설계 채택. 로컬 구현·검증 진행 중이며 운영 활성화는 별도다.


Component tree: CalendarHeader(기준 수집시각/범위) → RangeControl(7/30) → CategoryControl(전체/지표/중앙은행/입찰) → DateGroupList → EventCard → CoverageNote → SourceMethodFooter.

EventCard props 는 ValidatedInsightEvent 의 정확한 time/date basis 와 range·guide·href 다. state 는 range/category 선택뿐이며 source truth 나 발표 상태를 JS 에서 갱신하지 않는다. “시간 미정”은 접근 가능한 본문이다.

기본 7 일은 정적 HTML 에서 우선 보여주고 30 일 후속 목록으로 이동 가능한 native anchor/details 를 제공한다. JS 가 있으면 DOM 에서 필터하며 필터 결과 0 과 원천 미확인을 구별한다. exact KST 와 현지 날짜-only 를 같은 타임존이라고 표시하지 않는다. calendar JSON 을 browser 가 외부 API 로 요청하지 않는다.

모바일은 날짜별 세로 카드로 구성한다. 월간 7 열 grid·가로 스크롤을 요구하지 않는다. keyboard focus/filter selected 상태·screen-reader date label·200% 확대를 검증하고 u181 의 hub/nav 에 살아 있는 링크 1 개만 추가한다.


Source/권리/시점 선택은 CSS/JS 의 책임이 아니다. 상태별 한국어 내용, 숫자 단위·출처·면책은 HTML 에 제공하며 [C7](../../public-insights-20261012/contracts.md)의 실제 렌더 수용을 통과해야 한다.
