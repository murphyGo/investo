"""u72 — render §⑥ 오늘의 관전 포인트 as a bounded observational matrix.

Problem (2026-05-24 ten-subagent review): even after u64 added watchpoint
actionability diagnostics, §⑥ still reads like a list of generic monitoring
verbs (``관찰`` / ``확인`` / ``점검`` / ``비교``). A reader cannot tell which
signal matters, what the current observed state is, what would flip it
bullish or bearish, how confident the system is, or what it implies for the
section's watchlist context.

u72 converts the *already-generated* §⑥ bullets into a standard six-column
matrix. It is **not** a watchlist matcher rewrite and **not** a
recommendation engine:

  | 관찰 신호 | 현재 | 상방 확인 조건 | 하방 확인 조건 | 신뢰도 | 섹션 내 관심 영향 |

Reader-facing Korean labels are observational by design (plan §Goal):
``Bullish trigger → 상방 확인 조건``, ``Bearish trigger → 하방 확인 조건``,
``Portfolio implication → 섹션 내 관심 영향`` (section-local context only —
the Direct/Related/Uncertain/Rejected watchlist workflow grouping belongs to
u73, not here).

Relationship to u64 (extend, do NOT replace)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
u64 shipped :func:`investo.publisher.reader_format.check_watchpoint_actionability`,
which flags §⑥ bullets lacking source + trigger + implication structure. u72
**reuses that exact contract** — the same ``_WATCHPOINT_SOURCE_RE`` /
``_WATCHPOINT_TRIGGER_RE`` / ``_WATCHPOINT_IMPLICATION_RE`` regexes — so there
is a single source/trigger/threshold/implication validation rule, not two.
A bullet u64 would reject (generic monitor verb only) becomes an explicit
``데이터부족`` matrix row here instead of an invented trigger. u72 only
*formats* successful output into the matrix.

Confidence labels (plan Step 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``높음``       — source-backed bullet WITH a verified numeric threshold and
                non-limited segment coverage.
``보통``       — source-backed bullet (u64 evidence reason exists) but no
                verified numeric threshold, or partial coverage.
``낮음``       — only carryover/topic evidence (no fresh numeric/source anchor).
``데이터부족`` — segment coverage limited/failed, or the bullet lacks the
                required source/trigger/implication structure.

Compliance (u56 — UNCHANGED)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The matrix is observational only. This module never emits buy/sell verbs,
position sizing, or target prices; the cell text is copied verbatim from the
LLM-generated bullet (which has already passed the Stage-2 prompt contract),
and the orchestrator still runs :func:`scan_compliance` over the full matrix
text afterwards. The matrix lives in table cells, which the compliance
scanner already masks — so the scanner is additionally run by the orchestrator
on the un-masked source bullets *before* table rendering, and on the full
document text. No advice wording is introduced here.

Module boundary
~~~~~~~~~~~~~~~
* Imports stdlib only + ``reader_format`` structure regexes (both publisher).
* Does NOT import from ``briefing/`` / ``sources/`` / ``notifier/``.

Disclaimer enforcement
~~~~~~~~~~~~~~~~~~~~~~~
Pure ``str -> str`` transform. The disclaimer footer lives at the document
tail and is never touched (the transform only rewrites the §⑥ body region).

R13 hygiene
~~~~~~~~~~~
No secret-bearing input. WARN extras carry only ``segment`` / ``count``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final, Literal

from investo.publisher.reader_format import (
    _BULLET_RE,
    _SECTION_HEADER_RE,
    _WATCHPOINT_IMPLICATION_RE,
    _WATCHPOINT_SOURCE_RE,
    _WATCHPOINT_TRIGGER_RE,
)

_logger = logging.getLogger(__name__)

ConfidenceLabel = Literal["높음", "보통", "낮음", "데이터부족"]

# Closed confidence label set (plan Step 1). Pinned in tests.
CONFIDENCE_LABELS: Final[frozenset[ConfidenceLabel]] = frozenset(
    {"높음", "보통", "낮음", "데이터부족"}
)
DATA_LIMITED_CONFIDENCE: Final[ConfidenceLabel] = "데이터부족"

# Reader-facing column headers — observational labels per plan §Goal.
MATRIX_COLUMNS: Final[tuple[str, ...]] = (
    "관찰 신호",
    "현재",
    "상방 확인 조건",
    "하방 확인 조건",
    "신뢰도",
    "섹션 내 관심 영향",
)

# Maximum visible rows; extra bullets are summarised into a trailing note so
# §⑥ stays daily-readable rather than growing unbounded.
MAX_VISIBLE_ROWS: Final[int] = 6

# Verified-numeric-threshold signal: a percent / dollar / yield figure that
# turns a source-backed bullet from 보통 into 높음. Reuses the broad numeric
# trigger vocabulary but requires an actual figure (digit + %/$ or 금리/수익률).
_VERIFIED_NUMERIC_RE: Final[re.Pattern[str]] = re.compile(
    r"\d[\d,\.]*\s*(?:%|bp|bps|\$|원|달러|포인트|pt)|\$\s*[\d,]"
)

# Carryover / prior-context-only markers (plan precedence rule 3): when a
# bullet only references prior context it is downgraded to 낮음 even if it
# happens to mention a source word.
_CARRYOVER_ONLY_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:어제 예고|전일 예고|carryover|이월|지속 관찰|연장)"
)

# Data-limited sentinel phrases the LLM may already emit (u64 allows
# "데이터 부족" to short-circuit the structure check). Matched leniently.
_DATA_LIMITED_RE: Final[re.Pattern[str]] = re.compile(r"데이터\s*부족|데이터부족")

# Clause splitter: break a bullet into observation clauses. We split on
# semicolons, the centre-dot list separator, and a full-stop *followed by a
# space* (so a decimal point inside ``4.5%`` does NOT split the clause).
_CLAUSE_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"\s*[;；·]\s*|\.\s+|。")  # noqa: RUF001 — full-width semicolon is valid Korean punctuation

# Keyword vocabularies used to slot a clause into the bullish / bearish /
# implication columns. Directional verbs are the most specific signal so they
# are matched first; the implication bucket then takes a remaining clause,
# preferring the explicit ``관심 영향`` / ``섹션 내`` markers before the broad
# ``시사 / 영향 / 리스크`` fallbacks.
_IMPLICATION_STRONG_KEYWORDS: Final[tuple[str, ...]] = ("관심 영향", "섹션 내")
_IMPLICATION_WEAK_KEYWORDS: Final[tuple[str, ...]] = ("시사", "영향", "리스크")
_BULLISH_KEYWORDS: Final[tuple[str, ...]] = ("상회", "돌파", "회복", "상방")
_BEARISH_KEYWORDS: Final[tuple[str, ...]] = ("하회", "이탈", "하방", "방어", "약화", "되돌림")

# Markdown table-cell escaping: a literal pipe would break the table grid.
_PIPE_RE: Final[re.Pattern[str]] = re.compile(r"\|")
_DASH = "—"

# u87 Step 1 — §⑥ bullet pre-filter (AC-87.1). A trace-footer diagnostic line
# (``- `input_hash`: `…```, ``stage1_hash: …``, ``stage2_hash: …``,
# ``input_hash: …``) is a backtick-wrapped lowercase key followed by a colon
# (the full-width colon variant is included too). Such lines sit in the §⑥ body
# region at render time and must never reach ``build_watchpoint_rows`` as rows.
_DIAGNOSTIC_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^`?[a-z][a-z0-9_]*`?\s*[:：]")  # noqa: RUF001 — full-width colon is a valid diagnostic separator

# u87 Step 2 — markdown-link unwrap (AC-87.2). Replace ``[text](url)`` with its
# link text so a truncation can never cut a URL mid-stream (``](http…``). Kept
# as a local publisher constant (module boundary: no ``briefing/`` import).
_MD_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[([^\]]+)\]\((?:[^)]*)\)")

# u87 Step 2 — dangling-particle trim (AC-87.3). A signal label must never end
# on a bare Korean 조사 (e.g. ``…원이`` / ``…구도가`` / ``BTC-USD가``).
_TRAILING_PARTICLE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:이|가|은|는|을|를|와|과|도|의|에|로|으로)\s*…?$"
)

# Any Hangul syllable — used by the pre-filter to drop bare-link / pure-symbol
# bullets that carry no Korean observation text.
_HANGUL_RE: Final[re.Pattern[str]] = re.compile(r"[가-힣]")

# u87 Step 3 — single pinned data-limited note (AC-87.4). When no usable
# observation row survives, §⑥ collapses to this one blockquote line instead of
# rendering a ≥2-row wall of ``데이터부족``.
DATA_LIMITED_NOTE: Final[str] = (
    "> **관전 포인트**: 구조화 가능한 관찰 신호가 부족합니다 — 본문 §②·§④ 참조"
)


def _is_observation_bullet(bullet: str) -> bool:
    """True when ``bullet`` is a reader-facing §⑥ observation (u87 Step 1).

    Rejects (AC-87.1): trace-footer diagnostic / backtick-key lines
    (``input_hash`` / ``stage1_hash`` / ``stage2_hash``), bullets that — after
    stripping markdown links and whitespace — carry no Hangul syllable (a bare
    link or pure-symbol bullet), and empty/whitespace bullets.
    """
    stripped = bullet.strip()
    if not stripped:
        return False
    if _DIAGNOSTIC_LINE_RE.match(stripped):
        return False
    unwrapped = _MD_LINK_RE.sub(r"\1", stripped).strip()
    return _HANGUL_RE.search(unwrapped) is not None


@dataclass(frozen=True, slots=True)
class WatchpointRow:
    """One observational matrix row.

    All fields are reader-facing Korean strings copied/derived from a single
    LLM-generated §⑥ bullet. ``confidence`` is drawn from the closed
    :data:`CONFIDENCE_LABELS` set. No field carries advice wording — the cell
    text is a slice of the already-compliance-checked bullet.
    """

    signal: str
    current: str
    bullish_trigger: str
    bearish_trigger: str
    confidence: ConfidenceLabel
    implication: str

    @classmethod
    def data_limited(cls, signal: str) -> WatchpointRow:
        """Build an explicit ``데이터부족`` row (plan AC-72.2)."""
        return cls(
            signal=signal or "관전 포인트",
            current=_DASH,
            bullish_trigger="데이터부족",
            bearish_trigger="데이터부족",
            confidence=DATA_LIMITED_CONFIDENCE,
            implication=_DASH,
        )


def _is_structured(bullet: str) -> bool:
    """Reuse u64's source+trigger+implication contract (single source of truth)."""
    return bool(
        _WATCHPOINT_SOURCE_RE.search(bullet)
        and _WATCHPOINT_TRIGGER_RE.search(bullet)
        and _WATCHPOINT_IMPLICATION_RE.search(bullet)
    )


