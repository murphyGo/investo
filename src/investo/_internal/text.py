"""Text helpers shared across internal unit boundaries."""

from __future__ import annotations

from typing import Final

# Shared cap for stderr excerpts included in operator-visible errors.
STDERR_BYTE_CAP: Final[int] = 1024


def truncate_stderr(value: str | None) -> str | None:
    """Truncate ``value`` to ``STDERR_BYTE_CAP`` UTF-8 bytes.

    Returns ``None`` for ``None`` input. For non-None strings, the cap
    is enforced on encoded UTF-8 bytes, not code points. A cut that
    lands mid-codepoint is recovered by decoding with ``errors="ignore"``,
    dropping the partial sequence cleanly.
    """

    if value is None:
        return None
    encoded = value.encode("utf-8")
    if len(encoded) <= STDERR_BYTE_CAP:
        return value
    return encoded[:STDERR_BYTE_CAP].decode("utf-8", errors="ignore")
