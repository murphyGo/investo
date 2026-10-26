# u187 Public Insights calendar and chart UI

2026-10-26. User: “주요일정이 캘린더 UI로 표시되면 좋겠어 … 축의 의미와 스케일을 알 수 있는 … 별도 라이브러리 …” then “gogo”. This authorizes implementing the requested presentation refinement and its ordinary validation/delivery choices. It does not change source permissions or scheduled acceptance.

## Stage decision

Focused functional/NFR design is required for mixed date semantics, real axis distances, accessibility and a new browser dependency; it is recorded in [design](../u187-public-insights-calendar-and-chart-ui/design.md) before implementation. Existing FR-026–029, US-011–013 and NFR-002/004/005/008 remain the data, publication and cost contracts. No new source/model schema, API, scheduler, LLM or notification path. No separate infrastructure design is needed for self-hosted static assets.

## Steps and acceptance

- [x] 1. Inspect current renderer/assets, confirm bounded design and select pinned MIT uPlot1.6.32 for numeric/time axes; calendar remains native HTML/CSS/JS.
- [x] 2. Render a month grid, bounded month navigation and selected-date agenda; retain category/7/30 filters, verified timezone/date-only/range semantics and complete no-JS list. Add boundary/escape/month/DST regressions.
- [x] 3. Add vendor provenance/license and shared plotting layer. Yield curve uses actual maturity years; history uses actual date distances, unit-specific labels, visible linear scale/domain, gaps, exact table and keyboard value inspection. Preserve source notices and one-point honesty.
- [ ] 4. Run focused Python/Node and existing policy/static/strict-site checks; verify actual-source mobile/desktop, light/dark, JS on/off, zoom, navigation/history/error handling. Use labeled synthetic fixtures only for gap/negative/flat-history seams.
- [ ] 5. Independent dev-investo Step5.1 code review, fix findings, exact release CI. Preserve unrelated dirty root and concurrent main.
- [ ] 6. Deliver static assets and renderer-compatible runtime release; rerender existing validated snapshots through a narrowly scoped presentation update without changing current/history/snapshot/source clocks; update only manifest index_hash values required by the changed HTML. Verify live Pages/HTML/asset identity and three screens. Record code/policy SHA and keep genuine scheduled counts separate.

## Files

Publisher `src/investo/publisher/insights/calendar.py`, `macro.py` and a focused presentation helper if needed; `site_docs/assets/insights-calendar.js`, `insights.js`, new `insights-charts.js`, scoped CSS and pinned vendor assets; `mkdocs.yml`; meaningful Python/Node/browser verification; requirements/state/session/audit. Existing receipt/CAS and source adapters stay authoritative.

Runtime promotion must start from current private pin873cea37 and contain only this unit's reviewed application changes. Public main's unrelated event work is preserved and is not implicitly promoted. Existing NY Fed rights and required notices stay attached to values and history. No source recollection is needed to publish a new view of the same validated snapshots.
