# u145 Public HF Limited Radar — Functional Design

**Date**: 2026-07-22
**Status**: Complete

## Result

Functional Design is fixed in:

- `business-logic-model.md`: L1-L12 request, normalization, coverage, calculation,
  projection, and last-good workflow.
- `business-rules.md`: R1-R33 source, credential, bar, metric, coverage, publication,
  activation, compatibility, and phase rules.
- `domain-entities.md`: E1-E19 with seven cross-entity invariants.
- `frontend-components.md`: C1-C7 deterministic Pages components and state behavior.

## Key decisions

- Keep u139 NAV/private models and artifacts unchanged; add sibling public types.
- Extract source-neutral mathematical kernels and retain existing `nav_*` wrappers.
- Use price-specific `iex_price_*` fields so source semantics survive serialization.
- Request only SPY plus ten supported sectors; XLRE is structurally unavailable and
  never requested, inferred, proxied, or ranked.
- Exclude volume from every score/classification path.
- Require all-eleven-card rendering, first-viewport scope labels, HF/IEX attribution,
  derived-only storage, and a shared deterministic snapshot id.
- Do not enable schedule or Pages navigation before five isolated GHA probes pass.

## Remaining gate

NFR/Security requirements and the staged code-generation plan can be authored now.
Credentialed payload assumptions and implementation remain blocked until an
operator-owned HF account, verified email, and current 30-day API key exist.
