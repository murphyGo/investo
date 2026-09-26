"""Candidate reservations and source-qualified shared routing."""

from collections import Counter
from datetime import timedelta

import pytest
from pydantic import HttpUrl

from investo.briefing.event_input import observe_candidates, select_event_input_items
from investo.briefing.event_routing import is_shared_official_event, share_official_event_candidates
from investo.models import NormalizedItem
from tests.unit.briefing.test_event_evidence import NOW


def test_protected_policy_lane_has_no_new_global_cap_and_lookahead_stays_bounded() -> None:
    policies = [
        NormalizedItem(
            source_name=f"policy-{i // 20}",
            category="news",
            title=f"Official decision {i}",
            published_at=NOW,
            raw_metadata={"policy_priority": "crypto_regulation", "official_source": "true"},
        )
        for i in range(30)
    ]
    future = [
        NormalizedItem(
            source_name=f"calendar-{i // 20}",
            category="calendar",
            title=f"Future event {i}",
            published_at=NOW,
            scheduled_at=NOW + timedelta(days=1),
        )
        for i in range(40)
    ]
    selected = select_event_input_items([*future, *policies], target_date=NOW.date())
    assert all(item in selected for item in policies)
    assert sum(item.scheduled_at is not None for item in selected) == 12


def test_required_actual_over_source_budget_is_explicit_failure() -> None:
    items = [
        NormalizedItem(
            source_name="actual",
            category="macro",
            title=f"Release {i}",
            published_at=NOW,
            raw_metadata={
                "macro_event_key": f"release:{i}",
                "macro_event_status": "actual",
                "macro_priority": "P0",
            },
        )
        for i in range(25)
    ]
    with pytest.raises(ValueError, match="required macro actual"):
        select_event_input_items(items, target_date=NOW.date())


def test_explicit_nonrequired_actual_has_reservation_and_shadow_visibility() -> None:
    prices = [
        NormalizedItem(
            source_name=f"price-{i // 24}", category="price", title=f"price{i}", published_at=NOW
        )
        for i in range(96)
    ]
    actual = NormalizedItem(
        source_name="statistics",
        category="macro",
        title="New output release",
        published_at=NOW - timedelta(hours=1),
        raw_metadata={
            "macro_event_key": "output:2026-08",
            "macro_event_status": "actual",
            "macro_priority": "P2",
            "macro_release_period": "2026-08",
        },
    )
    selected = select_event_input_items([*prices, actual], target_date=NOW.date())
    assert actual in selected
    assert observe_candidates([*prices, actual], selected).news_count == 1
    assert observe_candidates([*prices, actual], prices).reservation_starved
    scheduled = actual.model_copy(update={"scheduled_at": NOW + timedelta(days=1)})
    assert observe_candidates([scheduled], [scheduled]).news_count == 0
    monthly = actual.model_copy(
        update={
            "source_name": "fred-macro",
            "raw_metadata": {
                "series_id": "OLD",
                "release_date": "2026-08-01",
            },
        }
    )
    assert observe_candidates([monthly], [monthly]).news_count == 0


def test_tracking_variants_cannot_exhaust_source_budget() -> None:
    copies = [
        NormalizedItem(
            source_name="news",
            category="news",
            title="Same event",
            published_at=NOW,
            url=f"https://example.invalid/story?utm_source={i}",
        )
        for i in range(24)
    ]
    distinct = NormalizedItem(
        source_name="news",
        category="news",
        title="Important new event",
        published_at=NOW - timedelta(seconds=1),
        url="https://example.invalid/important",
    )
    selected = select_event_input_items([*copies, distinct], target_date=NOW.date())
    assert len(selected) == 2 and distinct in selected
    assert selected == select_event_input_items(
        [distinct, *reversed(copies)], target_date=NOW.date()
    )


def test_duplicate_rows_cannot_consume_round_robin_positions() -> None:
    original = NormalizedItem(
        source_name="A",
        category="news",
        title="Same story",
        published_at=NOW,
        url="https://example.invalid/story?utm_source=0",
    )
    copies = [
        original.model_copy(
            update={"url": HttpUrl(f"https://example.invalid/story?utm_source={i}")}
        )
        for i in range(24)
    ]
    distinct = NormalizedItem(
        source_name="A",
        category="news",
        title="Second story",
        published_at=NOW - timedelta(seconds=1),
        url="https://example.invalid/second",
    )
    peers = [
        NormalizedItem(source_name=source, category="news", title=f"{source}-{i}", published_at=NOW)
        for source in "BCDEFG"
        for i in range(4)
    ]
    prices = [
        NormalizedItem(
            source_name=f"prices-{i // 24}", category="price", title=f"price{i}", published_at=NOW
        )
        for i in range(96)
    ]
    with_duplicates = select_event_input_items(
        [*copies, distinct, *peers, *prices], target_date=NOW.date()
    )
    without_duplicates = select_event_input_items(
        [original, distinct, *peers, *prices], target_date=NOW.date()
    )
    assert distinct in with_duplicates
    assert with_duplicates == without_duplicates


def test_thousand_items_reserve_news_and_remain_permutation_invariant() -> None:
    items = [
        NormalizedItem(
            source_name=f"prices-{i % 6}" if i < 950 else f"news-{i % 4}",
            category="price" if i < 950 else "news",
            title=f"item-{i:04}",
            published_at=NOW,
        )
        for i in range(1000)
    ]
    selected = select_event_input_items(items, target_date=NOW.date())
    assert selected == select_event_input_items(list(reversed(items)), target_date=NOW.date())
    assert len(selected) == 96
    assert max(Counter(row.source_name for row in selected).values()) <= 24
    assert sum(row.category == "news" for row in selected) >= 24


def test_official_global_sharing_requires_source_and_endpoint_class() -> None:
    rows = [
        NormalizedItem(
            source_name="fomc-rss",
            category="news",
            title=f"Fed release {i}",
            published_at=NOW,
            url=f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{i}.htm",
        )
        for i in range(8)
    ]
    enforcement = rows[0].model_copy(
        update={"url": "https://www.federalreserve.gov/newsevents/pressreleases/enforcement.htm"}
    )
    rumor = rows[0].model_copy(
        update={"source_name": "general-news", "title": "War and Fed crisis"}
    )
    assert not is_shared_official_event(enforcement)
    assert not is_shared_official_event(rumor)
    native = {"domestic-equity": (), "us-equity": tuple(rows), "crypto": ()}
    shared = share_official_event_candidates([*rows, enforcement, rumor], native)
    assert len(shared["domestic-equity"]) == len(shared["crypto"]) == 6
    assert shared["us-equity"] == tuple(rows)
    assert native["domestic-equity"] == ()
