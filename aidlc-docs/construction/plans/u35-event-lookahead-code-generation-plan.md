# Code Generation Plan: `u35 event-lookahead`

**Date**: 2026-05-08
**Unit**: u35 event-lookahead
**Stage**: Code Generation

---

## Goal

Lift each daily briefing from a backward-looking recap into forward-looking context by surfacing the upcoming week's and month's high-impact scheduled events (FOMC / FRB calendar, US macro releases, Big Tech earnings, KRX option-expiry, crypto token unlocks / major upgrades) inside the segment narrative — vertical slice from source adapter to LLM prompt to segment markdown to Telegram summary, all on free public data and within existing budgets, gates, and module boundaries.

---

## Definition of Done

- [ ] Forward-looking event coverage extends across all 3 segments via free public sources only:
  - Existing `nasdaq-earnings-calendar` lookahead window opt-in (past N days + next 7 days) instead of past-only.
  - New FOMC / FRB calendar adapter (Federal Reserve public RSS or ICS) for US macro segment.
  - New US economic-release calendar adapter (FRED / Treasury / BLS public release-schedule feed).
  - New crypto event adapter (CoinGecko events public endpoint or equivalent free source) for token unlocks / major upgrades.
  - KRX option-expiry / 공시 lookahead for domestic-equity segment when a free RSS/JSON feed exists; otherwise registered as a follow-up TECH-DEBT, not a blocker.
- [ ] Model layer expresses scheduled time distinct from publish time: `NormalizedItem.scheduled_at: datetime | None` (None = backward-looking item, retains existing semantics); a forward-looking category flag (reuse `Category.EVENT_CALENDAR` or add a sibling) routes items into a separate lookahead bucket.
- [ ] `FetchWindow` / aggregator runs two passes per market timezone — the existing backward window (KST / America/New_York / UTC per u8) plus a forward lookahead window (`+7d` short-term + `+30d` long-term derived from `now`); lookahead pass applies the same R14 fair-access UA policy and the same `retry_get` identity-encoding contract (u11).
- [ ] Stage 1 classification prompt gains a forward-looking sub-category contract so past issues and scheduled events do not blur; Stage 2 system prompt adds a "주요 일정" section with explicit rules: (a) cite only the events present in the input, (b) **no arbitrary forecast or impact estimate** (extension of u25 numeric-integrity rule), (c) prefer "이번 주" (오늘 ~ +7일 KST) and "이번 달" (오늘 ~ 월말) framing.
- [ ] Briefing pipeline applies a separate sub-cap to lookahead candidates inside the existing u13 total-96 / per-source-24 LLM input cap (proposed: max 12 lookahead items per segment) so a high-volume earnings calendar cannot starve backward evidence.
- [ ] Segment markdown renders the lookahead block — either as a dedicated section (e.g., "## ⑥-2 주요 일정") or a clearly-fenced sub-block inside the existing ⑥ 관전 포인트 — without breaking the u15 coverage badge contract or the u20 archive trust contract.
- [ ] Telegram summary "오늘 한 줄" prepends an imminent-event tag (deterministic, not LLM-generated) when an event sits inside a 24~72h horizon, e.g. `📅 FOMC D-2`, `📊 NVDA 실적 D-1`; absence of imminent events leaves the line unchanged.
- [ ] `SegmentCoverage` carries a new `reason_code` for "주요 일정 데이터 부족" (extension of u22 source coverage transparency) so missing FOMC / earnings / unlock feeds are visible to the reader and operator instead of silently empty.
- [ ] Token / character budget guard for the lookahead block: ~300 chars per segment, fully separate from the u34 recent-context ~500-char-per-segment-per-day budget so segment context stays under ~800 chars per segment.
- [ ] R8 (no raw stdlib XML — `defusedxml` only for any new RSS/ICS adapter) and R13 (secret hygiene; sanitize chokepoint at u27 redaction module) preserved across all new adapters and new render surfaces.

---

## Steps

### Step 1 — Source Layer (Forward-Looking Adapters)

