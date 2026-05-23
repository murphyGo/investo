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

Deduplicated out:
- No generic quality KPI unit: u69 is limited to cross-public-surface contradiction detection and canonical rendering.
- No generic numeric validator: u70 only makes existing verified anchors single-source across surfaces.
- No generic first-viewport gate: u71 only reorders/collapses reader surfaces after u61 validation.
- No generic watchlist matcher: u73 consumes u64 match confidence and adds workflow grouping.
- No generic chart redesign: u75 changes payload ownership/lazy loading, not chart semantics.
- No generic glossary/carryover work: u76 excludes u68 mechanics and focuses on section-level meaning prose.

---

## Definition of Done — Inception Phase Output

이 매핑이 다음 단계(Construction)의 입력입니다:
- 각 unit별 Functional Design 대상이 명확 (execution-plan.md의 selective per-unit 정책 참조)
- 각 unit별 NFR Requirements 작성 시, 본 표의 "AC delivered" 컬럼이 출발점
- Code Generation은 unit-of-work.md의 Definition of Done 체크리스트를 task로 변환