def _classify_confidence(bullet: str, *, coverage_limited: bool) -> ConfidenceLabel:
    """Map a structured bullet to a confidence label per plan Step 1.

    Precedence: limited coverage → 데이터부족; carryover-only → 낮음;
    verified numeric threshold present → 높음; otherwise source-backed → 보통.
    """
    if coverage_limited or _DATA_LIMITED_RE.search(bullet):
        return DATA_LIMITED_CONFIDENCE
    if _CARRYOVER_ONLY_RE.search(bullet) and not _VERIFIED_NUMERIC_RE.search(bullet):
        return "낮음"
    if _VERIFIED_NUMERIC_RE.search(bullet):
        return "높음"
    return "보통"


# Source-prefix patterns stripped before deriving the signal so the label is
# the indicator (``10Y 금리``), not the citation (``확인 소스: FRED``).
_SOURCE_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:확인\s?소스|출처|소스|근거)\s*[:：]\s*[^·.。\n]*[·]\s*",  # noqa: RUF001 — full-width colon is valid Korean punctuation
)


def _clauses(bullet: str) -> list[str]:
    """Split ``bullet`` into trimmed observation clauses (decimal-safe)."""
    return [c.strip(" -—·") for c in _CLAUSE_SPLIT_RE.split(bullet) if c.strip(" -—·")]


