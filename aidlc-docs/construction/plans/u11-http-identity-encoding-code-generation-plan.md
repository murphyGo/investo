# Code Generation Plan: `u11 http-identity-encoding`

**Date**: 2026-05-07
**Unit**: u11 http-identity-encoding
**Stage**: Code Generation

---

## Goal

Prevent GitHub Actions source collection from failing across unrelated JSON/RSS endpoints because upstream responses advertise a compressed content encoding that httpx cannot decode.

---

## Definition of Done

- [x] Shared HTTP retry helper requests identity encoding by default.
- [x] Adapter-supplied headers such as `User-Agent` continue to pass through.
- [x] Explicit adapter `Accept-Encoding` overrides remain possible.
- [x] Retry and streaming body-cap contracts remain unchanged.

---

## Steps

### Step 1 — Default Request Headers

- [x] Add a default `Accept-Encoding: identity` header in `retry_get`.
- [x] Merge the default with caller-provided headers.
- [x] Preserve caller-provided `Accept-Encoding` case-insensitively.

### Step 2 — Regression Tests

- [x] Assert caller headers and query params still pass through.
- [x] Assert default identity encoding is sent.
- [x] Assert explicit accept-encoding is preserved.
