# u163 Functional Design: terminal numeric emphasis containment

Status: Authorized for implementation, 2026-10-09. Priority:P0-1.
User instruction: “유닛 개발 진행해줘 / 하나 완료할떄마다 커밋 푸시해줘”.
Evidence: [25-run review](../source-reliability-20261009/review.md).

## Problem and scope

Four segments were trust-blocked by `markdown.broken_numeric_bold` despite successful generation. Actual repair leaves synthetic `**+**2.3%` and `**-**$100` unchanged. Exact rejected production sentences are unavailable: synthetic characterization is not an exact incident replay.

Extend u112 text repair and u144 finalization. u150 is link containment, u153 sentence bounds, u154 layout, u149 numeric evidence; none is reimplemented here. No source/LLM retry or weakened content gate.

## Fixed rules and entities

- Existing `SurfaceQualityIssue`/region disposition and finalizer remain canonical.
- Repair a recognized split-sign span by removing only the erroneous sign emphasis: `**+**2.3%` → `+2.3%`, `**-**$100` → `-$100`. Preserve digits, commas, decimal, sign, currency, unit and surrounding text. Ambiguous spans remain blocked.
- Protect valid emphasis, escaped syntax, inline/fenced code, links, tables and owned diagnostic regions; preserve existing nested-dollar/percent repair.
- Apply at existing presentation repair boundary; scan fully assembled final text after producers/supplements. Repeat processing is idempotent.
- Summary DTOs derive from repaired final text. Numeric-anchor, unsupported-source and content-time failures keep existing blocking policies. Removing unsafe mandatory lines is not successful repair.
- Diagnostics contain enumerated repair counts, no full generated/private text.

## Acceptance and NFR

1. Split-sign variants/decimals/commas/currencies repair with unchanged numeric tokens; ambiguous cases remain blocked.
2. Protected spans/valid Markdown remain byte-identical.
3. Actual `finalize_public_bundle` full/partial three-market paths retain valid survivors, summaries and independent content blockers.
4. Repeated repair/finalization has identical text/state; private original replay is recorded separately if acquired.

Reuse NFR-003/005/006/R13: bounded deterministic pure text, no new dependency/HTTP/secret/cost/model call. Offline synthetic fixtures; no public raw production originals. Operations: zero numeric-emphasis blocks in10 distinct normal scheduled runs on the reviewed execution pin.
