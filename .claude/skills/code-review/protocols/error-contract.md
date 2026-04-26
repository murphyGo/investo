# Error Contract Protocol

## Trigger

Code defines or relies on typed/sentinel errors for control flow, wraps errors across module boundaries, uses error type inspection to branch logic, or ignores error return values.

## Analysis Steps

### 1. Sentinel and Typed Error Integrity

For each package-level error value or custom error type:
- Is it exported and documented with its semantic meaning?
- If callers use equality or type-based checks, can wrapping break those checks?
- For custom error types: do they implement the interfaces needed for unwrapping?

Flag:
- **Silent wrapping breakage** — error wrapped in a way that defeats downstream type/value checks
- **Ambiguous error identity** — same error value reused for semantically different failures
- **Missing interface methods** — custom error type used with type inspection but lacks unwrap support

### 2. Propagation Chain Analysis

Trace error return values from origin to the outermost caller:
- At each layer boundary: is context added (which operation, which input, which component)?
- Is the original error preserved for inspection, or replaced with a new opaque error?
- Are there points where an error is logged **and** returned?

Flag:
- **Context-free propagation** — error crosses module boundary with no added context
- **Double handling** — error both logged and returned (caller may log again)
- **Chain truncation** — original error replaced with new error, losing causal chain

### 3. Ignored and Swallowed Errors

For each call that returns an error:
- Is the error checked?
- If discarded, is there a documented reason?
- In async/background contexts: can an error reach anyone, or is it silently lost?

Flag:
- **Silently ignored** — error return discarded without justification
- **Background black hole** — error in async work with no channel, callback, or log to surface it
- **Partial check** — multi-return function where some errors checked but others not

### 4. Error-Driven Control Flow Correctness

When error values or types are used to make branching decisions:
- Is the check correct? (value comparison vs. unwrap-aware comparison)
- Are all expected error cases handled, or does a catch-all mask unexpected failures?
- If a function returns multiple distinct errors, does the caller differentiate correctly?

Flag:
- **Wrong comparison method** — direct equality check on an error that may be wrapped
- **Catch-all masking** — broad handler swallows unexpected/novel error types
- **Missing case** — function documents N error conditions, caller handles fewer than N
