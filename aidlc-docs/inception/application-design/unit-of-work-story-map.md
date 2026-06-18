# Story-to-Unit Mapping: Investo

**Date**: 2026-04-27

---

## Mapping (Q1=A: 1:1 Component ↔ Unit)

| Story | Title | Primary Unit | Secondary Touch |
|-------|-------|--------------|-----------------|
| US-001 | 매일 시장 데이터를 자동 수집한다 | u1 sources | models |
| US-002 | AI가 한국어 데일리 시황을 작성한다 | u2 briefing | models |
| US-003 | GitHub Pages에 시황을 정적 게시한다 | u3 publisher | u6 infra (mkdocs/Pages) |
| US-004 | 공개 텔레그램 채널로 시황 요약이 푸시된다 | u4 notifier (BriefingPublisher) | u5 orchestrator (트리거) |
| US-005 | GitHub Actions cron으로 자동 실행된다 | u5 orchestrator | u6 infra (cron) |
| US-006 | 모든 시황을 영구 보관한다 | u3 publisher | u6 infra (Pages 인덱스) |
| US-007 | 파이프라인 실패 시 운영자 1:1 chat으로 알림 받는다 | u4 notifier (OperatorAlerter) | u5 orchestrator (실패 hook) |
| US-008 | 새 데이터 소스를 단일 모듈 추가로 통합한다 | u1 sources | (문서/CONTRIBUTING) |
| US-009 | 운영비를 월 $0으로 유지한다 | u2 briefing (Claude Code CLI) | u1 sources (free APIs) |

---

## Per-Unit Story Coverage

### u1 sources
- **Primary**: US-001, US-008
- **Touched by**: US-009 (free API constraint)
- **AC delivered**:
  - 무료 API/RSS만 사용 → US-001 AC + US-009 AC
  - Plugin registry + 단일 모듈 추가로 통합 → US-008 AC
  - Graceful degradation → US-001 AC + NFR-003

### u2 briefing
- **Primary**: US-002, US-009
- **AC delivered**:
  - Claude Code CLI 호출, Anthropic SDK 금지 → US-002 + US-009 AC
  - 7섹션 한국어 시황 → US-002 AC
  - 면책조항 자동 삽입 → US-002 AC + NFR-004
  - LLM retry → US-002 AC + NFR-003

### u3 publisher
- **Primary**: US-003, US-006
- **Touched by**: NFR-004 (disclaimer verify로 강제)
- **AC delivered**:
  - markdown archive 저장 → US-006 AC
  - git commit으로 영구 → US-006 AC
  - 게시 전 disclaimer 검증 → NFR-004 (US-002 AC 보강)
  - GitHub Pages 호환 markdown 생성 → US-003 AC (배포 자체는 u6)

### u4 notifier
- **Primary**: US-004 (BriefingPublisher), US-007 (OperatorAlerter)
- **AC delivered**:
  - 공개 채널 발송 + 4096자 한도 → US-004 AC
  - 운영자 1:1 chat 분리 → US-007 AC
  - 발송 실패가 게시를 막지 않음 → US-004 AC + NFR-003
  - 시크릿/PII 미포함 검증 → US-004 AC + NFR-007

### u5 orchestrator
- **Primary**: US-005
- **Touched by**: US-004, US-007 (트리거 위치), NFR-001 (시간 예산)
- **AC delivered**:
  - cron + workflow_dispatch + KST 시간대 → US-005 AC
  - ≤ 10분 단일 job → NFR-001
  - Graceful degradation 정책 → NFR-003 + 다수 US AC

### u6 infra/CI
- **Primary**: 인프라 자체. 모든 US가 간접적으로 의존.
- **AC delivered**:
  - cron 트리거 → US-005 AC
  - mkdocs build + GitHub Pages → US-003 AC
  - Secrets 주입 (CLAUDE_CODE_OAUTH_TOKEN, TELEGRAM_*) → NFR-007

---

## Cross-Cutting NFR Coverage