def _clause_for(keywords: tuple[str, ...], clauses: list[str]) -> str | None:
    for clause in clauses:
        if any(kw in clause for kw in keywords):
            return clause
    return None


def _short_signal(bullet: str) -> str:
    """Derive a terse signal label — the indicator after any source prefix.

    u87 Step 2: markdown links are unwrapped to their link text *first* so a
    truncation can never emit a ``](http…`` fragment (AC-87.2), and a trailing
    bare Korean particle is trimmed so the label never dangles on a 조사
    (AC-87.3).
    """
    stripped = _SOURCE_PREFIX_RE.sub("", bullet).strip()
    head = _MD_LINK_RE.sub(r"\1", stripped or bullet.strip())
    # Cut at the first directional verb / clause separator so the label stays
    # terse (e.g. ``10Y 금리가 4.5% 를``).
    for sep in ("가 ", "이 ", "는 ", "은 ", "："):  # noqa: RUF001 — full-width colon is valid Korean punctuation
        idx = head.find(sep)
        if 0 < idx <= 30:
            return _trim_trailing_particle(head[: idx + 1].strip(), truncated=False)
    truncated = len(head) > 30
    return _trim_trailing_particle(head[:30], truncated=truncated)


def _trim_trailing_particle(label: str, *, truncated: bool) -> str:
    """Strip a trailing bare 조사 (AC-87.3); re-append ``…`` iff truncated."""
    trimmed = _TRAILING_PARTICLE_RE.sub("", label).rstrip()
    return f"{trimmed}…" if truncated else trimmed


