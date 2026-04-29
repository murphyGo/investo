"""Notifier (u4) — Telegram dispatcher (BriefingPublisher + OperatorAlerter).

US-004 (공개 채널) + US-007 (운영자 1:1 chat).

Public surface for u5 orchestrator:

* :class:`BriefingPublisher` — public-channel sender
  (FR-004). Constructed with the public ``channel_id``.
* :class:`OperatorAlerter` — operator 1:1 chat sender (FR-007).
  Constructed with the disjoint ``operator_chat_id``.
* :func:`build_summary` — helper that composes the public-channel
  preview text from a :class:`Briefing` + site URL with UTF-16-aware
  truncation.

Both dispatcher classes use **kwargs-only** construction so callers
(u5 orchestrator) cannot positionally swap the channel and operator
chat IDs. CLAUDE.md project rule #5: the public-channel
``channel_id`` and the operator ``operator_chat_id`` MUST be disjoint
— enforced at construction time by the orchestrator from disjoint
environment variables (``TELEGRAM_BRIEFING_CHANNEL_ID`` vs
``TELEGRAM_OPERATOR_CHAT_ID``).

Both dispatchers follow a non-raising contract: HTTP failures,
Telegram API errors, and timeouts are encoded in
:class:`SendResult.ok=False` with sanitized error messages (bot
tokens redacted from any URL leakage or bare-shape leakage).

**Production tip for u5 orchestrator**: pass a *shared*
``httpx.AsyncClient`` to both classes' ``http=`` parameter to avoid
constructing a fresh client (and a fresh TLS handshake) on every
publish + alert call. The classes accept ``http=None`` for tests
and one-shot use; production should inject a single client
constructed at orchestrator startup.

The internal HTTP helper :mod:`investo.notifier._telegram` is NOT
re-exported — it's a u4-internal implementation detail.

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C4)
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
"""

from investo.notifier.briefing_publisher import BriefingPublisher
from investo.notifier.operator_alerter import OperatorAlerter
from investo.notifier.summary import build_summary

__all__ = [
    "BriefingPublisher",
    "OperatorAlerter",
    "build_summary",
]
