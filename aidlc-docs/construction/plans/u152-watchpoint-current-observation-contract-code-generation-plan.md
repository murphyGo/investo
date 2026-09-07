# Code Generation Plan: `u152 watchpoint-current-observation-contract`

**Date**: 2026-09-06
**Unit**: u152 watchpoint-current-observation-contract
**Stage**: Code Generation
**Status**: Backlog — ready for Functional Design; implementation design-gated
**Source**: `briefing-review-20260906.md`; September 2–4 domestic/crypto §⑥
**Estimated Effort**: ~6–9 h
**Dependencies**:
- u98/u110 card rendering/filtering — complete.
- u131 title segment bounding and u135 current resolution/fallback — complete.
- u144 typed watchpoint outcome and sealed document lifecycle — complete.
- u151 is not a prerequisite; shared macro classification is a different boundary.

## Problem Statement

Crypto September 3 §⑥ renders ETH's future 24h high/low conditions as its
`현재:` value without a current price. September 4's ETH CFTC card repeats
the complete conditional paragraph in that slot. Domestic September 4 repeats
a 100+ character foreign-flow paragraph across title/current/conditions.

`publisher/watchpoint_matrix.py::_build_row` uses the whole bullet when no
unused current clause exists. `resolve_watchpoint_currents` then accepts
`_CURRENT_VALUE_RE` before consulting the payload. A synthetic conditional
`ETH가 24h 고가 $2,523.23을 상회하면 강세 흐름 관찰` survives even when the
payload contains no anchors or items. Digit presence proves neither a current
observation nor its ownership.

## Goal

Every public current slot comes from a supported, exactly identified observation
in the existing trusted payload. Titles identify a signal, current shows its
observation, and conditions retain future observations to monitor.

## Existing Coverage / Deduplication

- u135 already builds value candidates and deterministic fallback cards.
  Replace its numeric passthrough exception; do not implement a second resolver
  or new fallback generator.
- u110 retains source promotion, confidence enum, duplicate-trigger filtering,
  and invalid-row handling.
- u131 retains its safe title bounding; provide it a clean semantic label
  instead of a full paragraph. Do not add another character-slicing algorithm.
- u64/u72 retain structure validation and post-conversion compliance scans.
- u144 retains typed `WatchpointRenderResult`, preserved supplements,
  limitation reasons and finalizer outcomes.
- This unit is not a general numeric-validation engine or new data adapter.

## Scope Boundary

In scope: supported current-value resolution, field ownership, exact signal
selection, date labels for CFTC current, final-render regression.
Out of scope: new KRX-flow/UST/TVL resolvers, new indicator families, source
routing, trigger forecasting, redesigned cards, matchers/watchlist behavior.

## Stage Decision

Functional Design: REQUIRED — numeric LLM current text previously survived
without evidence. Pin the replacement policy and unsupported-family behavior
before implementation. The rules below are the proposed fixed default.

NFR Requirements: SKIP — pure deterministic processing of existing payloads;
NFR-003/004/005/006 and R13, no new network/dependency/LLM/cost/retry.

## Fixed Contracts

1. A row is usable only when its signal resolves to exactly one semantic
   candidate family in `_current_value_candidates`. Supported families remain:
   reconciled segment anchors, CoinGecko price, fear/greed, funding, OI, and
   allow-listed CFTC contract groups. All current values, including numeric
   LLM strings, are replaced by that candidate's canonical current string.
   A digit in a source name, date or trigger can never satisfy this rule.
2. Reuse exact token matching and existing source specificity. Matching must
   identify both asset and metric: ETH funding cannot match ETH price merely
   because it contains ETH. Derive metric hints from the existing candidate
   families: `가격/종가/시세/가격 구간`, `공포/탐욕`, `펀딩/funding`,
   `미결제약정/OI`, `CFTC/COT/순포지션/계약`. Metric hints are read from the
   signal and source fields, not the future bullish/bearish thresholds.
   A bare asset with no metric hint defaults to its segment price candidate.
   Conflicting metric hints or multiple distinct assets reject the row.
3. Preserve the existing precedence within one semantic family. If the same
   highest-ranked semantic identity has conflicting canonical values, reject
   the row instead of breaking that conflict by input order. Identical
   duplicate candidates collapse. Do not let a broader asset token override
   a more specific contract/indicator identity.
4. Parse existing explicit signal/source/current/direction/impact delimiters
   into the current `WatchpointRow` shape. Keep direction and impact clauses
   out of signal/current. Remove the `current_clause or bullet.strip()`
   fallback. A missing current clause is allowed as an unresolved input slot;
   resolution, not a copied paragraph, fills it.
