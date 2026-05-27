"""u79 — grep guard: briefing ticker/text patterns have ONE home.

After u79 the canonical ticker / meaningful-text regexes live only in
:mod:`investo.briefing._text.patterns`. The consuming sites
(``segments``, ``citation_cardinality``, ``pipeline``, ``summary_quality``)
import them; none redeclares the moved ``re.compile`` literal. This test
fails the moment a site reintroduces one of the literals locally, which
is exactly the silent-divergence regression u79 closes.

It also pins that the moved patterns still resolve from the canonical
module (so a careless deletion is caught), and that the two crypto
patterns remain *distinct* (unifying them would be a behavior change).
"""

from __future__ import annotations

import re
from pathlib import Path

from investo.briefing._text import patterns

_SRC = Path(__file__).resolve().parents[3] / "src" / "investo" / "briefing"

# The exact ``re.compile`` literal bodies that u79 centralized. Any file
# other than ``_text/patterns.py`` re-declaring one of these is the
# divergence regression.
_MOVED_LITERALS = (
    r'r"\[(?:\d{6}|[A-Z]{3}\d{3})\]"',
    r'r"\b(?:AAPL|AMZN|GOOGL|META|MSFT|NVDA|SPY|QQQ|TSLA|DIS|CPNG)\b"',
    r'r"\b(?:BTC|ETH|SOL)\b"',
    r'r"\b(BTC|ETH)\b"',
    r'r"[A-Za-z0-9가-힣]"',
)


def test_moved_literals_appear_only_in_patterns_module() -> None:
    patterns_path = _SRC / "_text" / "patterns.py"
    offenders: dict[str, list[str]] = {}
    for path in _SRC.rglob("*.py"):
        if path == patterns_path:
            continue
        text = path.read_text(encoding="utf-8")
        hits = [literal for literal in _MOVED_LITERALS if literal in text]
        if hits:
            offenders[str(path.relative_to(_SRC))] = hits
    assert not offenders, f"moved patterns redeclared outside _text/patterns.py: {offenders}"


def test_patterns_module_still_exports_the_moved_patterns() -> None:
    assert patterns.KOREAN_EXCHANGE_TICKER.pattern == r"\[(?:\d{6}|[A-Z]{3}\d{3})\]"
    assert (
        patterns.US_TICKER.pattern
        == r"\b(?:AAPL|AMZN|GOOGL|META|MSFT|NVDA|SPY|QQQ|TSLA|DIS|CPNG)\b"
    )
    assert patterns.CRYPTO_TICKER.pattern == r"\b(?:BTC|ETH|SOL)\b"
    assert patterns.CRYPTO_TICKER_PAIR.pattern == r"\b(BTC|ETH)\b"
    assert patterns.MEANINGFUL_TEXT.pattern == r"[A-Za-z0-9가-힣]"


def test_crypto_patterns_remain_distinct() -> None:
    # Behavior-preserving guard: the citation counter recognises SOL,
    # segment routing does not. They must NOT be unified.
    assert patterns.CRYPTO_TICKER is not patterns.CRYPTO_TICKER_PAIR
    assert patterns.CRYPTO_TICKER.search("SOL rallies")
    assert patterns.CRYPTO_TICKER_PAIR.search("SOL rallies") is None


def test_consumers_share_the_canonical_objects() -> None:
    # The four sites must reference the *same* compiled objects, proving
    # they delegate rather than carry a private copy.
    from investo.briefing import citation_cardinality, pipeline, segments, summary_quality

    assert segments._KOREAN_EXCHANGE_TICKER is patterns.KOREAN_EXCHANGE_TICKER
    assert segments._US_TICKER is patterns.US_TICKER
    assert segments._CRYPTO_TICKER_RE is patterns.CRYPTO_TICKER_PAIR
    assert citation_cardinality._KOREAN_EXCHANGE_TICKER is patterns.KOREAN_EXCHANGE_TICKER
    assert citation_cardinality._US_TICKER is patterns.US_TICKER
    assert citation_cardinality._CRYPTO_TICKER is patterns.CRYPTO_TICKER
    assert pipeline._MEANINGFUL_TEXT_RE is patterns.MEANINGFUL_TEXT
    assert summary_quality._MEANINGFUL_TEXT_RE is patterns.MEANINGFUL_TEXT


def test_no_stray_compile_of_meaningful_text_anywhere() -> None:
    # Defensive: even a whitespace-variant re-declaration is caught.
    pattern_re = re.compile(r"re\.compile\(\s*r?\"\[A-Za-z0-9가-힣\]\"")
    patterns_path = _SRC / "_text" / "patterns.py"
    for path in _SRC.rglob("*.py"):
        if path == patterns_path:
            continue
        assert not pattern_re.search(path.read_text(encoding="utf-8")), path