def _build_row(bullet: str, *, coverage_limited: bool) -> WatchpointRow:
    """Turn a single §⑥ bullet into a matrix row.

    Generic / unstructured bullets (u64 contract fails) become an explicit
    ``데이터부족`` row — never an invented trigger (plan AC-72.2).
    """
    if not _is_structured(bullet) or coverage_limited:
        return WatchpointRow.data_limited(_short_signal(bullet))

    confidence = _classify_confidence(bullet, coverage_limited=coverage_limited)
    if confidence == DATA_LIMITED_CONFIDENCE:
        return WatchpointRow.data_limited(_short_signal(bullet))

    clauses = _clauses(bullet)
    # Directional verbs are the most specific — bucket them first.
    bullish = _clause_for(_BULLISH_KEYWORDS, clauses)
    bearish = _clause_for(_BEARISH_KEYWORDS, clauses)
    # Implication takes a *remaining* clause, preferring explicit markers.
    used = {bullish, bearish}
    remaining = [c for c in clauses if c not in used]
    implication = _clause_for(_IMPLICATION_STRONG_KEYWORDS, remaining) or _clause_for(
        _IMPLICATION_WEAK_KEYWORDS, remaining
    )
    return WatchpointRow(
        signal=_short_signal(bullet),
        current=bullet.strip(),
        bullish_trigger=bullish or "데이터부족",
        bearish_trigger=bearish or "데이터부족",
        confidence=confidence,
        implication=implication or _DASH,
    )


def build_watchpoint_rows(
    bullets: list[str],
    *,
    coverage_limited: bool = False,
) -> list[WatchpointRow]:
    """Build the bounded matrix rows from raw §⑥ bullets (pure)."""
    if not bullets:
        return []
    if coverage_limited:
        return [WatchpointRow.data_limited("데이터 수집 부족")]
    rows = [_build_row(b, coverage_limited=False) for b in bullets[:MAX_VISIBLE_ROWS]]
    return rows


def _escape_cell(text: str) -> str:
    # u87 Step 2 / AC-87.2 — unwrap markdown links to their text so no cell
    # (current / trigger / implication, not just the signal) can carry a
    # ``](http…`` fragment, and a literal pipe never breaks the table grid.
    unwrapped = _MD_LINK_RE.sub(r"\1", text)
    return _PIPE_RE.sub("/", unwrapped).replace("\n", " ").strip() or _DASH


