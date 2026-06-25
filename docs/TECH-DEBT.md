# Technical Debt Registry

## Summary

| Priority | Count | Oldest |
|----------|-------|--------|
| Critical | 0 | - |
| High | 0 | - |
| Medium | 7 | 2026-05-07 |
| Low | 31 | 2026-04-27 |

---

## Active Items

### Critical Priority

_No critical items._

### High Priority

_No high priority items._

### Medium Priority

#### DEBT-067: event-lookahead remaining adapters — CoinGecko fallback decision + KRX option-expiry public path

- **Created**: 2026-05-08
- **Source**: u35 event-lookahead QA review (H1 + M1 + M3)
- **Reference**: FR-002 (Korean briefing comprehension), FR-008 (segmented briefing), NFR-002 (cost / no paid APIs), NFR-003 (graceful degradation), NFR-006 (testing), NFR-007 (R10 — record/replay fixtures, no fabrication)
- **Description**: u35 Phase 1 lands the entire downstream pipe (model field `scheduled_at`, `FetchWindow.lookahead`, Stage 2 "주요 일정" prompt rules, `_render_lookahead_context_block` renderer, 12-row sub-cap, deterministic 72h Telegram imminent tag) end-to-end except for the four lookahead-specific source adapters that populate it: `fomc-calendar` (Federal Reserve `press_monetary` RSS), `fred-economic-calendar` (FRED / Treasury / BLS public release-schedule feed), `coingecko-events` (CoinGecko events public endpoint — gauge availability; deprecated upstream is possible), and KRX option-expiry public feed. R10 (record/replay fixtures, no fabrication) forbids landing the adapters with synthesized payloads — every fixture must be the byte output of a live API recording — and the offline session that delivered Phase 0 + Phase 1 partial does not have live API access for those four endpoints. The orchestrator wire-through (`_stage_notify_segmented_briefing` per-segment lookahead bucket → `build_segmented_summary`) and the `SegmentCoverage.reason_codes.LOOKAHEAD_DATA_MISSING` reason code are bundled here because (a) the wire-through is dead code on the production critical path until at least one populating adapter lands, and (b) shipping the reason code without any populating adapter would cause it to fire on every segment indefinitely, eroding the u22 coverage-trust contract that readers rely on. Sub-bullets register two contracts that the wire-through must honour:
  - **M1 (sub) — orchestrator wire-through clock-explicit contract**: `_stage_notify_segmented_briefing` must pass `now_utc` **explicitly** alongside `lookahead_items_by_segment` to `build_segmented_summary`; the notifier must raise `ValueError` if `lookahead_items_by_segment` is supplied while `now_utc=None`. Reason: the notifier stays clock-free (testability + determinism) — relying on `datetime.now(UTC)` inside `notifier/summary.py` would couple regression tests to wall-clock time and make the deterministic D-1 / D-2 selector non-reproducible. Source: u35 QA M1.
  - **M3 (sub) — single-filter reuse contract**: the orchestrator must reuse the lookahead filter result computed by `briefing/pipeline.py::_render_lookahead_context_block` so the markdown context block (Stage 2 segment narrative) and the Telegram tag selector (`build_segmented_summary` → `_imminent_event_tag`) see exactly **one** filtered list. Filtering twice — once for the prompt and once for the tag — risks the two surfaces silently disagreeing (e.g., the prompt shows 5 events but the Telegram tag picks an event not in the prompt). Source: u35 QA M3.
- **Suggested Fix**:
  - Land the four adapters one at a time as live-credential sessions allow; each adapter reuses the existing `@register` plugin pattern, `retry_get` + `strip_html` + `defusedxml` per R8, and adapter-local browser-compatible UA per R14 where the upstream demands one. Pin each adapter's record/replay fixture set (HTTP body + headers) per R10 with the live recording hash captured in the test fixture path.
  - Once at least one adapter lands, wire `_stage_notify_segmented_briefing` to (a) compute `now_utc = datetime.now(UTC)` at orchestrator entry, (b) populate `lookahead_items_by_segment` from the new adapters' output filtered through `_render_lookahead_context_block`'s **single** filter call, and (c) pass both kwargs explicitly into `build_segmented_summary`. Pin the clock-explicit contract with a unit test that supplies `lookahead_items_by_segment` while leaving `now_utc=None` and asserts `ValueError`.
  - Once at least one adapter lands, add `SegmentCoverage.reason_codes.LOOKAHEAD_DATA_MISSING` to the u22 reason-code enum and emit it from the aggregator only when the lookahead pass for a given segment returns zero items **and** at least one lookahead-aware adapter was attempted (i.e., the reason code never fires on a segment that has no lookahead-aware adapter registered). Pin with a regression test that exercises the empty-adapter and zero-item branches.
