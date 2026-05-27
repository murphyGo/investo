"""§⑥ watch-point audit passes (action-bullet ratio + actionability).

Move-only extraction from the pre-split ``reader_format`` module (u81).
"""

from __future__ import annotations

import re
from typing import Final

from investo.publisher.reader_format._constants import (
    _BULLET_RE,
    _SECTION_HEADER_RE,
    _logger,
)

# Korean "observation" sentence endings — the LLM's default mode that
# u51 wants to *flag* (not block). All five are present in the 2026-05-11
# audit ("여부", "할 필요가 있다", "관건이다", "주목할 필요"...).
_ACTION_SUFFIX_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p)
    for p in (
        r"여부[\.\s]*$",
        r"필요가 있다[\.\s]*$",
        r"관건이다[\.\s]*$",
        r"주목할 필요[가\s]*있다[\.\s]*$",
        r"확인할 필요[가\s]*있다[\.\s]*$",
    )
)

ACTION_RATIO_THRESHOLD: Final[float] = 0.40

_WATCHPOINT_SOURCE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:소스|출처|확인\s?소스|근거|source|FRED|Yahoo|Stooq|KRX|DART|CoinGecko|Binance)",
    re.IGNORECASE,
)
_WATCHPOINT_TRIGGER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:임계|기준|상회|하회|돌파|이탈|확대|축소|발표|공개|마감|수익률|금리|거래량|%|\$|\d)"
)
_WATCHPOINT_IMPLICATION_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:시사|의미|영향|압력|부담|완화|확인|재평가|변동성|리스크)"
)


def check_action_bullet_ratio(
    text: str,
    *,
    section_marker: str = "⑥",
    segment: str | None = None,
) -> tuple[float, tuple[str, ...]]:
    """Compute the fraction of §⑥ bullets ending in observation suffixes.

    Returns ``(ratio, violating_bullets)``. ``ratio`` is in ``[0.0, 1.0]``
    — when no §⑥ bullets exist the ratio is ``0.0`` (vacuously clean).
    When ``ratio`` exceeds :data:`ACTION_RATIO_THRESHOLD` we WARN-log,
    but the function is *non-blocking* — generation variance makes a
    hard reject inappropriate (some days the watch-list is genuinely
    observation-shaped).
    """
    section_body = _extract_section_body(text, section_marker)
    if section_body is None:
        return 0.0, ()
    bullets = [match.group(1).strip() for match in _BULLET_RE.finditer(section_body)]
    if not bullets:
        return 0.0, ()
    violations = tuple(b for b in bullets if _ends_with_observation(b))
    ratio = len(violations) / len(bullets)
    if ratio > ACTION_RATIO_THRESHOLD:
        _logger.warning(
            "reader_format.action_ratio_high",
            extra={
                "segment": segment,
                "ratio": round(ratio, 3),
                "count": len(violations),
                "total": len(bullets),
            },
        )
    return ratio, violations


def check_watchpoint_actionability(
    text: str,
    *,
    section_marker: str = "⑥",
    segment: str | None = None,
) -> tuple[str, ...]:
    """Return §⑥ bullets that lack source/trigger/implication structure."""
    section_body = _extract_section_body(text, section_marker)
    if section_body is None:
        return ()
    bullets = [match.group(1).strip() for match in _BULLET_RE.finditer(section_body)]
    if not bullets:
        return ()
    violations = tuple(
        bullet
        for bullet in bullets
        if "데이터 부족" not in bullet
        and not (
            _WATCHPOINT_SOURCE_RE.search(bullet)
            and _WATCHPOINT_TRIGGER_RE.search(bullet)
            and _WATCHPOINT_IMPLICATION_RE.search(bullet)
        )
    )
    if violations:
        _logger.warning(
            "reader_format.watchpoint_actionability_low",
            extra={
                "segment": segment,
                "count": len(violations),
                "total": len(bullets),
            },
        )
    return violations


def _extract_section_body(text: str, marker: str) -> str | None:
    headers = list(_SECTION_HEADER_RE.finditer(text))
    for idx, match in enumerate(headers):
        if marker in match.group("header"):
            start = match.end()
            end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
            return text[start:end]
    return None


def _ends_with_observation(bullet: str) -> bool:
    # Strip trailing whitespace + a single trailing punctuation char.
    stripped = bullet.rstrip()
    return any(p.search(stripped) for p in _ACTION_SUFFIX_PATTERNS)
