"""u72/u98 — render §⑥ 오늘의 관전 포인트 as bounded observational cards.

Problem (2026-05-24 ten-subagent review): even after u64 added watchpoint
actionability diagnostics, §⑥ still reads like a list of generic monitoring
verbs (``관찰`` / ``확인`` / ``점검`` / ``비교``). A reader cannot tell which
signal matters, what the current observed state is, what would flip it
bullish or bearish, how confident the system is, or what it implies for the
section's watchlist context.

u72 originally converted the *already-generated* §⑥ bullets into a standard
six-column matrix. u98 keeps the same extraction/validation contract but
renders compact cards. It is **not** a watchlist matcher rewrite and **not** a
recommendation engine:

  #### 관찰 신호: {short_signal}

  - 출처: {source}
  - 현재: {current}
  - 확인 조건: 상방 {upside}; 하방 {downside}
  - 신뢰도: {confidence}
  - 관심 영향: {watchlist_impact}

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
* Imports stdlib + the neutral public-language wording owner and
  ``reader_format`` structure regexes.
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
from typing import Final, Literal, cast

from investo._internal.public_quality_language import (
    PUBLIC_LOW_COVERAGE_INLINE_TEXT,
    PUBLIC_LOW_COVERAGE_LABEL,
    PUBLIC_WATCHPOINT_LIMITED_TEXT,
    PUBLIC_WATCHPOINT_SOURCE_TEXT,
)
from investo.publisher.reader_format import (
    _BULLET_RE,
    _SECTION_HEADER_RE,
    _WATCHPOINT_IMPLICATION_RE,
    _WATCHPOINT_SOURCE_RE,
    _WATCHPOINT_TRIGGER_RE,
)

_logger = logging.getLogger(__name__)

ConfidenceLabel = Literal["높음", "보통", "낮음", "근거 제한"]
WatchpointRenderState = Literal["rendered", "limited"]
WatchpointLimitationReason = Literal["watchpoint_unavailable"]

# Closed confidence label set (plan Step 1). Pinned in tests.
CONFIDENCE_LABELS: Final[frozenset[ConfidenceLabel]] = frozenset(
    {"높음", "보통", "낮음", cast(ConfidenceLabel, PUBLIC_LOW_COVERAGE_LABEL)}
)
DATA_LIMITED_CONFIDENCE: Final[ConfidenceLabel] = cast(
    ConfidenceLabel,
    PUBLIC_LOW_COVERAGE_LABEL,
)

# Reader-facing column headers — observational labels per plan §Goal.
# Parser/card field labels retained as a compatibility constant. u98 no longer
# renders these as a Markdown table header.
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
_CLAUSE_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"\s*[;；·]\s*|,\s+|，|\.\s+|。")  # noqa: RUF001 — full-width punctuation is valid Korean text

# Keyword vocabularies used to slot a clause into the bullish / bearish /
# implication columns. Directional verbs are the most specific signal so they
# are matched first; the implication bucket then takes a remaining clause,
# preferring the explicit ``관심 영향`` / ``섹션 내`` markers before the broad
# ``시사 / 영향 / 리스크`` fallbacks.
_IMPLICATION_STRONG_KEYWORDS: Final[tuple[str, ...]] = ("관심 영향", "섹션 내")
_IMPLICATION_WEAK_KEYWORDS: Final[tuple[str, ...]] = ("시사", "영향", "리스크")
_BULLISH_KEYWORDS: Final[tuple[str, ...]] = ("상회", "돌파", "회복", "확대", "상방")
_BEARISH_KEYWORDS: Final[tuple[str, ...]] = ("하회", "이탈", "하방", "방어", "약화", "되돌림")

# Markdown table-cell escaping: a literal pipe would break the table grid.
_PIPE_RE: Final[re.Pattern[str]] = re.compile(r"\|")
_RAW_URL_RE: Final[re.Pattern[str]] = re.compile(r"https?://\S+|www\.\S+")
_BROKEN_MD_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\]\([^)]*|\[[^\]]*$")
_TRACE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"`?(?:input_hash|stage1_hash|stage2_hash)`?\s*[:：]?\s*`?[0-9a-fA-F]{6,}`?"  # noqa: RUF001 — full-width colon is a valid diagnostic separator
)
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
DATA_LIMITED_NOTE: Final[str] = f"> **관전 포인트**: {PUBLIC_WATCHPOINT_LIMITED_TEXT}"
_RENDERED_CONDITION_RE: Final[re.Pattern[str]] = re.compile(
    r"^- 확인 조건: 상방 (?P<upside>\S.+); 하방 (?P<downside>\S.+)$"
)
_RENDERED_OMISSION_RE: Final[re.Pattern[str]] = re.compile(
    r"^_관전 신호 \d+건 추가 — 본문 참조\._$"
)


@dataclass(frozen=True, slots=True)
class WatchpointRenderResult:
    """Typed availability result for the u144 assembly boundary."""

    markdown: str
    state: WatchpointRenderState
    usable_card_count: int
    limitation_reasons: tuple[WatchpointLimitationReason, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.markdown, str) or not self.markdown:
            raise ValueError("watchpoint result markdown must not be empty")
        if type(self.usable_card_count) is not int or self.usable_card_count < 0:
            raise ValueError("usable_card_count must be a non-negative int")
        reasons = tuple(self.limitation_reasons)
        if self.state == "rendered":
            if self.usable_card_count == 0 or reasons:
                raise ValueError("rendered watchpoint result requires usable cards and no reason")
        elif self.state == "limited":
            if self.usable_card_count != 0 or reasons != ("watchpoint_unavailable",):
                raise ValueError(
                    "limited watchpoint result requires zero cards and watchpoint_unavailable"
                )
        else:
            raise ValueError("watchpoint result state must be rendered or limited")
        object.__setattr__(self, "limitation_reasons", reasons)


def _existing_watchpoint_state(body: str) -> tuple[WatchpointRenderState, int] | None:
    """Recognize only exact renderer output, never a heading substring."""

    if body.strip() == DATA_LIMITED_NOTE:
        return ("limited", 0)
    if DATA_LIMITED_NOTE in body:
        return None
    lines = body.splitlines()
    index = 0
    card_count = 0
    while index < len(lines):
        while index < len(lines) and not lines[index]:
            index += 1
        if index >= len(lines):
            break
        if _RENDERED_OMISSION_RE.fullmatch(lines[index]):
            index += 1
            while index < len(lines) and not lines[index]:
                index += 1
            return ("rendered", card_count) if card_count and index == len(lines) else None
        if not lines[index].startswith("#### 관찰 신호: "):
            return None
        signal = lines[index].removeprefix("#### 관찰 신호: ").strip()
        if not signal:
            return None
        if index + 6 >= len(lines) or lines[index + 1] != "":
            return None
        fields = lines[index + 2 : index + 7]
        source = fields[0].removeprefix("- 출처: ").strip()
        if not fields[0].startswith("- 출처: ") or not source:
            return None
        current = fields[1].removeprefix("- 현재: ").strip()
        if not fields[1].startswith("- 현재: ") or not current:
            return None
        condition_match = _RENDERED_CONDITION_RE.fullmatch(fields[2])
        if condition_match is None:
            return None
        if fields[3] not in {f"- 신뢰도: {label}" for label in CONFIDENCE_LABELS}:
            return None
        implication = fields[4].removeprefix("- 관심 영향: ").strip()
        if not fields[4].startswith("- 관심 영향: ") or not implication:
            return None
        row = WatchpointRow(
            signal=signal,
            source=source,
            current=current,
            bullish_trigger=condition_match.group("upside"),
            bearish_trigger=condition_match.group("downside"),
            confidence=cast(ConfidenceLabel, fields[3].removeprefix("- 신뢰도: ")),
            implication=implication,
        )
        original_card = "\n".join(lines[index : index + 7])
        if (
            not _renderable_row(row)
            or render_matrix_table([row]) != original_card
            or card_count >= MAX_VISIBLE_ROWS
        ):
            return None
        card_count += 1
        index += 7
    return ("rendered", card_count) if card_count else None


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
    source: str
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
            source=PUBLIC_WATCHPOINT_SOURCE_TEXT,
            current=PUBLIC_WATCHPOINT_LIMITED_TEXT,
            bullish_trigger=PUBLIC_LOW_COVERAGE_INLINE_TEXT,
            bearish_trigger=PUBLIC_LOW_COVERAGE_INLINE_TEXT,
            confidence=DATA_LIMITED_CONFIDENCE,
            implication=PUBLIC_WATCHPOINT_LIMITED_TEXT,
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
_SOURCE_VALUE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:확인\s?소스|출처|소스|근거)\s*[:：]\s*([^·.;。,\n]+)"  # noqa: RUF001 — full-width colon is valid Korean punctuation
)
_SOURCE_CANDIDATE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:확인\s?소스|출처|소스|근거|source)\s*[:\uff1a]\s*"
    r"(.+?)(?=\s*(?:[·;。\n]|상방(?:\s*[:\uff1a]|\s+-)|"
    r"하방(?:\s*[:\uff1a]|\s+-)|관심\s*영향\s*[:\uff1a]|"
    r"섹션\s*내\s*관심\s*영향\s*[:\uff1a]|$))",
    re.IGNORECASE,
)
_FIELD_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:현재|출처|확인\s?소스|소스|근거|source|상방|하방|관심\s*영향|"
    r"섹션\s*내\s*관심\s*영향)\s*(?::|\uff1a|\s+-\s*|\s+[\u2013\u2014-]\s+)\s*",
    re.IGNORECASE,
)
_INVALID_SOURCE_VALUES: Final[frozenset[str]] = frozenset(
    {
        "",
        "확인 소스 미상",
        "source missing",
        "missing source",
        "데이터 부족",
        "데이터부족",
        PUBLIC_WATCHPOINT_SOURCE_TEXT,
        PUBLIC_WATCHPOINT_SOURCE_TEXT.rstrip("."),
    }
)
_GENERIC_CURRENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:[A-Z0-9.^=-]{2,12}|[가-힣A-Za-z0-9.^=-]{2,20}\s*(?:확인|점검|관찰|추세|흐름)?|"
    r"(?:FOMC|CPI|PPI|환율|금리|유가|비트코인|이더리움)\s*(?:확인|점검|관찰|추세|흐름)?)$"
)


def _clauses(bullet: str) -> list[str]:
    """Split ``bullet`` into trimmed observation clauses (decimal-safe)."""
    return [c.strip(" -—·") for c in _CLAUSE_SPLIT_RE.split(bullet) if c.strip(" -—·")]


def _clause_for(keywords: tuple[str, ...], clauses: list[str]) -> str | None:
    for clause in clauses:
        if any(kw in clause for kw in keywords):
            return clause
    return None


def _prefixed_clause_for(label: str, clauses: list[str]) -> str | None:
    pattern = re.compile(
        rf"^\s*{label}\s*(?::|\uff1a|\s+-\s*|\s+[\u2013\u2014-]\s+)",
        re.IGNORECASE,
    )
    for clause in clauses:
        if pattern.match(clause):
            return clause
    return None


def _is_source_only_clause(clause: str) -> bool:
    if not _SOURCE_CANDIDATE_RE.search(clause):
        return False
    without_label = _strip_field_prefixes(_strip_field_prefixes(clause))
    candidate = _source_candidate_from(clause)
    return bool(_valid_source(candidate) and without_label == candidate)


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


def _sanitize_card_text(text: str, *, default: str) -> str:
    """Return reader-safe card text without URLs, broken links, or trace tokens."""
    cleaned = _MD_LINK_RE.sub(r"\1", text)
    cleaned = _TRACE_TOKEN_RE.sub("", cleaned)
    cleaned = _RAW_URL_RE.sub("", cleaned)
    cleaned = _BROKEN_MD_LINK_RE.sub("", cleaned)
    cleaned = _PIPE_RE.sub("/", cleaned)
    cleaned = cleaned.replace("`", "").replace("\n", " ").strip(" -—·;")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or default


def _strip_field_prefixes(text: str) -> str:
    """Strip repeated card-field labels while preserving semantic direction words."""
    stripped = text.strip()
    while True:
        updated = _FIELD_PREFIX_RE.sub("", stripped, count=1).strip()
        if updated == stripped:
            return stripped
        stripped = updated


def _normalise_field_text(text: str, *, default: str) -> str:
    """Sanitize a field and remove template labels before card templating."""
    return _sanitize_card_text(_strip_field_prefixes(text), default=default)


def _source_candidate_from(text: str) -> str:
    match = _SOURCE_CANDIDATE_RE.search(text)
    raw = match.group(1) if match else text
    candidate = _normalise_field_text(raw, default="")
    candidate = re.split(
        r"\s+(?:상방|하방)(?:\s*[:\uff1a]|\s+-)|\s+관심\s*영향\s*[:\uff1a]",
        candidate,
        maxsplit=1,
    )[0]
    candidate = candidate.strip(" -—·;,.。")
    # Nested labels such as "출처: 확인 소스: FRED" need one extra peel.
    candidate = _strip_field_prefixes(candidate).strip(" -—·;,.。")
    return candidate


def _valid_source(candidate: str) -> bool:
    normalized = _sanitize_card_text(candidate, default="").strip()
    if not normalized:
        return False
    if normalized.lower() in _INVALID_SOURCE_VALUES:
        return False
    if _DATA_LIMITED_RE.fullmatch(normalized) or "미상" in normalized:
        return False
    return bool(_HANGUL_RE.search(normalized) or re.search(r"[A-Za-z0-9]", normalized))


def _promote_source(*fields: str) -> str:
    for idx, field in enumerate(fields):
        for match in _SOURCE_CANDIDATE_RE.finditer(field):
            candidate = _source_candidate_from(match.group(0))
            if _valid_source(candidate):
                return candidate
        candidate = _source_candidate_from(field)
        if idx == 0 and _valid_source(candidate) and len(candidate) <= 40:
            return candidate
        if _valid_source(candidate) and _SOURCE_CANDIDATE_RE.search(field):
            return candidate
    return PUBLIC_WATCHPOINT_SOURCE_TEXT


def _field_missing(text: str, *, data_limited_default: str) -> bool:
    normalized = _normalise_field_text(text, default="")
    if not normalized or normalized == data_limited_default:
        return True
    return bool(_DATA_LIMITED_RE.search(normalized))


def _trigger_key(text: str) -> str:
    normalized = _normalise_field_text(text, default="")
    normalized = re.sub(r"^(?:상방|하방)\s+", "", normalized).strip()
    return re.sub(r"\s+", " ", normalized).casefold()


def _trigger_display(text: str, *, default: str) -> str:
    normalized = _normalise_field_text(text, default=default)
    return re.sub(r"^(?:상방|하방)\s+", "", normalized).strip() or default


def _is_generic_current(text: str) -> bool:
    normalized = _normalise_field_text(text, default="")
    if not normalized or _DATA_LIMITED_RE.search(normalized):
        return True
    return bool(len(normalized) <= 24 and _GENERIC_CURRENT_RE.match(normalized))


def _renderable_row(row: WatchpointRow) -> bool:
    source = _promote_source(
        row.source,
        row.current,
        row.bullish_trigger,
        row.bearish_trigger,
        row.implication,
    )
    if not _valid_source(source):
        return False
    if _field_missing(
        row.bullish_trigger,
        data_limited_default=PUBLIC_LOW_COVERAGE_INLINE_TEXT,
    ):
        return False
    if _field_missing(
        row.bearish_trigger,
        data_limited_default=PUBLIC_LOW_COVERAGE_INLINE_TEXT,
    ):
        return False
    if _trigger_key(row.bullish_trigger) == _trigger_key(row.bearish_trigger):
        return False

    soft_invalids = 0
    if row.confidence == DATA_LIMITED_CONFIDENCE:
        soft_invalids += 1
    if _is_generic_current(row.current):
        soft_invalids += 1
    if _field_missing(
        row.implication,
        data_limited_default=PUBLIC_WATCHPOINT_LIMITED_TEXT,
    ):
        soft_invalids += 1
    return soft_invalids < 2


def _source_from_bullet(bullet: str) -> str:
    source = _promote_source(bullet)
    if _valid_source(source):
        return source
    match = _SOURCE_VALUE_RE.search(bullet)
    if not match:
        return PUBLIC_WATCHPOINT_SOURCE_TEXT
    candidate = _source_candidate_from(match.group(0))
    return candidate if _valid_source(candidate) else PUBLIC_WATCHPOINT_SOURCE_TEXT


def _build_row(bullet: str, *, coverage_limited: bool) -> WatchpointRow:
    """Turn a single §⑥ bullet into a card row.

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
    bullish = _prefixed_clause_for("상방", clauses) or _clause_for(_BULLISH_KEYWORDS, clauses)
    bearish = _prefixed_clause_for("하방", clauses) or _clause_for(_BEARISH_KEYWORDS, clauses)
    # Implication takes a *remaining* clause, preferring explicit markers.
    used = {bullish, bearish}
    remaining = [c for c in clauses if c not in used]
    implication = _clause_for(_IMPLICATION_STRONG_KEYWORDS, remaining) or _clause_for(
        _IMPLICATION_WEAK_KEYWORDS, remaining
    )
    used.add(implication)
    current_clause = next(
        (c for c in clauses if c not in used and not _is_source_only_clause(c)),
        "",
    )
    current = _normalise_field_text(current_clause or bullet.strip(), default="현재 신호 부족")
    bullish_trigger = _normalise_field_text(
        bullish or "",
        default=PUBLIC_LOW_COVERAGE_INLINE_TEXT,
    )
    bearish_trigger = _normalise_field_text(
        bearish or "",
        default=PUBLIC_LOW_COVERAGE_INLINE_TEXT,
    )
    implication_text = _normalise_field_text(
        implication or "",
        default=PUBLIC_WATCHPOINT_LIMITED_TEXT,
    )
    return WatchpointRow(
        signal=_short_signal(bullet),
        source=_promote_source(bullet, current, bullish_trigger, bearish_trigger, implication_text),
        current=current,
        bullish_trigger=bullish_trigger,
        bearish_trigger=bearish_trigger,
        confidence=confidence,
        implication=implication_text,
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
        return [WatchpointRow.data_limited("관전 포인트")]
    rows = [_build_row(b, coverage_limited=False) for b in bullets[:MAX_VISIBLE_ROWS]]
    return rows


def _escape_cell(text: str) -> str:
    # Kept for backwards-compatible imports from older tests/extensions.
    return _sanitize_card_text(text, default=_DASH)


def render_matrix_table(rows: list[WatchpointRow]) -> str:
    """Render rows as compact cards.

    The historical name is retained for compatibility with the u72 public-ish
    helper, but u98 intentionally no longer emits a six-column Markdown table.
    """
    if not rows:
        return ""
    body_lines: list[str] = []
    for row in rows:
        source = _promote_source(
            row.source,
            row.current,
            row.bullish_trigger,
            row.bearish_trigger,
            row.implication,
        )
        source_text = _normalise_field_text(
            source,
            default=PUBLIC_WATCHPOINT_SOURCE_TEXT,
        )
        upside = _trigger_display(
            row.bullish_trigger,
            default=PUBLIC_LOW_COVERAGE_INLINE_TEXT,
        )
        downside = _trigger_display(
            row.bearish_trigger,
            default=PUBLIC_LOW_COVERAGE_INLINE_TEXT,
        )
        implication = _normalise_field_text(
            row.implication,
            default=PUBLIC_WATCHPOINT_LIMITED_TEXT,
        )
        body_lines.append(
            "\n".join(
                [
                    f"#### 관찰 신호: {_normalise_field_text(row.signal, default='관전 포인트')}",
                    "",
                    f"- 출처: {source_text}",
                    f"- 현재: {_normalise_field_text(row.current, default='현재 신호 부족')}",
                    f"- 확인 조건: 상방 {upside}; 하방 {downside}",
                    f"- 신뢰도: {row.confidence}",
                    f"- 관심 영향: {implication}",
                ]
            )
        )
    return "\n\n".join(body_lines)


def render_watchpoint_matrix_result(
    text: str,
    *,
    section_marker: str = "⑥",
    segment: str | None = None,
    coverage_limited: bool = False,
) -> WatchpointRenderResult:
    """Rewrite §⑥ and return typed usable-card availability (pure).

    Idempotent: if §⑥ already contains card headings *or* the collapsed
    :data:`DATA_LIMITED_NOTE` (same-day re-run), the document bytes are returned
    unchanged with the matching typed state. The transform is bounded to the
    §⑥ body region; every other section and the disclaimer footer is
    byte-preserved. Missing/empty/unusable §⑥ is explicitly `limited`.
    """
    if not text:
        raise ValueError("watchpoint input markdown must not be empty")
    headers = list(_SECTION_HEADER_RE.finditer(text))
    for idx, match in enumerate(headers):
        if section_marker not in match.group("header"):
            continue
        body_start = match.end()
        body_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        body = text[body_start:body_end]
        # Idempotent (AC-87.7): accept only the exact complete card/note shape.
        existing_state = _existing_watchpoint_state(body)
        if existing_state is not None and existing_state[0] == "rendered":
            return WatchpointRenderResult(
                markdown=text,
                state="rendered",
                usable_card_count=existing_state[1],
            )
        if existing_state == ("limited", 0):
            return WatchpointRenderResult(
                markdown=text,
                state="limited",
                usable_card_count=0,
                limitation_reasons=("watchpoint_unavailable",),
            )
        # u87 Step 1 — drop non-observation lines (trace-footer diagnostics,
        # bare-link/pure-symbol bullets) before row building (AC-87.1).
        raw_bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(body)]
        bullets = [b for b in raw_bullets if _is_observation_bullet(b)]
        if not bullets and not coverage_limited:
            return WatchpointRenderResult(
                markdown=text,
                state="limited",
                usable_card_count=0,
                limitation_reasons=("watchpoint_unavailable",),
            )
        rows = build_watchpoint_rows(bullets, coverage_limited=coverage_limited)
        rows = [r for r in rows if _renderable_row(r)]
        # u87 Step 3 — collapse an all-데이터부족 (or empty) result to the single
        # pinned note instead of a ≥2-row wall of 데이터부족 (AC-87.4).
        if not rows:
            _logger.info(
                "watchpoint_matrix.data_limited_rows",
                extra={"segment": segment, "count": len(bullets)},
            )
            new_body = f"\n\n{DATA_LIMITED_NOTE}\n"
            return WatchpointRenderResult(
                markdown=text[:body_start] + new_body + text[body_end:],
                state="limited",
                usable_card_count=0,
                limitation_reasons=("watchpoint_unavailable",),
            )
        cards = render_matrix_table(rows)
        if not cards:
            return WatchpointRenderResult(
                markdown=text,
                state="limited",
                usable_card_count=0,
                limitation_reasons=("watchpoint_unavailable",),
            )
        omitted = max(0, len(bullets) - MAX_VISIBLE_ROWS)
        suffix = f"\n\n_관전 신호 {omitted}건 추가 — 본문 참조._" if omitted else ""
        new_body = f"\n\n{cards}{suffix}\n"
        return WatchpointRenderResult(
            markdown=text[:body_start] + new_body + text[body_end:],
            state="rendered",
            usable_card_count=len(rows),
        )
    return WatchpointRenderResult(
        markdown=text,
        state="limited",
        usable_card_count=0,
        limitation_reasons=("watchpoint_unavailable",),
    )


def render_watchpoint_matrix(
    text: str,
    *,
    section_marker: str = "⑥",
    segment: str | None = None,
    coverage_limited: bool = False,
) -> str:
    """Compatibility string view with no default segmented production caller."""

    if not text:
        return text
    return render_watchpoint_matrix_result(
        text,
        section_marker=section_marker,
        segment=segment,
        coverage_limited=coverage_limited,
    ).markdown


__all__ = [
    "CONFIDENCE_LABELS",
    "DATA_LIMITED_CONFIDENCE",
    "DATA_LIMITED_NOTE",
    "MATRIX_COLUMNS",
    "MAX_VISIBLE_ROWS",
    "ConfidenceLabel",
    "WatchpointRenderResult",
    "WatchpointRenderState",
    "WatchpointRow",
    "build_watchpoint_rows",
    "render_matrix_table",
    "render_watchpoint_matrix",
    "render_watchpoint_matrix_result",
]