- **Partial resolution (2026-05-10, u43)**: The orchestrator wire-through (M1 — clock-explicit `now_utc` in `_stage_notify_segmented_briefing` + `ValueError` invariant in `build_segmented_summary`), the single-filter chokepoint (M3 — `briefing.segments.filter_lookahead_items` reused by both the briefing pipeline's `_render_lookahead_context_block` and the orchestrator's notify stage), the `LOOKAHEAD_DATA_MISSING` reason code (with the anti-regression guard that it only fires on segments carrying ≥ 1 lookahead-aware adapter from `LOOKAHEAD_AWARE_SOURCES`), and **one of the four adapters** — `fomc-calendar` (Federal Reserve `calendar.json` forward schedule, Tier S, segment routing `us-equity`, R10-compliant fixture: 528 KB byte-equal recording from 2026-05-10) — landed. The us-equity Telegram imminent tag now fires from production data; the segment "주요 일정" prompt block now sees real forward FOMC events.
- **Partial resolution (2026-05-10, u43 follow-up)**: A second adapter — `fred-economic-calendar` (FRED `release/dates` forward schedule for 10 curated market-moving releases: CPI, PPI, NFP/Unemployment, GDP, PCE, Industrial Production, Retail Sales, JOLTS, Housing Starts, Existing Home Sales; Tier A, segment routing `us-equity`, R10-compliant fixtures: 4 byte-equal recordings + empty + invalid-key fixtures from 2026-05-10) — landed after the u43 main session's TLS handshake outage cleared. Network reachability verified: `api.stlouisfed.org` HTTP 200 on valid params, HTTP 400 on invalid api_key (TLS layer healthy). Adapter enrolled in `LOOKAHEAD_AWARE_SOURCES` + `_US_ONLY_SOURCES` + `_US_MARKET_SOURCES` + `ADAPTER_TIERS["fred-economic-calendar"] = "A"`. The us-equity "주요 일정" block now surfaces FOMC + macro release prints together; persona #4's "FOMC 이번 주 / NFP 이번 주말" first-line concern is now closed for the FRED-tracked surface. Two of four adapters remain deferred (CoinGecko events upstream-deprecated; KRX option-expiry has no public non-scraping path).
- **Status decision (2026-05-14)**: Demoted **High → Medium**. The original High trigger was user-visible dormancy after u35; u43 resolved that by landing FOMC + FRED, orchestrator wire-through, single-filter reuse, and `LOOKAHEAD_DATA_MISSING`. Remaining work is now bounded upside coverage: crypto event fallback selection and a domestic option-expiry public-path decision.
- **Remaining (sub-bullets — re-evaluate when live API access for the deferred surfaces is restored)**:
  - ~~**`fred-economic-calendar`**~~ — **Resolved 2026-05-10 (u43 follow-up).** FRED endpoint reachable; adapter landed with R10 fixtures + 24 unit tests + `INVESTO_FRED_CALENDAR_RELEASES` + `INVESTO_FRED_CALENDAR_LOOKAHEAD_DAYS` env overrides + R13 secret hygiene via existing `SECRET_ENV_VARS` enrollment.
  - **`coingecko-events`** — the public `https://api.coingecko.com/api/v3/events` endpoint returns 404 with `{"error":"Incorrect path. Please check https://docs.coingecko.com/"}` (verified live 2026-05-10). The endpoint is deprecated upstream. Fallback options: (a) CoinMarketCal (`https://developers.coinmarketcal.com/v1/events`) requires a free-tier key (returns HTTP 403 without one); user must register and add the key to `.env.local` + GHA secrets before the adapter can land. (b) Token-unlock-only aggregator (would not cover hard forks / mainnet launches). Decision needed on which path to take before the adapter can be implemented.
  - **`krx-option-expiry`** — no public KRX market-data path that exposes the option-expiry calendar without OTP / scraping is currently identified (consistent with u36's "no Naver / KRX scraping" out-of-scope rule). The closest public surface (`open.krx.co.kr` 200 OK with full HTML) is a search portal, not a JSON / CSV calendar feed. Domestic-equity readers continue to receive forward corporate events via `dart-disclosure` (u41). Defer until either KRX publishes a JSON path or a workaround is approved by the operator. Effect on `LOOKAHEAD_DATA_MISSING`: the reason code does not fire on `domestic-equity` today because no lookahead-aware adapter is mapped to that segment (anti-regression guard).
- **Effort (remaining)**: ~3 h for `coingecko-events` once a fallback aggregator + key is chosen; ~unknown for `krx-option-expiry` (depends on whether a public path is ever confirmed).
- **Priority Reasoning**: **P2 (Medium) as of 2026-05-14** — FOMC + FRED cover the core U.S. macro lookahead payoff and the production Telegram / briefing surfaces are no longer dormant. Keep active because CoinGecko/CoinMarketCal could improve crypto event recall and KRX option expiry could improve domestic derivatives context. Promote back to High only if a user-visible gap appears that one of the remaining adapters would have closed, or if the operator registers a CoinMarketCal key and explicitly wants the crypto-event adapter shipped next.

#### DEBT-049: SVG `@media (prefers-color-scheme)` disagrees with mkdocs Material site toggle

- **Created**: 2026-05-08
- **Source**: u26 visual-delivery-integrity QA review (M1)
- **Reference**: NFR-005 (consistency / theme parity), FR-002 (Korean briefing comprehension), FR-003 (static web publishing)
- **Description**: u26 introduced dark-mode support for `DataConfidenceCard` and `WatchlistCard` via option (a) — single SVG with embedded `<style>` block carrying `@media (prefers-color-scheme: dark)` rules driving classed `<rect>` / `<text>` elements. The SVGs are referenced from markdown via `<img src="...svg">`, so the `prefers-color-scheme` query is evaluated at the SVG document level, which only sees the **OS-level** scheme. mkdocs Material's site-level theme toggle (`data-md-color-scheme="slate"`) lives on the parent HTML and is invisible to the embedded SVG. As a result, an OS-light + site-dark reader (or OS-dark + site-light) sees a card rendered against the wrong scheme — the surrounding mkdocs page is dark, but the embedded card stays light, or vice versa. Reader-trust degrades visibly for any user who toggled the site theme away from their OS default.
- **Suggested Fix**: Either (b) inline `<svg>` embed in markdown + parent class selector that picks up the site `data-md-color-scheme` attribute on `<html>` (the SVG `<style>` block then targets `[data-md-color-scheme="slate"] .card-bg` etc.), or (c) render both light and dark variant SVG files and emit a `<picture>` element (`<source media="(prefers-color-scheme: dark)" srcset="...-dark.svg"> <img src="...-light.svg">`). Option (b) keeps the single-asset shape and the existing class hooks; option (c) doubles asset volume but works without inline `<svg>`. Either way, retain the chokepoint shape (one `_CARD_STYLE` block / one render path) so future card types inherit the fix automatically.
- **Effort**: ~1.5 h for option (b) including the markdown render path switch (`<img>` → inline `<svg>`), parent-attribute selector tests, and a regression test that pins both site-toggle states against a synthesized HTML wrapper. Option (c) ~45 min but requires a second variant render pass.
- **Priority Reasoning**: Medium — works correctly today for the OS-default theme, but the site toggle is a first-class mkdocs Material affordance and any reader exercising it sees a mismatched card. Reader-trust contract is the highest-leverage signal in the segmented-briefing UX, so the disagreement is worth closing once cleanly rather than carrying forward through every future card type.

#### DEBT-047: Producer ↔ gate reject set unification (`is_unsafe_summary_value` helper extraction)

- **Created**: 2026-05-08
- **Source**: u25 summary-fidelity-and-content-trust QA review (M2)
- **Reference**: NFR-005 (consistency / DRY), NFR-006 (test robustness), FR-002 (Korean briefing comprehension)
- **Description**: u25 widened both `src/investo/briefing/pipeline.py::_is_unsafe_summary_candidate` (producer side) and `src/investo/briefing/summary_quality.py::_validate_summary_value` (gate side) with the same 4-pattern reject set: marker-only (`^\d+\.$`), list-marker-only (`^[-*]\s*$`), conjunction-tail (e.g., `^.*\bvs\.$`), and empty/whitespace. The contract that producer rejection mirrors gate rejection is currently documented in the `summary_quality` module docstring, but the regexes themselves are duplicated. A future widening (say, "trailing colon" patterns) lands in only one site by default; the gate-side reject set is the publish blocker, but the producer site is what generates user-visible fallbacks, so divergence either leaks bad summaries (if only gate widened and producer keeps emitting them) or unnecessarily forces fallbacks (if only producer widened).
- **Suggested Fix**: Extract a public `is_unsafe_summary_value(value: str) -> bool` from `src/investo/briefing/summary_quality.py` carrying the canonical reject set. Have `briefing/pipeline.py` import and call it from `_is_unsafe_summary_candidate`. Pin the contract with a parametrize test that walks every reject pattern through both call paths simultaneously, so adding a new pattern requires exactly one regex edit.
- **Effort**: ~25 min including the helper extraction, producer-side import switch, and the parametrize regression test.
- **Priority Reasoning**: Medium — gate-side rejection is the actual publish blocker today, so reader-trust is preserved even on producer drift. Promote to High the moment a sixth reject pattern lands and reviewers ask "did this go in both sites?".

#### DEBT-040: Layout reposition ordering when multiple non-hero cards share the same anchor

- **Created**: 2026-05-07
- **Source**: u24 visual-provenance-and-layout QA review (M3)
- **Reference**: NFR-005 (consistency / contract integrity), NFR-006 (test robustness), FR-003 (static web publishing)
- **Description**: `_reposition_visual_links` in `src/investo/visuals/assets.py` reinserts non-hero cards via `lines[insert_at:insert_at] = […]`. When two or more non-hero asset paths anchor to the same H2 (e.g., two cards both flagged for `① 요약`), the inserts happen in `asset_paths` reverse order, so the rendered layout sees the cards in the opposite order from the iteration order. The ordering intent (intentional reverse vs. accidental) is not documented and no test pins it. A future contributor adding a third non-hero card to the same anchor will land an unintended layout reshuffle.
- **Suggested Fix**: Either (a) introduce a stable secondary sort key when collecting per-anchor inserts, e.g. `(anchor_line, -original_index)` to make the inversion explicit, or (b) keep the current `lines[insert_at:insert_at]` shape but document the inversion in a docstring on `_reposition_visual_links` plus add a test that pins layout order for ≥ 2 non-hero cards at the same anchor.
- **Effort**: ~30 min including the chosen fix + test.
- **Priority Reasoning**: Medium — works correctly today on the observed segment shapes (≤ 1 non-hero card per anchor), but is the kind of regression that escapes review when a fourth card type lands.

#### DEBT-041: `_provenance_caption_for` swallows the pydantic `ValueError` from corrupt sidecars

- **Created**: 2026-05-07
- **Source**: u24 visual-provenance-and-layout QA review (M4)
- **Reference**: NFR-003 (graceful degradation), NFR-007 (R13 — secret hygiene), FR-002 (Korean briefing comprehension)
- **Description**: `_provenance_caption_for` in `src/investo/visuals/assets.py` reads the `<asset>.json` sidecar and constructs a `VisualProvenanceManifest` to choose a Korean caption. If the sidecar JSON is corrupt or schema-violating, the pydantic `ValidationError` (a `ValueError` subclass) is swallowed and the function returns `None`, which renders an image without a caption. Today, `prepare_segment_visual_assets` writes manifests atomically and validates them at write time, so the corrupt-sidecar case is not reachable through the supported call path. However, any future call site that bypasses `prepare_segment_visual_assets` (e.g., a one-off backfill script that copies pre-existing assets) can produce captionless images while looking syntactically correct.
- **Suggested Fix**: Either (a) move sidecar validation **before** caption rendering inside `_provenance_caption_for` so corrupt sidecars raise `VisualAssetError` (re-using the existing publish-side fallback), or (b) re-raise as `VisualAssetError` from inside `_provenance_caption_for`, or (c) add an explicit `validate_sidecar_or_raise(asset_path)` helper and require every caller (including future ones) to invoke it before captioning.
- **Effort**: ~25 min including a test that pins the corrupt-sidecar rejection path.
- **Priority Reasoning**: Medium — not reachable through today's supported call path, but the silent fall-through is a degradation in observability and could mask malformed sidecars produced by future tooling.

#### DEBT-038: `source_outcomes` segment-filtering contract is not enforced at the type level

- **Created**: 2026-05-07
- **Source**: u22 source-coverage-transparency QA review (L4)
- **Reference**: NFR-005 (consistency / contract integrity), NFR-006 (test robustness), FR-008 (segmented briefing)
- **Description**: `build_segment_coverage(...)` in `src/investo/briefing/segments.py` accepts `Sequence[SourceOutcome]` for the segment's source results. The function trusts the caller to have already filtered outcomes to the current segment (orchestrator does this today), but the type signature is identical to a "global outcomes list", so a future refactor could silently feed cross-segment outcomes — leaking another segment's source statuses into a segment's data-confidence card or markdown reason callout.
- **Suggested Fix**: Introduce a `SegmentScopedOutcomes = NewType("SegmentScopedOutcomes", tuple[SourceOutcome, ...])` and have the orchestrator construct it via a small validating builder that asserts every outcome's category belongs to the segment's allowed categories. Alternatively, add a runtime guard inside `build_segment_coverage` that raises if any outcome category is not in the segment's allow-list.
- **Effort**: ~45 min including builder + orchestrator/test updates.
- **Priority Reasoning**: Medium — the orchestrator currently filters correctly, but the contract is invisible to mypy and would be the kind of regression that escapes review. Cheap to harden once and prevents a class of cross-segment data-leak bugs.

### Low Priority

#### DEBT-079: macro calendar↔actual share no canonical `event_key` (u59 carryover tracks them as two events)

- **Created**: 2026-05-31
- **Source**: u59 macro-actual-priority-and-lineage Step 8 closeout (developer-flagged)
- **Reference**: u59 AC-11 (macro carryover lifecycle), FR-001 (source coverage), the `advance_macro_lifecycle` event-key join contract
- **Description**: The macro carryover lifecycle (`briefing/macro_carryover.py::advance_macro_lifecycle`) joins schedule and actual events **strictly by `event_key`** (no substring matching, by design). But the two source adapters that feed a given release infer *different* event keys: `fred-economic-calendar` (the PPI schedule, `release_id=46`) and `fred-macro` (the PPI actual, `series_id=PPIFID`) produce distinct inferred keys. So a release and its corresponding actual currently track as **two separate lifecycle events** — the calendar row ages to `stale` while the actual row independently lands `confirmed`, instead of the intended scheduled→confirmed flow on one event. Adapters that already stamp an explicit `macro_event_key` get the unified flow today; only the inferred-key path is affected.
- **Suggested Fix**: Stamp a shared canonical `macro_event_key` (e.g. `us:PPI:{release_period}`) on both the `fred-economic-calendar` schedule item and the `fred-macro` actual item at adapter level, so `advance_macro_lifecycle` joins them as one event. Add a fixture-backed test asserting a PPI schedule on day N and the PPI actual on day N+k collapse to a single `confirmed` lifecycle event.

#### DEBT-080: `_segment_for_item` matches by object identity (won't survive serialization)

- **Created**: 2026-05-31
- **Source**: u59 macro-actual-priority-and-lineage Step 8 closeout (developer-flagged)
- **Reference**: u59 Step 8 orchestrator wire (`orchestrator/pipeline.py`)
- **Description**: The u59 carryover wire's `_segment_for_item(...)` helper resolves a collected item's segment by `is` (object identity) against the in-run routed item set. This is correct for the in-process pipeline (the same `NormalizedItem` objects are routed and then read), but it would silently fail if items were ever serialized/round-tripped (e.g., a future cached-collection or cross-process stage), returning no segment match.
- **Suggested Fix**: Key the lookup on a stable value (e.g. `(source_name, url)` or a content hash / the macro `event_key`) instead of object identity, before any stage gains a serialization boundary. Low urgency while collection→generation stays single-process.

#### DEBT-078: re-introduce a compact-card pre-fetch sparkline without inline history (product decision)

- **Created**: 2026-05-24
- **Source**: u75 chart-data-externalization-and-mobile-performance closeout (compact-card sparkline removed)
- **Reference**: AC-75.3 (compact cards render without fetching the sidecar), AC-75.1 (no full OHLC history inline), u50 lightweight-charts-embed, NFR-005 (consistency / reader UX)
- **Description**: The previous compact card rendered a small line sparkline by default, but that sparkline read the inline `data-history` JSON that u75 externalized to a lazy sidecar to satisfy AC-75.1 (no full OHLC history inline) and AC-75.3 (no fetch before expand). With the inline history gone, the compact card now shows ticker / price / change only — the at-a-glance trend sparkline is no longer present. This is **not** a defect: AC-75.3 explicitly requires the compact card to render without fetching the sidecar, and a sparkline that requires history would either re-inline the payload (violating AC-75.1) or force a fetch on render (violating AC-75.3). Whether the compact card *should* carry a tiny trend cue is a product decision that was intentionally left unimplemented.
- **Suggested Fix**: If a compact trend cue is wanted, emit a small, downsampled `data-spark` polyline attribute (e.g. ~12–20 closing points, not the full OHLC history) on the placeholder at publish time and render it inline in `investo-chart-init.js` without any fetch. The downsampled series stays well under the per-card inline budget (the AC-75.1 test asserts no full history / no serialized OHLC row arrays), so it does not re-introduce the heavy payload. Keep the lazy sidecar as the sole source for the expanded candlestick. Pin a payload-budget test for the `data-spark` attribute and a JS render check.
- **Effort**: ~1.5-2 h — add the downsampled `data-spark` builder in `charts.py`, render it in the JS compact path, and pin the inline-budget + JS render regressions.
- **Priority Reasoning**: Low — the compact card is fully functional (ticker / price / change render, expand still works) and the removal is a deliberate consequence of meeting AC-75.1 / AC-75.3, not a regression. Promote to Medium only if a user-quality / mobile review confirms the missing at-a-glance trend cue is a material UX loss.

#### DEBT-077: backfill chart sidecars for pre-existing committed archive briefings (legacy inline charts non-expandable)

- **Created**: 2026-05-24
- **Source**: u75 chart-data-externalization-and-mobile-performance closeout (legacy archive non-expandable risk)
- **Reference**: AC-75.1 (no full OHLC history inline), AC-75.2 (archive-local sidecar JSON staged with the briefing), AC-75.4 (lazy-load on expand), FR-003 (static web publishing / permanent archive)
- **Description**: u75 changed the chart placeholder schema from inline `data-history` to a `data-history-src` relative sidecar path, and `investo-chart-init.js` now hides the expand control for any `details` whose `data-history-src` is absent. Briefings already committed to `archive/` before u75 were rendered with the **old** inline `data-history` schema and have no sidecar file, so on the live site their chart cards render the compact summary but are **not expandable** (the JS treats a missing `data-history-src` as non-expandable rather than parsing the legacy inline JSON). This is **not** a reader-facing failure for new briefings (every briefing generated after u75 writes its sidecars and stages them per AC-75.2) and the compact summary still renders for legacy cards; the residual is that the permanent archive's older chart cards lost their expand-to-candlestick affordance. Backfilling historical archive payloads was explicitly out of scope for u75 (a Non-Goal in the plan).
- **Suggested Fix**: Add a one-shot migration / regeneration pass that walks `archive/**/*.md`, parses each legacy inline `data-history` (or re-derives history from the recorded source data where available), emits the deterministic sidecar JSON via `chart_sidecar.write_chart_sidecar()` into the matching `{stem}.assets/charts/` directory, and rewrites the placeholder to `data-history-src`. Run it once as an operator-driven backfill (not on the per-day critical path). Alternatively, teach `investo-chart-init.js` to fall back to a still-present legacy inline `data-history` when no `data-history-src` is found — a smaller change that re-enables legacy expand without rewriting archives, at the cost of keeping the old parse path alive.
- **Effort**: ~2-3 h — write the archive-walk backfill (reuse the `chart_sidecar` contract + `charts.py` placeholder rewrite), or ~1 h for the JS legacy-fallback alternative; pin a fixture for a legacy-schema archive file in either case.
- **Priority Reasoning**: Low — only the historical archive is affected and only the expand affordance is lost (compact summary still renders); all briefings generated after u75 are fully expandable per AC-75.4. It is archive-completeness polish, not a live-pipeline or reader-facing correctness issue. Promote to Medium only if archive expandability is deemed important for reader-trust or if a user review flags legacy charts as broken.

#### DEBT-076: cross-market cause-map re-derives type from rendered macro label strings — plumb structured `detected_macro_keys`

- **Created**: 2026-05-24
- **Source**: u74 market-channel-depth-v2 closeout (cause-map label-coupling risk)
- **Reference**: AC-74.5 (cross-market cause-map limited to u57-approved links, observational), NFR-005 (consistency / maintainability)
- **Description**: `src/investo/publisher/cross_market_cause_map.py` is double-gated correctly on u57 `BundleContext.shared_macro_block` (only keys hit by ≥2 segments) and the `cross_market_core_allowed` gate, so forbidden / single-segment links are already suppressed. However, `BundleContext` exposes only the *rendered* shared-macro **string**, not a structured key set, so the cause-map must re-derive its cause-map type (`geopolitical_oil_macro` / `fed_policy_event` / `global_systemic_risk`) by string-matching the Korean macro labels inside that block (`국제 유가` / `FOMC 일정` / `미 국채 수익률`). This label-coupling is brittle: a future relabel of the shared-macro block text (a presentation change) silently breaks the cause-map type derivation even though the underlying macro signal is unchanged. This is **not** a correctness or scope defect — the double gate still bounds which links can render, and forbidden types are suppressed + logged regardless — it is a maintenance / coupling concern.
- **Suggested Fix**: Add a structured `detected_macro_keys` field (typed key set, e.g. an enum or frozenset) to `BundleContext` in the orchestrator/u57 layer and have the cause-map key its type derivation off that field instead of the rendered label string. This is a **model change** — planner / scope-gated — so it is deferred rather than forced into the u74 presentation-only slice. Keep the double gate and the suppress-and-log behavior unchanged; the change only removes the label-text dependency. Note the related dormant type: `global_systemic_risk` has no emitting detector today, so its branch is currently exercised only by fixtures.
- **Effort**: ~1.5-2 h — add the `detected_macro_keys` field + populate it where the shared-macro block is computed, switch `cross_market_cause_map` type derivation to the structured key, and pin regression fixtures (allowed-link kept, forbidden-link still suppressed, relabel-resilient).
- **Priority Reasoning**: Low — the double gate already enforces the scope contract (AC-74.5 holds) and forbidden links are suppressed independent of the label match, so the residual is brittleness to a presentation relabel, not a reader-facing or scope error. Promote to Medium only if the shared-macro block labels are relabeled (or a new macro key is added) and the cause-map silently stops firing.

#### DEBT-075: watchlist Rejected near-miss heuristic (uppercase ticker-shaped lookalike) is intentionally broad

- **Created**: 2026-05-24
- **Source**: u73 watchlist-impact-center-v2 closeout (near-miss diagnostics noise risk)
- **Reference**: AC-73.1 (Direct/Related/Uncertain/Rejected grouping), AC-73.2 (short-ticker false-positive handling), R13 (no secret / redaction), NFR-005 (consistency / reader-trust)
- **Description**: `src/investo/briefing/watchlist_impact.py::_detect_rejected` flags Rejected near-misses for configured short ASCII tickers (≤4 chars) using two heuristics: a shared-prefix family check and an uppercase ticker-shaped lookalike check (±2 length, same first letter). The lookalike check is intentionally broad to catch SOL↔SLGL / BTC↔BTM-style false positives, so an **unrelated** uppercase ticker that merely shares a configured short ticker's first letter (and lands in the ±2 length window) can also appear in the Rejected diagnostics block. This is **not** a reader-facing or correctness defect: Rejected records are diagnostics-only, non-public, and reach the static watchlist daily page only inside a collapsed `<details>진단: 보류/제외된 후보</details>` block with titles R13-redacted to source name + reason code + offending token + 6-char title hash. The residual is operator-trust noise (the diagnostics block can list candidates that were never plausible matches), not a public misclassification — u64-accepted matches are excluded before the scan, so no valid Direct/Related hit is affected.
- **Suggested Fix**: Tighten the lookalike rule with a known-symbol allowlist (only flag tokens that resemble a *configured* term, or a recognized ticker shape from a small curated set) and/or an explicit edit-distance bound rather than the first-letter + ±2-length window. Keep the shared-prefix family check and the u64-accepted exclusion as-is; the change is a strictly additive precision tightening of the near-miss scan with regression fixtures for both the kept SOL/BTC rejections and the newly suppressed unrelated tickers.
- **Effort**: ~1-1.5 h — add the allowlist / edit-distance guard to `_detect_rejected`, pin kept-vs-suppressed near-miss fixtures.
- **Priority Reasoning**: Low — the noise is confined to a collapsed, R13-redacted, diagnostics-only block that never reaches the briefing body or Telegram (AC-73.4 holds) and never affects an accepted match. It is operator-trust polish, not a reader-facing error. Promote to Medium only if a user-quality / operator review flags the diagnostics block as materially noisy in practice.

#### DEBT-073: Backfill stale public quality surfaces that pre-date the u69 render-path fix

- **Created**: 2026-05-24
- **Source**: u69 quality-public-consistency-gate closeout (2026-05-22 live replay finding)
- **Reference**: AC-69.3 (denominator/unknown rendered only with evidence), FR-003 (static web publishing), NFR-005 (consistency / reader-trust), NFR-007 (R10 — record/replay, no fabrication)
- **Description**: u69 added a canonical cross-surface quality validator (`src/investo/publisher/quality_consistency.py`) and fixed the render path (`update_quality_page` -> `reconcile_kpis_with_history`) so an empty/lagging `archive/_meta/coverage.jsonl` (`outcomes:[]`) can no longer render `실패한 소스 누적 = 0` when `quality_history.jsonl` holds failure evidence. The fix corrects **future** publishes only. Running the new replay against the live archive flags **2026-05-22** with `quality.denominator_unknown_but_evidence_present`: the already-committed `site_docs/quality.md` renders the failed count as `0` / `n/a` while the bundle holds real failure evidence. Historical archive repair was a plan Non-Goal, so the stale committed page and any pre-fix `coverage.jsonl` rows are left as-is; the contradiction is reader-visible only on the historical 2026-05-22 dashboard view.
- **Suggested Fix**: A bounded one-shot repair pass (mirroring the u26 `scripts/backfill_2026_05_06_visuals.py` precedent) that (a) walks affected dates whose committed `site_docs/quality.md` fails `check_quality_consistency` against `quality_history.jsonl`, (b) re-renders the dashboard via the post-u69 `update_quality_page` / `reconcile_kpis_with_history` path, and (c) repairs or backfills empty `archive/_meta/coverage.jsonl` rows from the per-segment markdown status evidence where recoverable (never fabricating counts — leave `미집계` where evidence is genuinely absent). Optionally add a short operator runbook section explaining how to read the quality dashboard and what `QualityConsistencyError` / a skipped `quality_page_missing` finding means (ops handoff; can be split out as a separate Low item if preferred).
- **Effort**: ~1.5-2 h for the one-shot repair pass + per-date verification via the u69 validator; ~30 min for the optional runbook section.
- **Priority Reasoning**: Low — the going-forward render path is fixed and the publish-boundary gate now blocks new contradictions, so reader-trust is preserved for all future runs. The residual is one historical dashboard view (2026-05-22) that overstates run health; it does not affect the generated briefing artifacts themselves. Promote to Medium only if additional pre-fix dates are found to materially understate failures on the public dashboard.

#### DEBT-071: 24h 청산 (롱/숏 liquidations) has no no-key aggregate source

- **Created**: 2026-05-24
- **Source**: u66 crypto-channel-depth closeout (Gap A scope-out)
- **Reference**: R16d (crypto indicator scope-out), NFR-002 (free APIs / no paid keys), NFR-003 (graceful degradation), R10 (record/replay fixtures, no fabrication)
- **Description**: The crypto native indicator block (R16) renders Fear & Greed, BTC dominance, total market cap, BTC 펀딩비, and BTC OI from no-key sources, but **24h 청산 (롱/숏 liquidations)** has no no-key aggregate source. Coinglass — the canonical aggregate-liquidation endpoint — returns `{"code":"30001","msg":"API key missing"}` without a registered key (verified live 2026-05-24 by the lead reachability probe), and its key tiers are metered/paid. Per R16d and R10 (no fabrication), the liquidation row renders as an explicit `무료 검증 소스 미확정` unavailable row and u74 renders the `funding_oi_liquidation` liquidation leg as `not_yet_available` — values are never synthesized. The crypto coverage status is NOT downgraded by this absence (it is a designed scope-out, not a degradation).
- **Suggested Fix**: Promote a liquidation row only after a no-key JSON endpoint that aggregates exchange liquidations is identified, with (a) a recorded R10 live fixture (success/empty/malformed paths), (b) replay coverage, and (c) a stable upstream-terms check confirming no metered billing. If a free-tier Coinglass key is ever registered by the operator (and the cost-guard `INVESTO_OPENAI_VISUALS`-style env policy extended to gate it), an `coinglass-liquidations` adapter (`indicator="btc_liquidation"`, crypto-routed `category="macro"`) could land and populate the u74 liquidation leg.
- **Effort**: ~3-4 h once a no-key aggregate-liquidation endpoint is confirmed (adapter + R10 four-path fixtures + u74 render wire-through + contract test); unknown if no no-key path ever exists.
- **Priority Reasoning**: Low — the confirmed crypto indicators (sentiment / dominance / market cap / funding / OI) already give the reader the crypto-native state the 2026-05-22 review flagged as missing; liquidation is an enrichment leg, and the absence is visible (explicit unavailable row), not silent. Promote to Medium only if a no-key aggregate-liquidation source is confirmed or the operator registers a Coinglass key and explicitly requests the row.

#### DEBT-072: 거래소 netflow has no no-key source (CryptoQuant / Glassnode are paid)

- **Created**: 2026-05-24
- **Source**: u66 crypto-channel-depth closeout (Gap A scope-out)
- **Reference**: R16d (crypto indicator scope-out), NFR-002 (free APIs / no paid keys), NFR-003 (graceful degradation), R10 (record/replay fixtures, no fabrication)
- **Description**: **거래소 netflow** (exchange inflow/outflow — a positioning signal a crypto reader values) has no no-key source. The canonical providers — CryptoQuant and Glassnode — are paid / key-required (verified by the lead reachability probe 2026-05-24). Per R16d and R10, the netflow row renders as an explicit `무료 검증 소스 미확정` unavailable row and is never fabricated. The crypto coverage status is NOT downgraded by this absence (designed scope-out).
- **Suggested Fix**: Promote a netflow row only after a no-key JSON endpoint exposing exchange netflow is identified, with (a) a recorded R10 live fixture (success/empty/malformed), (b) replay coverage, and (c) a stable upstream-terms check confirming no metered billing. If no free-tier path is ever confirmed, keep the explicit unavailable row and accept the enrichment gap.
- **Effort**: ~3-4 h once a no-key netflow endpoint is confirmed (adapter + R10 four-path fixtures + u74 render wire-through + contract test); unknown if no no-key path ever exists (likely none — netflow requires on-chain + exchange-label data that the free providers gate behind paid tiers).
- **Priority Reasoning**: Low — same reasoning as DEBT-071; netflow is an enrichment leg and the absence is visible, not silent. The free-tier prospect is weaker than DEBT-071 (liquidation aggregators occasionally expose limited no-key reads; netflow uniformly requires paid on-chain labeling). Promote to Medium only if a no-key netflow source is confirmed.

#### DEBT-070: Inline first-use glossing variant (in-body parenthetical auto-gloss) deferred

- **Created**: 2026-05-24
- **Source**: u68 reader-aids-residual closeout (review Gap D — optional variant)
- **Reference**: FR-002 (Korean briefing comprehension), R-glossary.4 (callout recent-window scope), `unit-of-work.md` u68 ("(a) optional inline first-use glossing")
- **Description**: The glossary reader-aid surfaces unglossed first-use terms only through the header `> **용어 가이드**` callout (u40), now scoped to a recent trading-day window so terms are not re-announced daily (u68, R-glossary.4). The optional **inline** variant — auto-inserting an in-body parenthetical gloss at a term's first appearance (e.g., rewriting `EIA 주간 재고` to `EIA(에너지정보청) 주간 재고` inside the LLM prose) — is not implemented. unit-of-work.md marks this variant explicitly optional for u68.
- **Suggested Fix**: If ever warranted, add a deterministic post-render in-body glosser that inserts the `BASELINE_GLOSSARY` paren gloss at a term's first per-segment appearance only when the immediate-paren gloss is absent, reusing `_has_immediate_korean_gloss` to avoid double-glossing. Must not run arithmetic over or otherwise mutate numeric content (u25 guarantee) and must stay idempotent (FR-006). Pin with a regression test that the rewrite fires exactly once per term per segment and never alters numbers.
- **Effort**: ~2-3 h including the safe in-prose insertion logic + idempotency/no-number-mutation regression tests.
- **Priority Reasoning**: Low — the header callout plus cross-day suppression (u68) covers the reader-aid need for a 1-person tool; in-body auto-gloss risks distorting LLM prose and clashing with the u25 "no edits to numeric content" guarantee, and its ROI is unproven. Promote to Medium only if reader feedback shows the header callout is insufficient and in-body glossing is specifically requested.

#### DEBT-068: Yonhap numeric-index parse is best-effort terminal fallback for KOSPI/KOSDAQ close

- **Created**: 2026-05-24
- **Source**: u67 domestic-channel-depth closeout
- **Reference**: R15a (index-close precedence), NFR-002 (free APIs), NFR-003 (graceful degradation), R10 (record/replay fixtures)
- **Description**: The `stooq-kr-market` adapter's terminal index-close tier parses numeric KOSPI/KOSDAQ values out of the Yonhap `market.xml` RSS headlines/descriptions (`defusedxml`). When KRX (`fsc-krx-index-price`) AND Stooq are both empty for an index AND no numeric index headline is present in the feed, the index close is omitted from the body (surfaced via the coverage badge, not a hard fail). The parse is genuinely best-effort — Yonhap headlines are prose, not a structured feed, so coverage depends on whether a numeric headline happens to be published in the window. KOSDAQ is the most exposed because it has no Stooq tier (live 2026-05-24: Stooq carries no `^kosdaq` symbol), so its only fallback below KRX is this parse.
- **Suggested Fix**: Identify a dedicated free KRX index feed (a JSON/CSV/RSS path that publishes KOSPI/KOSDAQ close + 등락률 without OTP/scraping — none confirmed at u67 time, consistent with DEBT-067's `krx-option-expiry` finding) and insert it as a structured tier between Stooq and the Yonhap parse. Pin with an R10 live recording. If no structured free path is ever confirmed, keep the Yonhap parse as terminal and accept the coverage-badge degradation.
- **Effort**: ~2-3 h once a structured free KRX index path is confirmed (adapter tier + R10 fixture + precedence test); unknown if no public path exists.
- **Priority Reasoning**: Low — KRX + Stooq cover KOSPI on the hot path, and the degradation is visible (coverage badge), not silent. Promote to Medium if operations show the Yonhap terminal tier firing frequently (i.e., KRX + Stooq routinely empty on the KST-morning cron) such that KOSPI/KOSDAQ close is regularly missing for readers.

#### DEBT-069: Domestic anchor rows are close-only (no note column) — Yahoo KR history 429

- **Created**: 2026-05-24
- **Source**: u67 domestic-channel-depth closeout
- **Reference**: R15b (FX presence), FR-002 (Korean briefing comprehension), u49 (deterministic market anchor), NFR-002 (free APIs)
- **Description**: The domestic anchor table (`_build_kr_anchors_from_items` → `publisher/anchor_table.py`) renders KOSPI/KOSDAQ close + 등락률 + 원/달러 but the note column is `—` because no free intraday/history surface for KR symbols is available — Yahoo Finance KR history returned HTTP 429 on the GHA path during u67 Step 1 probing. US-equity and crypto anchors carry richer note context (52w / ATH proximity from the u49/u50 history fetch); the domestic anchor is close-only by comparison.
- **Suggested Fix**: Identify a free KR price-history source (daily OHLC lookback for KOSPI/KOSDAQ + 삼성전자/SK하이닉스 et al.) and backfill the note column with the same 52w/ATH-proximity treatment used for US/crypto. Reuse the u49/u50 anchor-history shape so the note column populates uniformly across segments. Pin with an R10 fixture for the chosen source.
- **Effort**: ~3-4 h including a reachability probe for a free KR history source, the adapter/history wire-through, and anchor-render tests.
- **Priority Reasoning**: Low — the domestic anchor already carries the most reader-relevant numbers (close + 등락률 + FX) from u67; the missing note column is an enrichment gap, not a correctness gap. Promote to Medium if a free KR history source is confirmed and the asymmetry vs US/crypto anchors becomes a reader-trust complaint.

#### DEBT-065: `og_card._wrap` word segmentation is inappropriate for Korean text

- **Created**: 2026-05-08
- **Source**: u29 site-discovery-v2 QA review (L4)
- **Reference**: FR-002 (Korean briefing comprehension), FR-003 (static web publishing)
- **Description**: `src/investo/visuals/og_card.py::_wrap` segments the conclusion line into wrapped chunks by ASCII whitespace. Korean prose typically has many fewer space boundaries per character than English, so a sparse-whitespace sentence (e.g., a long Korean clause with one space break) gets either no wrap (overflowing the OG card body) or a wrap point that lands inside a Korean phrase, plus the trailing `…` ellipsis is positioned by character count rather than by graphical width. The OG card still renders correctly for English-heavy lines but the Korean cases — which dominate the briefing surface — visibly degrade.
- **Suggested Fix**: Either (a) port a CJK-aware wrap (split on each Hangul syllable as a soft break, fall back to ASCII whitespace; account for Hangul syllable width vs ASCII char width when computing `max_chars`), or (b) replace the wrap with a `textLength` + `lengthAdjust="spacingAndGlyphs"` SVG attribute on the `<text>` element so the SVG renderer handles glyph-level spacing and overflow naturally. Option (a) gives finer control but increases code complexity; option (b) is one-line but depends on the SVG renderer respecting `lengthAdjust`. Pin with a regression test on a long Korean conclusion line.
- **Effort**: ~45 min for option (a) including the CJK soft-break logic + width estimator. Option (b) ~15 min including the SVG attribute switch + a visual regression test.
- **Priority Reasoning**: Low — the OG card still renders without crashing, but the visible truncation is imprecise on the dominant content shape. Promote to Medium once the PNG twin lands (DEBT-058), since the social-card unfurl will then surface the truncation to a much larger reader cohort.

#### DEBT-064: `_render_hero_block` markdown blockquote injection guarantee is not hard

- **Created**: 2026-05-08
- **Source**: u29 site-discovery-v2 QA review (L3)
- **Reference**: NFR-005 (consistency / contract integrity), FR-003 (static web publishing)
- **Description**: `src/investo/publisher/site_index.py::_render_hero_block` embeds the per-segment conclusion line into the `site_docs/index.md` hero quote card by wrapping it in a markdown blockquote with a trailing link (`> {conclusion}` followed by `[자세히 보기]({archive_url})`). If the archived briefing's conclusion body contains literal `]` or `)` characters — say, a parenthetical citation or a date in brackets — the surrounding markdown link parser can interpret them as link delimiters and emit malformed HTML. Today the LLM-generated conclusion bodies are unlikely to be hostile (Stage 2 prompt does not encourage parenthetical citations), but the guarantee is not hard: a future prompt edit, a future LLM regression, or an externally-edited archive entry could surface the fragility.
- **Suggested Fix**: Either (a) escape `[`, `]`, `(`, `)` inside the conclusion body before embedding (markdown backslash escapes), with a regression test exercising each character, or (b) replace the trailing link with a separate sibling line so the conclusion body is never inside a link parser scope. Option (b) is the clean structural fix; option (a) preserves the current single-line layout. Either way, pin with a parametrize regression that walks the conclusion body through each adversarial character.
- **Effort**: ~30 min for option (b) including the layout adjustment and the regression test.
- **Priority Reasoning**: Low — adversarial input is unlikely from the current LLM Stage 2 prompt path. Promote to Medium if the prompt is revised to encourage parenthetical citations or if any external archive editor is introduced.

#### DEBT-063: `_render_segment_index` `entry.parents[2]` slicing is fragile to archive restructuring

- **Created**: 2026-05-08
- **Source**: u29 site-discovery-v2 QA review (L2)
- **Reference**: NFR-005 (consistency / readability), NFR-006 (test robustness)
- **Description**: `src/investo/publisher/site_index.py::_render_segment_index` derives the relative archive path for each entry via `entry.parents[2]` slicing (effectively walking up `archive/<segment>/<YYYY>/<MM>/<YYYY-MM-DD>.md` to extract the segment / year / month). The slice depth `2` is a hard-coded structural assumption: if the archive directory layout ever changes (e.g., flatten to `archive/<segment>/<YYYY-MM-DD>.md`, or deepen with `archive/<segment>/<YYYY>/<MM>/<DD>/...`), the slice silently lands on the wrong directory and the rendered index pages emit broken links. `entry.relative_to(archive_dir)` would compute the relative path explicitly and break loudly if the structure changes.
- **Suggested Fix**: Replace `entry.parents[2]` with `entry.relative_to(archive_dir)` (where `archive_dir` is the resolved archive root). The relative path then carries the segment / year / month components without requiring knowledge of the depth, and any structural change either still works or raises `ValueError` at first call. Pin with a regression test that asserts the relative-path derivation under the current layout and one fixture-only deepened layout.
- **Effort**: ~20 min including the switch + regression test.
- **Priority Reasoning**: Low — works correctly today on the supported archive layout. Promote to Medium when an archive layout change is requested (none in flight).

#### DEBT-061: Calendar heatmap dark-mode toggle accuracy mirrors DEBT-049

- **Created**: 2026-05-08
- **Source**: u29 site-discovery-v2 QA review (TECH-DEBT P3)
- **Reference**: NFR-005 (consistency / theme parity), FR-003 (static web publishing)
- **Description**: u29's `src/investo/visuals/calendar_heatmap.py` renders a deterministic SVG that ships with the same dark-mode policy as the u26 visual cards — single SVG with embedded `<style>` carrying `@media (prefers-color-scheme: dark)`. As with DEBT-049, the SVG is referenced from markdown via `<img src="...svg">`, so the `prefers-color-scheme` query sees only the OS-level scheme and the mkdocs Material site-toggle (`data-md-color-scheme="slate"`) is invisible to the embedded heatmap. An OS-light + site-dark reader sees a heatmap rendered against the wrong scheme on `archive/index.md`. This is a cross-reference to DEBT-049, not a separate fix path — closing DEBT-049 by switching to inline `<svg>` + parent-attribute selectors (option (b) in DEBT-049) closes this item simultaneously.
- **Suggested Fix**: Resolve as part of DEBT-049 — when the visual-card render path moves to inline `<svg>` + `[data-md-color-scheme="slate"]` selectors, apply the same change to `calendar_heatmap.py`. No independent fix path; cross-reference only.
- **Effort**: ~5 min once DEBT-049 lands, to mirror the change in `calendar_heatmap.py` and add a regression test that pins the heatmap dark-mode shape under a synthesized site-toggle wrapper.
- **Priority Reasoning**: Low — same trust-degradation surface as DEBT-049 but on a less first-impression page (`archive/index.md`, not the segment briefing page). Resolves automatically when DEBT-049 is fixed.

#### DEBT-051: `WatchlistConfig` does not validate alias value cross-key collisions

- **Created**: 2026-05-08
- **Source**: u28 watchlist-usability-foundation QA review (M1)
- **Reference**: NFR-005 (consistency / contract integrity), FR-002 (Korean briefing comprehension)
- **Description**: `WatchlistConfig.aliases` accepts an arbitrary `dict[str, list[str]]` from user config. Today there is no validator that catches the case where an alias *value* collides with a different canonical *key* — e.g., a user who declares `aliases={"BTC": ("ETH",)}` is silently accepted, and any input mentioning `ETH` will be matched and labelled under both the `BTC` and `ETH` canonical entries. Reader-trust degrades because the same input string maps to two unrelated canonical assets in the same callout.
- **Suggested Fix**: Add a `model_validator(mode="after")` to `WatchlistConfig` that walks every `(canonical, alias_value)` pair and warns (or raises `ValueError` for strict mode) when `alias_value` already appears as a different canonical key in the merged `effective_aliases()` map. Pin with a parametrize test covering (a) clean config, (b) alias matches a different canonical key (rejected), and (c) alias matches the same canonical key (accepted — self-alias is harmless).
- **Effort**: ~25 min including the validator + parametrize regression test.
- **Priority Reasoning**: Low — exists today only when a user authors a colliding config by hand; the default core bundle is collision-free by construction. Promote to Medium when watchlist config grows beyond the core bundle (multiple users sharing configs, persona #4 wish-list).

#### DEBT-052: `match_watchlist_items` docstring lacks `partial` / `normal` semantics

- **Created**: 2026-05-08
- **Source**: u28 watchlist-usability-foundation QA review (M2)
- **Reference**: NFR-005 (consistency / readability), NFR-006 (test robustness)
- **Description**: `match_watchlist_items` (in `src/investo/briefing/watchlist.py`) explicitly documents the `insufficient` → coverage_hold branch but does not document the `partial` and `normal` branches. A future contributor changing `partial` semantics (e.g., to also suppress the LLM prompt context, mirroring coverage_hold) has no docstring contract to update — the contract lives only in the test fixtures and the call-site behaviour. The asymmetry will become a confusion vector once a fourth status is added.
- **Suggested Fix**: Extend the `match_watchlist_items` docstring with a "Coverage status semantics" subsection that documents what each `WatchlistImpactStatus` value means for site / LLM / Telegram surfaces. Mirror the structure already used by `summary_quality.py`'s module docstring (producer ↔ gate contract).
- **Effort**: ~10 min docs-only.
- **Priority Reasoning**: Low — works correctly today on the observed call paths; this is contract clarification for future edits.

#### DEBT-053: site cap 5 hard-coded in 4 declarations across `watchlist.py` and `cards.py`

- **Created**: 2026-05-08
- **Source**: u28 watchlist-usability-foundation QA review (M4)
- **Reference**: NFR-005 (consistency / DRY)
- **Description**: u28 raised the site watchlist match cap to 5 entries, but the value `5` is currently hard-coded in 4 places: `briefing/watchlist.py::_SITE_MAX_RENDERED_MATCHES`, `visuals/cards.py::WatchlistRelevanceCardInput.rows max_length=5`, the slice in `visuals/cards.py::build_watchlist_relevance_card`, and `briefing/watchlist.py::render_watchlist_prompt_context`. The constant exists in `briefing/watchlist.py` but `cards.py` does not import it, so a future cap change (e.g., 5 → 7 once the visual layout is widened) will land cleanly in three call sites and silently drift in the fourth.
- **Suggested Fix**: Have `cards.py` import `_SITE_MAX_RENDERED_MATCHES` from `briefing/watchlist.py` (or promote the constant to a shared `models/watchlist.py` so both `briefing` and `visuals` import from a foundation layer without crossing unit-to-unit boundaries). Replace the 3 hard-coded `5`s with the imported constant. Pin with a regression test that asserts every cap-using call path resolves to the same constant.
- **Effort**: ~25 min including the import + regression test.
- **Priority Reasoning**: Low — works correctly today at cap=5 on every surface; this is structural hardening for future cap edits.

#### DEBT-054: `WatchlistImpact` invariant `matches=()` for coverage_hold / unconfigured not enforced

- **Created**: 2026-05-08
- **Source**: u28 watchlist-usability-foundation QA review (M6)
- **Reference**: NFR-005 (consistency / contract integrity), NFR-006 (test robustness)
- **Description**: `WatchlistImpact` carries `status` and `matches` together. By construction in u28, `status="coverage_hold"` and `status="unconfigured"` always emit `matches=()` — but this is convention only; nothing in `WatchlistImpact.__post_init__` (or pydantic model validator) enforces it. A future call site that constructs a `WatchlistImpact` with `status="coverage_hold"` and a non-empty `matches` tuple would render a misleading "보류" callout that nonetheless lists matches.
- **Suggested Fix**: Add a `__post_init__` (or `model_validator(mode="after")` if migrating to pydantic) that asserts `matches == ()` when `status in {COVERAGE_HOLD, UNCONFIGURED}`. Raise `ValueError` for explicit construction violations; pin with a parametrize regression test covering each `status` value.
- **Effort**: ~20 min including the validator + parametrize test.
- **Priority Reasoning**: Low — every existing call site honours the invariant; this is structural hardening to prevent future contributors from emitting an inconsistent state.

#### DEBT-055: `WatchlistChannel` branching distributed across `watchlist`, `cards`, and `summary`

- **Created**: 2026-05-08
- **Source**: u28 watchlist-usability-foundation QA review (L1)
- **Reference**: NFR-005 (consistency / DRY), FR-003 (static web publishing), FR-004 (Telegram channel)
- **Description**: u28 introduced `WatchlistChannel` (SITE / TELEGRAM) but the site/telegram divergence heuristics still live in three modules: `briefing/watchlist.py` (`render_watchlist_prompt_context` + `_SITE_MAX_RENDERED_MATCHES`), `visuals/cards.py` (cap 5 + coverage_hold rendering), and `notifier/summary.py` (cap 3 + coverage_hold prefix strip + unconfigured skip). The channel parameter is the right *shape*, but each module re-derives "what does SITE mean here vs what does TELEGRAM mean here" instead of importing a shared adapter. Adding a fourth surface (e.g., a future RSS / atom feed) would require touching all three modules.
- **Suggested Fix**: Introduce a `WatchlistChannelAdapter` (in `briefing/watchlist.py` or a new `briefing/watchlist_channels.py`) carrying per-channel config: `max_matches`, `coverage_hold_copy`, `unconfigured_copy`, `suffix_renderer`. Each surface imports the adapter and calls into it rather than re-deriving channel semantics. Pin with a parametrize test that walks every channel through every status value.
- **Effort**: ~1 h including the adapter + 3-module migration + regression test.
- **Priority Reasoning**: Low — works correctly today on the two observed channels (SITE, TELEGRAM). Promote to Medium when a third channel is requested or when persona #4 wish-list (multi-watchlist + multi-channel under u33) lands.

#### DEBT-056: short ASCII ticker registration produces no config-load warning

- **Created**: 2026-05-08
- **Source**: u28 watchlist-usability-foundation QA review (L3)
- **Reference**: NFR-005 (consistency / readability), FR-002 (Korean briefing comprehension)
- **Description**: u28's `_matches_short_ticker` correctly handles 1-2 character ASCII tickers (case-sensitive raw token matching to avoid false positives like `AI` matching `ai` inside arbitrary words), but `WatchlistConfig` does not surface this to the user at config-load time. A user registering `tickers=["AI", "TS", "GO"]` gets the (correct) restrictive matching behaviour silently — a config-load advisory log line ("⚠️ short ticker 'AI' uses case-sensitive raw matching; consider adding `aliases={'AI': ['Artificial Intelligence']}` for keyword coverage") would help first-time authors understand the trade-off.
- **Suggested Fix**: Add a `model_validator(mode="after")` to `WatchlistConfig` that iterates `tickers` (and `assets`) and emits an advisory `_logger.warning` for each ≤ 2 ASCII entry. Do not raise — the matching is correct, just narrow. Pin with a regression test that asserts the warning fires for short ticker registration.
- **Effort**: ~20 min including the validator + log-capture test.
- **Priority Reasoning**: Low — UX hint only; matching behaviour is correct today. Promote to Medium when a user reports surprise about short-ticker matching in the field.

#### DEBT-057: `WatchlistMatch.matched_alias` exposure semantics not documented

- **Created**: 2026-05-08
- **Source**: u28 watchlist-usability-foundation QA review (L2)
- **Reference**: NFR-005 (consistency / readability), NFR-006 (test robustness)
- **Description**: `WatchlistMatch.matched_alias` carries the alias string that triggered the match (e.g., `엔비디아` for an NVDA ticker registered with the Korean alias). This metadata is used today for audit / log surfaces but is **not** displayed in the user-facing site callout, visual card, or Telegram suffix. The exposure boundary is convention; nothing in the docstring or in `WatchlistMatch` field metadata documents that `matched_alias` should not surface in reader-facing render paths. A future contributor reading `WatchlistMatch` may reasonably surface the alias in markdown as a "matched via 엔비디아" hint, which would shift the reader-facing copy semantics.
- **Suggested Fix**: Add a docstring note on `WatchlistMatch.matched_alias` documenting the audit/log-only exposure semantics, with a brief rationale ("user-facing callout names the canonical entry, not the alias path"). Pair with a regression test that asserts the rendered site / visual / Telegram surfaces never include a `matched_alias` value verbatim.
- **Effort**: ~15 min including docstring + regression test.
- **Priority Reasoning**: Low — convention is honoured today; this is contract clarification for future edits.

#### DEBT-050: `scripts/backfill_2026_05_06_visuals.py` retirement / generalisation path

- **Created**: 2026-05-08
- **Source**: u26 visual-delivery-integrity QA review (M4)
- **Reference**: NFR-005 (consistency / DRY), NFR-006 (test robustness)
- **Description**: u26 added `scripts/backfill_2026_05_06_visuals.py` as a one-shot curated backfill specific to the 2026-05-06 segmented archive entries. The script hard-codes the `2026-05-06` target date, the three card types active at that date (data-confidence / market-snapshot / watchlist-relevance), and the specific truncated quote-block lines that needed repair (`> **주의할 점**: 1.` and `> **핵심 동인**: **입법 가속화 vs.`). Reusing the script for any other date or any other truncation pattern would require code changes. Carrying it forward indefinitely creates a stale-script footprint and obscures the fact that the supported call path is `assets.insert_visual_links` on a fresh segmented publish.
- **Suggested Fix**: Either (a) delete the script around 2026-08, after the 2026-05-06 archive has aged out of the "latest" view and any reader returning to it has had several months to do so — keep the rendered assets in `archive/`, drop the script from `scripts/` — or (b) generalise into a reusable `backfill_visuals(target_date: date, segments: Sequence[str], quote_repairs: Mapping[str, str] = {}) -> BackfillReport` helper if a second backfill request appears, with parametrize tests covering at least two target dates. Option (a) is the default; option (b) is a contingency.
- **Effort**: ~5 min for option (a) (single-file delete + plan note). Option (b) ~1 h including the parametrize fixture for a second target date.
- **Priority Reasoning**: Low — the script is correct, idempotent against its target, and produced the intended 2026-05-06 artefacts. The cost of leaving it in place is purely cognitive (a future contributor reading `scripts/` may mistake it for a supported tool). Promote to Medium only if a second backfill request appears, since at that point option (b) becomes the right shape and the one-shot script becomes anti-pattern.

#### DEBT-048: `summary_quality._NUMBER_DOT_ONLY_RE` is a proper subset of `_LIST_MARKER_ONLY_RE`

- **Created**: 2026-05-08
- **Source**: u25 summary-fidelity-and-content-trust QA review (M4)
- **Reference**: NFR-005 (consistency / readability), NFR-006 (test robustness)
- **Description**: `src/investo/briefing/summary_quality.py::_NUMBER_DOT_ONLY_RE` matches the marker-only `^\d+\.$` shape, while `_LIST_MARKER_ONLY_RE` matches `^([-*]|\d+\.)\s*$` — the marker-only number is already covered by the list-marker constant. The redundant `_NUMBER_DOT_ONLY_RE` was retained intentionally for grep-ability ("which regex blocks `1.`?") at the cost of a dead constant in the reject pipeline. Tests still pass because `_LIST_MARKER_ONLY_RE` always fires first. This is dead code in the strict sense and a small readability vs. discoverability trade-off.
- **Suggested Fix**: Either (a) drop `_NUMBER_DOT_ONLY_RE` and add a `# covers ^\d+\.$ for marker-only summaries` comment to the `_LIST_MARKER_ONLY_RE` declaration so a future grep for "marker-only number" still lands on the right line, or (b) keep both but document the redundancy in the module docstring contract section so reviewers understand the duplication is intentional.
- **Effort**: ~10 min for option (a) including a parametrize test that pins `1.` rejection through `_LIST_MARKER_ONLY_RE`.
- **Priority Reasoning**: Low — purely a readability/maintainability issue with no behavioural impact today and no risk of regression (both constants reject the same shape).

#### DEBT-044: `_QUERY_REDACT_RE` over-redacts URL query strings under URL_AWARE callers

- **Created**: 2026-05-08
- **Source**: u27 secret-hygiene-unification-and-cost-guard QA review (M3)
- **Reference**: NFR-005 (consistency / explicit policy semantics), NFR-007 (R8 / R13 — secret hygiene), FR-002 (Korean briefing comprehension)
- **Description**: `src/investo/_internal/redaction.py::_QUERY_REDACT_RE` aggressively redacts URL query strings inside the `redact_text` chokepoint regardless of policy. Today the only `URL_AWARE` caller is `briefing.leak_guard.scan` via `scan_for_leak`, which does not invoke `redact_text`, so the over-redaction is **latent**. The risk surfaces the moment a future caller adopts `redact_text(..., policy=URL_AWARE)` for a markdown-excerpt rendering — every `https://example.com/path?utm_source=x` would lose its query string even though the query carried no secret. Reader-facing trust degrades silently when the rendered URL becomes lossy.
- **Suggested Fix**: Either (a) gate `_QUERY_REDACT_RE` on `policy == STRICT` so URL_AWARE callers only run the canonical secret patterns, or (b) keep the current behavior and document the caveat in the URL_AWARE docstring with a `# query-redact applies to URL_AWARE callers — pick STRICT only if your surface needs to preserve URL query strings` comment, plus a regression test pinning the URL_AWARE behavior so a future contributor explicitly sees the policy difference.
- **Effort**: ~25 min for option (a) including a parametrize test that pins STRICT vs URL_AWARE query-handling. Option (b) ~10 min docs-only.
- **Priority Reasoning**: Low — latent today (no `redact_text(URL_AWARE)` caller exists). Promote to Medium when the first markdown-excerpt URL_AWARE consumer lands, since the over-redaction degrades reader trust without raising any test failure.

#### DEBT-045: `_LONG_BASE64_RE` does not include URL-safe base64 characters

- **Created**: 2026-05-08
- **Source**: u27 secret-hygiene-unification-and-cost-guard QA review (M4)
- **Reference**: NFR-007 (R13 — no secret values in logs / errors / raw_metadata / fixtures)
- **Description**: `src/investo/_internal/redaction.py::_LONG_BASE64_RE` matches `[A-Za-z0-9+/]{40,}={0,2}` — the standard base64 alphabet only. Slack `xoxb-...` bot tokens, some shapes of GitHub fine-grained PATs, and other URL-safe oauth tokens use the URL-safe base64 alphabet (`-` and `_` instead of `+` and `/`) and slip the generic high-entropy catch-all. The shape-specific patterns earlier in `SECRET_PATTERNS` (JWT, GitHub `ghp_` / `github_pat_`, OpenAI `sk-...`) cover the most common cases, but a Slack incoming-webhook `xoxb-1234-...-...` payload can still reach a redacted-by-shape-only surface unredacted by the catch-all. The single-chokepoint architecture means the gap exists at exactly one place; recalibrating one regex closes it everywhere.
- **Suggested Fix**: Extend `_LONG_BASE64_RE` to `[A-Za-z0-9+/_-]{40,}={0,2}` and re-run the URL_AWARE false-positive surface (segment markdown excerpt) — adding `-` and `_` to the alphabet may match more legitimate URL fragments, so the regression test must validate that the existing URL_AWARE leak-guard scan still passes on the canonical positive/negative samples (existing `tests/unit/_internal/test_redaction.py` cases). If the false-positive surface widens unacceptably, narrow the catch-all by raising the length floor (e.g., 48 chars) or by requiring at least one `-` or `_` to bias toward URL-safe payloads only.
- **Effort**: ~20 min including the regex change + URL_AWARE false-positive recalibration tests.
- **Priority Reasoning**: Low — the JWT / GitHub PAT / OpenAI shape-specific patterns already cover the highest-likelihood operator-key shapes Investo touches (Telegram, FRED, OpenAI). Slack-shaped tokens are not part of Investo's secret surface today. Promote to Medium when a Slack-shaped or other URL-safe-base64 secret enters the project's env-var set.

#### DEBT-043: External image fetch builder bypass risk in `VisualProvenanceManifest`

- **Created**: 2026-05-07
- **Source**: u24 visual-provenance-and-layout QA review (L3)
- **Reference**: NFR-007 (R8 / R13 — secret hygiene), NFR-002 (no paid APIs / contract-only external image schema)
- **Description**: `build_external_provenance` in `src/investo/visuals/provenance.py` is the single sanitize hook for the `external_image` source type today. The model's `field_validator("source_attribution", "generator", "version")` does run `sanitize_provenance_text` on construction, so direct `VisualProvenanceManifest.model_validate({...source_type: "external_image"...})` calls are still sanitized. The risk is that as the field set grows (a new `crawl_target_url`, `image_alt_text`, etc.), a future contributor may add a field that needs sanitization but only update `build_external_provenance`, leaving `model_validate` callers with the unsanitized field. Today the model fields are exhaustively listed in the validator tuple, but the convention is brittle.
- **Suggested Fix**: Either (a) add a `model_validator(mode="after")` that asserts every string-typed user-/operator-derived field went through `sanitize_provenance_text` (e.g., by re-running it and comparing), or (b) document the rule in a docstring on `VisualProvenanceManifest` and add a test that walks all string-typed fields via `model_fields` and pins each one through `sanitize_provenance_text`. Option (b) is cheaper and equally robust.
- **Effort**: ~20 min for option (b).
- **Priority Reasoning**: Low — `model_validate` bypass is contract-only today (no caller exists), and the existing tuple-form `field_validator` covers every current field. The threat is field-set growth, not current behaviour.

#### DEBT-037: `_render_source_rows` silently truncates after 4 rows in SVG only

- **Created**: 2026-05-07
- **Source**: u22 source-coverage-transparency QA review (L3)
- **Reference**: NFR-005 (UX consistency between markdown and visual artefacts)
- **Description**: `src/investo/visuals/render.py::_render_source_rows` caps SVG source-row rendering at 4 entries and silently drops the rest. The corresponding markdown callout (in `src/investo/briefing/pipeline.py`) lists every source. When 5+ adapters fail in a segment, the SVG quietly hides the tail while markdown shows the full picture. Cosmetic today (the most-failed segment in tests has ≤4 sources), but a reader using only the SVG (e.g. on a device where the markdown is collapsed) misses information.
- **Suggested Fix**: Either (a) widen the SVG to render up to 8 rows with a smaller font, (b) render the first N and append a `+M more` row when truncated, or (c) accept the cap and document it in `_render_source_rows`'s docstring with a `# truncated to keep first-viewport height` comment.
- **Effort**: ~25 min for option (b) including a test that pins the `+M more` row.
- **Priority Reasoning**: Low — markdown already carries the full information; this is a visual completeness improvement, not a correctness bug.

#### DEBT-039: `CoverageReasonCode` Literal and `COVERAGE_REASON_LABELS` keys not pinned in sync by mypy

- **Created**: 2026-05-07
- **Source**: u22 source-coverage-transparency QA review (L7)
- **Reference**: NFR-005 (consistency), NFR-006 (test robustness)
- **Description**: `CoverageReasonCode` is a `Literal[...]` of allowed reason-code strings, and `COVERAGE_REASON_LABELS: dict[CoverageReasonCode, str]` carries the Korean label for each. Adding a new reason code to the Literal without adding its label to the dict raises only at runtime (when the missing key is first looked up), not at type-check time. Conversely, dropping a code from the Literal while leaving the dict entry behind passes mypy.
- **Suggested Fix**: Either (a) add an `assert_never` branch in the labelling helper so an unhandled code raises at typecheck time, (b) add a runtime assertion at module import that `set(COVERAGE_REASON_LABELS.keys()) == set(get_args(CoverageReasonCode))`, or (c) replace the Literal + dict pair with a `StrEnum` whose members carry their Korean label as a class attribute.
- **Effort**: ~20 min for option (b); ~45 min for option (c) including downstream call-site updates.
- **Priority Reasoning**: Low — the pair is in sync today and the test suite indirectly covers every label via existing reason-callout assertions; this is contract hardening for future edits.

#### DEBT-004: `_sanitize.py` depends on `bleach` (maintenance-mode)

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/sources/_sanitize.py` (Step 4)
- **Reference**: NFR-007 AC-7.2 (sanitization library)
- **Description**: `bleach>=6` is in maintenance-only mode and the maintainers have publicly recommended `nh3` (Rust-based, actively maintained) as the successor. Today bleach 6 is correct and behaves as we expect; the risk is future EOL or accumulating `DeprecationWarning`s from the underlying `html5lib`.
- **Suggested Fix**: When bleach hits EOL, replace `bleach.clean(text, tags=[], strip=True, strip_comments=True)` with `nh3.clean_text(text)` (or `nh3.clean(text, tags=set())` for HTML output). Single-function module makes the migration trivial. Update the pipeline so HTML entities still decode and whitespace still collapses.
- **Effort**: ~30 min including test updates and verifying nh3 entity-decoding behavior.
- **Priority Reasoning**: Low — the project's only sanitization need is plain-text output; bleach 6 is fine for v1. Watch for EOL announcements or CI deprecation warnings.

---

## Resolved Items

#### DEBT-062: `_stage_publish_segments` archive-paths absolute / relative branching couples production code to test shape

- **Created**: 2026-05-08
- **Resolved**: 2026-06-25 (u121 publish-archive-path-normalization) — Added `publisher.paths.normalize_archive_publish_path(...)` and normalized every `write_briefing` return immediately inside `_stage_publish_segments`. Absolute paths under the active archive root now become the same repo/archive-relative shape as production before index, heatmap, OG-card, quality, forecast, watchlist, monthly, and weekly side effects run. Absolute paths outside the archive root raise `PublisherIOError` through the publish stage. The old `all(not path.is_absolute())` branch was removed, and the publish side-effect test helper now returns absolute paths so tests exercise the normalization path directly.
- **Source**: u29 site-discovery-v2 QA review (L1)
- **Reference**: NFR-005 (consistency / contract integrity), NFR-006 (test robustness)
- **Description**: `src/investo/orchestrator/pipeline.py::_stage_publish_segments` used to branch on whether publisher archive paths were absolute or relative, causing tests with absolute paths to skip index/heatmap/OG/weekly side effects. u121 closes this by normalizing once at the publish boundary.
- **Suggested Fix**: Resolved by option (a): normalize archive paths to relative-to-archive-root before downstream side effects.
- **Effort**: Completed in u121.
- **Priority Reasoning**: Closed.

#### DEBT-074: §⑥ watchpoint-matrix clause-slotting heuristic can under-populate trigger columns — plumb typed evidence

- **Created**: 2026-05-24
- **Resolved**: 2026-05-31 (u87 watchpoint-matrix-rehabilitation) — Closed by attacking the under-population at its two real causes rather than the typed-evidence plumbing originally suggested. (i) The **Stage-2 §⑥ prompt** (`briefing/prompts.py`) now mandates the `source + (상방/하방) trigger + implication` shape per bullet — the exact shape `_is_structured` requires — with one populatable example and one rejected-fragment example, so real bullets populate non-`데이터부족` rows. (ii) `publisher/watchpoint_matrix.py::render_watchpoint_matrix` now (a) pre-filters non-observation lines (trace-footer `input_hash`/`stage1_hash`/`stage2_hash` diagnostics, bare-link/pure-symbol bullets) via `_is_observation_bullet` + `_DIAGNOSTIC_LINE_RE` before row building (AC-87.1), (b) hardens `_short_signal` to unwrap markdown links (`_MD_LINK_RE`, AC-87.2 — also applied at `_escape_cell` so every cell is URL-fragment-free) and trim a dangling Korean particle (`_TRAILING_PARTICLE_RE`, AC-87.3), and (c) **collapses** an all-`데이터부족` (or empty) result to a single pinned `DATA_LIMITED_NOTE` blockquote instead of rendering a ≥2-row wall of `데이터부족` (AC-87.4). The u64 `_is_structured` contract and the closed `{높음,보통,낮음,데이터부족}` enum are reused unchanged; a structured bullet still populates a row (AC-87.5). The transform stays pure `str -> str`, idempotent for both the matrix-header and `DATA_LIMITED_NOTE` states, and byte-preserves everything outside §⑥ + the disclaimer (AC-87.7). The data-limited WARN log (`watchpoint_matrix.data_limited_rows`) is preserved and additionally fires (count = total bullets) when the collapse triggers, so operators still see under-population. The originally-suggested typed-evidence enrichment remains a valid *future* upside but is no longer required to close the reader-facing defect. Pinned by `tests/unit/publisher/test_watchpoint_matrix.py` (seven AC-87 defect-shape fixtures) + `tests/unit/briefing/test_prompts.py` (§⑥ rule assertion). Unit summary: `aidlc-docs/construction/u87-watchpoint-matrix-rehabilitation/code/summary.md`.
- **Source**: u72 watchpoint-action-matrix closeout (clause-slotting risk), escalated by the 2026-05-26 briefing review.
- **Reference**: AC-72.1 (bounded matrix fields), AC-72.3 (rows consume verified anchors/carryover/watchlist evidence without inventing facts), AC-87.1..87.7, NFR-005 (consistency), NFR-007 (R10 — no fabrication)

#### DEBT-059: `INVESTO_PUBLISH_WEEKLY` env-var keyed via byte-identical schedule match is fragile

- **Created**: 2026-05-08
- **Resolved**: 2026-05-14 — Added `scripts/resolve_weekly_flags.py` so the daily-briefing workflow derives `INVESTO_PUBLISH_WEEKLY` and `INVESTO_WEEKLY_OPS_DIGEST` from scheduled-run KST wall-clock intent (`schedule` event during Asia/Seoul Saturday 09:00) instead of comparing the exact cron string. `workflow_dispatch` remains opt-out by default. Regression tests pin Saturday/non-Saturday/manual-dispatch behavior, `GITHUB_ENV` output, and the absence of the old `github.event.schedule == '0 0 * * 6'` expression in `.github/workflows/daily-briefing.yml`.
- **Source**: u29 site-discovery-v2 QA review (TECH-DEBT P2)
- **Reference**: NFR-003 (graceful degradation), NFR-005 (consistency / explicit policy semantics), FR-003 (static web publishing)

#### DEBT-046: `_SEGMENT_MARKET_TZ` single source-of-truth across briefing and sources

- **Created**: 2026-05-08
- **Resolved**: 2026-05-14 — Added `src/investo/models/segments.py` as the foundation-layer source of truth for `MarketSegment`, `SEGMENT_MARKET_TZ`, and `SEGMENT_MARKET_TZ_LABEL`. `briefing/pipeline.py`, `sources/aggregator.py`, `models/market_calendar.py`, and `briefing/segments.py` now import the shared catalog instead of redeclaring market-clock mappings. Regression coverage asserts that the reader-facing timestamp watermark uses the same UTC window as `_window_for_adapter` for representative domestic-equity, us-equity, and crypto sources.
- **Source**: u25 summary-fidelity-and-content-trust QA review (M1)
- **Reference**: NFR-005 (consistency / DRY across module boundaries), FR-008 (segmented briefing), FR-003 (static web publishing)

#### DEBT-066: `*.svg.json` provenance manifest sidecars not enumerated in `asset_paths`

- **Created**: 2026-05-08
- **Resolved**: 2026-05-14 — The segmented visual asset stage now adds each generated asset's provenance manifest sidecar to the publish/rollback path set after `prepare_segment_visual_assets` writes the SVG/PNG/JPG. Regression coverage pins both `git add` inclusion for `*.svg.json` and rollback removal for summary-quality failures. The same recovery slice also hardened `commit_and_push` so stdout-only git diagnostics are logged and duplicate target-date publishes with only untracked files are treated as successful no-ops.
- **Source**: u29 site-discovery-v2 developer self-review
- **Reference**: NFR-003 (graceful degradation), NFR-005 (consistency / contract integrity), NFR-007 (R13 — secret hygiene)

#### DEBT-058: OG image PNG twin generation for social-card unfurl

- **Created**: 2026-05-08
- **Resolved**: 2026-05-09 — u38 landed the cairosvg path: `visuals/og_card.py` writes `assets/og-card.png` beside the SVG, both assets receive provenance sidecars, `overrides/main.html` advertises PNG as primary `og:image` with SVG retained as secondary `og:image:secure_url`, and `.github/workflows/daily-briefing.yml` installs/preflights libcairo/cairosvg before the runtime publish. Unit summary: `aidlc-docs/construction/u38-og-card-png-twin/code/summary.md`.
- **Source**: u29 site-discovery-v2 QA review (H2 / M5)
- **Reference**: FR-003 (static web publishing), NFR-005 (consistency / reader-trust contract)
- **Description**: u29 emitted an OG image meta tag pointing at `https://murphygo.github.io/investo/assets/og-card.svg`. The major OG consumers — Telegram, Slack, Twitter / X, and LinkedIn — do not reliably honour SVG `og:image` payloads, so social-card unfurl needed a PNG twin.

#### DEBT-060: Conclusion prefix / extraction helper duplicated 5x across publisher, visuals, and briefing

- **Created**: 2026-05-08
- **Resolved**: 2026-05-08 — 5 surface (`publisher/site_index.py`, `publisher/weekly_digest.py`, `visuals/og_card.py`, `visuals/assets.py`, `briefing/context.py`) 가 모두 새 chokepoint `briefing/extract.py` 위로 통합. 6번째 consumer 등장 시 `tests/unit/briefing/test_extract.py::test_no_surface_redeclares_prefix_literal` grep guard 가 즉시 fail. Phase 0 of u35 event-lookahead landed `briefing/extract.py` (`extract_conclusion`, `extract_key_drivers`, `extract_caution`, `extract_watermark`) plus public `CONCLUSION_PREFIX` / `DRIVER_PREFIX` / `CAUTION_PREFIX` / `WATERMARK_PREFIX` exports on `briefing/summary_quality.py`; all 5 sites switched to chokepoint imports and the local prefix literals were removed.
- **Source**: u29 site-discovery-v2 QA review (M4)
- **Promoted**: 2026-05-08 — Medium → **High** by u34 recent-briefings-context cross-check (DEBT-060 priority reasoning explicitly identified "fifth consumer lands" as the promotion trigger; that condition was met when `briefing/context.py` landed as the fifth consumer). Resolved by u35 Phase 0 the same day before any sixth consumer could land.
- **Reference**: NFR-005 (consistency / DRY), FR-003 (static web publishing), FR-002 (Korean briefing comprehension)
- **Description**: u29 added three new conclusion-extraction call sites — `src/investo/publisher/site_index.py` (`_render_hero_block`), `src/investo/publisher/weekly_digest.py` (per-segment 5-day list), `src/investo/visuals/og_card.py` (OG card body) — each of which duplicated the conclusion-prefix matching logic already present in `src/investo/visuals/assets.py`. u34 then introduced a fifth call site at `src/investo/briefing/context.py` (recent-briefings-context loader's `_CONCLUSION_PREFIX` / `_DRIVER_PREFIX` / `_WATERMARK_PREFIX` local literals). The five sites agreed by inspection but a future change to any of the prefix markers would have landed in only one site by default and the rendered hero / weekly digest / OG card / visual card / Stage 2 recent-context block would have silently disagreed — directly inverting the reader-trust contract.

#### DEBT-035: Bot-token / chat-id redaction regex duplicated across `__main__` and `models/coverage`

- **Created**: 2026-05-07
- **Resolved**: 2026-05-08 — Extracted into `src/investo/_internal/redaction.py` (u27). Both `__main__._redact_diagnostic_text` and `models.coverage.sanitize_source_error_message` now delegate to `redact_text(..., policy=RedactionPolicy.STRICT)`; the bot-token / chat-id regexes live in a single `SECRET_PATTERNS` tuple and cannot drift. Pinned by `tests/unit/_internal/test_redaction.py::TestSingleSourceOfTruth::test_main_redaction_does_not_carry_local_regex_module` (scans `__main__.py` for any reintroduced `re.compile` with a bot-token-shaped literal).
- **Source**: u22 source-coverage-transparency QA review (L1)
- **Reference**: NFR-007 (R13 — no secret values in logs / errors / raw_metadata / fixtures), NFR-005 (DRY constants across module boundaries)
- **Description**: Two redaction regexes for the bot-token / chat-id shape lived in two places with **non-identical** patterns:
  - `src/investo/__main__.py::_redact_diagnostic_text` used `\b\d{6,}:[A-Za-z0-9_-]{20,}\b`.
  - `src/investo/models/coverage.py::sanitize_source_error_message` used `(?<![\d:])\d{6,}:[A-Za-z0-9_-]{20,}(?![\w-])`.
  The patterns differed on word-boundary handling (lookaround vs `\b`), so a borderline payload could be redacted by one site and not the other.

#### DEBT-036: `_SECRET_ENV_VARS` set is wider than the `__main__._redact_diagnostic_text` literal list

- **Created**: 2026-05-07
- **Resolved**: 2026-05-08 — Replaced `__main__`'s 4-name literal list with `redact_text` (u27 chokepoint), which iterates the project-wide `SECRET_ENV_VARS` tuple (6 names including `OPENAI_API_KEY` and `FRED_API_KEY`). New env vars onboarded via the chokepoint propagate to every redaction surface automatically. Pinned by `tests/unit/_internal/test_redaction.py::TestSingleSourceOfTruth::test_secret_env_vars_covers_known_secrets`.
- **Source**: u22 source-coverage-transparency QA review (L2)
- **Reference**: NFR-007 (R13 — secret hygiene), NFR-005 (consistency)
- **Description**: `_SECRET_ENV_VARS` (in `models/coverage.py`) covered 6 env vars, but `__main__._redact_diagnostic_text`'s in-line redacted-name set covered only 4. New secrets risked landing in `_SECRET_ENV_VARS` without the matching update to `_redact_diagnostic_text`, leaving Step Summary output exposed.

#### DEBT-042: Sanitizer policy unification across coverage / provenance / leak-guard

- **Created**: 2026-05-07
- **Resolved**: 2026-05-08 — `src/investo/_internal/redaction.py` (u27) is the single sanitizer chokepoint. The four call sites (`__main__._redact_diagnostic_text`, `models.coverage.sanitize_source_error_message`, `visuals.provenance.sanitize_provenance_text`, `briefing.leak_guard.scan`) all delegate to `redact_text` (STRICT) or `scan_for_leak` (URL_AWARE precedence) — a single named-policy enum (`RedactionPolicy.STRICT` vs `URL_AWARE`) makes the (small, intentional) policy difference explicit. Adding a fifth surface picks one of the two entry points and inherits the full pattern set automatically. Pinned by `tests/unit/_internal/test_redaction.py::TestSurfacesShareChokepoint` which cross-tests every canonical secret shape against every surface.
- **Source**: u24 visual-provenance-and-layout QA review (L2)
- **Reference**: NFR-005 (consistency across symmetric components), NFR-007 (R8 / R13 — secret hygiene)
- **Description**: `sanitize_source_error_message` (from u22) had 3 call-site locations — coverage badge, visual provenance sanitizer, and `__main__._redact_diagnostic_text`. On top of those, `briefing.leak_guard` carried its own pattern set. Pattern drift across these 4 sites threatened R13 secret hygiene as new surfaces and patterns landed.

#### DEBT-024: `astral-sh/setup-uv@v3` not pinned to a SHA in either workflow

- **Created**: 2026-05-01
- **Resolved**: 2026-05-04 — Replaced both `astral-sh/setup-uv@v3` workflow references with the peeled `v3` commit SHA `caf0cab7a618c569241d31dcd442f54681755d39` and kept a `# v3` trailing comment for reviewability. Added `.github/dependabot.yml` with weekly `github-actions` updates so action pins stay visible and maintainable.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L4)
- **Reference**: NFR-007 baseline (supply-chain hygiene)
- **Description**: Both `.github/workflows/daily-briefing.yml:95` and `pages.yml:72` use `astral-sh/setup-uv@v3` — major-version pin. A compromised v3 release could exfiltrate the 5 GitHub Secrets injected via `env:`. For a 1-person tool with no untrusted contributors the supply-chain risk is minimal, but pinning to a SHA per the canonical GitHub-recommended pattern would tighten the boundary.
- **Suggested Fix**: Replace both `@v3` references with `@<full-sha>`. Add a Dependabot config (`.github/dependabot.yml`) so the SHA stays current.
- **Effort**: ~15 min including Dependabot setup.
- **Priority Reasoning**: Low — see "1-person tool" above. Re-evaluate if the project ever onboards external contributors or stores higher-value secrets.

#### DEBT-006: `call_claude_code` cancellation does not stop the worker thread

- **Created**: 2026-04-29
- **Resolved**: 2026-05-04 — Closed after u5 orchestrator re-evaluation. `_stage_generate` awaits u2's async `generate_briefing` directly, `run_pipeline` does not wrap stage calls in `asyncio.wait_for`, and `tests/unit/orchestrator/test_run_pipeline.py::test_pipeline_source_has_no_asyncio_wait_for_on_stages` statically pins that contract. With no stricter outer cancellation wrapper around `call_claude_code`, the remaining `asyncio.to_thread(subprocess.run, timeout=...)` behavior is bounded by the existing per-call timeout and does not need the larger async-subprocess refactor.
- **Source**: Code review of `src/investo/briefing/claude_code.py` (Step 6 sub-agent M1)
- **Reference**: NFR-001 (≤10 min), NFR-003 (graceful degradation); FD R3 (per-call timeout)
- **Description**: `call_claude_code` uses `asyncio.to_thread(subprocess.run, ...)`. If the awaiting coroutine is cancelled (e.g. an upstream `asyncio.wait_for` enforces a stricter deadline than the per-call timeout), the `CancelledError` propagates to the awaiter but the inner thread continues running until `subprocess.run`'s own `timeout=` fires. During that window, the spawned `claude` child process is still alive. For u2's bounded use (per-call ≤120 s), this is acceptable — the kernel reaps the child when `subprocess.run` raises `TimeoutExpired` inside the orphaned thread — but it could matter when u5 orchestrator wraps `generate_briefing` in its own `wait_for`.
- **Suggested Fix**: Switch to `asyncio.create_subprocess_exec("claude", "-p", prompt, stdout=PIPE, stderr=PIPE)` for true async cancellation (sends SIGTERM/SIGKILL to the child on cancellation). Trade-off: changes the runner-seam Protocol shape (no more `subprocess.run` signature compatibility); `FakeClaudeRunner` would need a parallel async-mode entry point. Defer until u5 orchestrator's `wait_for` wrapping is finalized.
- **Effort**: ~2 hours including FakeClaudeRunner refactor + test migration.
- **Priority Reasoning**: Low — orchestrator does not currently wrap `call_claude_code` in `wait_for` (the per-call timeout is enforced by `subprocess.run` itself, not asyncio). When u5 lands and the wrapping pattern is concrete, re-evaluate; if u5 takes the simpler "no outer wait_for, trust the inner timeout" path, this can be closed without action.

#### DEBT-003: `retry_get` 5 MB body cap is post-hoc, not streaming

- **Created**: 2026-04-27
- **Resolved**: 2026-05-04 — Switched `retry_get` from `client.get()` to `client.stream("GET", ...)` for successful responses. The helper now rejects oversized `Content-Length` before reading the body, enforces the cap while accumulating `aiter_bytes()`, and returns a fully buffered synthetic `httpx.Response` so adapter callers keep the same surface. Added tests that prove the body is not read when `Content-Length` already exceeds the cap and that no-length streams abort once the running total crosses the cap.
- **Source**: Code review of `src/investo/sources/_retry.py` (Step 3)
- **Reference**: NFR-007 AC-7.1 (5 MB response body cap)
- **Description**: `retry_get` checks `len(response.content) > max_response_bytes` after `httpx.AsyncClient.get()` has already buffered the full body into memory. A hostile server returning a 100 MB payload would briefly hold 100 MB resident before the cap fires. Acceptable for v1 because the only adapter (FOMC RSS, Step 8) returns < 200 KB; would matter if a future adapter pulled larger feeds or hit a hostile endpoint.
- **Suggested Fix**: Switch to `client.stream("GET", url)` and (a) reject up-front if `Content-Length` header exceeds the cap, (b) accumulate via `aiter_bytes()` and abort once the running total exceeds the cap. Trade-off: streaming requires constructing a synthetic `httpx.Response` to return, since downstream callers expect a fully-buffered response.
- **Effort**: ~1 hour including test updates (need a streaming MockTransport response).
- **Priority Reasoning**: Low — the threat is "hostile server returning huge body", which is unlikely against the curated free-tier endpoints `u1` consumes. Re-evaluate when a non-RSS adapter (e.g. JSON market data) lands.

#### DEBT-005: Aggregator log line is printf-style, not structured

- **Created**: 2026-04-27
- **Resolved**: 2026-05-04 — Changed `fetch_all` source-failure logging to `_logger.warning("source failed", extra={...})` with `source_name`, `category`, `error`, and `transient` fields. The structured log keeps the existing debugging contract by using the `SourceFetchError` self-reported `source_name` while taking `category` from the registered adapter. Updated unit and integration assertions to inspect `LogRecord` fields instead of rendered printf text.
- **Source**: Code review of `src/investo/sources/aggregator.py` (Step 7)
- **Reference**: FD `business-logic-model.md` L5 (logging contract — "structured fields"), NFR-007 baseline
- **Description**: `_logger.warning("source %s failed: %s (transient=%s)", ...)` is a printf approximation of L5's structured-fields requirement (`source_name`, `category`, `error`, `transient`). It's grep-friendly but not JSON-parseable. The rest of the codebase has no structured-logging convention yet (NFR AC-D.4 explicitly defers metrics + structured logs to v2 / future ADR).
- **Suggested Fix**: When the project adopts structured logging (likely as part of an operations ADR), migrate to `_logger.warning("source failed", extra={"source_name": ..., "transient": ..., "category": ..., "error": str(result)})`. Update any test that assert on log message format.
- **Effort**: ~30 min including test updates and verifying the chosen logging adapter (stdlib logging + JSON formatter, structlog, etc.).
- **Priority Reasoning**: Low — printf logs are fine for a 1-person operator using `journalctl` / `gh actions logs`. Re-evaluate when remote log aggregation enters the picture.

#### DEBT-011: Integration PoC bypasses `aggregator.fetch_all`

- **Created**: 2026-04-30
- **Resolved**: 2026-05-04 — Updated `tests/integration/test_briefing_pipeline_poc.py` to call `aggregator.fetch_all(_TARGET_DATE)` with `aggregator.list_sources` patched to two controlled adapters: one wraps the recorded FOMC fixture through `FomcRssAdapter`, and one raises `SourceFetchError`. The test now pins registry-driven fan-out, failure isolation, warning-log behavior, and u1→u2 briefing generation in the same PoC.
- **Source**: Step 9.5 sub-agent code review (M2 / Q4)
- **Reference**: u1 R6 (failure isolation), u1 L5 (warning-log contract), FD L9 (PoC integration scope)
- **Description**: `tests/integration/test_briefing_pipeline_poc.py` calls `FomcRssAdapter().fetch(client, window)` directly via `httpx.MockTransport`, bypassing `investo.sources.fetch_all`. Consequences: (a) the aggregator's `gather(return_exceptions=True)` failure-isolation contract is not exercised end-to-end — covered only by u1's unit tests; (b) registry-driven adapter discovery is bypassed; (c) the warning-log behavior on adapter failures is not cross-unit-pinned. Today FomcRss is the only registered adapter so the impact is minimal, but this is a brittle assumption that widens silently as u1 grows.
- **Suggested Fix**: Once a second u1 adapter exists (e.g., a price feed or earnings calendar), upgrade the integration test to call `fetch_all(target_date)` and use `monkeypatch` to control adapter responses (one returns FOMC fixture data, one raises `SourceFetchError`). Verify the failed adapter contributes `[]` and the briefing still generates from the remaining items.
- **Effort**: ~45 min including the second-adapter mock setup. Cannot land before u1 has a second adapter.
- **Priority Reasoning**: Low — the contract being uncovered is u1's, which has its own unit tests. The integration test still exercises u1→u2 wiring for the only adapter that currently exists. Re-evaluate when a second adapter is added.

#### DEBT-014: u4 BriefingPublisher uses `parse_mode="Markdown"` without escape fallback

- **Created**: 2026-04-30
- **Resolved**: 2026-05-04 — `BriefingPublisher.send` now retries Telegram `"can't parse entities"` failures once with `parse_mode=None`, allowing malformed LLM Markdown to publish as plain text instead of failing the public-channel send. `_telegram.send_message` omits `parse_mode` when callers pass `None`, and unit tests pin both the retry and the no-retry behavior for unrelated API errors.
- **Source**: Step 7 sub-agent code review of u4 notifier (L3 / TD-N01)
- **Reference**: FR-004 (Telegram channel), NFR-003 (graceful degradation)
- **Description**: `BriefingPublisher.send` and `OperatorAlerter.alert` both pass `parse_mode="Markdown"` to the Telegram API. If the LLM-generated `briefing.market_summary` (or formatted alert text) contains an unbalanced `*` or `_`, or unescaped `[`, Telegram returns 400 with `"can't parse entities..."` which we encode as `SendResult(ok=False)`. The pipeline degrades gracefully — but the public-channel publish silently fails until an operator notices. The current prompt template doesn't specifically instruct the LLM to avoid Markdown footguns.
- **Suggested Fix**: One of (in order of effort):
  1. Document the failure mode in the prompt template (cheapest).
  2. Add a `parse_mode=None` retry in `BriefingPublisher.send` when the API returns "can't parse entities" — the briefing publishes as plain text instead of failing.
  3. Switch to `parse_mode="MarkdownV2"` and escape the body with a vetted helper (heaviest; loses some readability).
- **Effort**: Option 2 ~1 hour including tests; option 1 trivial; option 3 ~3 hours.
- **Priority Reasoning**: Low — graceful-degradation already covers the failure (operator alert fires when the publish step's `SendResult.ok=False` lands). No silent data loss. Re-evaluate when the first real Markdown-parse failure occurs in production.

#### DEBT-027: Windows checkout symlink limitation undocumented

- **Created**: 2026-05-01
- **Resolved**: 2026-05-04 — Added a `CONTRIBUTING.md` cross-platform note documenting the `site_docs/archive` symlink, the Windows `core.symlinks=true` plus Developer Mode/admin requirement, and the expected local MkDocs symptom when symlinks are checked out as plain text files.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (Q9)
- **Reference**: NFR-005 (cross-platform clarity)
- **Description**: `site_docs/archive` is a git symlink (mode 120000) → `../archive`. Linux runners (GHA `ubuntu-latest`) and macOS dev environments handle it natively. Windows checkouts require `core.symlinks=true` AND either developer mode enabled OR admin privileges. Investo runs on Linux only (GHA + macOS-dev), so this is fine in practice; if a Windows contributor ever appears they'll see the symlink as a regular file containing the literal text `../archive`.
- **Suggested Fix**: Add a "Cross-platform notes" section to CONTRIBUTING.md documenting the symlink limitation, OR migrate to a non-symlink solution (e.g., mkdocs-monorepo-plugin or post-build copy). Re-evaluate when a Windows contributor surfaces.
- **Effort**: ~10 min docs edit; ~1 hour for full migration.
- **Priority Reasoning**: Low — Investo is a 1-person Linux/macOS tool; Windows is hypothetical.

#### DEBT-034: `_mock_client` test helper duplicated across 5 news-adapter test files

- **Created**: 2026-05-01
- **Resolved**: 2026-05-04 — Added shared `tests/unit/sources/_mock_transport.py::mock_client()` for source adapter tests, including optional request capture for the SEC User-Agent pin. Updated Yahoo Finance, SEC EDGAR 8-K, Yonhap Market, The Block Crypto, and CNBC Top News tests to import the shared helper instead of carrying local `httpx.MockTransport` wrappers.
- **Source**: Phase 4 cross-cutting qa review of u1 sources Extension #3 (L4)
- **Reference**: NFR-006 (test-suite/source maintainability)
- **Description**: A `_mock_client(body, status=200)` test helper appears in 5 news-adapter test files: `test_yahoo_finance_news.py`, `test_sec_edgar_8k.py`, `test_yonhap_market.py`, `test_theblock_crypto.py`, `test_cnbc_top_news.py`. The bodies differ only by content-type header value (`application/rss+xml` vs `application/atom+xml` vs `text/xml`); the SEC variant additionally captures the outgoing request to assert the User-Agent header (R14 test). Five copies of a small but non-trivial httpx `MockTransport`-wrapping helper — a clear consolidation target.
- **Suggested Fix**: Extract a shared `tests/unit/sources/_mock_transport.py` helper exporting `mock_client(body: bytes | str, status: int = 200, content_type: str = "application/rss+xml", capture_requests: bool = False)`. Returns `httpx.AsyncClient` plus optionally a `list[httpx.Request]` capture sink. Update all 5 test files to import. SEC's UA-pin test uses `capture_requests=True`.
- **Effort**: ~25 min including the new helper + 5 test-file import updates + verification all 5 test files still green. Test-code only — no production-code touch.
- **Priority Reasoning**: Low — test code only, not production; works correctly today; cleanup pays off when the 6th news adapter lands or when the underlying httpx test API ever changes (single update site vs five). Pairs naturally with DEBT-016 (`_mock_client` duplicated across 3 u4 test files) — both could be resolved together via a shared `tests/_helpers/mock_transport.py` if the lead chooses to widen scope.

#### DEBT-010: u2 briefing test helpers duplicated across 4 files

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Added shared `tests/_helpers/briefing_pipeline.py` for valid Stage 1 classification stdout and Stage 2 markdown payloads. Moved the unit briefing zero-backoff autouse fixture into `tests/unit/briefing/conftest.py`. Updated the three u2 unit files and the integration PoC to consume the shared helpers.
- **Source**: Step 9.5 sub-agent code review (L1 / Q8)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `_valid_classification_stdout(item_count)` was copied across 4 files, `_valid_stage2_markdown()` was duplicated in 2 files, and `_zero_backoff` appeared in 2 unit files.
- **Suggested Fix**: Consolidate shared helpers and the zero-backoff fixture so future prompt/output shape changes have one update site.
- **Effort**: ~30 min including import updates and verifying no fixture-name collisions.
- **Priority Reasoning**: Low — defensive duplication; all tests already passed.

#### DEBT-013: u3 publisher test `_build_briefing` fixture duplicated

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Added shared `tests/_helpers/briefings.py::build_briefing()` plus `DEFAULT_TARGET_DATE`, then updated publisher unit and integration smoke tests to use the shared builder. The helper keeps the explicit `model_construct` path for malformed disclaimer fixtures.
- **Source**: Step 8 sub-agent code review of u3 publisher (M3 finding)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `_build_briefing()` helper lived in both `tests/unit/publisher/test_writer.py` and `tests/integration/test_publisher_smoke.py`.
- **Suggested Fix**: Lift to a shared test helper so both unit and integration tests can import it.
- **Effort**: ~20 min.
- **Priority Reasoning**: Low — defensive duplication; all tests already passed.

#### DEBT-016: `_mock_client` test helper duplicated across 3 u4 test files

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Replaced the three u4 notifier-local `_mock_client(handler)` helpers with shared `tests/unit/notifier/conftest.py::mock_client()`, then updated telegram, briefing publisher, and operator alerter tests to import the helper.
- **Source**: Step 7 sub-agent code review of u4 notifier (L5 / TD-N04)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: Three near-identical `_mock_client(handler)` helpers lived in `test_telegram.py`, `test_briefing_publisher.py`, and `test_operator_alerter.py`.
- **Suggested Fix**: Move `_mock_client` to `tests/unit/notifier/conftest.py` as a module-level helper, then import from each test file.
- **Effort**: ~10 min.
- **Priority Reasoning**: Low — defensive duplication; all tests already passed.

#### DEBT-015: `_TrackingClient` test pattern fragile to httpx version changes

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Replaced the `httpx.AsyncClient` subclass-based tracking test with a `MagicMock` factory that returns a MockTransport-backed client and asserts `timeout=30.0` from `call_args`.
- **Source**: Step 7 sub-agent code review of u4 notifier (L1 / TD-N03)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `test_briefing_publisher_creates_default_client_when_http_none` subclassed `httpx.AsyncClient`, coupling the test to httpx constructor internals.
- **Suggested Fix**: Replace with a factory-mock pattern.
- **Effort**: ~30 min including verifying the new test still pins the timeout contract.
- **Priority Reasoning**: Low — only mattered at httpx upgrade time, but was cheap to harden.

#### DEBT-030: SEC accession-number extraction uses regex on summary instead of canonical `<id>`

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Changed `SecEdgar8kAdapter` to parse `raw_metadata["accession_no"]` from the canonical Atom `<id>` `accession-number=...` payload first, with the existing summary `AccNo:` regex retained as a defensive fallback. Added synthetic tests for canonical-id precedence and summary fallback.
- **Source**: Phase 3 cross-cutting qa review of u1 sources Extension #2 (M2 / Developer self-flag #2)
- **Reference**: R8 (NormalizedItem field rules — `raw_metadata` provenance), R10 (test fixtures)
- **Description**: `sec_edgar_8k.py` extracted `raw_metadata["accession_no"]` by regex on the HTML-stripped summary text even though SEC's Atom feed exposes the accession number canonically in `<id>`.
- **Suggested Fix**: Switch to `<id>` parsing first and keep the regex on summary as fallback if `<id>` is missing.
- **Effort**: ~15 min code change + tests.
- **Priority Reasoning**: Low — current path worked on the recorded fixture; this removes a future-fragile dependency on summary HTML shape.

#### DEBT-025: `ConfigError.missing_vars` overloaded for "malformed value" case

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Added `ConfigError.bad_value_var` plus `ConfigError.for_bad_value()` for present-but-malformed env vars. Updated malformed `SITE_URL_BASE` and `INVESTO_TARGET_DATE` paths to use the new discriminator while leaving `missing_vars` reserved for absent required vars.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L6 — surfaced by the INVESTO_TARGET_DATE side-quest)
- **Reference**: NFR-005 (clarity / discriminator integrity)
- **Description**: `_resolve_target_date_override()` reported a present-but-malformed `INVESTO_TARGET_DATE` through `missing_vars`, blurring the original absent-var discriminator.
- **Suggested Fix**: Add `bad_value_var: str | None = None` field to `ConfigError` and a factory for malformed values.
- **Effort**: ~20 min including factory + tests.
- **Priority Reasoning**: Low — operator alert text was already actionable; this tightens the internal error contract.

#### DEBT-018: AST-grep deny tests use substring matching instead of callable identity

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Replaced substring checks with AST callable-identity helpers that only match calls to the explicit stage-runner whitelist (`_stage_collect`, `_stage_generate`, `_stage_publish`, `_stage_notify_briefing`).
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L4)
- **Reference**: NFR-006 (test robustness)
- **Description**: `tests/unit/orchestrator/test_run_pipeline.py`'s 3 AST-grep deny tests used `"_stage_"` substring matching against `ast.unparse` output, making them brittle to future stage function renames.
- **Suggested Fix**: Replace substring match with callable-identity match.
- **Effort**: ~20 min.
- **Priority Reasoning**: Low — current tests worked; this future-proofs the static contract.

#### DEBT-017: `_TRACEBACK_EXCERPT_MAX_CHARS` duplicated between `pipeline.py` and `models/results.py`

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Promoted the model limit to public `TRACEBACK_EXCERPT_MAX` in `investo.models.results` and updated the orchestrator truncation helper/tests to use the shared constant without widening the package-root `investo.models` public API.
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L1)
- **Reference**: NFR-005 (maintainability — DRY constants across module boundaries)
- **Description**: `pipeline.py` and `models/results.py` both carried the traceback excerpt limit as separate 2000-char constants. Drift would make `FailureContext` construction fail from the orchestrator's catch site.
- **Suggested Fix**: Promote one to a public constant and import it in `pipeline.py`.
- **Effort**: ~5 min.
- **Priority Reasoning**: Low — no current drift, but future edits had an obscure failure mode.

#### DEBT-009: `_executable_source` AST helper is duplicated across two test files

- **Created**: 2026-04-29
- **Resolved**: 2026-05-03 — Added shared `tests/_helpers/ast_helpers.py::executable_source()` and updated both briefing source-shape test files to import it instead of carrying duplicate helper bodies.
- **Source**: Step 8.5 sub-agent code review (L1 / Q8); also flagged in the Step 8.4 docstring
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: The `_executable_source(module)` helper appeared verbatim in `tests/unit/briefing/test_claude_code.py` and `tests/unit/briefing/test_pipeline_no_prompt_strings.py`.
- **Suggested Fix**: Move to `tests/_helpers/ast_helpers.py`.
- **Effort**: ~10 min including import updates.
- **Priority Reasoning**: Low — small duplication, but cheap to remove.

#### DEBT-008: `_parse_classification` does not catch `RecursionError` on adversarial JSON

- **Created**: 2026-04-29
- **Resolved**: 2026-05-03 — Added a 64 KiB Stage 1 stdout byte cap before `json.loads`; over-cap classification output now raises `ValueError` and enters the existing classification retry/failure path. Added a unit test that pins rejection before JSON parsing.
- **Source**: Step 8.5 sub-agent code review (M2 / Q5) of `pipeline.py`
- **Reference**: AC-3.2 (failure contract — BGE wraps LLM-traceable failures), AC-3.4 (programmer errors propagate as-is)
- **Description**: `_parse_classification` called `json.loads(stdout)` on raw LLM stdout. Deep or oversized adversarial JSON could raise outside the intended LLM-failure path.
- **Suggested Fix**: Add a cheap `len(stdout) > 64 * 1024` upper-bound check before `json.loads` and route over-cap to retry as a malformed response.
- **Effort**: ~15 min including unit test.
- **Priority Reasoning**: Low — defense-in-depth for abnormal LLM output.

#### DEBT-033: `_FEED_URL` placement inconsistent — sec_edgar_8k uses module-level while 4 sibling news adapters use `ClassVar`

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Moved SEC EDGAR endpoint configuration onto `SecEdgar8kAdapter` as class-level `_FEED_URL` / `_USER_AGENT` `ClassVar[str]` fields and updated the adapter/test call sites to use the class attribute, matching sibling news-adapter shape.
- **Source**: Phase 4 cross-cutting qa review of u1 sources Extension #3 (L1)
- **Reference**: NFR-005 (consistency across symmetric components), R2 (plugin module shape)
- **Description**: Across the 5 news adapters, `_FEED_URL` placement diverged: `yahoo_finance_news.py`, `yonhap_market.py`, `theblock_crypto.py`, `cnbc_top_news.py` declared it as class-level `ClassVar[str]` inside the adapter class; `sec_edgar_8k.py` declared it as module-level `Final[str]`.
- **Suggested Fix**: Move `sec_edgar_8k._FEED_URL` to `ClassVar[str]` on `SecEdgar8kAdapter`. The `_USER_AGENT` constant should follow the same placement decision for symmetry.
- **Effort**: ~5 min — single-file move, no test changes needed beyond the existing SEC User-Agent assertion.
- **Priority Reasoning**: Low — purely cosmetic; the inconsistency surfaced only when a developer read two adapter sources side by side.

#### DEBT-029: SEC URL-constant placement diverges from sibling adapters

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Resolved alongside DEBT-033 by moving `sec_edgar_8k` endpoint configuration from module-level constants to class-level `ClassVar` attributes on `SecEdgar8kAdapter`.
- **Source**: Phase 3 cross-cutting qa review of u1 sources Extension #2 (M1)
- **Reference**: NFR-005 (consistency across symmetric components), R2 (plugin module shape)
- **Description**: 5 of 6 registered adapters declared their endpoint URL as a class-level `ClassVar[str]`; the 6th — `sec_edgar_8k._FEED_URL` — used module-level `Final[str]`. No test or import required the module-level position.
- **Suggested Fix**: Move `sec_edgar_8k._FEED_URL` and `_USER_AGENT` to class-level `ClassVar` on `SecEdgar8kAdapter`.
- **Effort**: ~5 min code move.
- **Priority Reasoning**: Low — purely cosmetic, no behavior impact, no test pressure.

#### DEBT-026: `archive/.gitkeep` redundant once `archive/index.md` exists

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Removed `archive/.gitkeep`; `archive/index.md` already keeps the archive directory tracked.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L3)
- **Reference**: NFR-005 (no dead files)
- **Description**: `archive/.gitkeep` was created to ensure the directory existed in git before the daily-briefing bot's first write. `archive/index.md` already keeps the directory tracked, so `.gitkeep` was redundant.
- **Suggested Fix**: `git rm archive/.gitkeep`.
- **Effort**: ~1 min.
- **Priority Reasoning**: Low — harmless artifact.

