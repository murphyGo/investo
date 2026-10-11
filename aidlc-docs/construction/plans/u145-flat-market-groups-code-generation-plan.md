# u145 follow-up — flat market groups

## Authorization and stage decision

User approval, 2026-10-10: “네 제안대로 진행해줘”. It approves implementation
of the proposed flat industry/theme view, category filters and retained eleven-sector
market overview. Earlier publication authorization persists. Functional Design and
NFR Requirements are required and completed in the accompanying artifacts before code.
NFR/Infrastructure Design reuse the existing Python/Actions/Pages architecture.
Commit/push and publication are in scope; unrelated news/site-shell planning is preserved.

The Yahoo permission exception and Browser waiver remain u145-specific, unverified /
WAIVED / NOT_EXECUTED. This is a bounded extension of that same dedicated Yahoo radar;
no new provider or strict u140 acceptance is implied. All nonvisual gates remain binding.

## Source decision

The optional software question was presented asynchronously. Pending any user correction,
implementation uses XSW as software/IT-services exposure; no user answer is fabricated.
XTH is rejected: issuer announced liquidation in 2020. A fixed representative hardware
basket supplies the missing hardware view; it is explicitly a synthetic price index.

| Group | Fixed inputs | Kind / scope |
| --- | --- | --- |
| Semiconductor/equipment | SMH | industry ETF; US-listed domestic/foreign issuers |
| Software/IT services | XSW | industry ETF; US all-cap software/services plus limited adjacent exposures |
| Hardware/equipment | AAPL, DELL, HPQ, HPE, CSCO, ANET, NTAP, GLW | representative eight-stock, daily equal-weight price index; not a complete industry |
| Big tech M7 | MAGS | theme ETF; overlaps technology, communication and discretionary groups |

Other ten sector ETFs remain in the flat view, with XLK retained in the market-overview
view only. Fourteen flat groups and eleven overview sectors have separate rankings.
One fixed 23-asset request set (SPY + original11 + new3ETFs + hardware8) shares the
existing 36-attempt / 36-per-minute, concurrency2, 120s collection budget. Ambient secrets,
raw bars, volume, URLs, provider text and diagnostics never enter derived public records.

Issuer evidence: [SMH](https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/),
[XSW](https://www.ssga.com/us/en/institutional/etfs/state-street-spdr-sp-software-services-etf-xsw),
[MAGS](https://www.roundhillinvestments.com/etf/mags/),
[XTH closure announcement](https://www.nasdaq.com/press-release/state-street-global-advisors-announces-changes-to-spdrr-etf-lineup-2020-05-21).
Local source availability probe received HTTP429 for every candidate, so no local
source qualification PASS is inferred. Exact-commit runner qualification precedes activation.

No new briefing adapter: source registry, aggregator/tier/market-window/segment routes
remain outside this dedicated radar, as in u145. Adapter remains `sector_dashboard/yahoo_data.py`;
there is no new key, dependency, paid tier, runtime issuer scraping or LLM call.

## Execution

- [x] 1. Scope, source research, FD/NFR contracts and explicit authorization record.
- [x] 2. Closed additional asset/group models and schema3 with canonical schema2 compatibility.
- [x] 3. Shared neutral price math, strict same-date hardware index, independent14-group ranking/regime.
- [x] 4. Extend the single bounded Yahoo collector; wire opt-in build/probe and production CLI.
- [x] 5. Flat cards/charts/table, industry/theme labels, market-overview switch and display-only filters.
- [x] 6. Meaningful models/math/source/build/store/UI tests; lint/type/policy/site checks and independent review.
- [x] 7. Maximum-shape resource gate and five exact-commit read-only runner probes including new assets/groups.
- [x] 8. Preserve concurrent main, scoped commit/push, quality CI, real refresh, Pages and live identity/UI checks.
- [x] 9. Cross-check, operational evidence and source-policy/Browser residual limits; final closeout.

Closeout: reviewed/integrated code25eb9220; exact quality38025047604 PASS6,836;
five final source runs38025074477/38025159382/38025228852/38035923091/38036015469 PASS.
Refresh38036114019 promotes23/11/14fresh2026-10-09; data8ff7abde and Pages38036145271
PASS; live canonical8a1e76ae, JSON/CSS/JS byte equality and desktop/mobile light/dark
tabs/filter/keyboard/anchor/noJS checks PASS. No waived Browser acceptance is claimed.
Detailed evidence: `docs/sessions/2026-10-10-u145-flat-market-groups.md` and cross-check.

Acceptance: fourteen exact group identities; all ten reused sector metrics equal overview;
no XLK row in flat groups; ETF and representative basket distinguished; same SPY calendar,
full64 sessions and current as-of required; missing hardware member suppresses its entire
group; missing extra group preserves usable overview; parent source/resource failure
preserves complete last-good pair. No filter-dependent rank recalculation or overlap sum.
Schema2 reader/hash/Markdown and private NAV golden bytes stay compatible; schema3 binds
both views into the same existing atomic JSON/Markdown pair and one snapshot hash.
