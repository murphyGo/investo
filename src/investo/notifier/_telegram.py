"""Internal HTTP helper for the Telegram Bot API.

Two pure-or-near-pure entry points:

* :func:`telegram_api_url` — build the canonical sendMessage URL.
* :func:`send_message` — POST a single ``sendMessage`` call and
  return a :class:`SendResult`. Non-raising: HTTP failures, timeouts,
  and Telegram API ``ok: false`` responses are encoded in
  ``SendResult(ok=False, error=...)`` rather than raised.

Bot-token redaction (NFR-007 GitHub-Secrets safety): any error string
that ends up in ``SendResult.error`` is sanitized so the bot token —
which appears in the URL path of every Telegram API call — never
leaks into logs or operator alerts when httpx surfaces the URL in
its error message.

Per the u27 single-chokepoint contract, redaction here delegates to
:func:`investo._internal.redaction.redact_text` under the
:data:`RedactionPolicy.STRICT` policy. The chokepoint's ``bot_token``
pattern matches both the URL form
(``https://api.telegram.org/bot<token>/<method>``) — the lookbehind
``(?<![\\d:])`` admits the ``t`` of ``/bot`` — and the bare shape
(``<digits>:<≥20-tail>``) used by hand-crafted log lines. No local
regex is maintained here; the marker emitted is
``[REDACTED_BOT_TOKEN]`` (the chokepoint's named replacement).

The module is internal (leading underscore) and is NOT re-exported
from ``investo.notifier``. It is consumed by ``BriefingPublisher``
(Step 4) and ``OperatorAlerter`` (Step 5).

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C4)
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
        (Step 2)
    u27 QA M1 — single chokepoint enforcement (this module formerly
        carried two local regex literals; folded into the chokepoint).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

import httpx

from investo._internal import retry_budget
from investo._internal.redaction import RedactionPolicy, redact_text
from investo.models import SendResult

_logger = logging.getLogger(__name__)

# u31 Step 1 — bounded retry policy for Telegram dispatch. Telegram's
# rate limiter responds with HTTP 429 + ``Retry-After`` (or
# ``parameters.retry_after`` in the JSON body) when the bot exceeds its
# per-second / per-minute message budget. Transient 5xx and connection
# resets also benefit from a brief wait. We cap retries tightly because
# the briefing publish path runs once per cron and an over-eager retry
# burns the GHA minute budget for no operator value.
_MAX_RETRIES: Final[int] = 3
_BASE_BACKOFF_S: Final[float] = 1.0
_MAX_BACKOFF_S: Final[float] = 2.0
# Hard ceiling on any single ``Retry-After`` honor — Telegram has been
# observed to return very long values (minutes) under bot abuse, but
# the cron run cannot wait that long. Cap, log, and fall through to the
# normal failure branch when exceeded.
_RETRY_AFTER_CEILING_S: Final[float] = 30.0


def _redact_bot_token(text: str) -> str:
    """Redact bot tokens (URL form + bare shape) via the project chokepoint.

    Thin shim over :func:`investo._internal.redaction.redact_text` under
    the :data:`RedactionPolicy.STRICT` policy. Kept as a named function
    (rather than inlined at the two call sites in this module and one
    in :mod:`operator_alerter`) so the surface stays auditable: every
    call site routes through one shim into the chokepoint.

    The chokepoint's ``bot_token`` pattern replaces matches with
    ``[REDACTED_BOT_TOKEN]``; in URL form the surrounding ``/bot`` /
    ``/sendMessage`` path segments are preserved for debuggability.
    """
    return redact_text(text, policy=RedactionPolicy.STRICT)


def telegram_api_url(bot_token: str, method: str = "sendMessage") -> str:
    """Build the canonical Telegram Bot API URL for ``method``."""
    return f"https://api.telegram.org/bot{bot_token}/{method}"


async def send_message(
    client: httpx.AsyncClient,
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str | None = "Markdown",
    disable_web_page_preview: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> SendResult:
    """POST a single ``sendMessage`` call with bounded retry. Non-raising.

    Returns ``SendResult(ok=True, message_id=...)`` on Telegram API
    success. Returns ``SendResult(ok=False, error=str)`` on:

    * ``httpx.TimeoutException`` (timeout reaching api.telegram.org)
    * Any other ``httpx.HTTPError`` (DNS, connection refused, etc.)
    * Non-2xx HTTP status code
    * Telegram API response ``{"ok": false, "description": "..."}``
      (e.g., chat not found, bot blocked, invalid parse_mode)

    The error string in the failure ``SendResult`` is bot-token-
    redacted via :func:`_redact_bot_token`.

    u31 Step 1 — retry policy. Up to :data:`_MAX_RETRIES` extra
    attempts on transient outcomes:

    * HTTP 429 with ``Retry-After`` header or
      ``parameters.retry_after`` JSON field — wait the indicated
      seconds (capped at :data:`_RETRY_AFTER_CEILING_S`).
    * HTTP 5xx — exponential 1s → 2s backoff.
    * ``TimeoutException`` / connection-level ``HTTPError`` — same
      exponential schedule.

    Non-transient failures (4xx other than 429, ``ok: false`` API
    responses) return immediately. ``sleep`` is injectable so tests can
    drive the retry loop without real wall-clock waits.
    """
    url = telegram_api_url(bot_token)
    payload: dict[str, object] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode

    last_attempt: _AttemptOutcome | None = None
    for attempt in range(_MAX_RETRIES + 1):
        if attempt > 0:
            assert last_attempt is not None
            # u31 Step 5 — process-wide retry budget gate. Stop
            # retrying when the global counter is exhausted even if
            # this site's local retry quota still has slack.
            if not retry_budget.allow_retry():
                _logger.info(
                    "[telegram] global retry budget exhausted; stopping after attempt %d",
                    attempt,
                )
                break
            backoff = min(_BASE_BACKOFF_S * (2 ** (attempt - 1)), _MAX_BACKOFF_S)
            wait_s = max(backoff, last_attempt.retry_after_s or 0.0)
            _logger.info(
                "[telegram] retrying after %.2fs (attempt %d/%d)",
                wait_s,
                attempt + 1,
                _MAX_RETRIES + 1,
            )
            await sleep(wait_s)
        last_attempt = await _send_message_once(client, url=url, payload=payload)
        if last_attempt.ok:
            return SendResult(ok=True, message_id=last_attempt.message_id, error=None)
        if not last_attempt.transient:
            break
    assert last_attempt is not None
    return SendResult(
        ok=False, message_id=None, error=last_attempt.error or "telegram dispatch failed"
    )


@dataclass(frozen=True, slots=True)
class _AttemptOutcome:
    """Internal record of one Telegram dispatch attempt."""

    ok: bool
    message_id: int | None
    error: str | None
    transient: bool = False
    retry_after_s: float | None = None


async def _send_message_once(
    client: httpx.AsyncClient,
    *,
    url: str,
    payload: dict[str, object],
) -> _AttemptOutcome:
    """Single dispatch — returns an attempt record (success or typed error)."""
    try:
        response = await client.post(url, json=payload)
    except httpx.TimeoutException as exc:
        return _AttemptOutcome(
            ok=False,
            error=_redact_bot_token(f"timeout: {exc}"),
            message_id=None,
            transient=True,
        )
    except httpx.HTTPError as exc:
        return _AttemptOutcome(
            ok=False,
            error=_redact_bot_token(f"http error: {exc}"),
            message_id=None,
            transient=True,
        )

    status = response.status_code
    if status == 200:
        try:
            body = response.json()
        except ValueError as exc:
            return _AttemptOutcome(
                ok=False,
                error=_redact_bot_token(f"invalid json response: {exc}"),
                message_id=None,
                transient=False,
            )
        if not body.get("ok"):
            description = body.get("description", "(no description)")
            return _AttemptOutcome(
                ok=False,
                error=_redact_bot_token(f"telegram api: {description}"),
                message_id=None,
                transient=False,
            )
        message_id = body.get("result", {}).get("message_id")
        return _AttemptOutcome(ok=True, message_id=message_id, error=None, transient=False)

    transient = status == 429 or 500 <= status < 600
    retry_after = _resolve_retry_after(response) if status == 429 else None
    return _AttemptOutcome(
        ok=False,
        error=_redact_bot_token(f"http status {status}: {response.text[:200]}"),
        message_id=None,
        transient=transient,
        retry_after_s=retry_after,
    )


def _resolve_retry_after(response: httpx.Response) -> float | None:
    """Honor either the HTTP ``Retry-After`` header or the JSON body field.

    Returns the value clamped to :data:`_RETRY_AFTER_CEILING_S`. Returns
    ``None`` when the value is unparsable, non-numeric, or absent — the
    caller falls back to the exponential backoff schedule.
    """
    header_val = response.headers.get("Retry-After")
    if header_val is not None:
        try:
            seconds = float(header_val)
            return min(seconds, _RETRY_AFTER_CEILING_S) if seconds >= 0 else None
        except ValueError:
            pass
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    parameters = body.get("parameters")
    if isinstance(parameters, dict):
        retry_after = parameters.get("retry_after")
        if isinstance(retry_after, (int, float)) and retry_after >= 0:
            return min(float(retry_after), _RETRY_AFTER_CEILING_S)
    return None
