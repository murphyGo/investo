# NFR Requirements Plan: `u145 sector-dashboard-public-hf-limited-radar`

**Date**: 2026-07-22
**Stage**: NFR Requirements
**Status**: Complete — recommended defaults applied under autonomous user direction
**Approved Functional Design**: `aidlc-docs/construction/u145-sector-dashboard-public-hf-limited-radar/functional-design/`

## Context Loaded

- u140 strict source search blocked after 25 candidates; HF fact sheet and current official
  account/API/terms/license/known-issues pages reviewed.
- u139 private sector models, metric/regime engine, deterministic pair, PBT, and privacy
  boundaries inspected.
- u145 Functional Design R1-R33, E1-E19, I1-I7, C1-C7, L1-L12 approved by progression.
- Existing `httpx`, Pydantic, central redaction, NYSE calendar, publisher transaction, no-paid,
  leak-scan, pytest/Hypothesis, strict mypy, and MkDocs conventions inspected.

## Recommended Decisions Applied

1. Existing stack only; no provider SDK/dataframe/calendar/database dependency.
2. Header-only `HF_DATA_API_KEY`, central secret catalogue, fixed host, no cross-host redirect.
3. 100 requests/minute conservative authority, concurrency 3, two retries, 120-second run cap.
4. 2 MiB/10,000-row/128-field/depth-8 response envelope and 256 MiB peak-memory target.
5. Derived-only public retention and synthetic schema-equivalent tests; no raw live fixture.
6. Versioned NYSE calendar with fail-unknown outside authoritative coverage.
7. First publish fail-closed; later last-good bytes unchanged with stale operational failure.
8. Dedicated no-write probe workflow; five successes before schedule/nav/deploy activation.
9. Manual 30-day key rotation runbook; Investo detects expiry but does not automate identity.

## Stage Checklist

- [x] Security, rights, cost, request, resource, reliability, integrity, UX, and operations ACs.
- [x] Test Strategy TS-1 through TS-8.
- [x] Technology/dependency/calendar/persistence/fixture/deployment choices.
- [x] Contextless code-generation plan with a credentialed Step 0 hard gate.
- [x] No implementation, account action, secret, payload fetch, workflow activation, or public
  artifact introduced during design.

## Gate Result

Design is complete. Code Generation is not authorized past Step 0 because no operator-owned
HF account/key is present and therefore endpoint shape, adjustment semantics, and authenticated
error behavior have not been live-qualified.
