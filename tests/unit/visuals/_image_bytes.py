"""Tiny valid PNG / JPEG byte fixtures for visual asset tests.

The deterministic SVG renderer is dimension-validated by u24, and the
PNG / JPEG validators now require a readable IHDR / SOFn frame. The
8-byte signature plus zero padding used in earlier tests is no longer a
valid image; this helper produces the minimum bytes the validator
accepts (a 256x256 PNG and a 16x16 baseline JPEG).
"""

from __future__ import annotations

import struct
import zlib
from typing import Final


def make_png(width: int = 256, height: int = 256) -> bytes:
    """Return a deterministically encoded minimal PNG of ``width x height``."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    row = b"\x00" + b"\x00\x00\x00" * width
    raw = row * height
    compressed = zlib.compress(raw)
    idat_crc = zlib.crc32(b"IDAT" + compressed)
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND")
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return sig + ihdr + idat + iend


def make_jpeg(width: int = 256, height: int = 256) -> bytes:
    """Return a synthetic JPEG with a valid SOFn frame at ``width x height``.

    The remaining segments are minimal stubs sufficient for the u24
    dimension reader; nothing decodes the entropy data.
    """
    soi = b"\xff\xd8"
    # SOF0 marker: 0xFFC0, length 17, precision 8, height, width, 3 components
    sof = (
        b"\xff\xc0"
        + struct.pack(">H", 17)
        + b"\x08"
        + struct.pack(">H", height)
        + struct.pack(">H", width)
        + b"\x03"
        + b"\x01\x22\x00"
        + b"\x02\x11\x01"
        + b"\x03\x11\x01"
    )
    # COM (comment) segment with padding so the file passes the
    # 100-byte minimum-length check applied by the asset validator.
    pad_len = 200
    com = b"\xff\xfe" + struct.pack(">H", 2 + pad_len) + b"\x00" * pad_len
    eoi = b"\xff\xd9"
    return soi + sof + com + eoi


VALID_PNG_BYTES: Final[bytes] = make_png()
VALID_JPEG_BYTES: Final[bytes] = make_jpeg()


__all__ = ["VALID_JPEG_BYTES", "VALID_PNG_BYTES", "make_jpeg", "make_png"]
