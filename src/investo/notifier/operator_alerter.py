"""Operator-only Telegram 1:1 chat dispatcher (FR-007, US-007).

``OperatorAlerter.alert`` posts a formatted ``FailureContext`` to the
operator's 1:1 chat. Same non-raising contract as
:class:`BriefingPublisher`: HTTP / API / timeout failures land in
:class:`SendResult.ok=False` with bot-token-redacted error strings.

CLAUDE.md project rule #5: the operator chat ``operator_chat_id``
MUST be disjoint from the public-channel ``channel_id`` used by
:class:`BriefingPublisher`. The orchestrator (u5) wires both from
disjoint environment variables and is responsible for the
construction-time disjointness assertion.

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C4)
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
        (Step 5)
"""

from __future__ import annotations

import httpx

from investo.models import FailureContext, SendResult
from investo.notifier._telegram import _redact_bot_token, send_message
from investo.notifier.summary import DEFAULT_MAX_UNITS, _utf16_truncate, _utf16_units


def _format_alert_text(failure: FailureContext) -> str:
    """Format the operator alert text from the failure context.

    Layout::

        ⚠️ Pipeline failure: {stage}

        {error_type}: {error_message}

        Occurred: {occurred_at.isoformat()}

        ```{traceback_excerpt}```   (only when traceback_excerpt is set)
    """
    header = f"⚠️ Pipeline failure: {failure.stage}\n\n"
    err_line = f"{failure.error_type}: {failure.error_message}\n\n"
    occurred = f"Occurred: {failure.occurred_at.isoformat()}"

    if failure.traceback_excerpt is not None:
        traceback_block = f"\n\n```\n{failure.traceback_excerpt}\n```"
    else:
        traceback_block = ""

    return header + err_line + occurred + traceback_block


class OperatorAlerter:
    """Operator-only 1:1 chat dispatcher (FR-007).

    Same non-raising contract as :class:`BriefingPublisher`. Alert
    text is bot-token-redacted defensively (the ``error_message``
    field of a ``FailureContext`` could embed the token if a poorly
    sanitized log line was passed through).
    """

    def __init__(
        self,
        *,
        bot_token: str,
        operator_chat_id: str,
        http: httpx.AsyncClient | None = None,
        dry_run: bool = False,
    ) -> None:
        self._bot_token = bot_token
        self._operator_chat_id = operator_chat_id
        self._http = http
        self._dry_run = dry_run

    async def alert(self, failure: FailureContext) -> SendResult:
        """Post the formatted failure alert to the operator chat.

        The full alert text is bot-token-redacted (defense in depth
        against a ``FailureContext.error_message`` that accidentally
        contains the token) and truncated to fit under the 4096-unit
        Telegram cap (the ``traceback_excerpt`` model already caps
        at 2000 chars but the surrounding error_message + error_type
        are unbounded).

        Dry-run (u31 Step 2) — when constructed with ``dry_run=True``,
        returns ``SendResult(ok=True, ...)`` immediately without I/O.
        Operator boot alerts during dry-run are silenced so the
        dry-run does not page the operator on every config-error
        rehearsal.
        """
        if self._dry_run:
            return SendResult(ok=True, message_id=None, error=None)
        text = _format_alert_text(failure)
        text = _redact_bot_token(text)
        if _utf16_units(text) > DEFAULT_MAX_UNITS:
            text = _utf16_truncate(text, DEFAULT_MAX_UNITS - 1) + "…"

        if self._http is None:
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await self._dispatch(client, text)
        return await self._dispatch(self._http, text)

    async def _dispatch(self, client: httpx.AsyncClient, text: str) -> SendResult:
        return await send_message(
            client,
            bot_token=self._bot_token,
            chat_id=self._operator_chat_id,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )


__all__ = ["OperatorAlerter"]
