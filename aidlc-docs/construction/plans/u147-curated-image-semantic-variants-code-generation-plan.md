# Code Generation Plan: `u147 curated-image-semantic-variants`

**Date**: 2026-08-03
**Status**: Complete (2026-08-03)

## Stage Decision

- Functional Design: Skipped
- NFR Requirements: Skipped
- Reason: bounded deterministic u141/u86 selection refinement with no new external call, dependency, secret, storage family, cost, or public policy.
- Source of requirements: FR-002, FR-003, FR-008, FR-012, NFR-003, NFR-006, NFR-007/R13; 2026-08-03 final-asset-review findings.

## Fixed Contracts

1. `SemanticAlias(text, rank)` is registry metadata; the registry tuple is the only ordering SoT.
2. Candidate order is `(rank, offset, registry_order, alias_order, key)`. Person rows have no special global priority.
3. Rank tiers are: driver theme 0; exact person/asset/index/institution/indicator 10; bounded market/location 20; broad market 30; generic motion/macro 40.
4. The winning key's filed assets retain registry order. Variant index is `sha256(narrative_sha256 + NUL + segment + NUL + key) mod filed_count`; deferred assets do not enter the modulo.
5. Provenance records `variant_contract=narrative-key-digest-mod-v1`, index/count, semantic rank, alias offset, matched key, and narrative digest.
6. Registry validation fails on duplicate keys, empty aliases/assets/affinity, dangling IDs, duplicate asset ownership, same-rank same-alias ambiguity in overlapping segments, and every filed orphan.
7. New keys are data center, clean energy, gold, and Bitcoin mining. Narrow mining hardware is never a generic Bitcoin variant. History-only KOSPI and semiconductor remain alias contracts without registry rows until candidates clear every byte-identity, dimension, freshness, and R13 rule.

## Steps

### Step 1 - Alias ranking and deterministic variants `[x]`
- [x] Replace `_REGISTRY_PRIORITY` with alias-level match records and registry-order tie-break.
- [x] Add variant metadata to `CuratedSelection` and selected-asset provenance.

### Step 2 - Registry expansion and hard integrity `[x]`
- [x] Add four topical keys and four u146 assets; make orphan/ambiguity states fail the CI and runtime guards.
- [x] Add specificity, earliest-offset, person non-dominance, variant reachability, deferred filtering, and integrity tests.

### Step 3 - Replay fit/diversity audit `[x]`
- [x] Add an operator audit script and fixed 11-date/33-segment golden semantic-fit fixture.
- [x] Gate all 33 allowed-key/abstain rows, role-only person matches at zero, and bounded concentration regression thresholds; report concentration separately from semantic fit.

### Step 4 - Quality gate and independent review `[x]`
- [x] Run focused/integration tests, Ruff/format, mypy, curated/no-paid gates, and `git diff --check`.
- [x] Resolve fresh-eyes findings and record summary/session/audit/state updates.