def render_matrix_table(rows: list[WatchpointRow]) -> str:
    """Render rows as a compact Markdown table (header + alignment + body)."""
    if not rows:
        return ""
    header = "| " + " | ".join(MATRIX_COLUMNS) + " |"
    align = "| " + " | ".join(["---"] * len(MATRIX_COLUMNS)) + " |"
    body_lines = []
    for row in rows:
        cells = (
            _escape_cell(row.signal),
            _escape_cell(row.current),
            _escape_cell(row.bullish_trigger),
            _escape_cell(row.bearish_trigger),
            row.confidence,
            _escape_cell(row.implication),
        )
        body_lines.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, align, *body_lines])


def render_watchpoint_matrix(
    text: str,
    *,
    section_marker: str = "⑥",
    segment: str | None = None,
    coverage_limited: bool = False,
) -> str:
    """Rewrite §⑥ body bullets into the observational matrix table (pure).

    Idempotent: if §⑥ already contains the matrix header *or* the collapsed
    :data:`DATA_LIMITED_NOTE` (same-day re-run), the document is returned
    unchanged. Missing / empty §⑥ → unchanged. The transform is bounded to the
    §⑥ body region; every other section and the disclaimer footer are
    byte-preserved.
    """
    headers = list(_SECTION_HEADER_RE.finditer(text))
    for idx, match in enumerate(headers):
        if section_marker not in match.group("header"):
            continue
        body_start = match.end()
        body_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        body = text[body_start:body_end]
        header_line = "| " + " | ".join(MATRIX_COLUMNS) + " |"
        # Idempotent (AC-87.7): a same-day re-run that already contains the
        # matrix header *or* the collapsed DATA_LIMITED_NOTE returns unchanged.
        if header_line in body or DATA_LIMITED_NOTE in body:
            return text
        # u87 Step 1 — drop non-observation lines (trace-footer diagnostics,
        # bare-link/pure-symbol bullets) before row building (AC-87.1).
        raw_bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(body)]
        bullets = [b for b in raw_bullets if _is_observation_bullet(b)]
        if not bullets and not coverage_limited:
            return text  # also covers "all bullets filtered out"
        rows = build_watchpoint_rows(bullets, coverage_limited=coverage_limited)
        # u87 Step 3 — collapse an all-데이터부족 (or empty) result to the single
        # pinned note instead of a ≥2-row wall of 데이터부족 (AC-87.4).
        all_data_limited = not rows or all(r.confidence == DATA_LIMITED_CONFIDENCE for r in rows)
        if all_data_limited:
            _logger.info(
                "watchpoint_matrix.data_limited_rows",
                extra={"segment": segment, "count": len(bullets)},
            )
            new_body = f"\n\n{DATA_LIMITED_NOTE}\n"
            return text[:body_start] + new_body + text[body_end:]
        table = render_matrix_table(rows)
        if not table:
            return text
        omitted = max(0, len(bullets) - MAX_VISIBLE_ROWS)
        suffix = f"\n\n_관전 신호 {omitted}건 추가 — 본문 참조._" if omitted else ""
        new_body = f"\n\n{table}{suffix}\n"
        if any(r.confidence == DATA_LIMITED_CONFIDENCE for r in rows):
            _logger.info(
                "watchpoint_matrix.data_limited_rows",
                extra={
                    "segment": segment,
                    "count": sum(1 for r in rows if r.confidence == DATA_LIMITED_CONFIDENCE),
                },
            )
        return text[:body_start] + new_body + text[body_end:]
    return text


__all__ = [
    "CONFIDENCE_LABELS",
    "DATA_LIMITED_CONFIDENCE",
    "DATA_LIMITED_NOTE",
    "MATRIX_COLUMNS",
    "MAX_VISIBLE_ROWS",
    "ConfidenceLabel",
    "WatchpointRow",
    "build_watchpoint_rows",
    "render_matrix_table",
    "render_watchpoint_matrix",
]
