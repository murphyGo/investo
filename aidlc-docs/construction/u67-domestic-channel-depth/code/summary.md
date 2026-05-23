# u67 domestic-channel-depth — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u67 domestic-channel-depth
**Status**: Complete (7/7 steps)

## Goal

Give the domestic-equity channel a reliable index-close line, a 원/달러 anchor, sector depth for 반도체/2차전지, and an explicit overnight-US → KR-open bridge — all from free sources, without weakening compliance, channel separation, or module boundaries (plan Problem Statement gaps 1-4).

## Step 1 — Free-Source Reachability (live 2026-05-24)

| Need | Source probed | Result | Decision |
|------|---------------|--------|----------|
| 원/달러 환율 | yfinance `KRW=X` | HTTP 429 | Not used |
| 원/달러 환율 | Stooq `usdkrw` | 200 / close 1518.21 | **Primary** |
| KOSPI close | Stooq `^kospi` | 200 / close 7847.71 | Fallback after KRX |
| KOSDAQ close | Stooq `^kosdaq` (+4 variants) | all N/D | No Stooq tier — yonhap-parse only |
| KOSPI/KOSDAQ news close | Yonhap `market.xml` | 200 (UA required) | best-effort numeric parse (terminal fallback) |
| 반도체 / 2차전지 가격 | existing `fsc-krx-stock-price` | already collected | grouping gap → handled in prompt, not a new fetch |

**Confirmed precedence**:
- 원/달러 = Stooq `usdkrw`.
- KOSPI close = KRX (`fsc-krx-index-price`) → Stooq `^kospi` → Yonhap numeric parse.
- KOSDAQ close = KRX (`fsc-krx-index-price`) → Yonhap numeric parse (Stooq carries no KOSDAQ symbol).

No paid key introduced; all chosen sources are no-key free tier. Fixtures recorded per R10.

## Key Deliverables

- `src/investo/sources/stooq_kr_market.py`: no-key adapter `stooq-kr-market` — Stooq CSV (`usdkrw`, `^kospi`) primary + Yonhap `market.xml` RSS numeric-close parse as the terminal index fallback; KST market-close `published_at` semantics; per-symbol failure isolation.
- `src/investo/sources/__init__.py`: adapter registered (`@register` import path).
- `src/investo/briefing/segments.py`: `stooq-kr-market` added to `_DOMESTIC_ONLY_SOURCES`.
- `src/investo/briefing/prompts.py`: `DOMESTIC_DEPTH_NOTE` — 반도체 (삼성전자/SK하이닉스) + 2차전지 grouping hint + overnight-US → KR-open bridge instruction (domestic-scoped, compliance-safe).
- `src/investo/briefing/pipeline.py`: `_render_segment_context` threads the domestic depth note into the Stage-2 domestic prompt scope.
- `src/investo/orchestrator/pipeline.py`: `_ANCHOR_SEGMENT_ROUTING` + `_build_kr_anchors_from_items` so the domestic anchor table carries KOSPI/KOSDAQ close, 등락률, and 원/달러.
- `src/investo/publisher/anchor_table.py`: `_TABLE_PRIORITY` updated for the domestic anchor rows.
- Fixtures under `tests/unit/sources/fixtures/api/stooq-kr-market/`: `usdkrw.csv`, `kospi.csv`, `kosdaq.csv` (live recordings), `yonhap_index.xml` (synthetic — labelled in `meta.json` per R10).
- Tests: `tests/unit/sources/test_stooq_kr_market.py`, `tests/unit/sources/test_kr_anchors.py`, `tests/unit/briefing/test_segment_depth_notes.py`; `tests/unit/sources/test_plugin_contract.py` count 26 → 27.
- `docs/tech-env.md`: domestic FX / index source list + ticker docs.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-1 | KRX empty → KOSPI (and KOSDAQ when available) close + 등락률 with provenance in body | MET | `stooq-kr-market` Stooq `^kospi` + Yonhap parse fallback; provenance tag in trace; `test_stooq_kr_market.py` mocks KRX-empty path |
| AC-2 | `usd_krw` populated from free source + 원/달러 anchor line in body | MET | Stooq `usdkrw` → `_core_fact_map` `usd_krw`; `_build_kr_anchors_from_items` renders FX row; `test_kr_anchors.py` |
| AC-3 | 반도체 (삼성전자/SK하이닉스) + 2차전지 narrated in §③ when prices collected | MET | `DOMESTIC_DEPTH_NOTE` grouping hint; existing `fsc-krx-stock-price` supplies prices; `test_segment_depth_notes.py` |
| AC-4 | Overnight-US → KR-open bridge sentence, domestic-scoped, no cross-segment leakage | MET | `DOMESTIC_DEPTH_NOTE` bridge instruction; existing `cross_segment_lint` BC-3 already passes — no lint change required |
| AC-5 | No paid key; free-tier; per-source isolation; `defusedxml` on RSS; channel separation + disclaimer untouched | MET | `stooq-kr-market` no-key; per-symbol isolation in adapter; Yonhap parse via `defusedxml`; no notifier/publisher gate change |

## FD Divergences Ratified

- KOSDAQ has no Stooq symbol (all 5 variants returned N/D live), so the index-close precedence chain for KOSDAQ skips the Stooq tier (KRX → Yonhap-parse only). The plan's "KRX → Stooq → yonhap-parse" precedence holds for KOSPI but is two-tier for KOSDAQ. Recorded in `u1-sources` FD (R15 / L6.12) and the audit entry.
- yfinance `KRW=X` is unusable on the GHA path (live 429); the FX primary is Stooq `usdkrw`, not yfinance as the plan's reachability table listed first. Ratified in FD L6.12.

## TECH-DEBT Registered

- **DEBT-068** — Yonhap numeric-index parse is genuinely best-effort: when KRX + Stooq are both blank and no numeric headline exists, the index close is omitted (surfaced via coverage badge, not hard-fail). A dedicated free KRX index RSS would harden the terminal tier.
- **DEBT-069** — Domestic anchor rows are close-only (Yahoo KR history 429); the note column renders `—`. A future free KR history source could backfill the note column.

## Verification Gate

| Gate | Result |
|------|--------|
| `ruff check` | clean |
| `ruff format --check` (changed scope) | clean |
| `mypy --strict` | clean (131 files) |
| `pytest -q` | 2428 passed (+16 net; +19 new domestic tests) |
| `mkdocs build --strict` | clean |

Lead re-verification: 19 new tests pass, only `defusedxml` used for RSS, no secret / paid key introduced (R13 + R1 clean).
