# Cross-check: u188–u190 macro reference sources

Scope: new source additions and their existing publication contracts, not all Investo requirements. Checked2026-10-30 by Codex. User-approved TGA → GSCPI → OFR order implemented.

| Requirement / acceptance | Status | Evidence |
| --- | --- | --- |
| FR-001 / US-001/008 official free collection and registry | Complete locally | Three single-module adapters, explicit descriptor/import/plugin coverage, live-check three successful no-key requests |
| FR-001 NY observation cutoff and source failure isolation | Complete locally | `test_cutoff_uses_new_york_calendar_and_normalizes_timezone`, `test_sibling_survives_aggregate_collection_failure` |
| FR-002/FR-008 source-grounded US reference display | Complete locally | `test_finalizer_renders_three_sources_and_overwrites_generated_numbers` both native/legacy; other segments excluded |
| NFR-001 bounded collection work | Complete for additions | 30s/source timeout; two attempts; row/byte caps; live each under1.2s. Existing end-to-end runtime SLO not requalified |
| NFR-002 no-paid/LLM constraints | Complete | No keys/dependencies/LLM calls; paid and SDK guards PASS |
| NFR-003 malformed/stale/missing behavior | Complete | Fault and boundary fixtures; no invented zero or old-value fallback; required macro failure not masked |
| NFR-004/008 disclaimer, source attribution, rights separation | Complete locally | Existing finalizer disclaimer enforcement retained; provider notices and NYFed fixture attribution; only government/OFR aggregate numbers and licensed NYFed CSV |
| NFR-005/006 maintainability and testing | Complete locally | Registry model, shared typed reference; independent PASS and211 integrated tests; full execution and correction verification in validation.md |
| Release/GHA/first scheduled observation | Pending release | No new commit/deploy requested; existing runtime pins unchanged |

Specific source contracts: TGA's closing account row uses `open_today_bal` in USD millions and reconciles opening+deposits-withdrawals; GSCPI newest release-vintage column is distinct from its month-end observation; OFR only aggregate OFRFSI is emitted, with two-business-day lag. All outputs warn that current downloads can be revised and do not certify historical publication availability.

No scope gap identified in the implemented source/reference contract. Public Insights dashboard metrics/history, new-release event qualification, derived liquidity/trading signals and existing article-generation failures remain outside these units. No unrelated debt or unit is marked complete.