| NFR | Where Implemented | Verified By |
|-----|-------------------|-------------|
| NFR-001 Performance (≤10분) | u5 orchestrator (time budget per stage) | u5 integration test + first cron run |
| NFR-002 Cost ($0/월) | u1 (free APIs only) + u2 (Claude Code CLI only) | grep/lint check + PR review |
| NFR-003 Reliability (graceful degradation) | u1 (per-source isolation) + u2 (LLM retry) + u3 (git retry) + u4 (non-blocking failure) + u5 (stage policy) | per-unit failure tests + integration test |
| NFR-004 Compliance (disclaimer) | u2 (auto append) + u3 (verify presence) | u2/u3 unit tests |
| NFR-005 Maintainability (plugin) | u1 (registry/protocol) | u1 unit test + CONTRIBUTING |
| NFR-006 Testing (PBT partial) | models (round-trip), u1 norms, u2 prompt builders, u4 summary | hypothesis 기반 테스트 |
| NFR-007 Security (secrets via GH Secrets) | u6 (workflow secrets), u2 + u4 (env-only auth) | workflow audit + secret scan |

---

## Post-MVP Quality Review Follow-Up Units

Five-reader quality review on 2026-05-07 generated the following follow-up units. These are not new base stories; they refine existing FR/US/NFR coverage based on actual reader/operator experience.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u14 summary-quality-contract | First-viewport summary trust | FR-002, FR-003, FR-008 | u4 notifier summary reuse |
| u15 coverage-confidence-badges | Reader-visible source coverage and confidence | FR-001, FR-002, FR-008, NFR-003 | u10 diagnostics |
| u16 public-site-discovery | Latest segmented briefing discovery and docs drift | FR-003, FR-006, FR-008 | u3 publisher, u6 MkDocs |
| u17 operations-visibility | Partial-success operator awareness | FR-004, FR-005, FR-007, NFR-003 | u5 orchestrator |
| u18 watchlist-relevance | Personal relevance for the primary user | FR-002, FR-004, FR-008 | future portfolio/company-analysis extension |
| u19 briefing-visual-assets | Data-derived visual cards for market state and confidence | FR-002, FR-003, FR-004, FR-008 | u7 segmented briefing, u15 coverage, u18 watchlist |
| u20 archive-trust-and-latest-index | Trustworthy latest archive discovery and legacy separation | FR-003, FR-006, FR-008 | u3 publisher, u6 MkDocs |
| u21 summary-quality-gate | Publish-time first-viewport summary validation | FR-002, FR-003, FR-008, NFR-003 | u14 summary contract |
| u22 source-coverage-transparency | Reader-visible source status and coverage reasons | FR-001, FR-002, FR-008, NFR-003 | u10 diagnostics, u15 coverage |
| u23 notification-actionability | Segment-distinct actionable alerts and partial notify visibility | FR-004, FR-007, FR-008, NFR-003 | u17 operations visibility |
| u24 visual-provenance-and-layout | Visual provenance, captions, and first-viewport layout | FR-002, FR-003, FR-008, NFR-007 | u19 visual assets |

### Follow-Up Priority

1. **u14 summary-quality-contract** — fixes visible broken text in the briefing header.
2. **u15 coverage-confidence-badges** — makes data limitations explicit before users trust the narrative.
3. **u16 public-site-discovery** — aligns the public site with the segmented product and latest archive flow.
4. **u17 operations-visibility** — makes partial failures visible to the one-person operator.
5. **u18 watchlist-relevance** — adds product relevance after the reliability and trust surface is stable.
6. **u19 briefing-visual-assets** — adds generated visual cards after the text, confidence, discovery, and relevance surfaces are stable.
7. **u23 notification-actionability** — smallest high-impact user-facing alert improvement.
8. **u21 summary-quality-gate** — prevents broken first-viewport summaries from reaching public archive pages.
9. **u20 archive-trust-and-latest-index** — removes stale/legacy discovery risk after summary quality is guarded.
10. **u22 source-coverage-transparency** — deeper coverage diagnostics for reader trust.
11. **u24 visual-provenance-and-layout** — provenance and layout polish after alert and text trust surfaces.

