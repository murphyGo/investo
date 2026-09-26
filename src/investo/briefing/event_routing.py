"""Conservative shared official-event inputs; native coverage stays separate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

from investo.briefing.event_input import event_item_sort_key, item_evidence_key
from investo.models import NormalizedItem
from investo.models.segments import MarketSegment


def is_shared_official_event(item: NormalizedItem) -> bool:
    if item.url is None or item.scheduled_at is not None:
        return False
    url = urlsplit(str(item.url))
    if url.scheme != "https" or url.hostname not in {
        "www.federalreserve.gov",
        "federalreserve.gov",
    }:
        return False
    # press_all.xml includes enforcement/bank supervision announcements. A
    # feed name or the word "Fed" alone must never promote these to policy.
    return (
        item.source_name == "fomc-rss" and url.path.startswith("/newsevents/pressreleases/monetary")
    ) or (
        item.source_name == "fed-speech-rss"
        and item.raw_metadata.get("official_source") == "true"
        and url.path.startswith("/newsevents/speech/")
    )


def share_official_event_candidates(
    items: Sequence[NormalizedItem],
    native: Mapping[MarketSegment, Sequence[NormalizedItem]],
) -> dict[MarketSegment, tuple[NormalizedItem, ...]]:
    """Add up to six source-qualified inputs; classification decides relevance.

    u74's cause allowlist is not an article-level authorization. There is no
    current typed geopolitical/systemic source producer, so those sharing
    lanes remain dormant rather than treating a headline keyword as evidence.
    """
    shared = sorted(
        (item for item in items if is_shared_official_event(item)), key=event_item_sort_key
    )
    result: dict[MarketSegment, tuple[NormalizedItem, ...]] = {}
    for segment, rows in native.items():
        seen = {item_evidence_key(item) for item in rows}
        additions: list[NormalizedItem] = []
        for item in shared:
            key = item_evidence_key(item)
            if key not in seen:
                seen.add(key)
                additions.append(item)
                if len(additions) == 6:
                    break
        result[segment] = (*rows, *additions)
    return result
