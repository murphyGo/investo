"""Shared helpers for u4 notifier tests."""

from __future__ import annotations

import httpx


def mock_client(handler: object) -> httpx.AsyncClient:
    """Build an AsyncClient backed by MockTransport."""
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return httpx.AsyncClient(transport=transport)