- [ ] Extend `nasdaq-earnings-calendar` to opt-in lookahead (next 7 days) while preserving its existing backward window contract.
- [ ] Add `fomc-calendar` adapter (Federal Reserve public RSS / ICS) under the existing `@register` plugin pattern, `retry_get` + `strip_html` + `defusedxml` per R8.
- [ ] Add `fred-economic-calendar` adapter (FRED / Treasury / BLS release-schedule public feed) for US macro.
- [ ] Add `coingecko-events` adapter (or equivalent free crypto event endpoint) for token unlocks / major upgrades.
- [ ] Investigate KRX option-expiry / 공시 lookahead; ship if a free feed exists, otherwise log as TECH-DEBT and proceed.
- [ ] All new adapters apply R14 fair-access UA policy and identity-encoding (u11).

### Step 2 — Model Layer

- [ ] Add `NormalizedItem.scheduled_at: datetime | None` (None = backward-looking, default).
- [ ] Confirm or add forward-looking category enum value; ensure router separates lookahead items from backward items into per-segment buckets.

### Step 3 — Aggregator + FetchWindow Lookahead

- [ ] Add `FetchWindow.lookahead(days_short, days_long)` (or equivalent) producing forward windows aligned to each adapter's market timezone (KST / America/New_York / UTC per u8).
- [ ] Aggregator runs the existing backward pass plus a lookahead pass; per-source `SourceOutcome` records both windows so u22 coverage transparency reports them honestly.

### Step 4 — LLM Prompt + Briefing Layer

- [ ] Stage 1 classification prompt gains an explicit forward-looking contract (past vs scheduled).
- [ ] Stage 2 system prompt adds "주요 일정" section + the three usage rules (input-only citation / no forecast / 이번 주·이번 달 framing).
- [ ] `briefing/pipeline.py::_select_llm_candidate_items` (or equivalent) applies the lookahead sub-cap (max 12 per segment) inside the u13 total-96 / per-source-24 cap.
- [ ] Segment markdown renderer inserts the lookahead block at a stable anchor; data-limited fallback path stays valid when zero lookahead items are present.
- [ ] `SegmentCoverage.reason_codes` adds the "주요 일정 데이터 부족" code wired through u22's source-status block.

### Step 5 — Notifier Surface (Imminent Tag)

- [ ] `notifier/summary.py::_one_line_summary` (or equivalent) computes the imminent-event tag deterministically from the lookahead bucket (D-distance ≤ 72h, capped to top-1 by deterministic ordering) and prepends it to the segment one-liner; LLM is not asked to generate this tag.
- [ ] Absence of imminent events keeps the line unchanged; coverage_hold / unconfigured branches skip the tag.

### Step 6 — Verification

- [ ] Unit tests per new adapter under record/replay fixture pattern (per u1 plugin contract).
- [ ] Aggregator regression: lookahead window correctly aligned per market TZ; backward window unaffected.
- [ ] Prompt regression: Stage 1 forward-vs-past contract; Stage 2 "주요 일정" section + no-forecast rule.
- [ ] Briefing markdown regression: lookahead block render + zero-item fallback + coverage reason code.
- [ ] Notifier regression: imminent-tag deterministic order, ≤ 72h gating, suppression on coverage_hold / unconfigured.
- [ ] `leak_guard.scan` + `verify_disclaimer` + `summary_quality` no-regression.
- [ ] Full quality gate (`ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest -q`, `mkdocs build --strict`).

---

## Source

User direct request 2026-05-08: "어제/오늘일은 아니지만 이번주나 이번달 중요한 이벤트가 있으면 미리 파악해서 주요 일정을 시황에 포함하면 좋을듯. 그러기 위해서는 데이터소스부터 프롬프트 생성까지 전부 건드려야 할 듯. 일단 계획후 유닛 만들고 진행." Wave 4 (사용자 직접 요청 — 페르소나 평가 wave 와 분리; u34 와 동일 wave). Aligned with persona #3 (analyst) and persona #4 (watchlist tracker) wish-list signals around "옵션·실적·배당락 캘린더 7-day 룩어헤드"; partial overlap with u33 watchlist depth (u33 = watchlist-specific lookahead, u35 = general segment lookahead — kept distinct so provenance stays clean). No new paid API, no module-boundary change (orchestrator → sources / briefing only); R8 / R13 / R14 preserved across new adapters.
