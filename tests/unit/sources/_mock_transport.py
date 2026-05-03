"""Shared MockTransport helpers for source adapter tests."""

from __future__ import annotations

import httpx


def mock_client(
    body: bytes | str,
    *,
    status: int = 200,
    content_type: str = "application/rss+xml",
    captured: list[httpx.Request] | None = None,
) -> httpx.AsyncClient:
    content = body.encode("utf-8") if isinstance(body, str) else body

    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(
            status,
            content=content,
            headers={"content-type": content_type},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
