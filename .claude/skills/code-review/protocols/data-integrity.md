# Data Integrity Protocol

## Trigger

Code performs durable writes (write-ahead logs, checkpoints, snapshots), uses atomic file or record operations (temp-write + rename, compare-and-swap), implements crash recovery logic, or makes delivery/ordering guarantees about data flowing through a pipeline.

## Analysis Steps

### 1. Atomic Write Correctness

For each operation that must be all-or-nothing:
- Is the write truly atomic from the perspective of a crash at any point?
- For file-based atomicity (temp + rename): is the temp file on the same filesystem? Is data flushed before rename? Is the directory entry synced after rename?
- For database/store-based atomicity: is a transaction or compare-and-swap used? What isolation level?

Flag:
- **Flush gap** — data written but not flushed to stable storage before considered committed
- **Cross-volume rename** — temp file on different mount than target (non-atomic)
- **Directory sync omission** — file synced but directory entry not (metadata lost on crash)
- **Partial write exposure** — readers can observe an in-progress write

### 2. Crash Recovery Analysis

Simulate a crash (power loss, process kill) at each step of a multi-step write sequence:
- For each step: what state is on stable storage?
- On restart: does recovery logic detect the incomplete state?
- Is data replayed, skipped, or corrupted?

Flag:
- **Unrecoverable gap** — crash at a specific point leaves data neither committed nor recoverable
- **Silent data loss** — recovery skips uncommitted data without logging or alerting
- **Replay without idempotency** — recovered data replayed into system that doesn't handle duplicates
- **Checkpoint drift** — checkpoint updated before the operation it records is durable

### 3. Ordering and Delivery Guarantees

Identify what the code promises about event/message flow:
- At-most-once, at-least-once, or exactly-once?
- Per-partition/per-key ordering, global ordering, or unordered?
- Does the implementation uphold these guarantees under normal operation, retry, and crash recovery?

Flag:
- **Guarantee mismatch** — API promises stronger semantics than implementation delivers
- **Retry reordering** — retry of failed write arrives after a subsequent write
- **Duplicate emission** — same data emitted more than once without deduplication

### 4. Pipeline Stage Failure Isolation

For multi-stage data pipelines (buffer -> log -> external system):
- If a downstream stage fails, does backpressure propagate or does upstream silently drop data?
- Is there a dead-letter or fallback path for undeliverable data?
- Can a stage failure cause unbounded buffering in the preceding stage?

Flag:
- **Silent drop** — data discarded on downstream failure without metric or dead-letter
- **Backpressure gap** — upstream continues at full rate while downstream is stuck
- **Poison message** — single malformed record blocks entire pipeline with no skip mechanism
