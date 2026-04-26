# Performance Analysis Protocol

## Trigger

Code contains nested iteration over collections, algorithmic complexity above O(n), hot-path logic (request handlers, tight loops), or redundant/repeated expensive operations.

## Analysis Steps

### 1. Algorithmic Complexity Audit

For each loop or recursive call:
- State the complexity in Big-O notation relative to input size
- For nested loops: is the inner collection size bounded or proportional to outer?
- Flag O(n^2) or worse when n can be large or unbounded

```
for each item in A:         <- O(|A|)
    for each item in B:     <- O(|A| * |B|)  -- acceptable if |B| is bounded
        lookup in map C     <- O(1) amortized
```

Flag:
- **Quadratic or worse with unbounded input** — performance cliff
- **Linear scan where O(1) lookup exists** — use map/set instead
- **Recursive without memoization** — exponential blowup on overlapping subproblems

### 2. Hot Path Identification

Identify code on the critical request/response path:
- Is this called per-request, per-event, or per-item in a batch?
- What is the expected call frequency? (once/startup vs. thousands/second)
- Are there expensive operations on the hot path that could be hoisted?

Flag:
- **Repeated compilation** — regex, template, or query compiled inside loops or per-request
- **Redundant I/O** — same data fetched multiple times without caching
- **Unnecessary allocation** — objects created per-iteration that could be reused

### 3. Data Structure Fitness

- Is the chosen data structure appropriate for the access pattern?
- Linear search where a map/set would be O(1)?
- Sorted structure where insertion order suffices?
- Array where linked structure (or vice versa) better fits the mutation pattern?

Flag:
- **Wrong data structure for access pattern** — e.g., list for frequent lookups
- **Sorted maintenance for unsorted access** — unnecessary overhead

### 4. Batching and Amortization

- Are N individual operations done where a single batch operation exists?
- Can work be amortized across calls (precomputation, memoization)?
- Is there an N+1 query pattern (fetch list, then fetch detail per item)?

Flag:
- **N+1 query** — database round-trip per item instead of batch fetch
- **Individual HTTP calls in loop** — batch API available but not used
- **Repeated computation** — same expensive result calculated multiple times

### 5. Observability Overhead

For metrics, tracing, and structured logging on the hot path:
- Are metric labels/tags low-cardinality? (high-cardinality = unbounded memory in registry)
- Is metric registration at init time, or repeated per-call?
- Are histogram bucket boundaries appropriate for the value range?
- Is log serialization on hot path — could it be deferred or sampled?

Flag:
- **High-cardinality label** — metric dimension with unbounded distinct values (user ID, request ID)
- **Per-call registration** — metric collector created inside handler or loop
- **Excessive hot-path logging** — serialization cost on every request without sampling
