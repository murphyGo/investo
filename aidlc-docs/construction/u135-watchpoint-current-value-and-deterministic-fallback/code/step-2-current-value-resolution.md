# u135 Step 2 — Current-value resolution

## Outcome

- Added publisher-owned `WatchpointValuePayload` with immutable scalar metadata
  snapshots and reconciled `MarketAnchor` inputs.
- Resolved non-numeric `현재:` fields from exact signal tokens for canonical
  anchors, CoinGecko price, F&G, funding/OI, and segment-correct CFTC rows.
- Omitted payload-backed rows whose final current value contains no digit and
  has no exact resolution candidate.
- Repaired canonical legacy cards once; the repaired output is byte-idempotent.

## Fixed-contract behavior

- Anchor candidates use `anchor_label` ticker/short/Korean/display tokens and
  the segment's reconciled anchor family only.
- Crypto-only candidates cannot resolve in US or domestic payloads. CFTC rows
  require `crypto` or the approved US contract groups; domestic consumes no
  item-derived candidate.
- Candidate selection uses exact ASCII/Hangul token boundaries and longest
  matching-token specificity. Partial symbols and embedded Korean substrings do
  not match.
- Source promotion happens before current substitution, so u110 source
  ownership is preserved.
- Supplying a payload requires an explicit matching render segment. Omitting or
  mismatching the segment fails fast.
- Existing numeric current text and every no-payload call preserve prior u110
  behavior.

## Numeric and mutation safety

- Raw item metadata is copied to immutable `(key, value)` tuples; mutating the
  original `NormalizedItem.raw_metadata` after payload construction cannot
  change resolution.
- Price/OI must be finite and positive; funding is finite and bounded; F&G is
  an integer in 0–100; CFTC percentage is bounded to ±100; all numeric text and
  display magnitudes are capped before allocation.
- Malformed, nonfinite, negative, or oversized candidates fail closed.

## Review and validation

- Fresh-eyes review initially found one High, two Medium, and one Low issue:
  missing segment gates, shallow metadata freezing, optional segment identity,
  and incomplete numeric domains. All were fixed and independently re-reviewed
  with no remaining findings.
- Watchpoint matrix tests: 55 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
