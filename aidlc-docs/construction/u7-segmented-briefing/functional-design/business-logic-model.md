# Business-Logic Model — `u7 segmented briefing`

**Date**: 2026-05-07

---

## L1. End-to-end segmented flow

```text
run_pipeline(target_date)
  |
  |-- collect all items via u1.fetch_all(target_date)
  |
  |-- segment_items(items)
  |     -> domestic-equity items
  |     -> us-equity items
  |     -> crypto items
  |
  |-- for each segment in fixed order:
  |     build segment-scoped prompt context
  |     generate_briefing(target_date, segment_items, segment_context)
  |     validate disclaimer/leak guard via existing u2/u3 contracts
  |
  |-- write all 3 markdown files under archive/{segment}/YYYY/MM/
  |
  |-- one git commit: "briefing: YYYY-MM-DD segmented"
  |
  |-- publish one Telegram message with 3 summaries + 3 links
```

The fixed order is domestic-equity, us-equity, crypto for presentation stability.

---

## L2. Segment routing algorithm

Pseudo-code:

```python
def segment_items(items: Sequence[NormalizedItem]) -> SegmentedItems:
    domestic = []
    us = []
    crypto = []

    for item in items:
        text = f"{item.source_name} {item.title} {item.summary or ''}".lower()

        if is_crypto(item, text):
            crypto.append(item)
        if is_domestic_equity(item, text):
            domestic.append(item)
        if is_us_equity(item, text):
            us.append(item)

    return SegmentedItems(tuple(domestic), tuple(us), tuple(crypto))
```

Classification helpers are small pure predicates with tests. An item may route to multiple segments when it is cross-market.

---

## L3. Data-limited prompt behavior

Before generation:

```python
data_limited = len(segment_items) < threshold[segment]
```

If `data_limited` is true, prepend segment context:

```text
This segment has limited direct source coverage today.
State "데이터 부족" in section ① and do not fill this segment with unrelated markets.
Use only the routed items below.
```

This keeps publication useful while avoiding misleading filler.

---

## L4. Archive and URL derivation

Path:

```python
archive_path_for_segment(segment, target_date)
```

URL:

```python
briefing_url_for_segment(segment, target_date, site_url_base)
```

Both must be tested for:

- segment slug in path
- zero-padded month
- no double slash when `SITE_URL_BASE` ends with `/`

---

## L5. Code generation impact map

Expected touch points:

| Area | Change |
|------|--------|
| models | Add small segment value object only if needed; prefer local dataclasses first. |
| briefing | Add segment routing and segment prompt context. |
| publisher | Add segment archive path helper and multi-file commit support if current helper is too narrow. |
| notifier | Add segmented Telegram summary builder. |
| orchestrator | Replace single generate/publish/notify path with segmented loop while preserving failure policy. |
| tests | Unit tests for routing/paths/summary + integration test for 3 archive files and 3 URLs. |

