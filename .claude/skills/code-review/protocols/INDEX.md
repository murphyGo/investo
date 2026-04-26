# Protocol Index

Deep-analysis protocols that activate when specific code patterns are detected during review.

## How to Use

After reading the code under review (Step 2), scan for the signals below. For each match, load and apply the corresponding protocol during Step 3.

## Signal-to-Protocol Mapping

| Signals in Code | Protocol | File |
|----------------|----------|------|
| Mutex, lock, synchronized, atomic, channel, goroutine, thread, async task pool, select/poll | Concurrency | concurrency.md |
| Database write, file write, WAL, transaction, checkpoint, snapshot, temp+rename, batch insert | Data Integrity | data-integrity.md |
| Custom error types, sentinel errors, error wrapping, Result<>/Either, try/catch chains, ignored error returns | Error Contract | error-contract.md |
| Cache, buffer, queue, unbounded collection, append-only list, long-lived map, bulk data loading | Memory | memory.md |
| Nested loops over collections, algorithmic complexity above O(n), hot-path handler, repeated expensive call in loop | Performance | performance.md |
| Open/Close, connect/disconnect, acquire/release, pool, defer/finally, Drop trait, context manager | Resource Lifecycle | resource-lifecycle.md |
| User input parsing, HTTP request handling, auth check, token validation, SQL/query construction, secret/key/credential | Security Boundary | security-boundary.md |

## Multiple Protocols

Code often triggers multiple protocols. Apply all that match.

**Priority order** (when time-constrained): Security Boundary > Concurrency > Data Integrity > Resource Lifecycle > Error Contract > Memory > Performance

## Skipping Protocols

Skip a protocol only if you are certain none of its signals are present. When in doubt, apply it.