### u19 Planning Notes

u19 must favor Investo-generated data visuals over scraped third-party images. The safe v1 scope is data confidence, market snapshot, price snapshot, and watchlist relevance cards derived from `NormalizedItem`, `SegmentCoverage`, and `WatchlistImpact`. News thumbnails, chart screenshots, unverified logos, and long time-series charts remain out of scope until licensing, data retention, and manifest policies are designed.

### u20-u24 Planning Notes

The second five-reader quality review on 2026-05-07 prioritized user trust and operator actionability. The requested implementation order is `u23 -> u21 -> u20`, with `u22` and `u24` kept as planned follow-up units.

### u54-u57 Planning Notes

The 2026-05-13 ten-agent review of generated briefings was deduplicated against u51, u52, and u53 before adding new units.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u54 source-status-severity-and-quality-kpi | Source failures/zero-item sources are labeled as `정상`, and quality KPIs do not explain coverage risk | FR-001, FR-002, FR-003, FR-008, NFR-003 | u22 coverage transparency, u42 quality KPI history |
| u55 numeric-freshness-and-market-fact-gates | Core numeric claims, date tokens, market direction, and stale archive status need source-backed gates | FR-001, FR-002, FR-003, FR-006, FR-008, NFR-003 | u25 summary fidelity, u32 numeric self-check, u49 market anchor |
| u56 compliance-language-and-observational-tags | Prompt/gate language can drift into investment-advice wording despite footer disclaimer | FR-002, FR-003, FR-004, FR-008, NFR-004 | u21 summary gate, u23 notification actionability |
| u57 segment-narrative-scope-and-time-reconciliation | Segment-native scope and `장중/출발/마감` states need reconciliation across the same bundle | FR-002, FR-008, NFR-003 | u45 routing exclusivity, u52 carryover |

Deduplicated out:
- u51 already owns reader layout, TL;DR, anchor table, H3 conversion, number bolding, glossary dedupe, and action-ratio diagnostics.
- u52 already owns prior-briefing carryover and event lifecycle tracking.
- u53 already owns domestic flow and US sector/macro ETF input coverage.

### u58 Planning Notes

The 2026-05-14 CLARITY Act Senate Banking markup miss was source-coverage and candidate-priority debt: the event existed on official congressional/committee surfaces but was not guaranteed to enter the crypto briefing candidate set. u58 keeps the implementation scope to official, public U.S. policy sources and avoids brittle third-party scraping.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u58 crypto-regulation-policy-sources | CLARITY/market-structure/stablecoin legislative events need official source coverage and crypto priority handling | FR-001, FR-002, FR-008, NFR-003, R10, R13 | u36 source expansion bundles, u45 routing exclusivity, u53 signal recall |

### u59 Planning Notes

The 2026-05-13 U.S. PPI miss showed that macro schedule collection is not enough: the pipeline also needs structured official actuals, deterministic priority before candidate caps, required macro preservation through both LLM stages, and operator lineage that explains exactly where a macro event disappeared.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u59 macro-actual-priority-and-lineage | High-importance macro events such as CPI/PPI/NFP/PCE/GDP/FOMC need official actual data, priority scoring, required output validation, and end-to-end drop diagnostics | FR-001, FR-002, FR-003, FR-008, NFR-003, R10, R13 | u13 candidate caps, u22 coverage transparency, u43 lookahead adapters, u52 carryover, u54 severity/KPI, u55 numeric gates, u57 shared macro, u58 priority preservation |

### u60 Planning Notes

The 2026-05-13 shared macro block rendered `미 국채 수익률 — Immunefi to absorb Code4rena bug bounty customers after shutdown decision` because the u57 UST detector matched the `ust` substring inside `customers`. u60 keeps the scope narrow: harden shared macro evidence matching and representative-title selection without changing source collection, LLM prompts, or archive backfill.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u60 shared-macro-evidence-hardening | Shared macro evidence must be source-backed and must not classify substring accidents like `customers` as UST yield | FR-002, FR-008, FR-015, NFR-003, R13 | u45 routing exclusivity, u55 numeric fact discipline, u57 BundleContext/shared macro, u59 macro lineage boundary |