5. Use the selected candidate's canonical label as the signal when the parsed
   signal contains field delimiters, conditional text or exceeds the existing
   title bound. Extend the private `_CurrentValueCandidate` with a label/family
   discriminator; reuse `anchor_label` and existing indicator/contract labels.
   Do not infer a label from text after a future condition. u131 still handles
   final title segment bounding without mid-word cuts.
6. CFTC currents retain net contracts and %OI, and append existing valid
   `as_of_date` / `release_date` in the same date format as the channel row:
   `{as_of_date} 기준/{release_date} 공개 · 주간 지연`. Missing/invalid dates
   reject that candidate. Confidence is `보통`; date metadata is not a
   claimed live observation. Other families retain their current u135
   freshness/confidence policy.
7. Unsupported families, including current KRX investor flows without a
   supported candidate, are filtered. Their body evidence is preserved.
   With zero surviving cards, u135 synthesizes up to two supported cards;
   with no supported payload it emits the existing limited note. Do not
   retain an unsupported row merely to preserve card count or synthesize a
   new KRX-flow adapter.
8. Keep card shape, visible-row cap, trigger text, and implication semantics.
   Preserve owned image/chart fragments. Post-conversion compliance still
   applies. Current-value replacements cannot bypass u144 terminal gates.

## Implementation Steps

- [ ] Step 1 — Add synthetic September 3 ETH threshold-only and September 4
  CFTC/full-paragraph fixtures; prove the pre-change empty-payload bypass.
- [ ] Step 2 — Amend `_build_row`, `_short_signal`, and private candidate
  identity/labels in `publisher/watchpoint_matrix.py` to keep slots distinct.
- [ ] Step 3 — Replace the early numeric return in
  `resolve_watchpoint_currents` with metric-aware exact candidate resolution
  for every row; preserve existing within-family source precedence.
- [ ] Step 4 — Add CFTC date formatting/validation to `_cftc_candidate` using
  existing metadata; reject missing dates and update the same synthesized
  candidate consumers in `watchpoint_fallback.py`.
- [ ] Step 5 — Confirm `segment_reader_format.py` still invokes the existing
  zero-row fallback and compliance scan and forwards one typed outcome.
  Update fixtures that intentionally relied on ungrounded numeric currents.
- [ ] Step 6 — Exercise `finalize_public_bundle` and notification summaries
  with generated cards, pre-rendered cards, partial bundles, empty payloads
  and preserved visual fragments. Record the supported-family tradeoff.

## Acceptance Criteria

1. AC-152.1: Threshold-only, source-digit-only and date-only current strings
   never survive without a supported observation payload.
2. AC-152.2: A supported ETH price signal uses the payload price even when the
   input contains a different numeric current; an ETH funding signal never
   resolves to its price candidate.
3. AC-152.3: Current/title contain no copied direction or impact clause;
   bullish/bearish conditions and meaningful body evidence remain available.
4. AC-152.4: Ambiguous assets/metrics or conflicting best candidates are
   filtered; duplicate equivalent candidates produce stable output.
5. AC-152.5: CFTC current states both existing dates and weekly delay, and is
   never raised above `보통` confidence. Missing dates reject the candidate.
6. AC-152.6: Unsupported domestic-flow rows fall through to existing supported
   fallback cards or the exact limited note; no fabricated flow current.
7. AC-152.7: Sealed Markdown and notification extraction contain the resolved
   observation, preserve supplements/disclaimer, and pass existing compliance
   and hard gates. Repeated conversion is byte-stable.

## Tests / Validation

- Extend `tests/unit/publisher/test_watchpoint_matrix.py`,
  `test_watchpoint_fallback.py`, and
  `test_watchpoint_incident_regression_u135.py`.
- Add `tests/unit/publisher/test_watchpoint_observation_contract_u152.py` with
  finalized-document fixtures for the two crypto cases, domestic unsupported
  flow, ambiguous asset/metric, stale/missing CFTC metadata and pre-rendered
  cards. Fixtures use synthetic values and `example.invalid` source URLs.
- Extend `tests/unit/publisher/test_public_document_incident_chain_u144.py`
  only for the typed outcome and preserved-supplement assertions.
- Local gate: `uv run --extra dev pytest tests/unit/publisher/test_watchpoint_matrix.py tests/unit/publisher/test_watchpoint_fallback.py tests/unit/publisher/test_watchpoint_incident_regression_u135.py tests/unit/publisher/test_watchpoint_observation_contract_u152.py tests/unit/publisher/test_public_document_incident_chain_u144.py -q`;
  scoped Ruff/check+format and `uv run --extra dev mypy src`.

## Non-Goals

No new data source, signal score, buy/sell rule, per-card LLM call, generic
financial fact verifier, archive backfill, public workflow dispatch or send.
