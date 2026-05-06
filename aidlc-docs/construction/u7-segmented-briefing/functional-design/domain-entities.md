# Domain Entities — `u7 segmented briefing`

**Date**: 2026-05-07

---

## E1. MarketSegment

Closed set of market segments produced by the daily pipeline.

```python
MarketSegment = Literal["domestic-equity", "us-equity", "crypto"]
```

User-facing labels:

| Segment | Label |
|---------|-------|
| `domestic-equity` | 국내 증시 |
| `us-equity` | 미국 증시 |
| `crypto` | 크립토 |

The segment ID is stable and path-safe. The label is presentation text only.

---

## E2. SegmentedItems

Container produced after collection and before LLM generation.

```python
@dataclass(frozen=True)
class SegmentedItems:
    domestic_equity: tuple[NormalizedItem, ...]
    us_equity: tuple[NormalizedItem, ...]
    crypto: tuple[NormalizedItem, ...]
```

Rules:

- The same item may appear in more than one segment only when it is clearly cross-market, such as a Fed decision relevant to US equities and crypto.
- Segment assignment is deterministic Python logic, not an LLM decision.
- Unassigned low-signal items are dropped from segment generation.

---

## E3. SegmentBriefing

Successful output for one segment.

```python
@dataclass(frozen=True)
class SegmentBriefing:
    segment: MarketSegment
    label: str
    briefing: Briefing
    item_count: int
    data_limited: bool
```

`briefing.target_date` remains the shared pipeline target date. `data_limited=True` means the segment was generated from insufficient direct signal and must say so in the body.

---

## E4. SegmentedPipelineOutput

Pipeline-level success payload.

```python
@dataclass(frozen=True)
class SegmentedPipelineOutput:
    target_date: date
    segments: tuple[SegmentBriefing, SegmentBriefing, SegmentBriefing]
    urls: dict[MarketSegment, HttpUrl]
```

The three segment IDs must all be present. Partial public publication is deferred for v1; see business rules.