### u66-u68 Planning Notes

The 2026-05-24 reader-facing feature-gap review split P2/P3 findings into crypto depth, domestic depth, and reader-aid residuals. u67 and u68 are closed. u66 remains the crypto-depth backlog owner and now has a formal plan that fixes the no-key v1 contract: Alternative.me Fear & Greed, CoinGecko global dominance/totals, Bybit→OKX BTC 펀딩비/OI (no-key, geo-safe), existing DeFiLlama structure, UTC 24h framing — with explicit unavailable rows only for 24h 청산/netflow (no no-key source → scope-out, TECH-DEBT), per the lead's 2026-05-24 live reachability probe.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u66 crypto-channel-depth | Crypto briefings need native sentiment/dominance/global-market rows and UTC 24h framing, without brittle paid or scraped derivatives feeds | FR-001, FR-002, FR-008, FR-009, R10, R13 | u45 routing exclusivity, u55 numeric facts, u56 compliance, u58 policy priority, u74 channel wrapper |
| u67 domestic-channel-depth | Domestic briefings need KOSPI/KOSDAQ close fallback, 원/달러, sector depth, and overnight-US framing | FR-001, FR-002, FR-009 | u49 anchors, u53 sector/macro depth, u57 cross-segment wording |
| u68 reader-aids-residual | Remaining reader-aid work after u52/u64/u40 is limited to glossary/carryover residual verification and suppression | FR-002, FR-006, FR-009 | u40 glossary, u52 carryover, u64 watchpoints |

### u69-u76 Planning Notes

The 2026-05-24 user-quality review follow-up is scoped as improvements to already-delivered briefing quality surfaces. These units were generated only after excluding duplicate implementations: u54/u62/u65 already own source quality and replay foundations, u55 owns numeric fact gates, u51/u61 own summary formatting gates, u64 owns watchlist matching/actionability, u66/u67 own crypto/domestic depth, u50 owns lightweight chart embedding, and u68 owns glossary/carryover residuals.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u69 quality-public-consistency-gate | Public quality surfaces contradict each other across `quality.md`, `quality_history.jsonl`, markdown status, and replay output | FR-001, FR-003, FR-006, FR-010, NFR-003 | u54 severity/KPI, u62 snapshot reconciliation, u65 replay harness |
| u70 cross-surface-numeric-anchor-reconciliation | The same anchor value/label diverges across table, prose, trace, and chart card surfaces | FR-001, FR-002, FR-003, FR-011, NFR-003 | u55 numeric gates, u49 market anchors, u50 chart placeholders, u67 fallbacks |
| u71 reader-first-viewport-reflow | Reader sees diagnostics and raw errors before useful summary/action context | FR-002, FR-003, FR-004, FR-009, FR-012 | u51 layout, u61 summary gate, u54/u62 status inputs, u56 compliance |
| u72 watchpoint-action-matrix | Watchpoints need trigger/current/confidence/implication structure without investment advice | FR-002, FR-004, FR-009, FR-012 | u64 watchpoint actionability, u52 carryover, u55 numeric facts, u56 compliance |
| u73 watchlist-impact-center-v2 | Watchlist should behave like a daily impact workflow, including rejected/uncertain matches | FR-002, FR-003, FR-004, FR-009 | u18/u28/u33 watchlist foundations, u64 strict matching, site watchlist pages |
| u74 market-channel-depth-v2 | Remaining channel-depth gaps need one presentation contract after u66/u67 | FR-001, FR-002, FR-008, FR-009, FR-013 | u66 crypto indicators, u67 domestic depth, u57 BundleContext, u53 sector/macro depth |
| u75 chart-data-externalization-and-mobile-performance | Compact charts still embed large inline OHLC payloads; payload should lazy-load | FR-003, FR-006, FR-009, NFR-001, NFR-002 | u50 lightweight charts, compact chart card change, publisher asset staging |
| u76 plain-language-reader-aids | Each major section needs a short plain-Korean meaning line for non-expert readers | FR-002, FR-009, FR-012 | u40 glossary, u51 layout, u56 compliance, u68 reader-aid residuals |
| u87 watchpoint-matrix-rehabilitation | §⑥ matrix is 100% `데이터부족` across segments and leaks broken markdown links + a diagnostic hash into reader cells | FR-002, FR-004, FR-009, FR-012 | u72 matrix renderer, u64 structured-bullet contract, u56 compliance, DEBT-074 escalation |

