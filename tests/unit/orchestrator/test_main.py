"""Tests for ``investo.__main__`` — env validation + exit codes.

Pins AC-007-1 (5-var validation), AC-007-2 (chat-ID disjointness),
AC-007-3 (best-effort alert when token+operator-id available even on
ConfigError), AC-003-7 (top-level exception → alert(stage="orchestrator")
+ exit 1), and the SUCCESS/PARTIAL/FAILED → 0/0/1 exit-code mapping
from ``component-methods.md`` C5.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

import investo.__main__ as main_mod
from investo.models import FailureContext, PipelineResult, PipelineStatus, SendResult

_VALID_ENV: dict[str, str] = {
    "CLAUDE_CODE_OAUTH_TOKEN": "fake-claude-token",
    "TELEGRAM_BOT_TOKEN": "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ",
    "TELEGRAM_BRIEFING_CHANNEL_ID": "@example_public_channel",
    "TELEGRAM_OPERATOR_CHAT_ID": "12345678",
    "SITE_URL_BASE": "https://example.github.io/investo",
}


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Clear all 5 required env vars + any test-leaked values."""
    for name in main_mod._REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    yield


def _set_env(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> None:
    """Set the 5 valid env vars, with overrides. ``None`` deletes."""
    env = dict(_VALID_ENV)
    for name, value in overrides.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    for name in main_mod._REQUIRED_ENV_VARS:
        if name in env:
            monkeypatch.setenv(name, env[name])
        else:
            monkeypatch.delenv(name, raising=False)


def _make_pipeline_result(
    status: PipelineStatus = PipelineStatus.SUCCESS,
) -> PipelineResult:
    return PipelineResult(
        target_date=date(2026, 4, 27),
        status=status,
        duration_seconds=1.0,
    )


@contextlib.contextmanager
def _stub_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: PipelineResult | None = None,
    raise_exc: BaseException | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Replace ``run_pipeline`` in __main__'s import binding so tests
    don't need real u1-u4 wiring. Returns a list capturing the kwargs
    passed to each call.
    """
    captured: list[dict[str, Any]] = []

    async def _fake_run_pipeline(
        target_date: date | None = None,
        **kwargs: Any,
    ) -> PipelineResult:
        captured.append({"target_date": target_date, **kwargs})
        if raise_exc is not None:
            raise raise_exc
        return result if result is not None else _make_pipeline_result()

    monkeypatch.setattr(main_mod, "run_pipeline", _fake_run_pipeline)
    yield captured


@contextlib.contextmanager
def _capture_alerts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[FailureContext]]:
    """Intercept the boot-alert path by replacing OperatorAlerter in
    __main__'s import binding with a stub that records ``alert`` calls.
    """
    captured: list[FailureContext] = []

    class _StubAlerter:
        def __init__(self, **kwargs: Any) -> None:
            self._kwargs = kwargs

        async def alert(self, ctx: FailureContext) -> SendResult:
            captured.append(ctx)
            return SendResult(ok=True, message_id=1)

    monkeypatch.setattr(main_mod, "OperatorAlerter", _StubAlerter)
    yield captured


# ---------------------------------------------------------------------------
# AC-007-1 — missing env vars
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", list(main_mod._REQUIRED_ENV_VARS))
def test_main_returns_1_when_required_var_missing(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """Each of the 5 required env vars individually missing → exit 1."""
    _set_env(monkeypatch, **{missing: None})
    with _stub_pipeline(monkeypatch), _capture_alerts(monkeypatch):
        assert main_mod.main() == 1


def test_main_treats_empty_string_as_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub Secrets surface as empty string when unset; treat that
    the same as absent.
    """
    _set_env(monkeypatch, CLAUDE_CODE_OAUTH_TOKEN="")
    with _stub_pipeline(monkeypatch), _capture_alerts(monkeypatch):
        assert main_mod.main() == 1


def test_main_returns_1_with_multiple_missing_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(
        monkeypatch,
        CLAUDE_CODE_OAUTH_TOKEN=None,
        TELEGRAM_BRIEFING_CHANNEL_ID=None,
        SITE_URL_BASE=None,
    )
    with _stub_pipeline(monkeypatch), _capture_alerts(monkeypatch):
        assert main_mod.main() == 1


# ---------------------------------------------------------------------------
# AC-007-2 — chat-ID disjointness
# ---------------------------------------------------------------------------


def test_main_rejects_equal_channel_and_operator_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Briefing channel == operator chat → ConfigError → exit 1."""
    _set_env(
        monkeypatch,
        TELEGRAM_BRIEFING_CHANNEL_ID="same-id",
        TELEGRAM_OPERATOR_CHAT_ID="same-id",
    )
    with _stub_pipeline(monkeypatch) as calls, _capture_alerts(monkeypatch):
        rc = main_mod.main()
    assert rc == 1
    # Pipeline never invoked — disjointness is checked before
    # construction per CLAUDE.md #5.
    assert calls == []


@pytest.mark.parametrize(
    ("channel", "operator"),
    [
        # H2 regression — without strip(), each of these pairs would
        # bypass the disjointness check (raw strings unequal) but
        # Telegram resolves both to the same chat. The fix strips both
        # sides so the check is whitespace-tolerant.
        ("@invest_brief", " @invest_brief"),  # leading space on operator.
        ("@invest_brief", "@invest_brief "),  # trailing space on operator.
        (" @invest_brief", "@invest_brief"),  # leading space on channel.
        ("@invest_brief\n", "@invest_brief"),  # trailing newline.
        ("@invest_brief\t", "\t@invest_brief"),  # mixed whitespace.
    ],
)
def test_main_rejects_chat_ids_equal_after_whitespace_strip(
    monkeypatch: pytest.MonkeyPatch,
    channel: str,
    operator: str,
) -> None:
    """H2 regression — chat-ID disjointness MUST be whitespace-
    tolerant. A single stray space in one of the two GitHub Secrets
    used to silently bypass CLAUDE.md #5 and route operator alerts to
    the public channel.
    """
    _set_env(
        monkeypatch,
        TELEGRAM_BRIEFING_CHANNEL_ID=channel,
        TELEGRAM_OPERATOR_CHAT_ID=operator,
    )
    with _stub_pipeline(monkeypatch) as calls, _capture_alerts(monkeypatch):
        rc = main_mod.main()
    assert rc == 1
    # Disjointness rejected → pipeline never invoked.
    assert calls == []


# ---------------------------------------------------------------------------
# AC-007-3 — best-effort alert on ConfigError when token+operator present
# ---------------------------------------------------------------------------


def test_main_attempts_boot_alert_on_config_error_when_alert_prereqs_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_OPERATOR_CHAT_ID`` present
    but other vars missing → ConfigError → boot-alert attempted with
    stage="orchestrator".
    """
    _set_env(monkeypatch, CLAUDE_CODE_OAUTH_TOKEN=None, SITE_URL_BASE=None)
    with _stub_pipeline(monkeypatch), _capture_alerts(monkeypatch) as alerts:
        assert main_mod.main() == 1

    assert len(alerts) == 1
    assert alerts[0].stage == "orchestrator"
    assert alerts[0].error_type == "ConfigError"


def test_main_skips_boot_alert_when_bot_token_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without TELEGRAM_BOT_TOKEN, alert prereq fails → no alert
    attempt (we have no way to authenticate the bot). Pipeline still
    exits 1; GHA email default is the operator's only signal.
    """
    _set_env(monkeypatch, TELEGRAM_BOT_TOKEN=None)
    with _stub_pipeline(monkeypatch), _capture_alerts(monkeypatch) as alerts:
        assert main_mod.main() == 1
    assert alerts == []


def test_main_skips_boot_alert_when_operator_chat_id_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, TELEGRAM_OPERATOR_CHAT_ID=None)
    with _stub_pipeline(monkeypatch), _capture_alerts(monkeypatch) as alerts:
        assert main_mod.main() == 1
    assert alerts == []


# ---------------------------------------------------------------------------
# Site URL parsing
# ---------------------------------------------------------------------------


def test_main_rejects_malformed_site_url_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unparseable URL → ConfigError → exit 1."""
    _set_env(monkeypatch, SITE_URL_BASE="not-a-url")
    with _stub_pipeline(monkeypatch), _capture_alerts(monkeypatch):
        assert main_mod.main() == 1


def test_main_accepts_https_site_url_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy URL parses cleanly and is forwarded to run_pipeline."""
    _set_env(monkeypatch)
    with (
        _stub_pipeline(monkeypatch) as calls,
        _capture_alerts(monkeypatch),
    ):
        assert main_mod.main() == 0
    assert len(calls) == 1
    assert "site_url_base" in calls[0]
    assert "example.github.io/investo" in str(calls[0]["site_url_base"])


# ---------------------------------------------------------------------------
# Exit-code mapping (PipelineStatus → int)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected_rc"),
    [
        (PipelineStatus.SUCCESS, 0),
        (PipelineStatus.PARTIAL, 0),
        (PipelineStatus.FAILED, 1),
    ],
)
def test_main_exit_code_maps_pipeline_status(
    monkeypatch: pytest.MonkeyPatch,
    status: PipelineStatus,
    expected_rc: int,
) -> None:
    """SUCCESS|PARTIAL → 0; FAILED → 1 per component-methods.md C5."""
    _set_env(monkeypatch)
    result = _make_pipeline_result(status)
    with _stub_pipeline(monkeypatch, result=result), _capture_alerts(monkeypatch):
        assert main_mod.main() == expected_rc


# ---------------------------------------------------------------------------
# AC-003-7 — top-level exception → alert + exit 1
# ---------------------------------------------------------------------------


def test_main_top_level_exception_attempts_alert_and_exits_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run_pipeline`` raises an unexpected programmer error
    (KeyError, etc.) → main() catches per AC-003-7, attempts alert
    with stage="orchestrator", returns 1. Does NOT propagate the
    exception.
    """
    _set_env(monkeypatch)
    with (
        _stub_pipeline(monkeypatch, raise_exc=KeyError("missing fixture")),
        _capture_alerts(monkeypatch) as alerts,
    ):
        assert main_mod.main() == 1
    # Alert was attempted with stage="orchestrator".
    assert len(alerts) == 1
    assert alerts[0].stage == "orchestrator"
    assert alerts[0].error_type == "KeyError"


def test_main_top_level_exception_does_not_mask_failure_when_alert_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Top-level exception with no alert prereqs → exit 1 without
    raising even though no alert can be sent.
    """
    _set_env(monkeypatch, TELEGRAM_BOT_TOKEN=None)
    with (
        _stub_pipeline(monkeypatch, raise_exc=RuntimeError("synthetic")),
        _capture_alerts(monkeypatch) as alerts,
    ):
        assert main_mod.main() == 1
    assert alerts == []  # no alert prereq.


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_main_happy_path_runs_pipeline_and_exits_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All env vars valid, run_pipeline returns SUCCESS → exit 0."""
    _set_env(monkeypatch)
    with (
        _stub_pipeline(monkeypatch) as calls,
        _capture_alerts(monkeypatch) as alerts,
    ):
        assert main_mod.main() == 0
    assert len(calls) == 1
    assert alerts == []


def test_main_does_not_invoke_run_pipeline_on_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ConfigError fails fast — no pipeline invocation, no httpx
    client constructed.
    """
    _set_env(monkeypatch, SITE_URL_BASE=None)
    with (
        _stub_pipeline(monkeypatch) as calls,
        _capture_alerts(monkeypatch),
    ):
        assert main_mod.main() == 1
    assert calls == []


# ---------------------------------------------------------------------------
# _missing_env_vars helper
# ---------------------------------------------------------------------------


def test_missing_env_vars_returns_in_declaration_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Order of returned names matches declaration order — operator
    alert text shows them in the AC-007-1 contract order.
    """
    # Set only the 2nd and 4th — the 1st, 3rd, 5th should report missing.
    _set_env(
        monkeypatch,
        CLAUDE_CODE_OAUTH_TOKEN=None,
        TELEGRAM_BRIEFING_CHANNEL_ID=None,
        SITE_URL_BASE=None,
    )
    missing = main_mod._missing_env_vars()
    assert missing == (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "TELEGRAM_BRIEFING_CHANNEL_ID",
        "SITE_URL_BASE",
    )


def test_missing_env_vars_empty_tuple_when_all_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch)
    assert main_mod._missing_env_vars() == ()


