# AI-DLC State

## Project Information
- **Project Name**: Investo
- **Project Type**: Greenfield
- **Start Date**: 2026-04-26
- **Workspace Root**: /Users/user/Desktop/Projects/investo

## Code Location Rules
- Application code: Workspace root (NEVER in aidlc-docs/)
- Documentation: aidlc-docs/ only

## Stage Progress

### INCEPTION PHASE
| Stage | Status | Date |
|-------|--------|------|
| Workspace Detection | ✅ Complete | 2026-04-26 |
| Reverse Engineering | ⏭️ Skipped (Greenfield) | 2026-04-26 |
| Requirements Analysis | ✅ Complete (via interactive refinement) | 2026-04-26 |
| User Stories | ✅ Complete | 2026-04-26 |
| Workflow Planning | ✅ Complete | 2026-04-26 |
| Application Design | ✅ Complete | 2026-04-27 |
| Units Generation | ✅ Complete | 2026-04-27 |

### CONSTRUCTION PHASE
| Stage | Status | Date |
|-------|--------|------|
| Functional Design | ✅ Complete (selective per-unit) | 2026-04-30 |
| NFR Requirements | ✅ Complete | 2026-04-30 |
| NFR Design | ⏭️ SKIP (NFR Requirements 수준에서 흡수) | |
| Infrastructure Design | ⏭️ SKIP (GitHub Actions YAML이 design 자체) | |
| Code Generation | ✅ Complete — original 6 units complete; u7 segmented briefing closed 2026-05-07; u8 source-window correction closed 2026-05-07; u9 reader-experience slice closed 2026-05-07; u10 source diagnostics slice closed 2026-05-07; u11 HTTP identity-encoding slice closed 2026-05-07; u12 Claude stdin-prompt slice closed 2026-05-07; u13 LLM input candidate cap slice closed 2026-05-07; u14-u19 post-MVP quality review follow-ups closed 2026-05-07 | 2026-05-07 |
| Build and Test | ✅ Complete — re-verified after u19 briefing visual assets follow-up on 2026-05-07: ruff ✅, ruff format ✅ (154 files), mypy --strict ✅ (59 source files), pytest ✅ 1011/1011, mkdocs build --strict ✅ | 2026-05-07 |

