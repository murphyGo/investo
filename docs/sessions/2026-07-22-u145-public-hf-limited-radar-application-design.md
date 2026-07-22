# u145 Public HF Limited Radar — Application Design

**Date**: 2026-07-22
**Stage**: Inception / Application Design
**Status**: Complete; Functional Design may proceed

## Trigger

u140 evaluated 25 non-duplicate public OHLCV candidates and exhausted the strict
inventory without finding a permanently free source that combined explicit public
derived-display rights, all 12 symbols, consolidated volume, and bounded daily access.
The user directed autonomous progress until a genuine blocker.

## Decision

Register `u145 sector-dashboard-public-hf-limited-radar` as an explicitly relaxed
sibling of u140.

- Keep: permanent-free basic access, explicit public reuse rights, freshness target,
  bounded automation, attribution, secret safety, and no raw-payload publication.
- Relax: exact 12-symbol coverage and consolidated-volume semantics only.
- Use: HF Data Library for SPY plus XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLU, XLV,
  and XLY.
- Missing: XLRE remains a typed `unavailable` card. No proxy or inferred series.
- Semantics: post-March-2022 OHLCV is an `IEX venue sample`; IEX volume never enters
  rank, regime, or a composite score.

## Component boundary

```text
HF API -> bounded adapter -> public bar series -> generalized pure metrics
       -> limited public snapshot -> deterministic Pages renderer -> isolated publish
                            |
                            +-> XLRE unavailable + source/coverage/provenance labels
```

The completed u139 private NAV path remains separate and byte-compatible. Only its pure
mathematics is generalized behind a source-neutral value-series interface. Public input,
provenance, output, rendering, and orchestration use new types and owners.

## Unit scope

Included:
- HF daily bars for the fixed supported 11-symbol request set
- deterministic return, SPY excess return, acceleration, realized volatility,
  drawdown, regime, and relative rank
- all-eleven-card rendering with XLRE unavailable
- HF/IEX attribution and machine provenance
- first-publish fail-closed plus last-good stale behavior
- local fixture tests and five isolated GitHub Actions probes
- Pages latest surface only after probe acceptance

Excluded:
- consolidated or market-wide volume claims
- volume/rank composite, dollar volume, and fund-flow inference
- Telegram
- earnings actual, constituent breadth, evidence narrative, and Phase 2 attention data
- any new paid dependency, source fallback, XLRE proxy, or raw provider archive

## Stage decisions

- Functional Design: required because public and private input/output contracts diverge.
- NFR Design: required because the unit adds a renewable secret, public artifact, network
  source, rate limit, freshness policy, and isolated deployment path.
- Security: required and scoped to credential handling, redaction, payload retention,
  provenance, attribution, and public projection.
- PBT: required for value-series/snapshot serialization and deterministic metric invariants;
  provider/network behavior uses fixed fixtures and explicit probes.

## External gate

HF's published terms require an account with accurate registration details, email
verification, and an API key that expires every 30 days. This session did not create an
account, fabricate identity data, verify email, obtain a key, fetch a provider payload,
or run GitHub Actions probes. Design work can continue without the credential; payload
qualification and implementation cannot cross that gate.

## Handoff

Next: author Functional Design, NFR/Security requirements, and a staged code-generation
plan. Stop before provider-payload assumptions and mark the construction gate blocked
until an operator-owned HF key exists.
