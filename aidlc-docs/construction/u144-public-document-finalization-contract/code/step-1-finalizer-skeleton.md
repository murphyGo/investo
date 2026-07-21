# Step 1.2 Pure Finalizer Skeleton

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The publisher-private skeleton now fixes the coordinator shape without
pretending that later phase algorithms are complete:

- one generated draft passes exactly through `assembled`, `projected`,
  `repaired`, and `validated` pure handlers;
- every handler result is asserted for phase, segment/date, and original
  generated-briefing identity before the next handler can run;
- phase/identity/draft-factory/artifact-selection and other programmer
  invariant failures are converted at the bundle boundary into bounded E8
  codes with the typed cause retained but not rendered;
- sealing occurs only after the validated witness and selects only staged
  artifact IDs already present in the segment's E1 descriptors;
- the bundle coordinator requires briefing keys to equal expected segments
  minus typed generation absences, preserves canonical expected order, and
  turns non-degradable typed segment signals into `trust_blocked` outcomes;
- zero survivors raise bounded E8, while any surviving subset is built through
  the E1-derived E6 factory.

Concrete assembly/projection/repair/validation handlers and the active-survivor
fixed point remain later explicit checklist items. The skeleton is publisher-
private and has no production caller or environment flag.
