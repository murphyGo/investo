"""Unit tests for ``investo.models.items`` (NormalizedItem + Category)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from investo.models.items import NormalizedItem


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _base_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source_name": "yahoo",
        "category": "news",
        "title": "Some headline",
        "published_at": _now_utc(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Valid construction
# ---------------------------------------------------------------------------


def test_valid_minimal_item() -> None:
    item = NormalizedItem(**_base_kwargs())
    assert item.source_name == "yahoo"
    assert item.category == "news"
    assert item.title == "Some headline"
    assert item.summary is None
    assert item.url is None
    assert item.raw_metadata == {}


def test_valid_item_with_all_fields() -> None:
    item = NormalizedItem(
        **_base_kwargs(
            summary="A short summary",
            url="https://example.com/news/1",
            raw_metadata={"author": "anon", "score": 7, "ratio": 1.5},
        )
    )
    assert item.summary == "A short summary"
    assert str(item.url) == "https://example.com/news/1"
    assert item.raw_metadata == {"author": "anon", "score": 7, "ratio": 1.5}


@pytest.mark.parametrize(
    "category",
    ["news", "price", "macro", "calendar", "earnings"],
)
def test_all_category_literals_accepted(category: str) -> None:
    item = NormalizedItem(**_base_kwargs(category=category))
    assert item.category == category


# ---------------------------------------------------------------------------
# Whitespace / blank handling (M2 fix from review)
# ---------------------------------------------------------------------------


def test_source_name_whitespace_only_rejected() -> None:
    with pytest.raises(ValidationError, match="non-whitespace"):
        NormalizedItem(**_base_kwargs(source_name="   "))


def test_title_whitespace_only_rejected() -> None:
    with pytest.raises(ValidationError, match="non-whitespace"):
        NormalizedItem(**_base_kwargs(title="\t\n  "))


def test_source_name_stripped() -> None:
    item = NormalizedItem(**_base_kwargs(source_name="  yahoo  "))
    assert item.source_name == "yahoo"


def test_title_stripped() -> None:
    item = NormalizedItem(**_base_kwargs(title="  hi  "))
    assert item.title == "hi"


def test_empty_summary_normalized_to_none() -> None:
    item = NormalizedItem(**_base_kwargs(summary=""))
    assert item.summary is None


def test_whitespace_summary_normalized_to_none() -> None:
    item = NormalizedItem(**_base_kwargs(summary="   \n"))
    assert item.summary is None


def test_real_summary_stripped() -> None:
    item = NormalizedItem(**_base_kwargs(summary="  hello  "))
    assert item.summary == "hello"


# ---------------------------------------------------------------------------
# Datetime tz validation (shared helper)
# ---------------------------------------------------------------------------


def test_naive_published_at_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        NormalizedItem(**_base_kwargs(published_at=datetime(2026, 4, 27, 9, 0, 0)))


def test_non_utc_tz_accepted() -> None:
    kst = timezone(timedelta(hours=9))
    dt = datetime(2026, 4, 27, 7, 0, tzinfo=kst)
    item = NormalizedItem(**_base_kwargs(published_at=dt))
    assert item.published_at == dt


# ---------------------------------------------------------------------------
# Category / extra-field rejection
# ---------------------------------------------------------------------------


def test_invalid_category_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedItem(**_base_kwargs(category="invalid"))


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedItem(**_base_kwargs(unexpected="field"))


# ---------------------------------------------------------------------------
# raw_metadata strict union (M1 fix from review)
# ---------------------------------------------------------------------------


def test_raw_metadata_str_int_float_accepted() -> None:
    item = NormalizedItem(**_base_kwargs(raw_metadata={"a": "x", "b": 1, "c": 1.5}))
    assert item.raw_metadata == {"a": "x", "b": 1, "c": 1.5}


def test_raw_metadata_bool_rejected() -> None:
    # StrictInt rejects bool (True/False) — important for provenance integrity.
    with pytest.raises(ValidationError):
        NormalizedItem(**_base_kwargs(raw_metadata={"flag": True}))


def test_raw_metadata_none_value_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedItem(**_base_kwargs(raw_metadata={"x": None}))


def test_raw_metadata_nested_dict_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedItem(**_base_kwargs(raw_metadata={"x": {"nested": 1}}))


# ---------------------------------------------------------------------------
# Frozen / immutability
# ---------------------------------------------------------------------------


def test_frozen_blocks_mutation() -> None:
    item = NormalizedItem(**_base_kwargs())
    with pytest.raises(ValidationError):
        item.title = "different"  # type: ignore[misc]


def test_frozen_can_be_round_tripped_via_model_copy() -> None:
    item = NormalizedItem(**_base_kwargs())
    new = item.model_copy(update={"title": "different"})
    assert new.title == "different"
    assert item.title == "Some headline"  # original unchanged


# ---------------------------------------------------------------------------
# Source-name length boundary
# ---------------------------------------------------------------------------


def test_source_name_max_length_100_accepted() -> None:
    item = NormalizedItem(**_base_kwargs(source_name="a" * 100))
    assert len(item.source_name) == 100


def test_source_name_over_max_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedItem(**_base_kwargs(source_name="a" * 101))
