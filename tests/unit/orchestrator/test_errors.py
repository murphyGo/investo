"""Tests for ``investo.orchestrator.errors``.

Pins the two-mode ``ConfigError`` contract (AC-007-1 missing vars +
AC-007-2 chat-ID disjointness) and the ``EmptyCollectError`` internal
sentinel (AC-003-2).
"""

from __future__ import annotations

import pytest

from investo.orchestrator.errors import ConfigError, EmptyCollectError

# ---------------------------------------------------------------------------
# ConfigError — basic construction
# ---------------------------------------------------------------------------


def test_config_error_inherits_from_runtime_error() -> None:
    """``ConfigError`` is a ``RuntimeError`` subclass — not a generic
    ``Exception`` — so ``main()``'s top-level ``except Exception`` only
    catches truly unexpected programmer errors after the dedicated
    ``except ConfigError`` block has already run.
    """
    err = ConfigError("test", missing_vars=("FOO",))
    assert isinstance(err, RuntimeError)
    assert isinstance(err, Exception)


def test_config_error_default_missing_vars_is_empty_tuple() -> None:
    """Default ``missing_vars`` is an empty tuple (chat-ID-equality
    case); never ``None`` so callers can iterate unconditionally.
    """
    err = ConfigError("synthetic")
    assert err.missing_vars == ()
    assert err.bad_value_var is None


def test_config_error_missing_vars_is_immutable_tuple() -> None:
    """Stored as a tuple so callers can safely log without copying."""
    err = ConfigError("x", missing_vars=("A", "B"))
    assert isinstance(err.missing_vars, tuple)
    assert err.missing_vars == ("A", "B")
    assert err.bad_value_var is None


def test_config_error_str_form_is_the_message() -> None:
    """``str(err)`` returns the constructor message verbatim — what
    stderr / GHA log will show.
    """
    err = ConfigError("specific message", missing_vars=("FOO",))
    assert str(err) == "specific message"


# ---------------------------------------------------------------------------
# ConfigError.for_missing — env var absence (AC-007-1)
# ---------------------------------------------------------------------------


def test_config_error_for_missing_single_var() -> None:
    err = ConfigError.for_missing(("CLAUDE_CODE_OAUTH_TOKEN",))
    assert err.missing_vars == ("CLAUDE_CODE_OAUTH_TOKEN",)
    assert "CLAUDE_CODE_OAUTH_TOKEN" in str(err)
    assert "missing required environment variable" in str(err)


def test_config_error_for_missing_multiple_vars_join_in_order() -> None:
    """Multiple missing vars are joined with ', ' in the order given —
    so callers control display order (e.g., the AC-007-1 var list).
    """
    err = ConfigError.for_missing(("TELEGRAM_BOT_TOKEN", "TELEGRAM_BRIEFING_CHANNEL_ID"))
    assert err.missing_vars == (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BRIEFING_CHANNEL_ID",
    )
    msg = str(err)
    assert "TELEGRAM_BOT_TOKEN" in msg
    assert "TELEGRAM_BRIEFING_CHANNEL_ID" in msg
    # Order preserved.
    assert msg.index("TELEGRAM_BOT_TOKEN") < msg.index("TELEGRAM_BRIEFING_CHANNEL_ID")


def test_config_error_for_missing_all_five_required_vars() -> None:
    """Pin the 5-var contract from AC-007-1 — these are the env vars
    ``main()`` reads at entry. If this list ever changes, the test
    needs updating in lockstep with ``component-methods.md`` C5.
    """
    all_five = (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BRIEFING_CHANNEL_ID",
        "TELEGRAM_OPERATOR_CHAT_ID",
        "SITE_URL_BASE",
    )
    err = ConfigError.for_missing(all_five)
    for var in all_five:
        assert var in str(err)


def test_config_error_for_missing_rejects_empty_tuple() -> None:
    """Empty ``missing_vars`` is the chat-ID-equality case and has its
    own factory; ``for_missing(())`` MUST raise to prevent the two
    failure modes from being silently conflated.
    """
    with pytest.raises(ValueError, match="for_equal_chat_ids"):
        ConfigError.for_missing(())