Deduplicated out:
- No generic quality KPI unit: u69 is limited to cross-public-surface contradiction detection and canonical rendering.
- No generic numeric validator: u70 only makes existing verified anchors single-source across surfaces.
- No generic first-viewport gate: u71 only reorders/collapses reader surfaces after u61 validation.
- No generic watchlist matcher: u73 consumes u64 match confidence and adds workflow grouping.
- No generic chart redesign: u75 changes payload ownership/lazy loading, not chart semantics.
- No generic glossary/carryover work: u76 excludes u68 mechanics and focuses on section-level meaning prose.

### u92-u95 Planning Notes

The 2026-06-04/09 daily-briefing speed investigation was deduplicated against existing runtime and briefing units before adding new work. u10 already logs source item counts and windows, u13 already caps candidate count, u75 already externalizes chart payloads for reader-side performance, and u84 already gives the orchestrator a stage abstraction. The remaining speed work is not another generic quality unit: it splits into measurement, prompt-byte reduction, bounded segment concurrency, and non-LLM critical-path budget.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u92 daily-briefing-runtime-observability | Coarse `generate` timing hides source, segment, context, visual, and LLM-attempt bottlenecks | FR-005, FR-007, FR-008, NFR-001, NFR-003 | u10 source diagnostics, u84 stage abstraction, GitHub step summary |
| u93 llm-prompt-input-slimming | Stage 1 sends uncapped prompt fields and Stage 2 carries large mechanical instructions/empty context blocks | FR-002, FR-008, FR-009, NFR-001, NFR-002 | u13 candidate caps, u55/u56/u61/u72/u76 gates |
| u94 bounded-segment-generation-concurrency | Domestic, US, and crypto segment LLM work runs sequentially even though failures are isolated per segment | FR-005, FR-008, NFR-001, NFR-003, NFR-007 | u7 segmented briefing, u84 stage abstraction, u92 timing |
| u95 workflow-and-enrichment-critical-path-budget | GitHub setup, market-anchor history fetch, and visual preparation sit on the critical path after the core pipeline has grown | FR-003, FR-005, FR-008, NFR-001, NFR-002, NFR-003 | u6 infra/CI, u49 anchors, u50/u75 visual/chart assets, u92 timing |

Deduplicated out:
- No generic source concurrency unit: `sources.aggregator.collect_sources` already runs registered adapters through `asyncio.gather`; u92 measures slow adapters before adapter-specific optimization.
- No second candidate-cap unit: u13 owns item-count caps; u93 owns prompt-field byte caps and empty optional context omission.
- No top-level orchestrator overlap unit: u84 keeps stage sequencing explicit; u94 only changes independent segment generation inside the generate stage.
- No chart redesign or visual product unit: u95 only constrains best-effort enrichment cost and workflow cold-start time.

### u96-u100 Planning Notes

The 2026-06-09 generated bundle was reviewed from a reader perspective by ten specialist agents, then distilled through stage-specific design discussion. The strongest pattern was not lack of raw information; it was a mismatch between facts, public status, hierarchy, and reader-facing narrative. The follow-up work is split into five independently shippable units so a context-free implementer can improve one layer without re-opening unrelated source adapters or the entire briefing prompt.

