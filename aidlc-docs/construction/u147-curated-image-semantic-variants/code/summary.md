# u147 Curated Image Semantic Variants

## Status

Code generation is complete (2026-08-03). Curated images are selected from the
final reader body by the most specific matching alias, with no global person
priority and no segment-default portrait.

## Delivered contract

- Candidate order is semantic rank, reader-visible offset, registry order,
  alias order, then key.
- Person portraits require an explicit visible name; role text such as Fed,
  FOMC, chair, or president cannot select a portrait.
- Bitcoin mining hardware requires explicit mining, ASIC, or hashrate context
  and is not interchangeable with a generic Bitcoin image.
- Complete selection provenance carries the final-body digest, matched key,
  semantic rank/offset, and deterministic variant index/count.
- CI and runtime integrity checks reject duplicate, dangling, ambiguous, and
  orphan registry states.

## Replay gate

The fixed 11-date/33-segment fixture validates every row against an allowed-key
or abstention contract. It selected 32 images with one intended abstention,
zero person portraits, five unique assets, a maximum single-asset share of
34.375%, and a top-four share of 96.875%. Narrow Bitcoin-mining imagery was not
selected for generic Bitcoin stories.

## Quality evidence

- Focused unit/integration scope: 115 tests passed; an independent semantic
  review scope passed 170 tests.
- Ruff lint/format and strict mypy on four changed source modules: passed.
- Curated graph: 19 filed, zero deferred; 15 legacy plus four evidence-backed.
- No-paid guard, replay gate, and `git diff --check`: passed.
- Final independent review: no remaining Critical/High/Medium finding.
