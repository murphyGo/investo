# u130 Code Generation Step 3 — Discontinuity Quarantine

## Scope Delivered

- Added `discontinuous` to `DomesticAnchorTrust`.
- Applied a strict `>15%` threshold to `^KOSPI`, `^KOSDAQ`, and `KRW=X`.
- Applied a strict `>30%` threshold to `005930.KS` and `000660.KS`.
- Threaded optional previous-close mappings through `domestic_anchor_verdicts` and `trusted_domestic_price_items` without changing existing callers.
- Added `load_previous_domestic_anchor_closes` for the prior seven calendar days.

## Archive Lookup Contract

The existing quality archive iterator is now the shared public walk and remains the owner of bounded archive enumeration. The u130 loader calls it with:

- `today = target_date - 1 day`;
- `window_days = 7`;
- domestic archive filtering;
- newest-first ISO-date ordering;
- first valid close wins independently per symbol.

This produces the exact inclusive range `target_date - 7 days` through `target_date - 1 day`, including weekend publications. It does not create a second date scanner.

The actual repository lookup for target `2026-06-30` returned:

- `^KOSDAQ = 477.00`;
- `^KOSPI = 8,800.00`;
- `005930.KS = 339,500.00`.

## Failure Semantics

- No prior value inside the window skips continuity classification.
- Missing or unreadable archive files are skipped.
- Non-positive, `NaN`, and infinite historical values are ignored.
- A directly supplied non-finite previous value also skips continuity classification.
- Non-finite candidate close/change metadata is `implausible`; it cannot raise during band or ratio comparison.
- Static plausibility, provenance, source-health, and staleness decisions retain precedence over continuity.

## Review

The first fresh-eyes pass found:

1. High — the initial recent-context loader skipped weekend publications;
2. Medium — non-finite Decimal history could raise during comparison.

Both were fixed by reusing the weekday-agnostic quality archive iterator and validating Decimal finiteness. Re-review approved Step 3 with no Critical/High/Medium issue. A Low request for downside and FX threshold coverage was also addressed.

## Validation

- `uv run pytest tests/unit/orchestrator/test_domestic_anchor_quarantine.py -q` — 22 passed.
- Related quality/recent-context/anchor/FRED regressions — 45 passed.
- `uv run pytest tests/unit/orchestrator -q` — 429 passed.
- `uv run ruff check ...` — passed.
- `uv run ruff format --check ...` — passed.
- `uv run mypy src` — passed, 248 source files.
- `git diff --check` — passed.

## TECH-DEBT

None added.

## Next Step

Step 4 loads this mapping once per run and supplies it consistently to domestic anchor assembly, quality-history reason aggregation, and the notification-side trusted-item filter.
