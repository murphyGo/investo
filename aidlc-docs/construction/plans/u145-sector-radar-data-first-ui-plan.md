# u145 — data-first sector radar presentation

## Stage decision and authorization

The user's 2026-10-10 request makes core data/charts the first content and moves
source details below them, with a more polished presentation. This bounded u145
follow-up is authorized for implementation and publication. Separate Functional
Design/NFR stages are skipped: snapshot, calculations, freshness, missing states,
source, attribution, publication and last-good contracts remain the same.

The presentation instruction supersedes R26/C1/C2's historical requirement to
place source qualifications before all metrics. Date, freshness and comparable
coverage stay visible at the top; source and required qualifications stay visible
below the data. Existing Browser waiver remains WAIVED / NOT_EXECUTED.

## Intended presentation

1. Compact title/date/status header, then four overview cards.
2. Diverging 21-session excess-return bars for all eleven sectors, alongside a
   four-regime board built only from existing typed regime results.
3. Detailed metric table ordered by the existing relative rank, missing rows last.
4. Missing coverage, source/limitations, then expandable methodology.

No client data fetch, new metric, dependency or raw price history is introduced.
CSS is restricted to the sector dashboard and supports both Material themes and
narrow screens. Text labels and numbers remain present without color or styling.

## Execution

- [x] Amend renderer/verification, scoped CSS and presentation design record.
- [x] Re-render the existing verified snapshot; retain identical JSON and snapshot id.
- [x] Verify canonical pairs, normal/partial/warming/missing behavior, ordering and
  chart geometry; run relevant sector tests, lint/type checks and strict site build.
- [x] Independent read-only review: APPROVE, no blocking findings.
- [ ] Commit/push and verify deployed HTML/assets and identity.

Local evidence and final rollout are tracked in
[the UI session](../../../docs/sessions/2026-10-10-u145-data-first-ui.md).

The historical u145 activation remains complete. This record tracks only the
presentation follow-up; unrelated site-shell modernization work is separate.
