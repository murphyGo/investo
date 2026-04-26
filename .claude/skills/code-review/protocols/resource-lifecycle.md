# Resource Lifecycle Protocol

## Trigger

Code acquires handles to external resources — files, network connections, database handles, HTTP clients, temporary allocations — that require explicit release.

## Analysis Steps

### 1. Acquisition-Release Pairing

For each resource acquired in the code:
- Identify the acquisition point (open, dial, connect, allocate)
- Identify the release point (close, disconnect, free, return-to-pool)
- Verify the release is **unconditional** — happens on all exit paths (success, error, panic)

Flag:
- **Unpaired acquisition** — resource opened but never closed
- **Conditional release** — close only on happy path, not on error branches
- **Late release** — resource held longer than necessary, blocking other consumers

### 2. Error Path Walk

For each function that acquires a resource:
- Trace every `return` / `throw` / early exit after acquisition
- At each exit point: is the resource released?
- For **multi-resource functions** where resource B is acquired after A — if B fails, is A still released?

```
acquire A
acquire B   <- if this fails, is A released?
use A + B
release B
release A
```

Flag:
- **Early return leaks resource** — return between acquire and deferred release
- **Multi-acquire partial failure** — second acquisition fails, first not cleaned up
- **Exception bypasses cleanup** — throw/panic between acquire and release

### 3. Ownership Transfer Analysis

When a resource handle is passed to another function or stored in a struct:
- Who is responsible for closing it — caller or callee?
- Is ownership documented or unambiguous from the API?
- Can the resource be double-closed if both caller and callee release it?

Flag:
- **Ambiguous ownership** — unclear who closes the resource
- **Double-close** — both caller and callee attempt to release
- **Orphaned after transfer** — resource stored in struct but struct has no cleanup method

### 4. Lifecycle Scope Check

- Is the resource scope as narrow as possible?
- Could the acquisition be moved closer to the usage point?
- Are long-lived resources (pools, caches) bounded and have health checks?

Flag:
- **Overly broad scope** — resource acquired at function start but used only in one branch
- **Long-lived without health check** — connection may go stale

### 5. Pool and Long-Lived Resource Health

For connection pools, thread/worker pools, and other managed resource sets:
- Is the pool size bounded? What happens when exhausted — block, reject, or grow unbounded?
- Do pooled resources have health checks or staleness eviction?
- Are pool metrics exposed (active, idle, waiting, exhausted)?
- For long-lived background workers: do they have liveness checks or watchdog supervision?

Flag:
- **Unbounded pool growth** — pool creates resources without limit under load
- **No health check** — stale or broken resources returned from pool
- **Silent exhaustion** — pool full with no metric, log, or timeout
- **Orphaned worker** — background task with no supervision or restart on failure