#### DEBT-023: `daily-briefing.yml` installs `--extra dev` but never runs pytest

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Changed the daily briefing workflow install step to runtime-only (`uv sync --no-dev`) and updated the step name/comment to reflect that tests and docs tooling run elsewhere.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L7)
- **Reference**: NFR-001 (cron run wall-clock budget)
- **Description**: `.github/workflows/daily-briefing.yml` installed dev dependencies even though the job only invokes `python -m investo`.
- **Suggested Fix**: Switch to `uv sync --no-dev` and update the step name + comment to "Install project (runtime only)".
- **Effort**: ~5 min YAML edit.
- **Priority Reasoning**: Low — saves cold-start install time; the 10-minute budget had margin.

#### DEBT-022: `pages.yml` permissions set at workflow level instead of job level

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Removed workflow-level Pages permissions and moved them to job level: `build` now has only `contents: read`; `deploy` has `pages: write` and `id-token: write`.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (M2)
- **Reference**: NFR-007 (least-privilege secrets / permissions handling)
- **Description**: `.github/workflows/pages.yml` granted `pages: write` and `id-token: write` to both `build` and `deploy`, though only `deploy` needs them.
- **Suggested Fix**: Move to job-level permissions.
- **Effort**: ~5 min YAML edit.
- **Priority Reasoning**: Low — cosmetic least-privilege improvement.

