"""HTML sanitization helper for source adapters.

Implements NFR-007 AC-7.2: feed-derived HTML in titles and summaries
MUST be reduced to plain text before constructing
:class:`investo.models.NormalizedItem`. We use ``bleach.clean`` with
``tags=[]`` and ``strip=True`` so every tag is dropped; HTML entities
are then decoded to their literal characters and whitespace runs are
collapsed to single spaces.

Adapters call :func:`strip_html` on every text-bearing field they
extract from a source response. This module is internal to the
sources package — not part of the public re-export surface.
"""

from __future__ import annotations

import html
import re

import bleach

# `\s` matches Unicode whitespace in Python 3 (NBSP U+00A0, ideographic
# space U+3000, etc.) — desirable for CJK feeds where U+3000 appears in
# Korean/Japanese titles and should collapse like ASCII whitespace.
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Strip every HTML tag from ``text`` and return plain text.

    Pipeline:

    1. ``bleach.clean(text, tags=[], strip=True, strip_comments=True)``
       drops every tag (and HTML comment); text content is retained.
    2. :func:`html.unescape` converts entities (``&amp;``, ``&#39;``)
       to their literal characters.
    3. Whitespace runs collapse to a single space; the result is
       stripped at both ends.

    Empty or whitespace-only input returns an empty string. Mixed
    Unicode (Korean + emoji) is preserved.
    """

    if not text:
        return ""
    cleaned = bleach.clean(text, tags=[], strip=True, strip_comments=True)
    decoded = html.unescape(cleaned)
    return _WHITESPACE_RE.sub(" ", decoded).strip()
