# u145 Public HF Limited Radar — NFR/Security and Code Plan

**Date**: 2026-07-22
**Status**: Design complete; Code Generation blocked before Step 0

## Completed

- NFR/Security AC-1.1 through AC-6.6.
- Test Strategy TS-1 through TS-8.
- Existing-stack technology decisions with no new dependency.
- Seven-step code-generation plan with credentialed qualification as a hard Step 0.

## Recommended defaults fixed

- Header-only key, central redaction catalogue, fixed HTTPS host, no cross-host redirect.
- 100 requests/minute, concurrency three, two retries, 120-second run ceiling.
- 2 MiB and 10,000-row per-response ceilings; 256 MiB peak-memory target.
- Derived-only retention and synthetic provider-shape fixtures.
- Static authoritative NYSE calendar or fail `unknown`—no weekday-only promotion.
- First publish fail-closed; last-good bytes and `as_of` unchanged on later failure.
- No-write manual probe workflow and five successes before activation.
- Manual 30-day key rotation with automated detection/redacted diagnosis only.

## Exact blocker

The provider requires accurate account details, email verification, and an API key. No
operator-owned HF key exists in the current environment, so authenticated payload shape,
adjustment semantics, and error behavior cannot be qualified. The design deliberately forbids
implementation assumptions before this evidence. No account or credential was fabricated.

Post-push live verification found no local `HF_DATA_API_KEY` and no secret with that name in
the GitHub Actions secret inventory. Only secret names and update timestamps were queried; no
secret value was available to or printed by the check.