### Per-Unit Construction Progress
| Unit | Functional Design | NFR Requirements | Code Generation | Notes |
|------|-------------------|------------------|-----------------|-------|
| models (foundation) | N/A | N/A | ✅ Complete (8/8) | 101 tests; 5 source files; summary.md written |
| u1 sources | ✅ Complete | ✅ Complete (+AC-3.6/AC-5.5 in extension) | ✅ Complete (10/10 base + 5/5 extension + 4/4 extension #2 + 4/4 extension #3 + extension #4 + extension #5) — ✅ Extension #5 closed 2026-05-03 (nasdaq-earnings-calendar); **11 adapters total**; **5/5 Category enum values covered** | 252 base tests + 55 ext-#1 tests + 35 ext-#2 tests + **54 ext-#3 tests** + **15 ext-#4 tests** + **18 ext-#5 tests (earnings)** = **429 u1 tests**; **19 source files (8 base + 4 ext-#1 + 2 ext-#2 + 3 ext-#3 + 1 ext-#4 + 1 ext-#5)**; 32 NFR ACs unchanged; +ext-#5 (Nasdaq Earnings Calendar public JSON); US-001 covers calendar/price/macro/news/earnings (5/5); US-008 plugin re-validated under 11-adapter contract; ext-#4 QA APPROVE_AFTER_FIXES (High UA mismatch fixed; Medium fixture metadata gap fixed; no TECH-DEBT); ext-#5 QA PASS (no Critical/High/Medium, no TECH-DEBT; Low test-helper coverage warning addressed with 404 status test); R14 added 2026-05-01 (SEC fair-access UA); Nasdaq adapters use adapter-local non-secret browser-compatible UA because live feed access hangs without UA. Plans: `aidlc-docs/construction/plans/u1-sources-extension-2026-05-code-generation-plan.md` ✅ + `u1-sources-extension-2026-05-news-code-generation-plan.md` ✅ + `u1-sources-extension-2026-05-news-2-code-generation-plan.md` ✅ |
| u2 briefing | ✅ Complete | ✅ Complete | ✅ Complete (10/10 — CG fully closed 2026-04-30) | FD + NFR + CG all closed; cross-check complete; US-002 + US-009 closed; DEBT-006/007/008/009/010/011 resolved |
| u3 publisher | ⏭️ SKIP | ⏭️ SKIP | ✅ Complete (9/9 — CG fully closed 2026-04-30) | FD + NFR + CG all closed; cross-check complete; US-003 + US-006 closed; DEBT-012/013 resolved |
| u4 notifier | ⏭️ SKIP | ⏭️ SKIP | ✅ Complete (8/8 — CG fully closed 2026-04-30) | FD/NFR both SKIP per execution-plan; cross-check complete; US-004 + US-007 dispatcher slice closed; DEBT-014/015/016 resolved |
| u5 orchestrator | ⏭️ SKIP | ✅ Complete (2026-04-30) | ✅ Complete (13/13 — CG fully closed 2026-04-30) | FD = SKIP; NFR Requirements ✅ closed (39 AC); cross-check complete; alert-delivery retry follow-up resolved 2026-05-04; US-005 runtime slice closed; DEBT-017/018/019/020/021 resolved |
| u6 infra/CI | N/A | N/A | ✅ Complete (7/7 — CG fully closed 2026-05-01) | FD/NFR both N/A per execution-plan; cross-check complete; scheduled workflow, Pages, runbook, and GHA fallback closed; DEBT-022/023/024/025/026/027 resolved |
| u7 segmented briefing | ✅ Complete (2026-05-07) | ⏭️ SKIP (u2/u5 NFRs reused; no new external deps) | ✅ Complete (6/6) | New post-MVP unit for FR-008: generate separate domestic-equity, us-equity, and crypto briefings so one market's source volume cannot dominate the whole daily output. Delivered deterministic segment routing, segment-aware u2 prompt context, segmented archive paths/URLs, production all-three-or-fail generate/publish, and one Telegram summary containing all three segment links. Cross-check complete 2026-05-07 (`docs/cross-checks/2026-05-07-u7-segmented-briefing.md`). |
| u8 market-aware source window | ⏭️ SKIP (source-level correction) | ⏭️ SKIP (no new external deps or NFR surface) | ✅ Complete (4/4) | Follow-up quality correction for FR-001/FR-008: aggregator now passes KST windows to domestic sources, America/New_York windows to US-market sources, and UTC windows to crypto sources so US/crypto items after the KST cutoff are not dropped. Cross-check complete 2026-05-07 (`docs/cross-checks/2026-05-07-u8-market-aware-source-window.md`). |
| u9 briefing reader experience | ⏭️ SKIP (u2/u7 UX correction) | ⏭️ SKIP (no new external deps) | ✅ Complete (4/4) | Follow-up quality correction from five-reader review: segment markdown now includes H1, segment navigation, and a 3-line brief; zero-item segments generate concise collection-status fallbacks without Claude; Stage 2 prompt receives source URLs and asks for newsletter-style narrative, source links, conservative wording, and grouped tickers. |
| u10 source coverage diagnostics | ⏭️ SKIP (observability correction) | ⏭️ SKIP (no new external deps) | ✅ Complete (5/5) | Follow-up operations slice for FR-001/FR-008: aggregator logs per-source `source returned` INFO records with source name, category, item count, and applied UTC window so GHA can distinguish HTTP-success-zero-items from source failures. GHA plain-text logs now render those fields directly, while structured `extra` fields remain available for future log processors. |
| u11 HTTP identity encoding | ⏭️ SKIP (transport hardening correction) | ⏭️ SKIP (no new external deps) | ✅ Complete (4/4) | Follow-up operations slice from GHA source diagnostics: `retry_get` now requests `Accept-Encoding: identity` by default so public JSON/RSS endpoints avoid broken compression negotiation in GitHub Actions, while preserving adapter-provided headers and explicit encoding overrides. |
| u12 Claude stdin prompt | ⏭️ SKIP (LLM runner hardening correction) | ⏭️ SKIP (no new external deps) | ✅ Complete (4/4) | Follow-up operations slice from recovered source volume: `call_claude_code` now invokes `claude -p` with the prompt on stdin instead of argv, avoiding OS argument-length failures when a segment has hundreds of collected items. |
| u13 LLM input candidate cap | ⏭️ SKIP (LLM input hardening correction) | ⏭️ SKIP (no new external deps) | ✅ Complete (4/4) | Follow-up operations slice from recovered source volume: briefing generation now caps LLM candidates to 96 total and 24 per source before classification, preventing one high-volume source such as the earnings calendar from exhausting Claude's timeout budget while preserving cross-source evidence. |
| u14 summary quality contract | ⏭️ SKIP (u2/u9 UX correction) | ⏭️ SKIP (no new external deps) | ✅ Complete (2/2) | Five-reader quality review P0 closed: segmented briefing headers now use a validated summary contract that strips markdown/list artifacts, and Telegram segmented summaries reuse the clean rendered conclusion line. Tests added for list-marker leakage, markdown cleanup, data-limited fallback, and notifier reuse. Summary: `aidlc-docs/construction/u14-summary-quality-contract/code/summary.md`. |
| u15 coverage confidence badges | ⏭️ SKIP (u1/u2/u7 quality correction) | ⏭️ SKIP (observability/UX correction; no new external deps) | ✅ Complete (3/3) | Five-reader quality review P0 closed: segmented briefings now compute normal/partial/insufficient coverage, render first-viewport data status with source/item counts and missing categories, constrain partial coverage through the data-limited prompt path, and expose compact Telegram coverage labels. Summary: `aidlc-docs/construction/u15-coverage-confidence-badges/code/summary.md`. |
| u16 public site discovery | ⏭️ SKIP (site content/navigation correction) | ⏭️ SKIP (no new external deps) | ✅ Complete (3/3) | Five-reader quality review P1 closed: Home/About/Archive now reflect the segmented product, expose latest domestic/us/crypto links, document current free-source coverage limits, and preserve the legacy single-briefing archive link. Summary: `aidlc-docs/construction/u16-public-site-discovery/code/summary.md`. |
| u17 operations visibility | ⏭️ SKIP (runtime operations correction) | ⏭️ SKIP (no new external deps) | ✅ Complete (3/3) | Five-reader/operator review P1 closed: GitHub Step Summary now exposes pipeline status, target date, briefing URL, duration, stage timings, and redacted partial failure context while preserving existing exit-code semantics. Summary: `aidlc-docs/construction/u17-operations-visibility/code/summary.md`. |
| u18 watchlist relevance | ⏭️ SKIP (product relevance extension) | ⏭️ SKIP initially (no paid data, no accounts, no trading) | ✅ Complete (3/3) | Five-reader/product review P2 closed: added non-secret JSON watchlist config support, deterministic relevance matching, first-viewport watchlist callout, LLM context injection, and Telegram impact suffix without accounts, paid sources, trading, or portfolio accounting. Summary: `aidlc-docs/construction/u18-watchlist-relevance/code/summary.md`. |
| u19 briefing visual assets | ⏭️ SKIP initially (visual UX extension) | ⏭️ SKIP initially (no paid data, no external image scraping) | ✅ Complete (4/4) | Post-MVP visual UX follow-up closed 2026-05-07: generated deterministic SVG briefing cards for data confidence, market snapshot, price snapshot, and watchlist relevance; inserted relative links into segmented markdown; staged assets with archive files; added visual diagnostics and text-only fallback. Cross-check complete 2026-05-07 (`docs/cross-checks/2026-05-07-u19-briefing-visual-assets.md`). |

## Extension Configuration
| Extension | Enabled | Opted In |
|-----------|---------|----------|
| Security Baseline | No | User declined (본인용 도구, 민감 데이터 없음, public repo) |
| Property-Based Testing | Partial | 순수 함수 + 직렬화 round-trip만 적용 |
