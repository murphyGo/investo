"""Atomic filesystem write primitives shared across publish/visual layers.

Both ``publisher`` and ``visuals`` reimplemented the same tmp-sibling +
``os.replace`` dance in eight call sites (writer / site_index /
weekly_digest / chart_sidecar / visuals.assets / visuals.og_card). This
module is the single home so a SIGINT-safety or encoding fix lands once.

The API is split by payload kind rather than a ``str | bytes`` union:
:func:`write_atomic` always encodes UTF-8 text, :func:`write_atomic_bytes`
writes verbatim bytes. Splitting keeps each signature honest under
``mypy --strict`` and avoids leaking the "str ⇒ utf-8 / bytes ⇒ verbatim"
contract into every caller.

Leak boundaries the helper cannot hide (state them, do not pretend):

* **Atomic only within a single filesystem.** The rename uses
  :func:`os.replace`, which is atomic only when ``tmp`` and the
  destination live on the same device. A cross-device move raises
  ``OSError`` (``EXDEV``); this helper does not paper over that.
* **No ``fsync`` durability guarantee.** The bytes are flushed by the
  ``with`` block close but not ``fsync``-ed, so a power loss immediately
  after return may lose the data even though the rename "succeeded".
  Callers needing crash-durability must add their own ``fsync``.

Both helpers create ``path.parent`` (``parents=True, exist_ok=True``)
and never leave the ``<path>.tmp`` sibling behind on the success path.
``OSError`` propagates unchanged to the caller (callers map it to their
own domain error as before).
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["write_atomic", "write_atomic_bytes"]


def write_atomic(path: Path, text: str) -> None:
    """Atomically write ``text`` (UTF-8) to ``path``.

    Writes to a ``<path>.tmp`` sibling then :func:`os.replace`-renames it
    onto ``path``, so a crash mid-write never leaves a half-written file
    at the destination. See the module docstring for the atomicity and
    durability leak boundaries.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def write_atomic_bytes(path: Path, data: bytes) -> None:
    """Atomically write raw ``data`` bytes to ``path``.

    Byte-for-byte counterpart of :func:`write_atomic`; see the module
    docstring for the atomicity and durability leak boundaries.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)
