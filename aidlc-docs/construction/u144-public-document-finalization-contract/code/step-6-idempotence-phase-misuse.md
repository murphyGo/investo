# Step 6.1 Idempotence and Phase Misuse

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

Lifecycle tests now prove both supported outcomes for repeated finalization:

- re-entering the generated boundary with the sealed document's compatibility
  `Briefing` produces byte-identical Markdown and the same SHA-256 seal;
- directly passing an E4 validated draft to the segment lifecycle is rejected
  as explicit `invariant.segment_start_phase` misuse.

The byte-stability fixture pins exactly one segment nav, one `## ①`, one
`## ⑥`, and one canonical disclaimer after the repeated lifecycle. Existing
tests continue to pin byte-idempotent public projection and idempotent typed
supplement wrapping.

## Validation

- public-document lifecycle/type tests: 42 passed;
- scoped Ruff and format check: passed;
- no production code, dependency, source, secret, network, or workflow change.
