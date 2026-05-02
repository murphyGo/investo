"""``python -m investo`` entrypoint (US-005, AC-007-1 ~ AC-007-5, AC-003-7).

Parses 5 environment variables, enforces the CLAUDE.md #5 chat-ID
disjointness invariant *before* constructing either dispatcher,
builds a shared ``httpx.AsyncClient`` for both Telegram dispatchers,
runs ``investo.orchestrator.run_pipeline``, maps the resulting
:class:`PipelineStatus` to an exit code, and (per AC-003-7) wraps
the whole thing so an unexpected programmer error still triggers a
best-effort operator alert + ``exit 1``.

Exit codes (per `aidlc-docs/inception/application-design/component-methods.md` C5):

* ``SUCCESS`` or ``PARTIAL`` → ``0``
* ``FAILED`` → ``1``
* :class:`ConfigError` (env validation) → ``1``
* unexpected ``Exception`` → ``1``

Per Q9=A+ (env validation):

* If ``TELEGRAM_BOT_TOKEN`` AND ``TELEGRAM_OPERATOR_CHAT_ID`` are
  present, a single best-effort ``OperatorAlerter.alert`` is
  attempted on ``ConfigError`` even though one or more *other* env
  vars are missing — operator gets visibility into the boot failure
  via Telegram, not just the GHA email default.
* On unexpected ``Exception`` (per AC-003-7) the same best-effort
  alert path is used with ``stage="orchestrator"``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, date, datetime
from typing import Final

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from investo.models import FailureContext, PipelineStatus
from investo.notifier import BriefingPublisher, OperatorAlerter
from investo.orchestrator.date_resolution import validate_target_date_sanity
from investo.orchestrator.errors import ConfigError
from investo.orchestrator.pipeline import run_pipeline

# The 5 required env vars per AC-007-1 + ``component-methods.md`` C5.
# Order pinned: governs the order ``ConfigError.for_missing`` reports.
_REQUIRED_ENV_VARS: Final[tuple[str, ...]] = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHANNEL_ID",
    "TELEGRAM_OPERATOR_CHAT_ID",
    "SITE_URL_BASE",
)

# Best-effort alert on ConfigError can only run when these two vars
# specifically are present (regardless of which others are missing).
# The token authenticates the bot; the chat_id is where the alert lands.
_ALERT_PREREQ_VARS: Final[tuple[str, ...]] = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OPERATOR_CHAT_ID",
)

_logger = logging.getLogger("investo")

# Optional override from the GHA ``workflow_dispatch`` input (u6
# ``daily-briefing.yml``). When present and non-empty, parsed via
# ``date.fromisoformat`` (ISO-8601 ``YYYY-MM-DD``) and passed to
# ``run_pipeline(target_date=...)`` — overrides
# ``resolve_target_date(now_utc)``. Used for backfills + US-public-
# holiday recoveries (per Q3=A: holiday days surface as empty-collect
# → operator alert; the operator re-triggers manually with
# ``target_date=last-trading-day``). Empty string or absent ⇒ default
# cron behavior (orchestrator resolves from ``now_utc``).
_TARGET_DATE_OVERRIDE_VAR: Final[str] = "INVESTO_TARGET_DATE"

# One-shot timeout for the boot-failure best-effort alert. Must be
# short — the pipeline has already failed and we're keeping the
# operator informed; if Telegram is also down, GHA's email default
# is the fallback.
_BOOT_ALERT_TIMEOUT_S: Final[float] = 5.0


def _missing_env_vars() -> tuple[str, ...]:
    """Return the names of required env vars absent from the
    environment, in the order declared by ``_REQUIRED_ENV_VARS``.

    Treats ``""`` (empty string) as missing — GitHub Secrets cannot
    surface an unset secret as anything other than empty, so empty
    is functionally the same as absent for env-validation purposes.
    """
    return tuple(name for name in _REQUIRED_ENV_VARS if not os.environ.get(name))


def _validate_env() -> tuple[str, str, str, str, HttpUrl]:
    """Validate the 5 required env vars and return their parsed values.

    Returns a 5-tuple in the order
    ``(claude_oauth_token, bot_token, briefing_channel_id,
    operator_chat_id, site_url_base)``.

    Raises
    ------
    ConfigError
        Per AC-007-1 (one or more required vars missing) or
        AC-007-2 (briefing channel and operator chat IDs identical).
        ``ConfigError.missing_vars`` discriminates: empty tuple ⇒
        equality violation; non-empty ⇒ missing-var case.
    """
    missing = _missing_env_vars()
    if missing:
        raise ConfigError.for_missing(missing)

    # ``.strip()`` defangs a sneaky misconfiguration where the operator
    # pastes ``"@invest_brief"`` into one secret and ``" @invest_brief"``
    # (leading whitespace) into the other. The raw strings are unequal
    # but Telegram's API resolves both to the same chat — without the
    # strip the disjointness check would pass and the public channel
    # would receive operator alerts. We carry the stripped values
    # forward so downstream callers see the canonical form too.
    claude_oauth = os.environ["CLAUDE_CODE_OAUTH_TOKEN"].strip()
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    channel_id = os.environ["TELEGRAM_BRIEFING_CHANNEL_ID"].strip()
    operator_id = os.environ["TELEGRAM_OPERATOR_CHAT_ID"].strip()
    site_url_raw = os.environ["SITE_URL_BASE"].strip()

    # CLAUDE.md project rule #5 — disjointness enforced BEFORE either
    # dispatcher is constructed. Whitespace differences (one secret has
    # a leading/trailing space, the other doesn't) MUST NOT bypass
    # this — strip both sides above + compare here.
    if channel_id == operator_id:
        raise ConfigError.for_equal_chat_ids()

    try:
        site_url_base = TypeAdapter(HttpUrl).validate_python(site_url_raw)
    except ValidationError as exc:
        # Surfaces as ``ConfigError`` with ``SITE_URL_BASE`` named so
        # the operator alert text is actionable.
        raise ConfigError.for_bad_value(
            "SITE_URL_BASE",
            f"SITE_URL_BASE is not a valid HTTP URL: {site_url_raw!r}",
        ) from exc

    return claude_oauth, bot_token, channel_id, operator_id, site_url_base


async def _attempt_boot_alert(exc: BaseException) -> None:
    """Best-effort operator alert during boot/top-level failure.

    Only fires when ``TELEGRAM_BOT_TOKEN`` AND ``TELEGRAM_OPERATOR_CHAT_ID``
    are both present (per AC-007-3). Construction errors and dispatch
    failures are silently swallowed — the underlying failure is
    already on its way to ``exit 1``; alert is the cherry on top, not
    a hard requirement.

    Note: we intentionally do NOT validate the chat-ID disjointness
    invariant here. The OperatorAlerter only knows the operator
    chat_id, never the public channel_id, so there's no risk of
    misroute even if the operator misconfigured them to be equal —
    the alert lands at the operator chat, full stop.
    """
    if any(not os.environ.get(name) for name in _ALERT_PREREQ_VARS):
        return

    # Truncate the exception text to fit ``FailureContext`` limits.
    # Use the same simple string fallback as the orchestrator's
    # ``_build_failure_context`` to keep the boot path independent
    # of the orchestrator's helpers (which import the four stage
    # runners and pull in u1-u4 even on a config-only failure path).
    error_message = str(exc) or type(exc).__name__

    try:
        ctx = FailureContext(
            stage="orchestrator",
            error_type=type(exc).__name__,
            error_message=error_message,
            occurred_at=datetime.now(UTC),
        )
    except (ValidationError, ValueError):
        return  # Construction failure ⇒ skip alert silently.

    try:
        async with httpx.AsyncClient(timeout=_BOOT_ALERT_TIMEOUT_S) as client:
            alerter = OperatorAlerter(
                bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
                operator_chat_id=os.environ["TELEGRAM_OPERATOR_CHAT_ID"],
                http=client,
            )
            await alerter.alert(ctx)
    except Exception:
        # Best-effort — never let alerter exceptions mask the
        # underlying failure exit code.
        pass


def _resolve_target_date_override() -> date | None:
    """Parse the optional ``INVESTO_TARGET_DATE`` env-var override.

    Returns
    -------
    date | None
        ``None`` if the var is absent or empty (default cron path —
        orchestrator resolves from ``now_utc``). A parsed
        :class:`datetime.date` if it's set to a valid ISO-8601
        ``YYYY-MM-DD`` string.

    Raises
    ------
    ConfigError
        If the var is set to a non-empty value that isn't a valid
        ISO-8601 date — fail loudly at the boundary so the operator's
        manual workflow_dispatch input doesn't silently roll back to
        the cron default.
    """
    raw = os.environ.get(_TARGET_DATE_OVERRIDE_VAR, "").strip()
    if not raw:
        return None
    try:
        return validate_target_date_sanity(date.fromisoformat(raw))
    except ValueError as exc:
        raise ConfigError.for_bad_value(
            _TARGET_DATE_OVERRIDE_VAR,
            f"{_TARGET_DATE_OVERRIDE_VAR} is not a valid supported ISO-8601 date "
            f"(YYYY-MM-DD): {raw!r}",
        ) from exc


async def _async_main() -> int:
    """Async core of :func:`main` — separated so ``main`` can synchronously
    drive ``asyncio.run`` and translate the final integer to the
    process exit code.
    """
    try:
        (
            _claude_oauth,  # consumed by the ``claude`` CLI itself, not by Python.
            bot_token,
            channel_id,
            operator_id,
            site_url_base,
        ) = _validate_env()
        # Optional override from u6's workflow_dispatch input. Parsed
        # alongside the required vars so a malformed value rejects
        # before any httpx client is constructed (matches the
        # ConfigError fail-fast pattern).
        target_date_override = _resolve_target_date_override()
    except ConfigError as exc:
        _logger.error("config error: %s", exc)
        await _attempt_boot_alert(exc)
        return 1

    try:
        # Single shared httpx.AsyncClient → one TLS handshake covers
        # both BriefingPublisher.send and any OperatorAlerter.alert
        # the pipeline issues internally. Production tip from u4
        # docstring (Step 7 L4 doc).
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            publisher = BriefingPublisher(
                bot_token=bot_token,
                channel_id=channel_id,
                http=http_client,
            )
            alerter = OperatorAlerter(
                bot_token=bot_token,
                operator_chat_id=operator_id,
                http=http_client,
            )

            result = await run_pipeline(
                target_date_override,
                publisher=publisher,
                alerter=alerter,
                site_url_base=site_url_base,
            )

        if result.status == PipelineStatus.FAILED:
            return 1
        return 0  # SUCCESS or PARTIAL.
    except Exception as exc:
        # Programmer errors (KeyError, AttributeError, ValidationError
        # constructing models, etc.) reach here. Log + best-effort
        # alert + exit 1.
        _logger.exception("unexpected pipeline error: %s", exc)
        await _attempt_boot_alert(exc)
        return 1


def main() -> int:
    """Synchronous module entrypoint.

    Configures stdlib logging, dispatches to :func:`_async_main`,
    returns the exit code. Idempotent w.r.t. the running event loop —
    ``asyncio.run`` creates a fresh loop on each invocation.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(_async_main())


if __name__ == "__main__":
    sys.exit(main())