Implementation priority after the 2026-06-11 five-reviewer-per-unit audit:
1. u96 first, because public status truth outranks narrative polish.
2. u97 second, because daily thesis should consume evidence hierarchy rather than amplify flat/weak evidence.
3. u99 and u100 as one product slice or adjacent slices: u99 inserts the first-viewport thesis, and u100 gates that final first-viewport text.
4. u98 after the core trust/narrative work, unless a small isolated §⑥ UI cleanup is explicitly selected.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u96 quality-current-run-snapshot-sync | Public quality dashboard looked healthier than segment markdown showing `[데이터부족]`, limited status, and core-source failure | FR-003, FR-007, FR-008, FR-009, NFR-003, NFR-006 | u54/u62/u65 quality metrics, u69 consistency gate, current-run publish snapshot; priority 1 |
| u97 evidence-weighted-story-hierarchy | Low-signal rows could carry the same story weight as core macro or market-wide evidence | FR-002, FR-008, FR-009, NFR-006 | u13 candidate caps, u57 narrative scope, u59 macro priority, u64/u73 watchlist routing; priority 2 and preferred prerequisite for u99 |
| u98 watchpoint-card-list-redesign | §⑥ table remained dense, repetitive, and fragile on mobile after u87 rehabilitation | FR-008, FR-009, NFR-003, NFR-006 | u72/u87 watchpoint renderer, u64 actionability contract, u56 compliance scan; priority 4 |
| u99 daily-thesis-layer | Segment briefings lacked a shared "오늘의 큰 그림" line that explains the cross-market day | FR-002, FR-008, FR-009, NFR-003, NFR-006 | u57 shared narrative, u74 channel depth and cause-map gating, bundle context, u97 evidence tiers; priority 3 paired with u100 |
| u100 surface-quality-gate | Broken first-viewport language artifacts such as `불강한성`, dangling `...`, and markdown fragments damaged trust | FR-002, FR-008, FR-009, NFR-003, NFR-006 | u56 compliance, u61 first viewport, u71 reflow, u76 meaning lines, u99 thesis line; priority 3 paired with u99 |

Deduplicated out:
- No new source adapter unit: the review defects were reader-facing synthesis, status, and formatting failures, not absence of a specific upstream feed.
- No generic prompt rewrite unit: u97 and u99 pass structured signals into the prompt/publisher path, while u98 and u100 keep deterministic rendering and validation ownership.
- No second watchlist/actionability matcher: u98 consumes the u64/u72/u87 structured watchpoint contract and changes only the reader-facing shape.
- No broad Korean spellchecker unit: u100 handles known deterministic artifacts and first-viewport breakage only.
- No quality KPI redesign: u96 synchronizes current-run facts across existing public surfaces and leaves severity/source policy untouched.
- No independent u99 rollout without a surface gate: u99 can be implemented separately, but product rollout should pair it with u100 or include a u99-local surface check for the inserted line.

### u101 Planning Notes

The 2026-06-16 US-equity briefing exposed a different trust class from numeric facts: a high-drift officeholder fact was absent from structured inputs, so Stage 2 filled the FOMC press-conference speaker from stale model memory and wrote Powell where current official data showed Kevin Warsh. u101 deliberately does not hard-code Warsh. It creates an official-source fact cache with short TTL and a publish guard that fails closed when the fact is stale or missing.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u101 verified-fact-cache-and-entity-guard | High-drift entity facts such as current Fed chair need official refresh, prompt injection, and publish blocking so model memory cannot name stale officeholders | FR-001, FR-002, FR-008, FR-009, NFR-003, NFR-006, R13 | u35/u43 FOMC lookahead, u59 macro lineage, u55/u70 trust gates, u85 validators, u100 surface gate |

Deduplicated out:
- No numeric fact validator: u55/u70 own numeric and market-anchor truth.
- No macro actual lifecycle replacement: u59 owns scheduled/actual macro events; u101 only supplies current officeholder context missing from schedule feeds.
- No hard-coded person registry as truth: stored snapshots expire and only official-source refresh can authorize current-role names.
- No broad fact-checking LLM: first slice uses deterministic source parsing and deterministic entity-role claim scanning.

### u102-u107 Planning Notes

