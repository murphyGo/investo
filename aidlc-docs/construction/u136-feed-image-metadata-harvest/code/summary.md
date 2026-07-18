# u136 Feed Image Metadata Harvest

## Status

Code Generation complete (5/5, 2026-07-18). Cross-check complete
(2026-07-19, **PASS**):
`docs/cross-checks/2026-07-19-u136-feed-image-metadata-harvest.md`.

## Stage Decision

Functional Design and NFR Requirements were both **skipped (confirmed)**
per the plan's Stage Decision: a bounded metadata-extraction extension
over existing verified adapters with no new entity, state machine, or
routing (u126 precedent), and zero new external calls, dependencies,
secrets, or costs (R8/R13 apply as existing rules). This unit directory
therefore contains only this Code-Generation closeout; the binding
contracts live in the plan
(`aidlc-docs/construction/plans/u136-feed-image-metadata-harvest-code-generation-plan.md`,
Fixed Contracts #1-#6).

## Delivered Scope

| Step | Commit | Delivered |
|------|--------|-----------|
| 1 | `1d37010` | `MEDIA_NS`/`MEDIA_CONTENT`/`MEDIA_THUMBNAIL`/`MEDIA_CREDIT` Clark-notation constants in `sources/_xml_namespaces.py` + new `sources/_feed_media.py` (`FeedImageRef` frozen dataclass, `extract_feed_image` pure function: media:content before media:thumbnail, first image only, http(s) scheme required, 1000-char URL cap, int-parse-or-None dimensions, 240-char credit cap) with the Step 1 unit-test matrix. |
| 2 | `642de28` | `yonhap-market` item-loop wiring + R10 live fixture re-record (2026-07-16, media:content present); 5-key `raw_metadata` merge, absent image = absent keys. |
| 3 | `cfed840` | `yahoo-finance-news` (incl. `media:credit` → `image_credit` mapping) + `theblock-crypto` (thumbnail path) wiring + fixture re-records; Contract #2 divergence ratified (below). |
| 4 | `7141661` | License-key non-pollution regression tests (Contract #4): `_manifest_from_item` is None for every replayed item, forbidden-key absence, and fail-on-request fetch spy with `INVESTO_EXTERNAL_IMAGE_ASSETS=1` armed. |
| 5 | `71c20ac` | Aggregator per-source "source returned" record gains `image_items=<n>` (Contract #6) + full quality gate. |

## Ratified Divergence

**Contract #2 gate extension (2026-07-17, audit 2026-07-18)** — the Yahoo
zenfs CDN emits `media:content` with neither `type` nor an image
extension, so `_is_image_content` gained a third acceptance path: type
absent AND both dimensions parse as positive integers. Non-image mimes
still skip; mime/extension paths unchanged. Documented in the
`_feed_media.py` module docstring, the plan's Step 3 inline note, and
audit.md; regression-pinned by the accepted/partial-dimensions-rejected
test pair against the real zenfs URL shape. Separately audited recording
fact: all `media:credit` elements in the 2026-07-16 Yahoo recording are
empty, so `image_credit` is absent from replayed Yahoo items; the credit
mapping itself is pinned via synthetic XML.

## Acceptance Criteria (cross-check verified)

| Criterion | Status |
|-----------|--------|
| AC-136.1 — 3 verified sources emit `image_url` (+width/height/mime/credit when available) | Complete |
| AC-136.2 — zero new HTTP requests | Complete |
| AC-136.3 — no license-family keys; dormant fetch path can't arm | Complete (triple-pinned: mapper / adapter replay / armed-flag fetch spy) |
| AC-136.4 — per-source diagnostics expose image-bearing count | Complete |
| AC-136.5 — R8/R13 compliance, no adapter regression | Complete |

## Final Quality Gate

Full gate green at Step 5: ruff / ruff format (changed scope) /
`mypy --strict` / pytest / `scripts/check_no_paid_apis.py` /
`mkdocs build --strict`. Two pre-existing briefing test failures
reproduce at baseline `3a67cbc` (pre-u136) → DEBT-081, not a u136
regression. Cross-check re-verification at worktree HEAD (2026-07-19):
u136 scope 165 passed, no-paid guard exit 0, scoped mypy clean.

## TECH-DEBT

- **DEBT-081** — pre-existing two-test briefing breakage surfaced by the
  Step 5 gate (registered at unit close; not caused by u136).
- **DEBT-082** — `_ALLOWED_SCHEMES` / `_FORBIDDEN_LICENSE_KEYS`
  duplication families (registered at unit close). Extended 2026-07-19
  with cross-check finding L1: the 1000-char URL cap duplicated as
  `_feed_media._URL_MAX_LEN` and `image_library._IMAGE_URL_MAX`.

## Cross-Check

Verdict **PASS** — 5/5 AC Complete, no Critical/High/Medium findings,
one Low (L1, folded into DEBT-082). Report:
`docs/cross-checks/2026-07-19-u136-feed-image-metadata-harvest.md`.
