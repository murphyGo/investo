"""Time-state regex catalogue (u57).

Maps a Korean-language source title to one of six time-state labels:

* ``pre-market`` — 개장 전 / 장 전 / 프리마켓
* ``open`` — 출발 (출발 후 등락) / 개장 직후
* ``intraday`` — 장중 (현재 코드는 ``open`` / ``close`` 이외 명시 매치 없음 → ``None``)
* ``close`` — 마감 / 장 마감 / 종가
* ``post-close`` — 시간 외 / 애프터마켓 / 장 후
* ``scheduled`` — 예정 / 전망 / 발표 예정

Pure module — no I/O, no logger, no global state. ``detect_time_state``
is deterministic and idempotent (NFR-003).

Conflict resolution
-------------------

A single title can match multiple patterns (e.g. ``"상승 출발 후 하락
마감"`` matches both ``open`` and ``close``). The final state is the
*factually latest* one — ``close`` wins over ``open`` etc. The priority
order is exposed as :data:`TIME_STATE_PRIORITY`.

Forbidden
---------

* Calling :func:`datetime.now` — labels are derived from the title text
  alone so the function is replay-safe across reruns.
* Importing anything from :mod:`investo.sources` /
  :mod:`investo.orchestrator` — this module is foundation-level.

References
----------

* u57 plan Step 1 — regex catalogue.
* u57 DoD — "Time-state label … derived deterministically from source
  title regex; ambiguous cases left to LLM in-context resolution".
"""

from __future__ import annotations

import re
from typing import Final

from investo.models.time_state import TimeState

# Priority — when multiple regex patterns match the same title the
# label with the highest priority value wins. ``close`` is higher than
# ``open`` because ``"상승 출발 후 하락 마감"`` describes the *final*
# state (close), not the opening.
TIME_STATE_PRIORITY: Final[dict[TimeState, int]] = {
    "scheduled": 0,
    "pre-market": 1,
    "open": 2,
    "intraday": 3,
    "post-close": 4,
    "close": 5,
}


# Patterns are intentionally bilingual-aware: each Korean phrase admits
# an optional space (``\s?``) because feed publishers wobble between
# ``"장 마감"`` and ``"장마감"``. ASCII alternatives (``pre-market``)
# are accepted for English-language headlines that survive
# normalisation.
TIME_STATE_PATTERNS: Final[dict[TimeState, list[re.Pattern[str]]]] = {
    "pre-market": [
        re.compile(r"(개장\s?전|장\s?전|프리마켓|pre-?market)", re.IGNORECASE),
    ],
    "open": [
        # ``상승 출발`` / ``하락 출발`` / ``2% 상승 출발`` / ``2.5%
        # 하락 출발`` — bare ``개장`` matches only when *not* followed
        # by ``전`` (to avoid clashing with ``pre-market``).
        re.compile(
            r"(\d+(?:\.\d+)?%?\s?(상승|하락)\s?출발|상승\s?출발|하락\s?출발|개장(?!\s?전))",
        ),
    ],
    "close": [
        re.compile(r"(마감|장\s?마감|종가)"),
    ],
    "post-close": [
        re.compile(r"(시간\s?외|애프터마켓|장\s?후|after-?hours)", re.IGNORECASE),
    ],
    "scheduled": [
        re.compile(r"(예정|전망|발표\s?예정|will\s+(announce|release))", re.IGNORECASE),
    ],
}


def detect_time_state(title: str) -> TimeState | None:
    """Return the highest-priority :data:`TimeState` matching ``title``.

    Empty / whitespace-only / ``None``-shaped strings → ``None``.
    No match → ``None`` (the caller treats this as "ambiguous, defer
    to LLM in-context disambiguation").
    """
    if not title or not title.strip():
        return None
    matches: list[TimeState] = []
    for state, patterns in TIME_STATE_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(title):
                matches.append(state)
                break
    if not matches:
        return None
    # Highest priority wins.
    return max(matches, key=TIME_STATE_PRIORITY.__getitem__)


__all__ = [
    "TIME_STATE_PATTERNS",
    "TIME_STATE_PRIORITY",
    "TimeState",
    "detect_time_state",
]