#### DEBT-021: Unused `PublisherError` re-export in `pipeline.__all__`

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Removed the unused `PublisherError` import/re-export and stale comment from `src/investo/orchestrator/pipeline.py`.
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L2)
- **Reference**: NFR-005 (no dead code)
- **Description**: `pipeline.__all__` re-exported `"PublisherError"` with a stale comment, but `__main__.py` does not import it.
- **Suggested Fix**: Drop `"PublisherError"` from `pipeline.__all__`.
- **Effort**: ~2 min.
- **Priority Reasoning**: Low — dead code, not load-bearing.

#### DEBT-020: `_safe_alert` and `_attempt_boot_alert` exception lists not aligned

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Broadened `_attempt_boot_alert` to catch `Exception`, matching `_safe_alert`; parametrized the boot-alert test across transport, validation, and future-contract failures.
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L6 — partially resolved by H1 fix)
- **Reference**: NFR-005 (consistency across symmetric helpers)
- **Description**: `_safe_alert` caught `Exception`, while `_attempt_boot_alert` used the narrower `(OSError, RuntimeError, httpx.HTTPError)`.
- **Suggested Fix**: Broaden `_attempt_boot_alert`'s `except` to `Exception`.
- **Effort**: ~5 min for the change + ~10 min for parametrized tests.
- **Priority Reasoning**: Low — pure consistency tightening.

