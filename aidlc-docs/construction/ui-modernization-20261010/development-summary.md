# UI u174–u179 개발 완료

2026-10-10. 사용자 전체 개발·유닛별 커밋 지시에 따라 별도 작업 트리 `/private/tmp/investo-ui-development-20261010`, 브랜치 `codex/ui-development-20261010`에서 여섯 유닛을 완료했다. 기존 루트와 문서 작업 트리의 미커밋 변경은 보존했다. 초기 문서화/관측과 최종 구현 인수를 구분한다.

| 유닛 | 결과 | 유닛 커밋 |
|---|---|---|
| [u174](../u174-calendar-svg-render-integrity/code/summary.md) | 캘린더 SVG DOM·과거 표시 복구와 build guard |51aaf1aa|
| [u175](../u175-chart-sidecar-url-and-theme-repair/code/summary.md) | 실제 날짜 URL의 차트 sidecar와 Material 테마 복구 |cfa8045a|
| [u176](../u176-site-shell-and-navigation-redesign/code/summary.md) | 공통 토큰·한국어 메뉴·키보드/모바일/no-JS 탐색 |f82b66dc|
| [u177](../u177-latest-bundle-home-cards/code/summary.md) | 실제 발행 날짜·상태·품질·fallback을 표시하는3시장 홈 카드 |011d96a5|
| [u178](../u178-responsive-briefing-data-and-accessibility/code/summary.md) | 동일 입력의 읽기 가능한 HTML 표/카드와 실제 목차·seal·접근성 |a616d733|
| [u179](../u179-month-grouped-archive-discovery/code/summary.md) | 월별 전체 링크·날짜 필터·안전한 optional 요약·오류/성능 계약 |이 문서와 함께 생성되는 마지막 유닛 커밋|

Ruff/format/strict Mypy303, strict MkDocs directory/flat, Material/calendar 및4정책 guard 통과. 전체 Python6774/1024.93s와 마지막 작은 scanner/legacy summary 변경 이후25/2.12s를 구분해 기록한다. Node22 실제 chart client29 통과. 실제 headless Chromium **총133사례**(12+10+33+20+22+36), 모든 유닛별 독립 검토 APPROVE/P1-P2zero. u179 실제5000파일 탐색/표시 예산도 통과했다. [검증 레코드](validation.json).

새 외부 호출·의존성·금융 데이터 계산을 추가하지 않았다. 기존 archived briefing Markdown/JSON/SVG/OG 바이트와 영구 URL을 보존했다. 생성 owner를 통해 홈·누적 관심 자산 index·세 시장 archive index만 갱신했다. 새 HTML briefing producer는 다음 생성 문서에 적용되며 과거 문서를 재발행하지 않는다. v3 실제 typed reader/hash/asset owner는 u169/u171, semantic/cutover는u172로 유지한다.

커밋은 로컬 브랜치에 있다. 원격 push·공개 배포·private production pin 변경은 수행하지 않았다. 이 검증은 u145 Browser 플러그인 조건이나 event-v3 실제 운영 인수를 대체하지 않는다.
