# Business Logic Model - `u109 domestic-anchor-sanity-quarantine`

**Date**: 2026-06-23
**Source**: `aidlc-docs/construction/plans/u109-domestic-anchor-sanity-quarantine-code-generation-plan.md`

This model fixes the deterministic sequence for classifying domestic anchors,
withholding untrusted exact values, and feeding existing u70/u74/u96 surfaces.
Rule ids reference `business-rules.md`; entity ids reference
`domain-entities.md`.

---

## 1. Candidate extraction

```
extract_domestic_anchor_candidates(items, existing_anchor_input, target_date):
  candidates = []
  for row in existing_anchor_input and domestic price/category items:
    normalized = normalize_symbol_against_registry(
      row.raw_metadata["ticker"] or row.symbol,
      row.aliases,
    )
    if normalized not in DomesticExactClaimRegistry:
      continue
    candidates.append(DomesticAnchorCandidate(
      symbol=normalized,
      display_name=registry.display_name,
      close=row.close,
      change_pct=row.change_pct,
      source_name=row.source_name,
      observed_at=row.observed_at or row.as_of,
      raw_metadata=row.raw_metadata,
      category=row.category,
    ))
  return candidates
```

Extraction is bounded to E2. It reuses existing normalized items and domestic
anchor input; it performs zero HTTP calls.

## 2. Candidate classification

```
classify_candidate(candidate, source_outcomes, target_date):
  if candidate.close is missing:
    return "unavailable"
  if candidate.close or candidate.change_pct cannot be parsed:
    return "implausible"
  if candidate.symbol in {"^KOSPI", "^KOSDAQ", "KRW=X"} and candidate.source_name != "stooq-kr-market":
    return "provenance_missing"
  if candidate.symbol in {"005930.KS", "000660.KS"} and candidate.source_name != "fsc-krx-stock-price":
    return "provenance_missing"
  if candidate.source_name is missing:
    return "provenance_missing"
  if source outcome for candidate source is failed/terminal/zero-items:
    return "provenance_missing"
  if candidate.observed_at is outside accepted domestic close window:
    return "stale"
  if candidate.close or change_pct violates R5 band:
    return "implausible"
  return "trusted"
```

Precedence is fixed so the same candidate always receives the same first reason.
The implementation must include boundary tests for inclusive band edges.

## 3. Quarantine result construction

```
build_quarantine_result(candidates):
  result = DomesticAnchorQuarantineResult()
  for candidate in candidates sorted by registry order:
    trust = classify_candidate(candidate, ...)
    if trust == "trusted":
      result.trusted[candidate.symbol] = TrustedDomesticAnchor(candidate)
    else:
      result.withheld[candidate.symbol] = trust
      result.public_missing_reasons[candidate.symbol] = map_to_u74_reason(trust)
      result.diagnostics += compact_diagnostic(candidate.symbol, trust, source_name, target_date)
  return result
```

If duplicate candidates exist for the same symbol, pick the first trusted
candidate by existing domestic anchor priority. If none are trusted, record the
highest-precedence non-trusted state from classification order.

## 4. Pipeline integration sequence

```
_stage_collect / _stage_generate domestic setup
  -> _build_kr_anchors_from_items(...)
  -> build_domestic_anchor_quarantine(...)
  -> stage_context.domestic_anchor_quarantine = result
  -> anchor_table_input = anchors_from(result.trusted)
  -> _stage_prepare_segment_visual_assets(... trusted anchors ...)
  -> _reconcile_anchor_closes(... trusted anchors ...)
  -> enforce_anchor_assertions(... canonical anchors ...)
  -> publish markdown / chart sidecar / visual card
  -> notifier summary from trusted anchors or filtered price_items
```

The implementation may place the helper in a small orchestrator/internal module,
but the public forks must all consume post-quarantine data. The key correctness
point is that visual preparation and Telegram snapshots never read raw
quarantined domestic values after the result exists.

## 5. Public projection behavior

| Trust state | Anchor table | Body exact claim | Chart/visual/Telegram | Quality note |
|-------------|--------------|------------------|-----------------------|--------------|
| `trusted` | exact value | allowed when u70 passes | exact value allowed | normal |
| `unavailable` | omit or number-free unavailable label | blocked | omitted | withheld |
| `stale` | omit or number-free stale label | blocked | omitted | withheld |
| `implausible` | omit | blocked | omitted | withheld |
| `provenance_missing` | omit | blocked | omitted | withheld |

The public number-free labels come from existing u74 `MissingReason` rendering
or the reader-safe quality note. The private state labels are not public prose.

## 6. Quality metadata sequence

```
quality_metadata_from_quarantine(result):
  reasons = unique(result.withheld.values()) sorted by fixed state order
  return {
    "domestic_anchor_withheld_count": len(result.withheld),
    "domestic_anchor_withheld_reasons": tuple(reasons),
    "domestic_anchor_public_note": "국내 기준값 일부 비공개" if reasons else None,
  }
```

The metadata is attached through existing u96 quality snapshot/history paths
with zero/empty defaults when no domestic anchors are withheld.

## 7. Failure and degradation model

- Helper exceptions caused by malformed candidate structures should fail closed
  for the affected candidate as `implausible` and include a compact diagnostic.
- Programmer errors outside candidate parsing are not swallowed.
- If all domestic anchors are withheld, domestic segment publishing may continue
  with number-free missing labels, but exact body claims must be blocked by u70.
- US and crypto segments do not instantiate the domestic quarantine policy.
