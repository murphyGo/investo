# Cross-Check: u136 feed-image-metadata-harvest

**Scope**: u136 feed-image-metadata-harvest
**Date**: 2026-07-19
**Checked by**: investo-qa
**Baseline**: `3a67cbc`
**Implementation commits**: `1d37010`, `642de28`, `cfed840`, `7141661`, `71c20ac` (verified via `git show --name-only`: source, tests, fixtures, and the plan file only)

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| Complete | 5 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| **Total** | **5** | **100%** |

**Overall Compliance**: 100%

**QA Verdict**: **PASS** (no Critical/High/Medium findings; one Low)

## Scope

u136 harvests Media RSS image references (`image_url`/`image_width`/`image_height`/`image_mime`/`image_credit`) into `raw_metadata` from the three feeds verified to carry per-item image elements (`yonhap-market`, `yahoo-finance-news`, `theblock-crypto`), with zero new HTTP requests and a pinned license-key non-pollution invariant (plan Fixed Contracts #1-#6). Functional Design and NFR Requirements were both skipped per the plan's confirmed Stage Decision, so the acceptance surface is the plan's unit-level AC-136.1 through AC-136.5 plus project rules.

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-136.1 — 3 verified sources emit `image_url` (+width/height/mime/credit when available) into `raw_metadata` | Complete | Wiring: `src/investo/sources/yonhap_market.py:173-175`, `yahoo_finance_news.py:293-295`, `theblock_crypto.py:261-263`; mapper `src/investo/sources/_feed_media.py:163-189`. Replay pins against the re-recorded 2026-07-16 fixtures: `tests/unit/sources/test_yonhap_market.py:186-207` (url+mime exactly), `test_yahoo_finance_news.py:190-209` (url+130×86, no mime/credit), `test_theblock_crypto.py:249-270` (thumbnail url+800×450). |
| AC-136.2 — zero new HTTP requests | Complete | `extract_feed_image` is a pure function over the already-fetched element (`_feed_media.py:79-99`); adapter fetch paths unchanged (single `retry_get`). Strongest pin: `tests/unit/visuals/test_external_image.py:216-245` (`test_scraping_flag_on_harvested_items_trigger_no_fetch` — fail-on-request MockTransport even with `INVESTO_EXTERNAL_IMAGE_ASSETS=1`). All adapter tests replay via MockTransport (R10). |
| AC-136.3 — no license-family keys; dormant fetch path can't arm | Complete | Mapper emits only the 5 `image_*` keys (`_feed_media.py:180-189`); pinned at mapper level (`tests/unit/sources/test_feed_media.py:328-343`), per-adapter replay level (`tests/unit/visuals/test_external_image.py:182-213` — `_manifest_from_item` is None for every replayed item + forbidden-key absence), and fetch level (above). |
| AC-136.4 — per-source diagnostics expose image-bearing count | Complete | `src/investo/sources/aggregator.py:146-170` (`image_items` in message + structured extra); `tests/unit/sources/test_aggregator.py:126-215` (0, 2, and empty-return cases). |
| AC-136.5 — R8/R13 compliance, no adapter regression | Complete | `image_metadata` returns `dict[str, str \| int]`, flat, absent-field=absent-key (`_feed_media.py:163-189`); `raw_metadata` type/emptiness pinned at `tests/unit/sources/test_yonhap_market.py:129-143`. Full adapter suites green (165 passed). No secret surface added; fixture `meta.json` carries only the pre-existing fictional recorder UA. |

## Ratified Divergence Verification

**Contract #2 gate extension (width+height acceptance)** — consistent and pinned. Implementation: `_feed_media.py:102-124` — the third acceptance path fires only when `type` is absent AND both dimensions parse as positive integers; non-image mimes still skip; mime/extension paths unchanged. Documented in the module docstring (`_feed_media.py:17-29`), the plan Step 3 inline note, and audit.md. Regression-pinned by `test_typeless_extensionless_content_with_dimensions_accepted` and `test_typeless_extensionless_content_with_partial_dimensions_rejected` (`tests/unit/sources/test_feed_media.py:157-179`) against the real zenfs URL shape confirmed in the fixture. The Yahoo empty-`media:credit` recording fact is separately audited and the credit mapping is pinned synthetically (`test_feed_media.py:57-71, 263-293`).

## Findings

### Critical / High / Medium

None.

### Low

**L1. 1000-char URL cap constant duplicated** — `src/investo/sources/_feed_media.py:58` (`_URL_MAX_LEN = 1000`) and `src/investo/visuals/image_library.py:134` (`_IMAGE_URL_MAX = 1000`) pin the same cross-unit cap independently. Values agree today; a drift would silently turn in-cap harvests into u137 `screened_skipped` drops. Same family as DEBT-082 — fold into it when DEBT-082 is worked.

## Verified Clean

- No `import anthropic` / `from anthropic` anywhere in src/scripts/tests (grep; only the guard scripts/tests reference the strings).
- No stdlib `xml.etree` import under `src/investo/sources/` — `_feed_media.py` takes Any-typed elements and imports no XML parser; all mentions are docstrings.
- Module boundary: `_feed_media` is sources-internal; adapters import nothing from visuals/briefing/publisher/notifier; the key-name alignment with `external_image._IMAGE_URL_KEYS` is by string contract, not import.
- Free APIs only: no endpoint changes; `check_no_paid_apis.py` exit 0.
- R8: strings/ints only, no nesting, absent=omitted (pinned).
- R13: `image_items` log field is a count, never a URL (`aggregator.py:147-149`); fixtures re-recorded from public feeds, no secrets.
- Contract #4 triple-pinned (mapper / adapter replay / armed-flag fetch spy).
- Step-level plan checkboxes, aidlc-state row, audit entries, and DEBT-081/082 registrations all present and mutually consistent.

## Verification

- Cross-check executed at worktree HEAD on 2026-07-19; all tests run, not inferred.
- u136 scope: 165 passed.
- `scripts/check_no_paid_apis.py`: exit 0.
- Scoped mypy: clean.

## Proposed Actions

- Fold L1 into DEBT-082 (constant-duplication family); effort ~15 min when DEBT-082 is addressed; Low. — **Done 2026-07-19**: extension recorded on DEBT-082 in `docs/TECH-DEBT.md`.
- Mark the u136 cross-check complete in `aidlc-docs/aidlc-state.md`.
- No new TECH-DEBT items; no development-plan additions.
