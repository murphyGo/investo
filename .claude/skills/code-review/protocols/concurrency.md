# Concurrency Analysis Protocol

## Trigger

Code accesses shared mutable state from multiple concurrent execution contexts (threads, goroutines, coroutines, async tasks, worker processes). Skip only if the code is entirely single-threaded with no async.

## Analysis Steps

### 1. Critical Section Boundary Map

For every public method that touches shared state, draw where mutual exclusion (lock, synchronized block, critical section) is acquired and released.

Flag **split critical sections** — where a method acquires exclusion, releases it, does work (I/O, network), then re-acquires. These are the highest-risk pattern.

```
MethodA(): [===critical===] ... I/O ... [===critical===]   <- split: HIGH RISK
MethodB(): [===============critical================]       <- single: lower risk
```

Flag:
- **Lock exists but data also accessed without it** — partial protection
- **Lock held across I/O or blocking calls** — contention and deadlock risk
- **Split critical section** — state can change between the two locked regions

### 2. Gap Interleaving Analysis

For each gap between critical sections in a split pattern:
- **Cross-method**: which fields can another method mutate during the gap?
- **Self-to-self**: what happens if the **same method** runs concurrently? (most commonly missed)
- Write at least one **concrete T1/T2 timeline** per gap:

```
T1: Save()  critical{ snapshot=count(50) }
T2: Save()                                  critical{ snapshot=count(50) }
T1:          I/O -> critical{ count -= 50 }                                   count: 50->0
T2:                                          I/O -> critical{ count -= 50 }   count: 0->-50 <- BUG
```

Flag:
- **Read-modify-write without atomicity** — classic race condition
- **Check-then-act without holding lock across both** — TOCTOU

### 3. Signal-Action Chain

Trace return values or callbacks that trigger caller actions:
- Method A returns a signal -> caller invokes method B
- Can two execution contexts both receive the signal simultaneously?
- Does this create concurrent calls to method B? (feeds back into step 2)

Flag:
- **Broadcast where signal suffices** — thundering herd
- **Signal sent but receiver may have exited** — lost wakeup

### 4. Field Invariant Verification

For each mutable field protected by the concurrency primitive:
- State the invariant (e.g., `counter >= 0`)
- Verify it holds under ALL interleaving scenarios from step 2
- If violated, describe the concrete impact

Flag:
- **Some fields protected, others not** — partial protection of related fields
- **Invariant between fields not maintained atomically** — e.g., `len <= cap`

### 5. Channel / Queue Coordination Analysis

For each message-passing primitive (channels, queues, mailboxes, pipes):
- Is it bounded or unbounded? What is the capacity rationale?
- Can a send block indefinitely — is there a timeout or cancellation path?
- Can a receive block after the producer has terminated — is the channel closed?
- Is the close signal issued exactly once, and only by the producing side?

Flag:
- **Unbounded channel/queue** — memory growth under load
- **Blocking send without timeout** — deadlock risk
- **Competing consumers closing the same channel** — double-close panic
- **Select/poll without cancellation branch** — blocks forever if no message

### 6. Graceful Shutdown Ordering

When the system performs ordered shutdown of multiple concurrent components:
- Map the shutdown dependency graph (ingress -> processing -> egress -> storage)
- Is the drain timeout sufficient for in-flight work to complete?
- Can a component block shutdown by not responding to cancellation?
- After shutdown completes, can late-arriving work still be enqueued?

Flag:
- **No cancellation mechanism** for long-running workers
- **Resources not cleaned up on shutdown path**
- **Post-close send** — work enqueued after shutdown signal
- **No force-terminate fallback** if graceful drain exceeds deadline
