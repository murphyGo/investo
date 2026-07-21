# Step 6.3 Partial Fixed-Point Matrix

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The bundle lifecycle tests now pin the complete bounded-partial matrix:

- initial generation absence remains `generation_absent`;
- `bundle_context=None` skips the neutral thesis redecision owner;
- one terminal trust block preserves a valid sibling;
- a notification-summary trust block preserves a valid sibling and its bounded
  issue code;
- two sequential trust blocks restart from original generated inputs and
  converge on the third and final pass;
- zero generated or zero surviving documents raises bounded E8;
- the surviving document renders canonical u63 navigation with both removed
  siblings marked `미발행`; and
- three expected segments produce at most three active-survivor passes.

The sequential test records every `(segment, active_segments)` assembly call.
Its exact 3 + 2 + 1 sequence proves both restart semantics and the strict pass
bound without relying on implementation-source inspection.

## Validation

- public-document lifecycle/type tests: 44 passed;
- scoped Ruff and format check: passed.
