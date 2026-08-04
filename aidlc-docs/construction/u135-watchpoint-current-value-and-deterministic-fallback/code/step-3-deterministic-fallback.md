# u135 Step 3 — Deterministic fallback synthesis

## Outcome

- Added pure `publisher/watchpoint_fallback.py` with closed range, CFTC, fear,
  and greed field templates.
- Synthesized at most two existing-shape `WatchpointRow` values in strict range
  → CFTC → F&G order.
- Performed no I/O, LLM call, public rendering, compliance decision, or quality
  snapshot mutation; those remain Step 4 owners.

## Signal contracts

- Crypto range requires a reconciled anchor plus same-symbol CoinGecko 24h
  high/low enclosing the close.
- US/domestic range reconstructs 52w high/low from the reconciled anchor's
  signed distance percentages and rejects nonpositive/zero-quantized bounds.
- CFTC requires an approved segment group, integer net short, and a consistent
  negative OI percentage; confidence is `보통`.
- F&G requires an integer 0–100 extreme. Values ≤20 use the pinned fear 20/10
  branch; values ≥80 use a separately closed greed 90/80 branch with the same
  shape/source/confidence/impact.
- Every synthesized row uses the existing u98 shape and never carries the
  low-coverage confidence label.

## Semantic correction

The original plan admitted both F&G extremes but supplied only fear-oriented
20/10 conditions. Rendering those conditions beside `85 (극단 탐욕)` would be
self-contradictory. Step 3 therefore ratified a second closed template rather
than inventing free text or silently dropping the planned ≥80 signal.

## Review and validation

- Fresh-eyes review initially found one High, one Medium, and one Low issue:
  extreme-greed threshold semantics, CFTC sign inconsistency, and a possible
  zero-after-quantization equity bound. All were fixed and re-reviewed with no
  remaining findings.
- Matrix + fallback tests: 62 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
