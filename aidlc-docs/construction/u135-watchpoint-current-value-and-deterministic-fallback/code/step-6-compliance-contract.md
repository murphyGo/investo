# u135 Step 6 — Structure and compliance contract

## Outcome

- Exercised all four closed template branches—RANGE, CFTC, FEAR, and GREED—
  through the real payload synthesis and card renderer.
- Verified each rendered card against the existing u64 source, trigger, and
  implication regex owners instead of duplicating their patterns.
- Verified each card contains no action/certainty/crypto P0 literal, matches no
  quantified-outcome P0 pattern, and returns no P0 hit from `scan_compliance`.
- Pinned forced partial rejection as one rendered, usable, synthesized card on
  both passes with byte-identical public output.
- Pinned forced total rejection as a non-blocking canonical limited note with
  zero usable/synthesized cards.

## Ownership

The tests reuse `models.compliance_phrases`, `reader_format` u64 regex exports,
and `publisher.compliance_language.scan_compliance`. u135 adds no phrase list,
scanner, structure regex, or exception policy.

## Review and validation

- Fresh-eyes review found no blocking issue.
- One Low test-strength recommendation requested explicit `rendered` and
  `usable_card_count == 1` checks after a partial drop; both were added.
- Compliance, reader-format, fallback, and orchestration gate: 101 passed.
- Scoped Ruff, format, and `git diff --check`: passed.
