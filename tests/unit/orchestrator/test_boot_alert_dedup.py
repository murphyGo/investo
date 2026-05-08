"""Tests for u31 Step 2 — boot-alert dedup ledger."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from investo.orchestrator import boot_alert_dedup


def _ts(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def test_should_alert_returns_true_when_ledger_missing(tmp_path: Path) -> None:
    state = tmp_path / "boot_alerts.json"
    assert boot_alert_dedup.should_alert(
        error_type="ConfigError",
        error_message="missing TELEGRAM_BOT_TOKEN",
        now_utc=_ts(2026, 5, 9),
        state_path=state,
    )


def test_record_then_should_alert_returns_false_within_window(tmp_path: Path) -> None:
    state = tmp_path / "boot_alerts.json"
    boot_alert_dedup.record_alert(
        error_type="ConfigError",
        error_message="missing TELEGRAM_BOT_TOKEN",
        now_utc=_ts(2026, 5, 1),
        state_path=state,
    )
    # Same fingerprint, 5 days later → suppressed.
    assert not boot_alert_dedup.should_alert(
        error_type="ConfigError",
        error_message="missing TELEGRAM_BOT_TOKEN",
        now_utc=_ts(2026, 5, 6),
        state_path=state,
    )


def test_should_alert_returns_true_after_window_expires(tmp_path: Path) -> None:
    state = tmp_path / "boot_alerts.json"
    boot_alert_dedup.record_alert(
        error_type="ConfigError",
        error_message="missing TELEGRAM_BOT_TOKEN",
        now_utc=_ts(2026, 5, 1),
        state_path=state,
    )
    # 15 days later → outside the 14-day window → re-alerts.
    assert boot_alert_dedup.should_alert(
        error_type="ConfigError",
        error_message="missing TELEGRAM_BOT_TOKEN",
        now_utc=_ts(2026, 5, 16),
        state_path=state,
    )


def test_different_message_is_not_deduped(tmp_path: Path) -> None:
    state = tmp_path / "boot_alerts.json"
    boot_alert_dedup.record_alert(
        error_type="ConfigError",
        error_message="missing TELEGRAM_BOT_TOKEN",
        now_utc=_ts(2026, 5, 1),
        state_path=state,
    )
    # Different error_message → different fingerprint → re-alerts.
    assert boot_alert_dedup.should_alert(
        error_type="ConfigError",
        error_message="missing SITE_URL_BASE",
        now_utc=_ts(2026, 5, 2),
        state_path=state,
    )


def test_record_alert_replaces_previous_entry(tmp_path: Path) -> None:
    state = tmp_path / "boot_alerts.json"
    boot_alert_dedup.record_alert(
        error_type="ConfigError",
        error_message="X",
        now_utc=_ts(2026, 5, 1),
        state_path=state,
    )
    boot_alert_dedup.record_alert(
        error_type="ConfigError",
        error_message="X",
        now_utc=_ts(2026, 5, 5),
        state_path=state,
    )
    raw = state.read_text(encoding="utf-8")
    # Only one entry persists; the newer timestamp won.
    assert raw.count("ConfigError") == 1
    assert "2026-05-05" in raw


def test_corrupt_ledger_does_not_block_alert(tmp_path: Path) -> None:
    state = tmp_path / "boot_alerts.json"
    state.write_text("not-valid-json{{", encoding="utf-8")
    assert boot_alert_dedup.should_alert(
        error_type="ConfigError",
        error_message="any",
        now_utc=_ts(2026, 5, 9),
        state_path=state,
    )


def test_resolve_state_dir_honours_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("INVESTO_OPERATOR_STATE_DIR", "/tmp/custom-state")
    assert boot_alert_dedup.resolve_state_dir() == Path("/tmp/custom-state")
    monkeypatch.delenv("INVESTO_OPERATOR_STATE_DIR")
    assert boot_alert_dedup.resolve_state_dir() == Path("archive/_meta/operator_state")


def test_fingerprint_is_stable_under_long_messages() -> None:
    """Truncation cap means a 10MB stack trace cannot bloat the ledger."""
    fp_short = boot_alert_dedup.fingerprint_for("ConfigError", "x" * 1024)
    fp_long = boot_alert_dedup.fingerprint_for("ConfigError", "x" * 10_000)
    # Both clamp at the same prefix → identical fingerprint.
    assert fp_short == fp_long