# ---------------------------------------------------------------------------
# Best-effort alert robustness — never lets exceptions propagate
# ---------------------------------------------------------------------------


def test_main_alert_construction_failure_silenced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If FailureContext construction fails for some reason (e.g. pydantic
    validation rejects a synthetic edge case), the alert path swallows
    silently — pipeline still exits 1.
    """
    _set_env(monkeypatch, CLAUDE_CODE_OAUTH_TOKEN=None)

    # Force FailureContext construction to fail by patching it with
    # a stub that always raises ValidationError.
    class _BrokenFailureContext:
        def __init__(self, **kwargs: Any) -> None:
            raise ValueError("synthetic")

    monkeypatch.setattr(main_mod, "FailureContext", _BrokenFailureContext)
    with _stub_pipeline(monkeypatch), _capture_alerts(monkeypatch):
        rc = main_mod.main()
    assert rc == 1


def test_main_alerter_dispatch_exception_silenced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the alerter raises an OSError during dispatch, the boot
    path silently skips and main() still returns 1.
    """
    _set_env(monkeypatch, CLAUDE_CODE_OAUTH_TOKEN=None)

    class _RaisingAlerter:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def alert(self, ctx: FailureContext) -> SendResult:
            raise OSError("synthetic transport failure")

    monkeypatch.setattr(main_mod, "OperatorAlerter", _RaisingAlerter)
    with _stub_pipeline(monkeypatch):
        assert main_mod.main() == 1


# ---------------------------------------------------------------------------
# Integration sanity — main() forwards correct args to run_pipeline
# ---------------------------------------------------------------------------


def test_main_forwards_publisher_alerter_and_site_url_base_to_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the orchestrator sees the constructed publisher / alerter
    / site_url_base — these are critical for CLAUDE.md #5 + AC-007-2.
    """
    _set_env(monkeypatch)
    with (
        _stub_pipeline(monkeypatch) as calls,
        _capture_alerts(monkeypatch),
    ):
        assert main_mod.main() == 0
    assert len(calls) == 1
    kwargs = calls[0]
    assert "publisher" in kwargs
    assert "alerter" in kwargs
    assert "site_url_base" in kwargs