#### DEBT-019: `resolve_target_date` PBT covers only 2026

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Widened both `resolve_target_date` hypothesis strategies from 2026-only to 2024-2030 and updated the test docstring to describe the broader domain.
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L5)
- **Reference**: NFR-006 (PBT coverage breadth)
- **Description**: `tests/unit/orchestrator/test_date_resolution.py`'s 2 hypothesis PBTs used 2026-only bounds, leaving leap-year edges and additional year-boundary crossings unverified.
- **Suggested Fix**: Widen the strategy to span 2024-2030.
- **Effort**: ~5 min.
- **Priority Reasoning**: Low — date math is mechanical; PBT primarily catches strategy bugs, not algorithm bugs.

#### DEBT-012: `_truncate_stderr` helper duplicated across u2 + u3 errors modules

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Added shared internal `investo._internal.text` module exporting `STDERR_BYTE_CAP` and `truncate_stderr()`. Updated u2 `BriefingGenerationError` and u3 `PublisherGitError` to use the shared helper, removing duplicated truncation implementations while preserving the 1024-byte UTF-8-safe behavior.
- **Source**: Step 8 sub-agent code review of u3 publisher (M1 finding)
- **Reference**: NFR-006 (test-suite/source maintainability); NFR-007 AC-7.4 (1024-byte stderr cap)
- **Description**: `_STDERR_BYTE_CAP: Final[int] = 1024` constant + `_truncate_stderr(value: str | None) -> str | None` helper appeared byte-identically in `src/investo/briefing/errors.py` and `src/investo/publisher/errors.py`. u4 notifier will likely need the same cap when bounding error-text payloads to Telegram. Three copies risked silent drift if one site changed the cap value or the `errors="ignore"` decode strategy.
- **Suggested Fix**: Lift to a shared internal module — `src/investo/_internal/text.py` (new) or extend `src/investo/models/_validators.py`. Both u2 + u3 errors modules import from there. u4 notifier picks it up at construction time.
- **Effort**: ~20 min including import updates and verifying both unit's truncation tests still pass.
- **Priority Reasoning**: Medium — promoted risk if u4 introduced a third copy. Addressed by creating one shared helper before further drift.

