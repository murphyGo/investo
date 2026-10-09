# Session: u174 code generation


2026-10-10. User authorized all six UI units and one local commit per completed unit. FD/NFR reuse remains justified; no new product semantics or runtime dependency.

The publisher emits `markdown="0"`. The MkDocs archive-only hook validates one canonical SVG and normalizes only the historical wrapper mode byte. Fences, duplicate/broken markers, incomplete XML, unknown elements/namespaces, and unrelated pages are unchanged. Source archive bytes are never written. The built-output guard rejects empty/split/unknown SVG content and runs before Pages upload and after strict Quality build.

## Validation

- Full Python regression: **6711 passed**, 853.55s. After the last independent-review hardening, final focused hook/actual-config integration: **25 passed**, 1.97s; earlier calendar/site-index/u154 regression: 43 passed.
- Ruff check and format, mypy: **302 source files**, strict MkDocs build, Material exact-pair/CSS guard, calendar guard and four policy guards passed.
- Real headless Chromium: **12 cases** (actual archive + all-status/empty actual-config fixtures × 1440×1000/390×844 × light/dark). Each checks SVG namespace/containment, nonzero bounds, original cell count and both theme transitions. Screenshot visually inspected. [Metrics](../browser-evidence/metrics.json).
- `archive/`, `pyproject.toml`, `uv.lock` unchanged. Local fixtures are excluded from commits/public output.

## Independent review

`ui_repair_review` requested two P2 fixes: indented list fences and unknown XHTML inside SVG. Both were fixed with regressions. Final review **APPROVE, P1/P2 0**. Applied security/input boundary, read-only build/data integrity and error-contract checks. No debt added.

## Acceptance traceability

| AC | Evidence |
|---|---|
| 174.1 | actual-config legacy/current integration; source-derived rect/text counts |
| 174.2 | strict full-site build + unchanged archive bytes |
| 174.3 | no-op/fence/malformed/duplicate tests + idempotence |
| 174.4 | u154 regression + Material rendered-pair and CSS guard |
| 174.5 | 12 real browser cases, SVG namespaces and toggles |
| 174.6 | guard positive/negative tests + Pages/Quality wiring/path triggers |

This is local construction acceptance. u145 Browser acceptance, public deployment and event-v3 semantic/cutover acceptance are separate.
