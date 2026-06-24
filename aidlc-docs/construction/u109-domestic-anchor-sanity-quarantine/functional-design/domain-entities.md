# Domain Entities - `u109 domestic-anchor-sanity-quarantine`

**Date**: 2026-06-23
**Source**: `aidlc-docs/construction/plans/u109-domestic-anchor-sanity-quarantine-code-generation-plan.md`

This unit introduces a deterministic trust boundary for Korean domestic market
anchors before those anchors reach public tables, prose assertion checks,
charts, visual cards, or Telegram summaries. It does not introduce a new source
adapter. Entities below describe the in-process shapes and metadata contracts
that a contextless implementation agent must preserve.

Entities: `E1`-`E6`. Invariants: `I1`-`I18`.

---

## E1. DomesticAnchorCandidate

An extracted domestic exact-value candidate from existing normalized items,
fallback anchors, or domestic anchor table input.

| Attribute | Type | Notes |
|-----------|------|-------|
| `symbol` | str | One of the bounded registry symbols in E2. |
| `display_name` | str | Public label such as `KOSPI`, `KOSDAQ`, `USD/KRW`, `삼성전자`, `SK하이닉스`. |
| `close` | Decimal or float or None | Candidate close value. Missing value classifies as `unavailable`. |
| `change_pct` | Decimal or float or None | Optional daily percent change used only for plausibility. |
| `source_name` | str or None | Explicit source provenance from `NormalizedItem.source_name`. |
| `observed_at` | date/datetime or None | Candidate observation/as-of timestamp. |
| `raw_metadata` | mapping | Existing metadata only; no new external fetch result is added. |
| `category` | str | `price` or the existing domestic anchor category consumed by u67. |

**Invariants**

- I1. A candidate is constructed only from existing in-memory collection output
  or existing domestic anchor structures; u109 never fetches live market data.
- I2. `source_name` must be explicit for a candidate to become trusted.
- I3. Index/FX candidates require `source_name == "stooq-kr-market"` and
  `raw_metadata["ticker"]` equal to `^KOSPI`, `^KOSDAQ`, or `KRW=X`.
  Large-cap candidates require `source_name == "fsc-krx-stock-price"` and
  `raw_metadata["ticker"]` equal to `005930` or `000660`.
- I4. Missing or unparsable numeric fields are represented as candidate
  classification inputs, not silently coerced to zero.

## E2. DomesticExactClaimRegistry

The bounded registry of domestic symbols whose precise public claims are gated
by u109.

| Symbol | Public aliases | Kind |
|--------|----------------|------|
| `^KOSPI` | `KOSPI`, `코스피` | index |
| `^KOSDAQ` | `KOSDAQ`, `코스닥` | index |
| `KRW=X` | `원/달러`, `USD/KRW`, `달러-원` | fx |
| `005930.KS` | `삼성전자`, `005930` | large_cap |
| `000660.KS` | `SK하이닉스`, `000660` | large_cap |

**Invariants**

- I5. u109 gates only symbols in this registry. Other domestic tickers keep the
  existing u55/u70 behavior unless they are later added by an explicit unit.
- I6. Alias matching is exact or existing normalized-alias matching. u109 does
  not add fuzzy matching.
- I7. A large-cap close must never satisfy an index symbol, and an index close
  must never satisfy a large-cap symbol.
- I7a. `raw_metadata["ticker"] == "005930"` canonicalizes to `005930.KS`;
  `raw_metadata["ticker"] == "000660"` canonicalizes to `000660.KS`.

## E3. DomesticAnchorTrust

The private trust state assigned to each `DomesticAnchorCandidate`.

```python
DomesticAnchorTrust = Literal[
    "trusted",
    "unavailable",
    "stale",
    "implausible",
    "provenance_missing",
]
```

