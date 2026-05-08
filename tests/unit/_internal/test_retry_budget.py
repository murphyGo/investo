"""Tests for u31 Step 5 — process-wide retry budget."""

from __future__ import annotations

import pytest

from investo._internal import retry_budget


@pytest.fixture(autouse=True)
def _reset() -> None:
    retry_budget.reset_budget()


def test_default_budget_constant() -> None:
    assert retry_budget.DEFAULT_RETRY_BUDGET == 30


def test_remaining_starts_at_default() -> None:
    assert retry_budget.remaining() == 30


def test_allow_retry_charges_one_each_call() -> None:
    assert retry_budget.allow_retry() is True
    assert retry_budget.remaining() == 29
    assert retry_budget.allow_retry() is True
    assert retry_budget.remaining() == 28


def test_allow_retry_returns_false_when_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_RETRY_BUDGET", "2")
    assert retry_budget.allow_retry() is True
    assert retry_budget.allow_retry() is True
    # 3rd call exhausts.
    assert retry_budget.allow_retry() is False


def test_zero_budget_blocks_first_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_RETRY_BUDGET", "0")
    assert retry_budget.allow_retry() is False


def test_invalid_env_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_RETRY_BUDGET", "not-a-number")
    assert retry_budget.remaining() == retry_budget.DEFAULT_RETRY_BUDGET


def test_negative_env_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_RETRY_BUDGET", "-5")
    assert retry_budget.remaining() == retry_budget.DEFAULT_RETRY_BUDGET


def test_reset_restores_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_RETRY_BUDGET", "1")
    retry_budget.allow_retry()
    assert retry_budget.allow_retry() is False
    retry_budget.reset_budget()
    assert retry_budget.allow_retry() is True
