"""Public Telegram channel dispatcher (FR-004, US-004).

``BriefingPublisher.send`` posts a :class:`BriefingNotification` to
the channel ``chat_id`` configured at construction time. Non-raising:
HTTP failures, timeouts, and Telegram API ``ok: false`` responses
are encoded in :class:`SendResult.ok=False` with bot-token-redacted
error strings.

Construction is **kwargs-only** so the orchestrator (u5) cannot
positionally swap ``channel_id`` with the operator chat ID for
:class:`OperatorAlerter` (CLAUDE.md project rule #5: the public
briefing channel and the operator 1:1 chat MUST NOT share a
``chat_id``).

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C4)
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
        (Step 4)
"""

from __future__ import annotations

import httpx

from investo.models import BriefingNotification, SendResult
from investo.notifier._telegram import send_message


def _is_markdown_parse_error(result: SendResult) -> bool:
    if result.ok or result.error is None:
        return False
    return "can't parse entities" in result.error.lower()


class BriefingPublisher:
    """Public Telegram channel/group dispatcher (FR-004).

    ``send_message`` is non-raising: any HTTP error, timeout, or
    Telegram API rejection lands in ``SendResult(ok=False, ...)``
    rather than propagating up.
    """

    def __init__(
        self,
        *,
        bot_token: str,
        channel_id: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._channel_id = channel_id
        self._http = http

    async def send(self, payload: BriefingNotification) -> SendResult:
        """Post the briefing summary to the configured channel.

        ``payload.summary_text`` is the message body; ``payload
        .site_url`` is reflected in the Telegram link preview when
        embedded in the body. The model already enforces the 4096
        UTF-16-unit cap, so no additional truncation is needed here.

        When ``self._http`` is ``None`` (production), creates an
        ``httpx.AsyncClient(timeout=30.0)`` for the duration of the
        call. Tests inject a pre-built client (typically with
        ``MockTransport``) to avoid network I/O.
        """
        if self._http is None:
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await self._dispatch(client, payload)
        return await self._dispatch(self._http, payload)

    async def _dispatch(
        self,
        client: httpx.AsyncClient,
        payload: BriefingNotification,
    ) -> SendResult:
        result = await send_message(
            client,
            bot_token=self._bot_token,
            chat_id=self._channel_id,
            text=payload.summary_text,
            parse_mode="Markdown",
            disable_web_page_preview=False,
        )
        if not _is_markdown_parse_error(result):
            return result

        return await send_message(
            client,
            bot_token=self._bot_token,
            chat_id=self._channel_id,
            text=payload.summary_text,
            parse_mode=None,
            disable_web_page_preview=False,
        )


__all__ = ["BriefingPublisher"]
