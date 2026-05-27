"""Shared Telegram dispatch with markdown→plain fallback (u80).

This module is a **code-reuse helper, not a Liskov base class.**
``BriefingPublisher.send(BriefingNotification)`` and
``OperatorAlerter.alert(FailureContext)`` have distinct public
surfaces — nobody holds a common supertype and calls a polymorphic
method — so the two clients are *not* substitutable. Folding the
duplicated "try ``parse_mode=Markdown``, on a parse error retry with
``parse_mode=None``" loop into a shared base class would imply an
is-a hierarchy that does not exist (and would tempt a shared/default
``chat_id`` field, which R5 forbids). Instead both clients *compose*
the free function :func:`dispatch`, each passing its own chat/channel
id explicitly. No shared or default chat id exists anywhere in this
module (review 2026-05-28, u80 Step 2; guide §3 LSP).

:func:`dispatch` OWNS ``parse_mode``: it sends Markdown first, then
plain text on a parse error. ``parse_mode`` is therefore excluded
from the ``**send_kwargs`` passthrough — a caller cannot inject or
override it and re-leak the markdown→plain quirk (guide §9.4
minimize-leak-surface). Passing ``parse_mode`` raises ``TypeError``.

The raw HTTP send + retry-budget integration stays in
:func:`investo.notifier._telegram.send_message`; this helper *wraps*
it, it does not replace it.
"""

from __future__ import annotations

import httpx

from investo.models import SendResult
from investo.notifier._telegram import send_message


def _is_markdown_parse_error(result: SendResult) -> bool:
    """Single definition of the markdown-parse-error predicate (AC-80.2).

    Telegram rejects malformed Markdown entities with an ``ok: false``
    response whose description contains ``can't parse entities``. When
    we see that, the dispatcher retries the same text with
    ``parse_mode=None`` (plain text) so the message still lands.
    """
    if result.ok or result.error is None:
        return False
    return "can't parse entities" in result.error.lower()


async def dispatch(
    client: httpx.AsyncClient,
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    plain_text: str | None = None,
    **send_kwargs: object,
) -> SendResult:
    """Send ``text`` as Markdown; on a parse error retry as plain text.

    Each caller passes its OWN ``chat_id`` — there is no shared or
    default value (R5 channel separation is preserved structurally).

    ``parse_mode`` is owned by this function and MUST NOT appear in
    ``send_kwargs`` (it would let a caller re-leak the markdown→plain
    quirk); passing it raises ``TypeError``. Other ``send_message``
    kwargs (e.g. ``disable_web_page_preview``) pass through unchanged
    and identically across both attempts.

    ``plain_text`` is the body used on the fallback attempt. When
    ``None`` (the operator-alert case) the same ``text`` is resent
    with Markdown disabled; the briefing publisher passes a
    markdown-stripped variant.
    """
    if "parse_mode" in send_kwargs:
        raise TypeError(
            "dispatch() owns parse_mode; it must not be passed via send_kwargs "
            "(the markdown→plain fallback is internal to dispatch)"
        )

    result = await send_message(
        client,
        bot_token=bot_token,
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        **send_kwargs,  # type: ignore[arg-type]
    )
    if not _is_markdown_parse_error(result):
        return result

    return await send_message(
        client,
        bot_token=bot_token,
        chat_id=chat_id,
        text=text if plain_text is None else plain_text,
        parse_mode=None,
        **send_kwargs,  # type: ignore[arg-type]
    )


__all__ = ["dispatch"]