#### DEBT-007: No byte-exact JSON snapshot test for `serialize_items_for_prompt`

- **Created**: 2026-04-29
- **Resolved**: 2026-05-03 — Added a byte-exact snapshot test in `tests/unit/briefing/test_pipeline_unit.py` that pins `serialize_items_for_prompt([item])` including key order, default JSON whitespace, URL string, and UTC timestamp format (`+00:00`). This protects FakeClaudeRunner prompt-hash fixture keys from accidental serializer drift.
- **Source**: Step 8.5 sub-agent code review (L4 / Q4) of `pipeline.py`
- **Reference**: AC-6.2 (serialize round-trip), `tests/_helpers/fake_claude_runner.py` (FakeClaudeRunner uses `sha256(prompt)[:16]` as fixture key)
- **Description**: `serialize_items_for_prompt` produces a JSON string that downstream becomes part of the Stage 1 prompt; that prompt is then SHA-256'd to derive the FakeClaudeRunner fixture key. The serializer is deterministic in practice (Python >=3.7 dict insertion order; explicit field order in the dict literal; `astimezone(UTC).isoformat()` always emits `+00:00`) but no test pinned the byte-exact JSON output. A future refactor that, e.g., switches to `json.dumps(payload, sort_keys=True)` or reorders keys would silently invalidate every recorded LLM fixture and break replay.
- **Suggested Fix**: Add a snapshot test in `test_pipeline_unit.py` that constructs a known `NormalizedItem` and asserts the exact bytes returned by `serialize_items_for_prompt([item])`. Pin both the key order (`{"id": 1, "category": ..., "source": ..., "title": ..., "summary": ..., "url": ..., "ts": ...}`) and the timestamp format (`"+00:00"` not `"Z"`). The PBT shape test does NOT cover this — it only checks the key set, not the order or whitespace.
- **Effort**: ~15 min including a 2-3 line test addition.
- **Priority Reasoning**: Medium — the determinism assumption is currently correct but undocumented; the FakeClaudeRunner architecture depends on it. Cheap to pin.

