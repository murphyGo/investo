# u135 Step 5 — 2026-06-29/30 incident regressions

## Outcome

- Added a 2026-06-29 crypto legacy-card fixture containing the production
  `현재: CoinGecko BTC` defect plus both reconciled anchor and CoinGecko item
  candidates. It now resolves to `$60,284.00 (+2.23%)` and never leaves the
  source label in the value slot.
- Added a 2026-06-30 US archive-shaped bounded-note fixture. The reconciled
  anchor plus exact archived CFTC row yields two cards in range → CFTC order
  with typed synthesized count 2.
- Added an empty-payload fixture that preserves the existing canonical bounded
  note byte-for-byte.

## Resolution precedence correction

The incident fixture exposed an equal `BTC` token tie between the core anchor
and CoinGecko snapshot. Candidate scoring now uses semantic indicator class,
then longest exact token, then source specificity, then stable input order.
This lets a `CoinGecko BTC` price card select its named snapshot while
separator-delimited `BTC · 펀딩` and `BTC · OI` remain funding/OI values. Asset
token matching is still mandatory and uses the existing exact boundaries.

## Fixture provenance

The US close, 52w-high distance, CFTC row, and bounded-note shape are evidenced
by the retained public archive. That archive does not expose the raw
`pct_from_52w_low` field needed to reconstruct both range bounds, so the
fixture marks its `20.00` value as a synthetic internal range-enabler. This is
an incident-shaped regression, not a claim of byte-identical raw-payload replay.

## Review and validation

- Fresh-eyes review found one High precedence regression: separator-delimited
  funding/OI could lose to the CoinGecko price source cue. Semantic indicator
  priority and two targeted regressions closed it; re-review approved.
- Focused matrix/fallback/incident suite: 68 passed.
- Full publisher unit suite: 1,022 passed.
- Fixture JSON, scoped Ruff/format, mypy, and `git diff --check`: passed.
- No security, R13, I/O, secret, or logging surface was added.
