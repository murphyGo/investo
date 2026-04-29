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

The module is internal (leading underscore) and is NOT re-exported
from ``investo.notifier``. It is consumed by ``BriefingPublisher``
(Step 4) and ``OperatorAlerter`` (Step 5).

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C4)
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
        (Step 2)
"""

from __future__ import annotations

import re

import httpx

from investo.models import SendResult

# Matches ``/bot{token}/`` in any URL or error message. The token can
# contain digits, colons, letters, underscores, and dashes; it ends
# at the next slash or end-of-string. Replacing with
# ``/bot[REDACTED]/`` keeps the URL shape recognizable for debugging
# while removing the secret.
_BOT_TOKEN_RE = re.compile(r"/bot[^/\s'\"]+")


def _redact_bot_token(text: str) -> str:
    """Replace ``/bot<token>`` with ``/bot[REDACTED]`` in ``text``."""
    return _BOT_TOKEN_RE.sub("/bot[REDACTED]", text)


def telegram_api_url(bot_token: str, method: str = "sendMessage") -> str:
    """Build the canonical Telegram Bot API URL for ``method``."""
    return f"https://api.telegram.org/bot{bot_token}/{method}"


async def send_message(
    client: httpx.AsyncClient,
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "Markdown",
    disable_web_page_preview: bool = False,
) -> SendResult:
    """POST a single ``sendMessage`` call. Non-raising.

    Returns ``SendResult(ok=True, message_id=...)`` on Telegram API
    success. Returns ``SendResult(ok=False, error=str)`` on:

    * ``httpx.TimeoutException`` (timeout reaching api.telegram.org)
    * Any other ``httpx.HTTPError`` (DNS, connection refused, etc.)
    * Non-2xx HTTP status code
    * Telegram API response ``{"ok": false, "description": "..."}``
      (e.g., chat not found, bot blocked, invalid parse_mode)

    The error string in the failure ``SendResult`` is bot-token-
    redacted via :func:`_redact_bot_token`.
    """
    url = telegram_api_url(bot_token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    try:
        response = await client.post(url, json=payload)
    except httpx.TimeoutException as exc:
        return SendResult(
            ok=False,
            error=_redact_bot_token(f"timeout: {exc}"),
            message_id=None,
        )
    except httpx.HTTPError as exc:
        return SendResult(
            ok=False,
            error=_redact_bot_token(f"http error: {exc}"),
            message_id=None,
        )

    if response.status_code != 200:
        return SendResult(
            ok=False,
            error=_redact_bot_token(f"http status {response.status_code}: {response.text[:200]}"),
            message_id=None,
        )

    try:
        body = response.json()
    except ValueError as exc:
        return SendResult(
            ok=False,
            error=_redact_bot_token(f"invalid json response: {exc}"),
            message_id=None,
        )

    if not body.get("ok"):
        description = body.get("description", "(no description)")
        return SendResult(
            ok=False,
            error=_redact_bot_token(f"telegram api: {description}"),
            message_id=None,
        )

    message_id = body.get("result", {}).get("message_id")
    return SendResult(ok=True, message_id=message_id, error=None)