# ---------------------------------------------------------------------------
# ConfigError.for_equal_chat_ids — CLAUDE.md #5 (AC-007-2)
# ---------------------------------------------------------------------------


def test_config_error_for_equal_chat_ids_empty_missing_vars() -> None:
    """``missing_vars`` is empty for the chat-ID-equality variant — the
    discriminator main() can use to route the alert wording.
    """
    err = ConfigError.for_equal_chat_ids()
    assert err.missing_vars == ()
    assert err.bad_value_var is None


def test_config_error_for_equal_chat_ids_message_names_both_vars() -> None:
    """Message must name both env vars so the operator alert is
    actionable without further context.
    """
    err = ConfigError.for_equal_chat_ids()
    msg = str(err)
    assert "TELEGRAM_BRIEFING_CHANNEL_ID" in msg
    assert "TELEGRAM_OPERATOR_CHAT_ID" in msg
    assert "disjoint" in msg.lower()


def test_config_error_for_equal_chat_ids_cites_claude_md_rule() -> None:
    """The message references CLAUDE.md project rule #5 so the operator
    can find the canonical statement of the invariant.
    """
    err = ConfigError.for_equal_chat_ids()
    assert "CLAUDE.md" in str(err)


# ---------------------------------------------------------------------------
# ConfigError.for_bad_value — present but malformed env var
# ---------------------------------------------------------------------------


def test_config_error_for_bad_value_sets_bad_value_var() -> None:
    err = ConfigError.for_bad_value(
        "INVESTO_TARGET_DATE",
        "INVESTO_TARGET_DATE is not a valid supported ISO-8601 date",
    )
    assert err.missing_vars == ()
    assert err.bad_value_var == "INVESTO_TARGET_DATE"
    assert "ISO-8601" in str(err)


def test_config_error_for_bad_value_rejects_empty_var_name() -> None:
    with pytest.raises(ValueError, match="requires a var name"):
        ConfigError.for_bad_value("", "bad")


def test_config_error_rejects_missing_and_bad_value_together() -> None:
    with pytest.raises(ValueError, match="both missing_vars and bad_value_var"):
        ConfigError("bad", missing_vars=("FOO",), bad_value_var="BAR")


# ---------------------------------------------------------------------------
# ConfigError — raise + catch round-trip
# ---------------------------------------------------------------------------


def test_config_error_raise_and_catch_preserves_missing_vars() -> None:
    """A caught ``ConfigError`` retains its ``missing_vars`` field —
    main() needs this for the AC-007-3 best-effort alert routing.
    """
    try:
        raise ConfigError.for_missing(("FOO", "BAR"))
    except ConfigError as caught:
        assert caught.missing_vars == ("FOO", "BAR")
        assert "FOO" in str(caught)


def test_config_error_caught_as_runtime_error() -> None:
    """Higher-level handlers expecting ``RuntimeError`` still catch us."""
    try:
        raise ConfigError.for_equal_chat_ids()
    except RuntimeError as caught:
        assert isinstance(caught, ConfigError)
        assert caught.missing_vars == ()


# ---------------------------------------------------------------------------
# EmptyCollectError — internal sentinel (AC-003-2)
# ---------------------------------------------------------------------------


def test_empty_collect_error_inherits_from_runtime_error() -> None:
    err = EmptyCollectError("no items")
    assert isinstance(err, RuntimeError)


def test_empty_collect_error_default_construction() -> None:
    """Constructible with no message — orchestrator may raise it as a
    pure control-flow signal then format the operator alert at the
    catch site.
    """
    err = EmptyCollectError()
    assert isinstance(err, EmptyCollectError)


def test_empty_collect_error_str_with_message() -> None:
    err = EmptyCollectError("aggregator returned 0 items for 2026-04-25")
    assert "0 items" in str(err)


def test_empty_collect_error_distinct_from_config_error() -> None:
    """``EmptyCollectError`` and ``ConfigError`` are unrelated — neither
    catches the other. ``main()`` only needs to handle ``ConfigError``
    explicitly; ``EmptyCollectError`` is contained inside
    ``run_pipeline``.
    """
    assert not issubclass(EmptyCollectError, ConfigError)
    assert not issubclass(ConfigError, EmptyCollectError)
