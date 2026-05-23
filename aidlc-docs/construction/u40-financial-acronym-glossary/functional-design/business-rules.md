# Business Rules — `u40 financial-acronym-glossary`

**Date**: 2026-05-09 (baseline) / 2026-05-24 (cross-day suppression extension)
**Source**: u40-financial-acronym-glossary-code-generation-plan.md (baseline) + u68-reader-aids-residual-code-generation-plan.md (extension)

Rules are listed in order of precedence. This FD is authored
retroactively at u68 close to host the cross-day suppression business
rule (`R-glossary.4`); `R-glossary.1`..`R-glossary.3` re-state the
contract already shipped by u40.

---

## R-glossary.1. First-appearance gloss requirement (FR-002, US-001/US-005)

- Every `BASELINE_GLOSSARY` term (financial acronym, futures code, market
  jargon) must carry a 1-3-word Korean paren gloss on its first
  appearance **per segment**.
- Subsequent appearances in the same segment do not need a re-gloss.

## R-glossary.2. Per-segment gloss scope

- Each segment (us-equity / domestic-equity / crypto) is its own gloss
  scope. A gloss in one segment never satisfies another segment's
  first-appearance requirement.

## R-glossary.3. Informational, non-blocking callout

- Glossary gaps render a soft `> **용어 가이드**` header callout, capped at
  5 terms with an `외 N건` suffix. The callout never blocks publication.

---

## R-glossary.4. Callout "처음 등장한" claim is scoped to the recent trading-day window (extension 2026-05-24, u68)

- The header callout's "이번 시황에서 처음 등장한 용어" claim is true only
  within a bounded recent window. A `BASELINE_GLOSSARY` term that was
  already glossed in the **same segment's** prior ≤N loaded trading-day
  archives (default N=3, bounded by `_MAX_CALENDAR_DAYS=21` calendar days)
  is suppressed from today's callout — it is not re-announced as
  "first appearance."
- "Already glossed in a prior archive" = the term appeared with an
  immediate Korean paren gloss OR inside a prior `> **용어 가이드**`
  callout line for that segment.
- When suppression empties the gap list, no callout line is emitted
  (R-glossary.3 empty-gaps behavior). No empty/false `> **용어 가이드**`
  line is ever produced.
- Degradation: missing/malformed/`OSError` archives contribute nothing
  and never raise; `archive_root=None` (fresh repo / data-limited) yields
  an empty suppression set → today-only behavior identical to
  R-glossary.1 (no regression).
- Idempotency (FR-006): the same `(segment, date, archive state)` yields a
  byte-equal callout.

**Violation**: re-firing the "처음 등장한" callout for a term glossed within
the recent window; emitting an empty `> **용어 가이드**:` line; raising on a
malformed/missing archive. Reject in review.
