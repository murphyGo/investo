"""u79 — canonical briefing ticker / text regex patterns (briefing-internal).

Before u79 the ticker-recognition regexes were defined verbatim in
:mod:`investo.briefing.segments` and :mod:`investo.briefing.citation_cardinality`,
and a ``[A-Za-z0-9가-힣]`` "is there meaningful text" probe was duplicated
between :mod:`investo.briefing.pipeline` and :mod:`investo.briefing.summary_quality`.
They agreed by inspection but a one-sided edit would silently diverge.
This module is the single home so a change is a one-line edit reviewed
once.

Scope note (behavior-preserving): only the patterns that are **byte-for-byte
identical across their consuming sites** are centralized here. The two
crypto-ticker regexes deliberately stay distinct — ``CRYPTO_TICKER``
(``BTC|ETH|SOL``, used by citation cardinality) and ``CRYPTO_TICKER_PAIR``
(``BTC|ETH``, used by segment routing) — because unifying them would
change which items match. They are co-located here so the divergence is
explicit and reviewable, not unified.

This package is briefing-internal; all consumers live under
``investo.briefing`` so there is no module-boundary concern. No ``Ticker``
value object is introduced (out of scope for Wave 14 — see the u79 plan
Non-Goals); this is regex centralization only.
"""

from __future__ import annotations

import re
from typing import Final

# Korean exchange ticker token: a bracketed 6-digit KRX code or the
# 3-letter + 3-digit form (e.g. ``[005930]`` / ``[ABC123]``). Identical
# in ``segments`` and ``citation_cardinality`` before u79.
KOREAN_EXCHANGE_TICKER: Final[re.Pattern[str]] = re.compile(r"\[(?:\d{6}|[A-Z]{3}\d{3})\]")

# Curated US ticker word list. Identical in ``segments`` and
# ``citation_cardinality`` before u79.
US_TICKER: Final[re.Pattern[str]] = re.compile(
    r"\b(?:AAPL|AMZN|GOOGL|META|MSFT|NVDA|SPY|QQQ|TSLA|DIS|CPNG)\b"
)

# Crypto ticker word list used by the citation-cardinality claim counter
# (BTC / ETH / SOL).
CRYPTO_TICKER: Final[re.Pattern[str]] = re.compile(r"\b(?:BTC|ETH|SOL)\b")

# Crypto ticker pair used by segment routing (BTC / ETH only, capturing
# group preserved). NOT the same set as ``CRYPTO_TICKER`` — see module
# docstring. Distinct on purpose.
CRYPTO_TICKER_PAIR: Final[re.Pattern[str]] = re.compile(r"\b(BTC|ETH)\b")

# "Is there any meaningful (alnum / Hangul) character?" probe. Identical
# literal in ``pipeline`` and ``summary_quality`` before u79.
MEANINGFUL_TEXT: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9가-힣]")

__all__ = [
    "CRYPTO_TICKER",
    "CRYPTO_TICKER_PAIR",
    "KOREAN_EXCHANGE_TICKER",
    "MEANINGFUL_TEXT",
    "US_TICKER",
]
