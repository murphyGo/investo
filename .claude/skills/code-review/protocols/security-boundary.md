# Security Boundary Protocol

## Trigger

Code processes external input (HTTP requests, CLI arguments, file uploads, message queue payloads), constructs queries or commands from input, renders templates with user data, or performs authentication/authorization checks.

## Analysis Steps

### 1. Input Trust Boundary Map

Identify every point where external data enters the system:
- HTTP request fields (path, query, headers, body)
- Message queue / event payloads
- File contents read from user-supplied paths
- Environment variables or configuration from untrusted sources

For each entry point:
- Is the input validated (type, length, format, allowed values)?
- Is validation done at the boundary, before the data propagates?
- What happens with invalid input — reject, sanitize, or silently accept?

Flag:
- **No validation at boundary** — external data flows into system unchecked
- **Validation too late** — input processed before being validated
- **Silent acceptance** — invalid input accepted without error or sanitization

### 2. Taint Flow Analysis

Trace external input from entry point to usage:
- Does untrusted input reach a **sensitive sink** without sanitization?
  - Query construction (SQL, NoSQL, LDAP)
  - Command execution (shell, subprocess)
  - Template rendering (HTML, email)
  - File path construction
  - Redirect URLs
  - Log output (log injection)

Flag any path from source to sink without validation or escaping:
- **SQL/NoSQL injection** — user input in query string without parameterization
- **Command injection** — user input in shell command without escaping
- **XSS** — user input rendered in HTML without encoding
- **Path traversal** — user input in file path without sanitization
- **Log injection** — user input written to logs without sanitization

### 3. Authentication and Authorization

If the code involves access control:
- Is authentication checked before authorization?
- Are there paths that bypass the auth check (early returns, middleware ordering)?
- Is the authorization check based on the authenticated identity, not client-supplied claims?
- Are privilege escalation paths possible (e.g., modifying your own role)?

Flag:
- **Auth bypass** — code path that skips authentication check
- **Client-supplied identity** — authorization based on client-provided role/ID instead of server-verified
- **Privilege escalation** — user can modify their own permissions
- **Middleware ordering** — auth middleware registered after route handler

### 4. Secret Handling

- Are secrets (API keys, tokens, passwords) hardcoded or logged?
- Are secrets compared using constant-time comparison?
- Are secrets transmitted over secure channels only?
- Do error messages leak internal details (stack traces, query strings, file paths)?

Flag:
- **Hardcoded secret** — credential in source code
- **Secret in logs** — token, key, or password written to log output
- **Timing-sensitive comparison** — secret compared with `==` instead of constant-time function
- **Information leakage** — error response exposes internal paths, stack traces, or query details