#### DEBT-002: No date sanity bounds on `target_date` / `published_at` (project-wide)

- **Created**: 2026-04-27
- **Resolved**: 2026-05-03 — Added `validate_target_date_sanity()` at the orchestrator boundary with `2024-01-01 <= target_date <= today(UTC)+1`; wired it into `run_pipeline()` and `INVESTO_TARGET_DATE` override parsing so malformed manual backfill dates fail before publish. Added an aggregator-level future timestamp guard that drops source items whose `published_at` is more than 30 days after the fetch window and logs a warning.
- **Source**: Code review of `src/investo/models/briefing.py` (Step 3); same pattern in `items.py`
- **Reference**: US-005 (scheduled execution), FR-006 (archival)
- **Description**: `Briefing.target_date`, `BriefingNotification.target_date`, and `NormalizedItem.published_at` accepted any valid date — including far-future (`date(2206, 4, 27)`) or pre-epoch values. A typo upstream could commit nonsensical archive paths or stamp items with bad timestamps.
- **Suggested Fix**: Add sanity bounds at the **orchestrator** boundary (`resolve_target_date`) rather than in the models, since the models are also used in historical replays where wider bounds may be needed. Concrete check: `2024-01-01 <= target_date <= today + 1`. For Source Adapters, reject items whose `published_at` is more than 30 days in the future.
- **Effort**: ~15 min in u5 orchestrator; ~10 min in u1 sources base.
- **Priority Reasoning**: Medium — defensive only; catches upstream typos before writing archive paths or sending future-dated items downstream.

