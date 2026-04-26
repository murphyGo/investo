# Memory Analysis Protocol

## Trigger

Code allocates large buffers or collections, appends to structures without bounds, holds references that prevent garbage collection, or processes bulk data without streaming.

## Analysis Steps

### 1. Growth Bound Analysis

For each collection or buffer that grows dynamically:
- Is there an upper bound on its size?
- What controls the growth — user input, external data, time?
- What happens if the bound is exceeded — OOM, graceful rejection, or silent degradation?

Flag:
- **Unbounded append** — collection grows without cap or eviction
- **Input-proportional allocation** — buffer sized by external input without validation
- **Accumulator without flush** — data accumulated across iterations/requests without periodic release

### 2. Lifetime and Retention

For each significant allocation:
- When is it eligible for collection/deallocation?
- Is it held longer than necessary? (stored in long-lived struct when only needed briefly)
- Could references in closures, callbacks, or caches prevent timely release?

Flag:
- **Closure capture** — large objects captured by closures that outlive intended scope
- **Cache without eviction** — in-memory cache that grows monotonically
- **Global/package-level collections** — populated at runtime without cleanup

### 3. Streaming Feasibility

For bulk data processing:
- Is the entire dataset loaded into memory, or processed as a stream?
- Could the operation work on chunks/batches instead of the full set?
- Is there a memory-bounded alternative (iterators, readers, channels)?

Flag:
- **Full materialization** — entire result set loaded when streaming would work
- **Large intermediate copies** — data copied between formats unnecessarily

### 4. Allocation on Hot Path

For code called at high frequency:
- Are there per-call allocations that could be pooled or reused?
- Are intermediate results allocated and immediately discarded?
- Could pre-allocated buffers reduce GC pressure?

Flag:
- **Per-request allocation of reusable objects** — pool candidate
- **String concatenation in loop** — use builder/buffer instead
- **Repeated serialization buffer creation** — reuse across calls
