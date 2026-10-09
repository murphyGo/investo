# u177 Latest bundle home cards — completed

2026-10-10. Complete local implementation under all-UI-development/unit-per-commit authorization; design choices are developer decisions.

A single canonical bundle-state tuple feeds home/archive. Home shows one H1, target bundle date, three market cards and44px primary links. Generated/absent/quality are distinct; current sealed text supplies canonical status, unknown stays unknown, fallback carries only actual discovered date/path. Existing MkDocs rewrites primary Markdown links to real directory/flat URLs. Legacy summaries use safe build-time inline emphasis; exact future terminal snippets remain escaped literal text, bypassing extraction. No missing v3 API/hash reader is fabricated.

Owner-controlled legacy intro/sections migrate outside the hero markers, preserving multiline card text and other sections/footer. Migration+marker replacement performs one atomic write. None preserves old compatibility. Existing quality consistency compares both card attributes and explicit visible fields against the same-run canonical snapshot. Pipeline reads home mandatorily before git; snapshots resolve the same call-time path owner as the writer.

## Validation

- Publisher/quality/pipeline/reconciliation/smoke/directory+flat/event publication slice: **192 passed**,58.38s; final migration/fallback/inline changes: **35 passed**,7.90s. Tests cover six statuses, absent/no-history, escaped long exact input, attribute/visible contradictions, duplicate/missing cards, bootstrap/idempotence/multiline migration, direct atomic failure, actual home-corruption rollback and zero git calls.
- Mypy302, Ruff/format, strict MkDocs, Material/calendar contracts passed. Final program-wide full regression follows u178/u179.
- Actual Chromium **20 cases**, desktop1440/mobile390 × light/dark × current partial+fallback/all-present/empty/no-history/long summary; three real read links200, oneH1, three cards,16px and44px targets, no document overflow, keyboard jumps, JS-off actual read,200% long text with70 limitation notices retained. [Evidence](../browser-evidence/metrics.json); screenshots inspected.
- Independent ui_home_review **APPROVE, residual P1/P2 zero** after link/fallback/atomic/multiline corrections.

AC177.1–8: heading/card/build links; canonical truth table; sealed text unchanged; canonical gate contradictions; migration/None/idempotence; pre-git rollback; actual responsive/no-JS/zoom evidence; next publish generator persists structure. Existing archive Markdown/JSON and financial data unchanged. Home static rendering was regenerated through its owner from actual2026-10-08 sealed texts. No push/deploy.
