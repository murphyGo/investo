"""Tests for u22 source coverage models + sanitization helper.

These pin the immutability contract of :class:`SourceOutcome` /
:class:`SourceCollectionReport` and the sanitization rules that keep
secret-shaped tokens out of any reader-facing failure reason.
"""

from __future__ import annotations

from datetime import datetime
from math import inf, nan

import pytest

from investo.models import (
    SourceCollectionReport,
    SourceOutcome,
    sanitize_source_error_message,
)


def test_source_outcome_ok_requires_positive_count() -> None:
    with pytest.raises(ValueError, match="item_count > 0"):
        SourceOutcome.ok("yfinance-price", "price", item_count=0)


def test_source_outcome_zero_carries_no_failure_reason() -> None:
    outcome = SourceOutcome.zero("yahoo-finance-news", "news")
    assert outcome.status == "zero"
    assert outcome.failure_reason is None
    assert outcome.transient is None


def test_source_outcome_carries_elapsed_seconds_when_provided() -> None:
    assert (
        SourceOutcome.ok("yfinance-price", "price", item_count=1, elapsed_s=1.25).elapsed_s == 1.25
    )
    assert SourceOutcome.zero("yahoo-finance-news", "news", elapsed_s=0.0).elapsed_s == 0.0


def test_source_outcome_rejects_negative_elapsed_seconds() -> None:
    with pytest.raises(ValueError, match="elapsed_s must be finite and >= 0"):
        SourceOutcome.from_failure(
            "fred-macro",
            "macro",
            message="connection reset",
            transient=True,
            elapsed_s=-0.1,
        )


@pytest.mark.parametrize("elapsed_s", [inf, nan])
def test_source_outcome_rejects_non_finite_elapsed_seconds(elapsed_s: float) -> None:
    with pytest.raises(ValueError, match="elapsed_s must be finite and >= 0"):
        SourceOutcome.zero("yahoo-finance-news", "news", elapsed_s=elapsed_s)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"status": "ok", "item_count": 0},
            "ok outcome requires item_count > 0",
        ),
        (
            {"status": "ok", "item_count": 1, "failure_reason": "boom"},
            "ok outcome forbids failure_reason",
        ),
        (
            {"status": "ok", "item_count": 1, "transient": False},
            "ok outcome forbids transient",
        ),
        (
            {"status": "zero", "item_count": 1},
            "zero outcome requires item_count == 0",
        ),
        (
            {"status": "zero", "failure_reason": "boom"},
            "zero outcome forbids failure_reason",
        ),
        (
            {"status": "zero", "transient": False},
            "zero outcome forbids transient",
        ),
        (
            {"status": "failed", "item_count": 1, "failure_reason": "boom", "transient": True},
            "failed outcome requires item_count == 0",
        ),
        (
            {"status": "failed", "failure_reason": "", "transient": True},
            "failed outcome requires failure_reason",
        ),
        (
            {"status": "failed", "failure_reason": "boom", "transient": None},
            "failed outcome requires transient bool",
        ),
        (
            {"status": "unknown", "item_count": 0},
            "status must be one of",
        ),
        (
            {"status": "zero", "category": "unknown"},
            "category must be one of",
        ),
        (
            {"status": "zero", "tier": "Z"},
            "tier must be one of",
        ),
        (
            {"status": "zero", "item_count": -1},
            "item_count must be >= 0",
        ),
    ],
)
def test_source_outcome_direct_construction_rejects_invalid_states(
    kwargs: dict[str, object],
    message: str,
) -> None:
    fields: dict[str, object] = {
        "source_name": "test-source",
        "category": "news",
        "status": "zero",
        "item_count": 0,
    }
    fields.update(kwargs)
    with pytest.raises(ValueError, match=message):
        SourceOutcome(**fields)  # type: ignore[arg-type]


def test_source_outcome_rejects_naive_latest_item_timestamp() -> None:
    with pytest.raises(ValueError, match="latest_item_at must be timezone-aware"):
        SourceOutcome.zero(
            "yahoo-finance-news",
            "news",
            latest_item_at=datetime(2026, 5, 13, 12, 0),
        )


def test_source_outcome_from_failure_sanitizes_message() -> None:
    outcome = SourceOutcome.from_failure(
        "yfinance-price",
        "price",
        message="boom 1234567890:abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL",
        transient=True,
    )
    assert outcome.status == "failed"
    assert outcome.failure_reason is not None
    assert "1234567890:" not in outcome.failure_reason
    assert "[REDACTED" in outcome.failure_reason
    assert outcome.transient is True


def test_source_outcome_is_frozen() -> None:
    outcome = SourceOutcome.ok("yfinance-price", "price", item_count=2)
    with pytest.raises((AttributeError, TypeError)):
        # frozen+slots dataclass rejects attribute assignment.
        outcome.status = "failed"  # type: ignore[misc]


def test_collection_report_outcomes_for_filters_to_subset() -> None:
    report = SourceCollectionReport(
        items=(),
        outcomes=(
            SourceOutcome.ok("yfinance-price", "price", item_count=3),
            SourceOutcome.zero("yahoo-finance-news", "news"),
            SourceOutcome.from_failure(
                "fred-macro", "macro", message="connection reset", transient=True
            ),
        ),
    )
    filtered = report.outcomes_for(frozenset({"yfinance-price", "fred-macro"}))
    assert {outcome.source_name for outcome in filtered} == {"yfinance-price", "fred-macro"}
    assert report.empty


def test_sanitize_strips_telegram_bot_token() -> None:
    text = "request to https://api.telegram.org/bot1234567890:ABCDEFG-thisIsALongerThan20Chars/send"
    cleaned = sanitize_source_error_message(text)
    assert "1234567890:" not in cleaned
    assert "ABCDEFG-thisIsALongerThan20Chars" not in cleaned


def test_sanitize_strips_long_chat_id() -> None:
    cleaned = sanitize_source_error_message("posted to chat 987654321 with success")
    assert "987654321" not in cleaned
    assert "[REDACTED_CHAT_ID]" in cleaned


def test_sanitize_redacts_query_string_keys() -> None:
    cleaned = sanitize_source_error_message(
        "GET https://api.example.com/v1/data?api_key=ABCDE&fmt=json failed with 401"
    )
    assert "api_key=ABCDE" not in cleaned
    assert "[REDACTED]=[REDACTED]" in cleaned


def test_sanitize_redacts_current_env_var_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "supersecret-token-value-xyz")
    cleaned = sanitize_source_error_message(
        "fetch failed with token supersecret-token-value-xyz in url"
    )
    assert "supersecret-token-value-xyz" not in cleaned
    assert "[REDACTED]" in cleaned


def test_sanitize_truncates_overly_long_message() -> None:
    # Use a non-base64 alphabet so the long-base64 redactor does not
    # collapse the input before truncation runs.
    cleaned = sanitize_source_error_message("연결 실패 " * 80)
    assert cleaned.endswith("…")
    assert len(cleaned) <= 120


def test_sanitize_collapses_whitespace() -> None:
    cleaned = sanitize_source_error_message("line one\n\n  line two\t\twith    spaces")
    assert "\n" not in cleaned
    assert "  " not in cleaned
