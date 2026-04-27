"""Shared retry/backoff helper for source adapters.

Implements the policy from
``aidlc-docs/construction/u1-sources/functional-design/business-rules.md``
R4 (timeout/retry), R5 (Retry-After), R6 (failure-isolation contract via
:class:`SourceFetchError`), and the NFR ACs:

* AC-1.2 — 60-s outer wall-clock cap
* AC-6.3 — pure :func:`compute_sleep` schedule, bounded ``0 <= sleep <= 30``
* AC-7.1 — 5 MB response body cap (post-hoc check; v1 does not stream)

This module is internal — adapters consume it via the package, not
directly. :class:`SourceFetchError` is re-exported here for backward
compatibility with existing imports; its canonical home is
:mod:`investo.sources.protocol` (Step 5 relocation).
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from investo.sources.protocol import SourceFetchError

__all__ = [
    "DEFAULT_CONFIG",
    "RetryConfig",
    "SourceFetchError",
    "compute_sleep",
    "retry_get",
]

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_RETRIES = 2
_DEFAULT_BACKOFFS: tuple[float, ...] = (1.0, 2.0)
_DEFAULT_TOTAL_BUDGET_S = 60.0
_DEFAULT_MAX_RETRY_AFTER_S = 30.0
_DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Knobs for :func:`retry_get` and :func:`compute_sleep`.

    Defaults match FD R4 / NFR AC-1.2 / AC-6.3 / AC-7.1. Adapters that
    need different knobs construct their own :class:`RetryConfig` and
    pass it in; they MUST NOT redefine the loop body.

    ``backoffs`` must have at least ``retries`` entries — the i-th retry
    (1-indexed) sleeps ``backoffs[i-1]`` seconds when no
    ``Retry-After`` header overrides it.
    """

    timeout_s: float = _DEFAULT_TIMEOUT_S
    retries: int = _DEFAULT_RETRIES
    backoffs: tuple[float, ...] = _DEFAULT_BACKOFFS
    total_budget_s: float = _DEFAULT_TOTAL_BUDGET_S
    max_retry_after_s: float = _DEFAULT_MAX_RETRY_AFTER_S
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if self.retries < 0:
            raise ValueError("retries must be non-negative")
        if len(self.backoffs) < self.retries:
            raise ValueError(f"backoffs ({len(self.backoffs)}) must cover retries ({self.retries})")
        if any(b < 0 for b in self.backoffs):
            raise ValueError("backoffs must be non-negative")
        if self.total_budget_s <= 0:
            raise ValueError("total_budget_s must be positive")
        if self.max_retry_after_s < 0:
            raise ValueError("max_retry_after_s must be non-negative")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")


DEFAULT_CONFIG = RetryConfig()


def _parse_retry_after(header: str | None) -> float | None:
    """Parse RFC 7231 ``Retry-After`` (delta-seconds OR HTTP-date).

    Returns ``None`` if absent or unparseable. Negative or past values
    are clamped to 0.0 (i.e. "retry immediately").
    """

    if header is None:
        return None
    text = header.strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        pass
    else:
        # Reject NaN / +-inf — `float("NaN")` succeeds but a NaN bound
        # would silently bypass `compute_sleep`'s [0, max_retry_after_s]
        # invariant (any comparison with NaN returns False).
        if not math.isfinite(seconds):
            return None
        return max(seconds, 0.0)
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return max((dt - datetime.now(UTC)).total_seconds(), 0.0)


def compute_sleep(
    attempt: int,
    retry_after_header: str | None,
    config: RetryConfig = DEFAULT_CONFIG,
) -> float:
    """Pure: how long to sleep before retry number ``attempt`` (1-indexed).

    Precedence:

    1. If ``retry_after_header`` parses to a non-negative value, use
       ``min(value, config.max_retry_after_s)``.
    2. Otherwise, fall back to ``config.backoffs[attempt - 1]``.
    3. If ``attempt`` is out of range for ``backoffs`` (≤ 0 or beyond
       the schedule), return ``0.0``.

    Output is bounded ``0.0 <= sleep <= config.max_retry_after_s`` so
    long as ``config.backoffs`` are themselves within that bound.
    """

    parsed = _parse_retry_after(retry_after_header)
    if parsed is not None:
        return min(parsed, config.max_retry_after_s)
    if attempt < 1 or attempt > len(config.backoffs):
        return 0.0
    return config.backoffs[attempt - 1]


def _is_retryable_status(status: int) -> bool:
    return status >= 500 or status == 429


_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


async def retry_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    source_name: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    config: RetryConfig = DEFAULT_CONFIG,
) -> httpx.Response:
    """Run a GET under the unit-wide retry / backoff / budget contract.

    Surface differs slightly from the Step 3 plan (``request_kwargs``
    dict) in favor of explicit ``url`` / ``headers`` / ``params`` for
    mypy strict ergonomics — the FOMC adapter (Step 8) only needs these
    three.

    Raises:
        SourceFetchError: when retries are exhausted (transient=True),
            the status is 4xx-not-429 (transient=False), the body
            exceeds ``config.max_response_bytes`` (transient=False),
            an httpx error is non-retryable (transient=False), or the
            outer wall-clock budget is hit (transient=True).
    """

    try:
        return await asyncio.wait_for(
            _retry_get_inner(
                client,
                url,
                source_name=source_name,
                headers=headers,
                params=params,
                config=config,
            ),
            timeout=config.total_budget_s,
        )
    except TimeoutError as exc:
        # asyncio.wait_for raises asyncio.TimeoutError, which in 3.11+
        # is an alias for the builtin TimeoutError.
        raise SourceFetchError(
            source_name=source_name,
            message=f"exceeded {config.total_budget_s:g}s total budget",
            transient=True,
            cause=exc,
        ) from exc


async def _retry_get_inner(
    client: httpx.AsyncClient,
    url: str,
    *,
    source_name: str,
    headers: dict[str, str] | None,
    params: dict[str, str] | None,
    config: RetryConfig,
) -> httpx.Response:
    for attempt_idx in range(config.retries + 1):
        # attempt_idx 0 = first try; 1, 2 = retries
        try:
            response = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=config.timeout_s,
            )
        except _RETRYABLE_EXCEPTIONS as exc:
            if attempt_idx == config.retries:
                raise SourceFetchError(
                    source_name=source_name,
                    message=f"network error after {attempt_idx + 1} attempts: {exc}",
                    transient=True,
                    cause=exc,
                ) from exc
            await asyncio.sleep(compute_sleep(attempt_idx + 1, None, config))
            continue
        except httpx.HTTPError as exc:
            # Non-retryable httpx error (e.g. UnsupportedProtocol).
            raise SourceFetchError(
                source_name=source_name,
                message=f"HTTP error: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        status = response.status_code
        if status < 400:
            if len(response.content) > config.max_response_bytes:
                raise SourceFetchError(
                    source_name=source_name,
                    message=(
                        f"response body {len(response.content)} bytes exceeds "
                        f"{config.max_response_bytes} cap"
                    ),
                    transient=False,
                )
            return response
        if _is_retryable_status(status):
            if attempt_idx == config.retries:
                raise SourceFetchError(
                    source_name=source_name,
                    message=f"status {status} after {attempt_idx + 1} attempts",
                    transient=True,
                )
            retry_after = response.headers.get("Retry-After")
            await asyncio.sleep(compute_sleep(attempt_idx + 1, retry_after, config))
            continue
        # 4xx not 429 → terminal.
        raise SourceFetchError(
            source_name=source_name,
            message=f"status {status} (terminal)",
            transient=False,
        )

    raise AssertionError("retry loop must return or raise")  # pragma: no cover