| State | Meaning |
|-------|---------|
| `trusted` | Candidate has bounded symbol, explicit provenance, acceptable as-of date, source outcome not failed, and plausible values. |
| `unavailable` | Required candidate or close value is absent. |
| `stale` | Candidate as-of date falls outside the accepted domestic market close window. |
| `implausible` | Numeric value or daily percent move falls outside fixed plausibility bands, or numeric parsing fails. |
| `provenance_missing` | Value exists but source/category/index provenance is insufficient for public precision. |

**Invariants**

- I8. Trust state is private implementation metadata. It is not rendered verbatim
  in public prose, visual text, or Telegram.
- I9. Classification is deterministic and depends only on candidate fields,
  source outcome metadata, the target report date, and fixed bands.
- I10. `trusted` is the only state allowed to carry exact public close values
  into downstream public payloads.

## E4. TrustedDomesticAnchor

The sanitized anchor payload passed downstream when classification succeeds.

| Attribute | Type | Notes |
|-----------|------|-------|
| `symbol` | str | Registry symbol from E2. |
| `display_name` | str | Reader-facing name. |
| `close` | Decimal or float | Exact value that passed u109 trust. |
| `change_pct` | Decimal or float or None | Optional, only if plausible. |
| `source_name` | str | Explicit source provenance. |
| `observed_at` | date/datetime | Accepted market close/as-of timestamp. |
| `quality_reason` | str | `trusted` only; non-trusted reasons stay in E5/E6. |

**Invariants**

- I11. Every `TrustedDomesticAnchor` must come from exactly one candidate with
  `DomesticAnchorTrust == "trusted"`.
- I12. It is the only domestic exact-value shape allowed in `anchor_table_input`,
  chart sidecars, visual-card text payloads, and Telegram market snapshots.
- I13. It does not change the u70 canonical anchor assertion format for US or
  crypto anchors.

## E5. DomesticAnchorQuarantineResult

The result of classifying candidates for one segment/report date.

| Attribute | Type | Notes |
|-----------|------|-------|
| `trusted` | mapping[str, TrustedDomesticAnchor] | Symbol-keyed trusted anchors. |
| `withheld` | mapping[str, DomesticAnchorTrust] | Symbol-keyed non-trusted states. |
| `public_missing_reasons` | mapping[str, MissingReason] | u74 public reason mapping for withheld anchors. |
| `diagnostics` | tuple[dict, ...] | Bounded internal evidence for logs/quality metadata. |

Mapping to u74 public reasons:

| Private state | u74 `MissingReason` |
|---------------|---------------------|
| `unavailable` | `not_collected` |
| `stale` | `stale` |
| `implausible` | `insufficient_items` |
| `provenance_missing` | `insufficient_items` |

**Invariants**

- I14. Public missing reasons do not include exact withheld numeric values.
- I15. Diagnostics may include symbol, state, source name, target date, and a
  compact reason code. They must not include secrets, full raw payloads, or
  unredacted source URLs.
- I16. The result is applied before `_reconcile_anchor_closes()` consumes
  domestic anchors.

## E6. DomesticAnchorQualityMetadata

Bounded quality metadata emitted through existing u96 quality snapshot/history
paths.

| Attribute | Type | Default | Notes |
|-----------|------|---------|-------|
| `domestic_anchor_withheld_count` | int | `0` | Count of withheld domestic exact anchors. |
| `domestic_anchor_withheld_reasons` | tuple[str, ...] | `()` | Unique states from `unavailable`, `stale`, `implausible`, `provenance_missing`. |
| `domestic_anchor_public_note` | str or None | None | Reader-safe visible quality wording when any exact values are withheld. |

Reader-safe visible wording:

```text
국내 기준값 일부 비공개
```

**Invariants**

- I17. Metadata distinguishes "exact value withheld" from ordinary absence.
- I18. Raw trust-state strings may be serialized in structured metadata, but
  visible public labels use the reader-safe Korean note above or the u74 public
  missing reason wording.