#### DEBT-001: `Briefing` model lacks `disclaimer ∈ rendered_markdown` invariant

- **Created**: 2026-04-27
- **Resolved**: 2026-05-03 — Added a `model_validator(mode="after")` on `Briefing` that rejects instances whose stripped `disclaimer` is absent from `rendered_markdown`. Added a model-level regression test and updated publisher/orchestrator failure-path tests that intentionally need malformed Briefing objects to use `Briefing.model_construct(...)` explicitly.
- **Source**: Code review of `src/investo/models/briefing.py` (Step 3)
- **Reference**: NFR-004 (compliance / disclaimer enforcement)
- **Description**: The `Briefing` pydantic model permitted a state where `disclaimer` text was not actually present in `rendered_markdown`. The only enforcement was `publisher.verify_disclaimer` (called pre-publish). Defense-in-depth shifted the guarantee one layer earlier — into the data model — so normal construction cannot represent that invalid state.
- **Suggested Fix**: Add a `model_validator(mode="after")` on `Briefing` that asserts `self.disclaimer.strip() in self.rendered_markdown`. Trade-off: rejects ambiguous test fixtures that pass section text without re-running the rendering pipeline. Tests that deliberately exercise publisher failure paths should bypass validation with `model_construct` to make the malformed fixture explicit.
- **Effort**: ~30 min including fixing fixtures
- **Priority Reasoning**: Medium — not yet a real bug because the publisher guard existed, but if anyone ever bypassed the publisher path (e.g., direct unit-tests, future replays, ADR'd alternate flow), the guard disappeared.

#### DEBT-028: `raw_metadata` numeric serialization is inconsistent across u1 adapters

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Added canonical `format_float()` / `format_int()` helpers to `src/investo/sources/_config.py`; updated yfinance, CoinGecko, and FRED numeric `raw_metadata` call sites to use fixed six-decimal float formatting and plain integer formatting. Added helper tests, updated adapter expectation tests, and verified the targeted source test suite.
- **Source**: Cross-cutting sub-agent code review of u1 sources extension Step 5.7 (M1)
- **Reference**: NFR-005 (consistency across symmetric components), R8 (NormalizedItem field rules), R9 (idempotence)
- **Description**: The 3 new u1 adapters used 3 different float-to-string idioms for `NormalizedItem.raw_metadata` values:
  - `yfinance.py` — `f"{value:.4f}"` for OHLC, `str(int)` for volume
  - `coingecko.py` — `f"{price:.6f}"` / `f"{pct:.6f}"` for prices+pct, `f"{value:.2f}"` for volume/market_cap
  - `fred.py` — `f"{value}"` (bare repr; depends on Python's float-to-str default)
  Two issues compounded: (a) the bare `f"{value}"` in FRED could drift between Python releases or with payload type (`f"{1.0}"` → `"1.0"` vs `f"{1}"` → `"1"`); (b) cross-adapter, identical numerics serialized to different strings (e.g., `1.5` became `"1.5000"` in yfinance, `"1.500000"` in coingecko, `"1.5"` in fred). R9 (idempotence — same source state → equal items) was technically satisfied within each adapter but the cross-adapter inconsistency meant u2's downstream prompt saw jagged data.
- **Suggested Fix**: Add a `_format_numeric()` helper to `src/investo/sources/_config.py` (or a new `_format.py` if scope grows): `format_float(v) -> str` (fixed precision, e.g. 6 decimals), `format_int(v) -> str`. Update all 3 adapters to call the helpers. Bonus: the helper becomes the canonical place to add NaN/inf handling if a future adapter needs it.
- **Effort**: ~30 min including helper + 3 adapter call-site updates + test fixture string updates.
- **Priority Reasoning**: Medium — not breaking anything today (each adapter's tests pass with their own format), but would surface as soon as a 4th adapter author had to choose between the 3 existing styles, OR when u2 starts grouping items by category and the cross-adapter inconsistency becomes visible in the LLM prompt. Addressed before the next adapter lands.

#### DEBT-031: `_NS_DC_CREATOR` namespace constant duplicated across 2 news adapters

- **Created**: 2026-05-01
- **Resolved**: 2026-05-01 — Extracted to new `src/investo/sources/_xml_namespaces.py` module exporting `DC_CREATOR: Final[str]`; both `yonhap_market.py` and `theblock_crypto.py` now import from there.
- **Source**: Phase 4 cross-cutting qa review of u1 sources Extension #3 (M2)
- **Reference**: NFR-006 (test-suite/source maintainability), NFR-005 (consistency across symmetric components)
- **Description**: The Dublin Core `<dc:creator>` namespace constant `_NS_DC_CREATOR: Final[str] = "{http://purl.org/dc/elements/1.1/}creator"` appears byte-identically in `src/investo/sources/yonhap_market.py` and `src/investo/sources/theblock_crypto.py`. Both adapters use it the same way: `entry.find(_NS_DC_CREATOR)`. Two copies is the minimum threshold for "extract" under NFR-006 — and any third RSS adapter that needs `<dc:creator>` (a common Dublin Core element across many Korean and English wire feeds) would land a third copy.
- **Suggested Fix**: Lift to a new module `src/investo/sources/_xml_namespaces.py` exporting a small set of curated Clark-notation namespace constants (`NS_DC_CREATOR`, room for `NS_DC_DATE`, `NS_MEDIA_THUMBNAIL`, etc. as future adapters need them). Update both call sites to import. The module mirrors `_config.py` / `_sanitize.py` as an underscore-prefixed internal helper.
- **Effort**: ~15 min including the new file + 2 import updates + ruff/mypy verification.
- **Priority Reasoning**: Medium — promotes to High when a third dc:creator-using adapter lands (likely soon given the Korean/English RSS pattern). Address before the next news-adapter extension.

#### DEBT-032: `_SUMMARY_MAX_LEN = 280` constant duplicated across 8 source adapters

- **Created**: 2026-05-01
- **Resolved**: 2026-05-01 — Lifted to `src/investo/sources/_config.py` as `SUMMARY_MAX_LEN: Final[int] = 280`; all 8 adapters (cnbc_top_news, coingecko, fomc_rss, fred, sec_edgar_8k, theblock_crypto, yfinance, yonhap_market) now import the constant.
- **Source**: Phase 4 cross-cutting qa review of u1 sources Extension #3 (M3)
- **Reference**: NFR-006 (test-suite/source maintainability), R8 (NormalizedItem field rules — summary length cap)
- **Description**: The 280-character summary truncation cap `_SUMMARY_MAX_LEN: Final[int] = 280` appears byte-identically across **8** adapter files: `cnbc_top_news.py`, `coingecko.py`, `fred.py`, `fomc_rss.py`, `sec_edgar_8k.py`, `yfinance.py`, `theblock_crypto.py`, `yonhap_market.py`. All 8 use it the same way: `summary[:_SUMMARY_MAX_LEN]` (or equivalent). Eight copies of a magic-number constant; any future change to the cap (e.g., raising to 400 chars to give the briefing layer richer context) requires touching 8 files in lockstep, with a high silent-drift risk if any is missed during a refactor. Independent of DEBT-028 (DEBT-028 = numeric formatting; this = string-length cap).
- **Suggested Fix**: Lift to `src/investo/sources/_config.py` as `SUMMARY_MAX_LEN: Final[int] = 280` (un-underscored at the module level since `_config` itself is the underscore boundary). Update all 8 adapters to `from ._config import SUMMARY_MAX_LEN`. Optionally, a small helper `truncate_summary(s: str | None) -> str | None` in `_config.py` would absorb the `summary[:cap] if summary else None` shape too.
- **Effort**: ~20 min including the constant lift + 8 import updates + verification (the existing per-adapter tests already pin truncation behavior empirically; no test rewrite needed).
- **Priority Reasoning**: Medium — not breaking anything today (all 8 copies are byte-identical), but the duplication is the single largest constant-drift surface in u1 and the next adapter author will land copy #9 if not fixed. Addresses NFR-006 directly.

---

*Managed by `/tech-debt` skill. Run `/tech-debt add` to add new items.*