The 2026-06-18 ten-agent source-expansion review found that Investo already has broad price/news/calendar coverage, so the next source work should avoid generic provider accumulation. The priority is official, free, structured, source-of-record data that closes clear briefing gaps without paid APIs, scraping, or fabricated fixtures. The work is split into small units so each slice can register adapters, fixtures, route/tier/window metadata, and reader-facing usage without reopening the full pipeline.

Recommended implementation order:
1. u102 first, because registry drift would make all later adapters less trustworthy.
2. u103 second, because Fed/SEC official RSS feeds are no-key, low-risk, and immediately improve source authority.
3. u104 third, because SEC company facts and Nasdaq symbol metadata provide durable US-equity anchors.
4. u105 fourth, because macro actuals should join with existing schedule/carryover logic before narrative use expands.
5. u106 fifth, because funding/energy/volatility context adds explanatory breadth once source mechanics are guarded.
6. u107 sixth, because CFTC positioning has high value but needs careful contract mapping and delayed-data labeling.

| Unit | Main Concern | Primary Coverage | Secondary Touch |
|------|--------------|------------------|-----------------|
| u102 source-adapter-registry-completeness | Source additions can silently miss tier, segment, or market-window registration | FR-001, FR-008, FR-009, NFR-003, NFR-006 | u1 source plugin contract, u8 market-aware windows, u22 source coverage |
| u103 official-policy-speech-rss-sources | Official Fed/SEC speeches and statements are missing while generic news and press releases already exist | FR-001, FR-002, FR-008, FR-009, NFR-002, NFR-003 | u35/u43 FOMC lookahead, u58 policy sources, u101 entity facts |
| u104 sec-company-facts-and-symbol-directory | US company/watchlist anchors need official CIK, listing, ETF, and XBRL fact context beyond 8-K Atom news | FR-001, FR-002, FR-008, FR-009, NFR-002, NFR-003 | u18/u73 watchlist impact, u55 numeric gates, u101 fact context |
| u105 macro-actual-source-of-record | Macro schedules exist but BLS/BEA source-of-record actuals and shared event keys remain incomplete | FR-001, FR-002, FR-008, FR-009, NFR-002, NFR-003 | u43 lookahead, u59 macro lineage, DEBT-079 event-key join |
| u106 money-energy-volatility-source-expansion | Rates/prices lack official SOFR/EFFR, petroleum inventory, and VVIX/SKEW explanatory context | FR-001, FR-002, FR-008, FR-009, NFR-002, NFR-003 | u49 market anchors, u55 numeric gates, u74 channel depth |
| u107 cftc-positioning-layer | Briefings lack regulated futures positioning across equity, rates, FX, commodities, VIX, and crypto | FR-001, FR-002, FR-008, FR-009, NFR-002, NFR-003 | u66 crypto indicators, u67 domestic flows, u74 channel depth |

Deduplicated out:
- No KRX/KIND/SEIBro/KOFIA HTML portal unit: public non-scraping structured endpoints remain unconfirmed.
- No Coinglass/CryptoQuant/Glassnode unit: paid/key-dependent liquidation and netflow products remain outside the no-paid source contract.
- No FRED-only credit-spread expansion using restricted ICE BofA OAS series: redistribution language conflicts with public briefing reuse.
- No generic alternative-data unit: Farside ETF flows, AAII/NAAIM, OCC option files, Deribit, Hyperliquid, and Etherscan require narrower license/rate-limit validation before implementation.
- No broad source-provider abstraction: existing `SourceAdapter`/registry/coverage contracts already provide the extension mechanism.

---

## Definition of Done — Inception Phase Output

이 매핑이 다음 단계(Construction)의 입력입니다:
- 각 unit별 Functional Design 대상이 명확 (execution-plan.md의 selective per-unit 정책 참조)
- 각 unit별 NFR Requirements 작성 시, 본 표의 "AC delivered" 컬럼이 출발점
- Code Generation은 unit-of-work.md의 Definition of Done 체크리스트를 task로 변환
