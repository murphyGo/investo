"""u33 Step 4 — free-tier webhook fan-out for watchlist events.

When a publish run completes, the orchestrator MAY broadcast a brief
watchlist-relevance summary to one or more free webhooks (Slack
incoming webhook URLs, Discord channel webhook URLs). The list is
configured via the :data:`WATCHLIST_WEBHOOKS_ENV` environment
variable, parsed as a JSON array of objects::

    [
        {"channel": "slack",   "url": "https://hooks.slack.com/services/..."},
        {"channel": "discord", "url": "https://discord.com/api/webhooks/..."}
    ]

Both kinds accept a plain text body — Slack via the legacy ``text``
field, Discord via the ``content`` field. Email is intentionally not
supported: there is no free, account-less SMTP relay we could rely on
without a paid SaaS.

Network behaviour:

* Best-effort. A 4xx / 5xx / connection error is logged at WARNING
  and DOES NOT raise — webhook delivery is observability, never on
  the critical path.
* No retry-after honor here (Slack / Discord webhook traffic is rare
  and the Telegram rate limiter already handles the high-frequency
  branch via :mod:`investo.notifier._telegram`).

R13 secret hygiene: the webhook URL itself is the secret. We never
log the URL on success, and on failure we redact the URL via the u27
chokepoint before logging.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import httpx

from investo._internal.redaction import RedactionPolicy, redact_text

_logger = logging.getLogger(__name__)

WATCHLIST_WEBHOOKS_ENV: Final[str] = "INVESTO_WATCHLIST_WEBHOOKS"
WebhookChannel = Literal["slack", "discord"]


@dataclass(frozen=True, slots=True)
class WebhookEndpoint:
    """One free-tier webhook destination."""

    channel: WebhookChannel
    url: str


def load_webhook_endpoints(raw: str | None = None) -> tuple[WebhookEndpoint, ...]:
    """Parse :data:`WATCHLIST_WEBHOOKS_ENV` (or ``raw``) into endpoints.

    Returns ``()`` for unset / empty / unparsable values. The parser
    is forgiving: a single malformed entry is dropped (logged at
    WARNING) without rejecting the rest.
    """
    text = raw if raw is not None else os.environ.get(WATCHLIST_WEBHOOKS_ENV, "")
    if not text.strip():
        return ()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        _logger.warning("[webhooks] invalid JSON in %s: %s", WATCHLIST_WEBHOOKS_ENV, exc)
        return ()
    if not isinstance(payload, list):
        _logger.warning(
            "[webhooks] %s must be a JSON list; got %s",
            WATCHLIST_WEBHOOKS_ENV,
            type(payload).__name__,
        )
        return ()
    out: list[WebhookEndpoint] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        channel = entry.get("channel")
        url = entry.get("url")
        if channel not in ("slack", "discord") or not isinstance(url, str) or not url:
            continue
        out.append(WebhookEndpoint(channel=channel, url=url))
    return tuple(out)


async def dispatch_watchlist_alert(
    text: str,
    *,
    http: httpx.AsyncClient,
    endpoints: Sequence[WebhookEndpoint],
) -> int:
    """Best-effort fan-out to ``endpoints``. Returns delivery success count."""
    if not endpoints or not text.strip():
        return 0
    successes = 0
    for endpoint in endpoints:
        try:
            response = await http.post(
                endpoint.url, json=_payload_for_channel(endpoint.channel, text)
            )
        except httpx.HTTPError as exc:
            _logger.warning(
                "[webhooks] %s dispatch failed: %s",
                endpoint.channel,
                redact_text(str(exc), policy=RedactionPolicy.STRICT),
            )
            continue
        if response.status_code >= 400:
            _logger.warning(
                "[webhooks] %s dispatch returned status %d",
                endpoint.channel,
                response.status_code,
            )
            continue
        successes += 1
    return successes


def _payload_for_channel(channel: WebhookChannel, text: str) -> dict[str, str]:
    if channel == "slack":
        return {"text": text}
    return {"content": text}


__all__ = [
    "WATCHLIST_WEBHOOKS_ENV",
    "WebhookChannel",
    "WebhookEndpoint",
    "dispatch_watchlist_alert",
    "load_webhook_endpoints",
]
