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
from collections.abc import Sequence
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from itertools import combinations
from typing import Final, Literal, cast

from investo._internal.decimal_format import shortest_exact_decimal
from investo._internal.public_quality_language import (
    PUBLIC_LOW_COVERAGE_INLINE_TEXT,
    PUBLIC_LOW_COVERAGE_LABEL,
    PUBLIC_WATCHPOINT_LIMITED_TEXT,
    PUBLIC_WATCHPOINT_SOURCE_TEXT,
)
from investo.models.items import NormalizedItem
from investo.models.market_anchor import MarketAnchor, anchor_label
from investo.models.segments import MarketSegment
from investo.publisher.reader_format import (
    _BULLET_RE,
    _SECTION_HEADER_RE,
    _WATCHPOINT_IMPLICATION_RE,
    _WATCHPOINT_SOURCE_RE,
    _WATCHPOINT_TRIGGER_RE,
)
from investo.publisher.reader_format.emphasis import wrap_numbers_bold

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
_SIGNAL_TITLE_MAX_CHARS: Final[int] = 30

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
    synthesized_card_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.markdown, str) or not self.markdown:
            raise ValueError("watchpoint result markdown must not be empty")
        if type(self.usable_card_count) is not int or self.usable_card_count < 0:
            raise ValueError("usable_card_count must be a non-negative int")
        if (
            type(self.synthesized_card_count) is not int
            or self.synthesized_card_count < 0
            or self.synthesized_card_count > self.usable_card_count
        ):
            raise ValueError(
                "synthesized_card_count must be a non-negative int no greater than usable cards"
            )
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
    parsed = _parse_existing_watchpoint_cards(body)
    if parsed is None:
        return None
    rows, _ = parsed
    return ("rendered", len(rows)) if rows else None


def _parse_existing_watchpoint_cards(
    body: str,
) -> tuple[tuple[WatchpointRow, ...], str] | None:
    """Parse only byte-canonical cards plus an optional omission suffix."""

    lines = body.splitlines()
    index = 0
    rows: list[WatchpointRow] = []
    while index < len(lines):
        while index < len(lines) and not lines[index]:
            index += 1
        if index >= len(lines):
            break
        if _RENDERED_OMISSION_RE.fullmatch(lines[index]):
            omission = lines[index]
            index += 1
            while index < len(lines) and not lines[index]:
                index += 1
            return (tuple(rows), omission) if rows and index == len(lines) else None
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
            or len(rows) >= MAX_VISIBLE_ROWS
        ):
            return None
        rows.append(row)
        index += 7
    return (tuple(rows), "") if rows else None


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


@dataclass(frozen=True, slots=True)
class WatchpointItemSnapshot:
    source_name: str
    metadata: tuple[tuple[str, str], ...]

    @classmethod
    def from_item(cls, item: NormalizedItem) -> WatchpointItemSnapshot:
        pairs = tuple(
            sorted(
                (key, str(value).strip())
                for key, value in item.raw_metadata.items()
                if not isinstance(value, bool) and str(value).strip()
            )
        )
        return cls(source_name=item.source_name, metadata=pairs)

    def get(self, key: str) -> str | None:
        for candidate, value in self.metadata:
            if candidate == key:
                return value
        return None


@dataclass(frozen=True, slots=True)
class WatchpointValuePayload:
    """Frozen reconciled inputs used only for exact current-value resolution.

    The publisher owns this plain-data DTO. It contains the canonical anchors
    and already-routed items supplied by the caller; constructing it performs
    no I/O and does not import orchestrator state.
    """

    segment: MarketSegment
    anchors: tuple[MarketAnchor, ...] = ()
    item_snapshots: tuple[WatchpointItemSnapshot, ...] = dataclass_field(
        default=(),
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchors", tuple(self.anchors))
        object.__setattr__(self, "item_snapshots", tuple(self.item_snapshots))

    @classmethod
    def from_inputs(
        cls,
        segment: MarketSegment,
        *,
        anchors: Sequence[MarketAnchor] = (),
        items: Sequence[NormalizedItem] = (),
    ) -> WatchpointValuePayload:
        """Snapshot mutable item metadata into immutable scalar tuples."""

        return cls(
            segment=segment,
            anchors=tuple(anchors),
            item_snapshots=tuple(WatchpointItemSnapshot.from_item(item) for item in items),
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
_CURRENT_VALUE_RE: Final[re.Pattern[str]] = re.compile(r"\d")
_MAX_NUMERIC_INPUT_CHARS: Final[int] = 64
_MAX_DISPLAY_MAGNITUDE: Final[int] = 18
_PRICE_QUANTUM: Final[Decimal] = Decimal("0.01")
_COINGECKO_SOURCE: Final[str] = "coingecko-price"
_CFTC_SOURCE: Final[str] = "cftc-cot-positioning"
_CFTC_US_GROUPS: Final[frozenset[str]] = frozenset(
    {"equity_index", "rates", "fx", "energy", "metals", "volatility"}
)
_CFTC_CRYPTO_GROUPS: Final[frozenset[str]] = frozenset({"crypto"})


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
        if 0 < idx <= _SIGNAL_TITLE_MAX_CHARS:
            return _trim_trailing_particle(head[: idx + 1].strip())

    segments = [segment.strip() for segment in head.split(" · ") if segment.strip()]
    while len(" · ".join(segments)) > _SIGNAL_TITLE_MAX_CHARS and len(segments) > 1:
        segments.pop()
    return _trim_trailing_particle(" · ".join(segments))


def _trim_trailing_particle(label: str) -> str:
    """Strip a trailing bare 조사 without introducing truncation residue."""
    return _TRAILING_PARTICLE_RE.sub("", label).rstrip()


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


@dataclass(frozen=True, slots=True)
class _CurrentValueCandidate:
    match_tokens: tuple[str, ...]
    current: str
    source_tokens: tuple[str, ...] = ()
    is_indicator: bool = False


def _metadata_text(item: WatchpointItemSnapshot, key: str) -> str | None:
    return item.get(key)


def _bounded_decimal(raw: object) -> Decimal | None:
    text = str(raw).strip()
    if not text or len(text) > _MAX_NUMERIC_INPUT_CHARS:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or abs(value.adjusted()) > _MAX_DISPLAY_MAGNITUDE:
        return None
    return value


def _format_price_value(value: object, *, prefix: str = "") -> str | None:
    decimal_value = _bounded_decimal(value)
    if decimal_value is None or decimal_value <= 0:
        return None
    try:
        quantized = decimal_value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return f"{prefix}{quantized:,.2f}"


def _format_pct_value(value: object) -> str | None:
    decimal_value = _bounded_decimal(value)
    if decimal_value is None or abs(decimal_value) > Decimal("1000000"):
        return None
    exact = shortest_exact_decimal(str(decimal_value))
    if exact is None:
        return None
    return f"{exact if decimal_value <= 0 else f'+{exact}'}%"


def _anchor_price_prefix(anchor: MarketAnchor, segment: MarketSegment) -> str:
    if segment == "crypto":
        return "$"
    if segment == "us-equity" and not anchor.ticker.startswith("^"):
        return "$"
    if segment == "domestic-equity" and anchor.ticker.endswith((".KS", ".KQ")):
        return "₩"
    return ""


def _anchor_candidate(
    anchor: MarketAnchor,
    *,
    segment: MarketSegment,
) -> _CurrentValueCandidate | None:
    if anchor.pct is None:
        return None
    price = _format_price_value(
        anchor.close,
        prefix=_anchor_price_prefix(anchor, segment),
    )
    pct = _format_pct_value(anchor.pct)
    if price is None or pct is None:
        return None
    label = anchor_label(anchor.ticker)
    return _CurrentValueCandidate(
        match_tokens=tuple(
            dict.fromkeys(
                token for token in (anchor.ticker, label.short, label.ko, label.display) if token
            )
        ),
        current=f"{price} ({pct})",
    )


def _anchor_belongs_to_segment(anchor: MarketAnchor, segment: MarketSegment) -> bool:
    ticker = anchor.ticker
    if segment == "crypto":
        return ticker.endswith("-USD")
    if segment == "domestic-equity":
        return ticker in {"^KOSPI", "^KOSDAQ", "KRW=X"} or ticker.endswith((".KS", ".KQ"))
    return not (
        ticker.endswith("-USD")
        or ticker in {"^KOSPI", "^KOSDAQ", "KRW=X"}
        or ticker.endswith((".KS", ".KQ"))
    )


def _coingecko_candidate(item: WatchpointItemSnapshot) -> _CurrentValueCandidate | None:
    if item.source_name != _COINGECKO_SOURCE:
        return None
    symbol = _metadata_text(item, "symbol")
    coin_id = _metadata_text(item, "coin_id")
    price = _metadata_text(item, "price_usd")
    pct = _metadata_text(item, "pct_24h")
    if None in (symbol, coin_id, price, pct):
        return None
    assert symbol is not None and coin_id is not None and price is not None and pct is not None
    rendered_price = _format_price_value(price, prefix="$")
    rendered_pct = _format_pct_value(pct)
    if rendered_price is None or rendered_pct is None:
        return None
    ticker = f"{symbol.upper()}-USD"
    label = anchor_label(ticker)
    return _CurrentValueCandidate(
        match_tokens=tuple(
            dict.fromkeys((symbol.upper(), ticker, coin_id, label.short, label.ko, label.display))
        ),
        current=f"{rendered_price} ({rendered_pct})",
        source_tokens=("CoinGecko",),
    )


def _fear_greed_candidate(item: WatchpointItemSnapshot) -> _CurrentValueCandidate | None:
    if _metadata_text(item, "indicator") != "fear_greed":
        return None
    value_text = _metadata_text(item, "value")
    value = _bounded_decimal(value_text) if value_text is not None else None
    if (
        value is None
        or value != value.to_integral_value()
        or not Decimal(0) <= value <= Decimal(100)
    ):
        return None
    classification = _metadata_text(item, "classification")
    suffix = f" ({classification})" if classification is not None else ""
    return _CurrentValueCandidate(
        match_tokens=("공포·탐욕", "공포 탐욕", "Fear & Greed", "Fear and Greed", "F&G"),
        current=f"{int(value)}{suffix}",
        is_indicator=True,
    )


def _funding_candidate(item: WatchpointItemSnapshot) -> _CurrentValueCandidate | None:
    if _metadata_text(item, "indicator") != "btc_funding":
        return None
    raw = _metadata_text(item, "btc_funding_rate")
    decimal_value = _bounded_decimal(raw) if raw is not None else None
    if decimal_value is None or abs(decimal_value) > Decimal(1):
        return None
    value = shortest_exact_decimal(str(decimal_value))
    if value is None:
        return None
    return _CurrentValueCandidate(
        match_tokens=("BTC 펀딩", "펀딩", "BTC funding", "funding rate", "funding"),
        current=f"펀딩 {value}",
        is_indicator=True,
    )


def _oi_candidate(item: WatchpointItemSnapshot) -> _CurrentValueCandidate | None:
    if _metadata_text(item, "indicator") != "btc_oi":
        return None
    raw = _metadata_text(item, "btc_oi_usd")
    value = _format_price_value(raw, prefix="$") if raw is not None else None
    if value is None:
        return None
    return _CurrentValueCandidate(
        match_tokens=("BTC 미결제약정", "BTC OI", "미결제약정", "open interest", "OI"),
        current=f"OI {value}",
        is_indicator=True,
    )


def _cftc_candidate(
    item: WatchpointItemSnapshot,
    *,
    groups: frozenset[str],
) -> _CurrentValueCandidate | None:
    if item.source_name != _CFTC_SOURCE:
        return None
    if _metadata_text(item, "contract_group") not in groups:
        return None
    contract = _metadata_text(item, "contract_label")
    net_raw = _metadata_text(item, "net_contracts")
    pct_raw = _metadata_text(item, "net_pct_open_interest")
    net = _bounded_decimal(net_raw) if net_raw is not None else None
    pct_value = _bounded_decimal(pct_raw) if pct_raw is not None else None
    pct = _format_pct_value(pct_value) if pct_value is not None else None
    if (
        contract is None
        or net is None
        or pct is None
        or abs(pct_value or Decimal(0)) > Decimal(100)
        or net != net.to_integral_value()
    ):
        return None
    return _CurrentValueCandidate(
        match_tokens=(contract,),
        current=f"순포지션 {int(net):,}계약 ({pct} OI, 주간 지연)",
        is_indicator=True,
    )


def _current_value_candidates(
    payload: WatchpointValuePayload,
) -> tuple[_CurrentValueCandidate, ...]:
    candidates: list[_CurrentValueCandidate] = []
    for anchor in payload.anchors:
        if not _anchor_belongs_to_segment(anchor, payload.segment):
            continue
        candidate = _anchor_candidate(anchor, segment=payload.segment)
        if candidate is not None:
            candidates.append(candidate)
    for item in payload.item_snapshots:
        builders = (
            (_coingecko_candidate, _fear_greed_candidate, _funding_candidate, _oi_candidate)
            if payload.segment == "crypto"
            else ()
        )
        for builder in builders:
            candidate = builder(item)
            if candidate is not None:
                candidates.append(candidate)
                break
        else:
            cftc_groups = _CFTC_CRYPTO_GROUPS if payload.segment == "crypto" else _CFTC_US_GROUPS
            if payload.segment != "domestic-equity":
                candidate = _cftc_candidate(item, groups=cftc_groups)
                if candidate is not None:
                    candidates.append(candidate)
    return tuple(candidates)


def _has_exact_signal_token(signal: str, token: str) -> bool:
    stripped = token.strip()
    if not stripped:
        return False
    escaped = re.escape(stripped)
    if stripped.isascii():
        return (
            re.search(
                rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])",
                signal,
                re.IGNORECASE,
            )
            is not None
        )
    return (
        re.search(
            rf"(?<![가-힣A-Za-z0-9]){escaped}(?![가-힣A-Za-z0-9])",
            signal,
            re.IGNORECASE,
        )
        is not None
    )


def _candidate_for_signal(
    signal: str,
    candidates: Sequence[_CurrentValueCandidate],
    *,
    source: str = "",
) -> _CurrentValueCandidate | None:
    best: _CurrentValueCandidate | None = None
    best_score = (-1, -1, -1, 0)
    for index, candidate in enumerate(candidates):
        matched_lengths = [
            len(token.strip())
            for token in candidate.match_tokens
            if _has_exact_signal_token(signal, token)
        ]
        if matched_lengths:
            source_specificity = int(
                any(
                    _has_exact_signal_token(f"{signal} {source}", token)
                    for token in candidate.source_tokens
                )
            )
            score = (
                int(candidate.is_indicator),
                max(matched_lengths),
                source_specificity,
                -index,
            )
            if score > best_score:
                best = candidate
                best_score = score
    return best


def resolve_watchpoint_currents(
    rows: Sequence[WatchpointRow],
    payload: WatchpointValuePayload,
) -> list[WatchpointRow]:
    """Resolve non-numeric current fields by exact signal token or drop them.

    Existing numeric current text is byte-preserved. A non-numeric value must
    match one canonical ticker/label/indicator token from the supplied payload;
    otherwise the row is omitted through the existing invalid-row flow.
    """

    candidates = _current_value_candidates(payload)
    resolved: list[WatchpointRow] = []
    for row in rows:
        source = _promote_source(
            row.source,
            row.current,
            row.bullish_trigger,
            row.bearish_trigger,
            row.implication,
        )
        promoted = replace(row, source=source)
        current = _normalise_field_text(row.current, default="")
        if _CURRENT_VALUE_RE.search(current):
            resolved.append(promoted)
            continue
        candidate = _candidate_for_signal(row.signal, candidates, source=source)
        if candidate is not None:
            resolved.append(replace(promoted, current=candidate.current))
    return resolved


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
    preserved_fragments: Sequence[str] = (),
    value_payload: WatchpointValuePayload | None = None,
) -> WatchpointRenderResult:
    """Rewrite §⑥ and return typed usable-card availability (pure).

    Idempotent: canonical cards and the collapsed :data:`DATA_LIMITED_NOTE`
    return unchanged on a same-day re-run, except that an explicit value
    payload may repair or drop a legacy non-numeric current field. The
    transform is bounded to the §⑥ body region; every other section and the
    disclaimer footer is byte-preserved. Exact caller-owned
    ``preserved_fragments`` inside §⑥ are treated as opaque bytes and reinserted
    ahead of the rewritten cards. The renderer neither parses nor reconstructs
    those fragments. Missing, empty, or unusable §⑥ content is explicitly
    `limited`.
    """
    if not text:
        raise ValueError("watchpoint input markdown must not be empty")
    if value_payload is not None:
        if segment is None:
            raise ValueError("watchpoint render segment is required with a value payload")
        if value_payload.segment != segment:
            raise ValueError("watchpoint value payload segment must match render segment")
    headers = list(_SECTION_HEADER_RE.finditer(text))
    for idx, match in enumerate(headers):
        if section_marker not in match.group("header"):
            continue
        body_start = match.end()
        body_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        body = text[body_start:body_end]
        watchpoint_body, owned_fragments = _extract_preserved_fragments(
            body,
            preserved_fragments,
        )
        # Idempotent (AC-87.7): accept only the exact complete card/note shape.
        existing_state = _existing_watchpoint_state(watchpoint_body)
        if existing_state is not None and existing_state[0] == "rendered":
            if value_payload is not None:
                parsed = _parse_existing_watchpoint_cards(watchpoint_body)
                assert parsed is not None
                existing_rows, omission = parsed
                resolved_rows = resolve_watchpoint_currents(existing_rows, value_payload)
                resolved_rows = [row for row in resolved_rows if _renderable_row(row)]
                if tuple(resolved_rows) != existing_rows:
                    content = (
                        render_matrix_table(resolved_rows) if resolved_rows else DATA_LIMITED_NOTE
                    )
                    if omission and resolved_rows:
                        content = f"{content}\n\n{omission}"
                    new_body = _compose_watchpoint_body(content, owned_fragments)
                    return WatchpointRenderResult(
                        markdown=text[:body_start] + new_body + text[body_end:],
                        state="rendered" if resolved_rows else "limited",
                        usable_card_count=len(resolved_rows),
                        limitation_reasons=() if resolved_rows else ("watchpoint_unavailable",),
                    )
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
        raw_bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(watchpoint_body)]
        bullets = [b for b in raw_bullets if _is_observation_bullet(b)]
        if not bullets and not coverage_limited:
            return WatchpointRenderResult(
                markdown=text,
                state="limited",
                usable_card_count=0,
                limitation_reasons=("watchpoint_unavailable",),
            )
        rows = build_watchpoint_rows(bullets, coverage_limited=coverage_limited)
        if value_payload is not None:
            rows = resolve_watchpoint_currents(rows, value_payload)
        rows = [r for r in rows if _renderable_row(r)]
        # u87 Step 3 — collapse an all-데이터부족 (or empty) result to the single
        # pinned note instead of a ≥2-row wall of 데이터부족 (AC-87.4).
        if not rows:
            _logger.info(
                "watchpoint_matrix.data_limited_rows",
                extra={"segment": segment, "count": len(bullets)},
            )
            new_body = _compose_watchpoint_body(DATA_LIMITED_NOTE, owned_fragments)
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
        new_body = _compose_watchpoint_body(f"{cards}{suffix}", owned_fragments)
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


def render_watchpoint_rows_result(
    text: str,
    rows: Sequence[WatchpointRow],
    *,
    section_marker: str = "⑥",
    segment: str | None = None,
    preserved_fragments: Sequence[str] = (),
) -> WatchpointRenderResult:
    """Replace §⑥ with already-validated synthesized rows."""

    if not text:
        raise ValueError("watchpoint input markdown must not be empty")
    rendered_rows = tuple(row for row in rows if _renderable_row(row))[:MAX_VISIBLE_ROWS]
    headers = list(_SECTION_HEADER_RE.finditer(text))
    for idx, match in enumerate(headers):
        if section_marker not in match.group("header"):
            continue
        body_start = match.end()
        body_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        body = text[body_start:body_end]
        _, owned_fragments = _extract_preserved_fragments(body, preserved_fragments)
        content = render_matrix_table(list(rendered_rows)) if rendered_rows else DATA_LIMITED_NOTE
        new_body = _compose_watchpoint_body(content, owned_fragments)
        return WatchpointRenderResult(
            markdown=text[:body_start] + new_body + text[body_end:],
            state="rendered" if rendered_rows else "limited",
            usable_card_count=len(rendered_rows),
            limitation_reasons=() if rendered_rows else ("watchpoint_unavailable",),
            synthesized_card_count=len(rendered_rows),
        )
    _logger.info(
        "watchpoint_matrix.synthesized_section_missing",
        extra={"segment": segment, "count": len(rendered_rows)},
    )
    return WatchpointRenderResult(
        markdown=text,
        state="limited",
        usable_card_count=0,
        limitation_reasons=("watchpoint_unavailable",),
    )


def matching_watchpoint_rows(
    text: str,
    rows: Sequence[WatchpointRow],
    *,
    section_marker: str = "⑥",
    preserved_fragments: Sequence[str] = (),
) -> tuple[WatchpointRow, ...]:
    """Recognize an exact canonical deterministic-row subset.

    The quality marker is deliberately not embedded in public Markdown. On an
    idempotent re-entry, exact equality with rows derivable from the same
    frozen payload restores the typed diagnostic count without fuzzy matching.
    """

    if not text or not rows:
        return ()
    rendered_rows = tuple(row for row in rows if _renderable_row(row))[:MAX_VISIBLE_ROWS]
    if not rendered_rows:
        return ()
    headers = list(_SECTION_HEADER_RE.finditer(text))
    for idx, match in enumerate(headers):
        if section_marker not in match.group("header"):
            continue
        body_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        watchpoint_body, _ = _extract_preserved_fragments(
            text[match.end() : body_end],
            preserved_fragments,
        )
        existing_state = _existing_watchpoint_state(watchpoint_body)
        if existing_state is None or existing_state[0] != "rendered":
            return ()
        existing_count = existing_state[1]
        if existing_count > len(rendered_rows):
            return ()
        for subset in combinations(rendered_rows, existing_count):
            expected = wrap_numbers_bold(render_matrix_table(list(subset)))
            if watchpoint_body.strip() == expected:
                return tuple(subset)
        return ()
    return ()


def matching_watchpoint_row_count(
    text: str,
    rows: Sequence[WatchpointRow],
    *,
    section_marker: str = "⑥",
    preserved_fragments: Sequence[str] = (),
) -> int:
    """Compatibility count view over :func:`matching_watchpoint_rows`."""

    return len(
        matching_watchpoint_rows(
            text,
            rows,
            section_marker=section_marker,
            preserved_fragments=preserved_fragments,
        )
    )


def _extract_preserved_fragments(
    body: str,
    preserved_fragments: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    """Remove exact caller-owned fragments without interpreting their bytes."""

    ordered = tuple(preserved_fragments)
    if any(not fragment for fragment in ordered):
        raise ValueError("preserved watchpoint fragments must not be empty")
    if len(set(ordered)) != len(ordered):
        raise ValueError("preserved watchpoint fragments must be unique")
    remainder = body
    found: list[str] = []
    for fragment in ordered:
        count = remainder.count(fragment)
        if count > 1:
            raise ValueError("preserved watchpoint fragment must occur at most once")
        if count == 1:
            remainder = remainder.replace(fragment, "", 1)
            found.append(fragment)
    return remainder, tuple(found)


def _compose_watchpoint_body(content: str, preserved_fragments: Sequence[str]) -> str:
    """Compose §⑥ while retaining every opaque fragment byte-for-byte."""

    body = "\n\n"
    for fragment in preserved_fragments:
        body += fragment
        if not fragment.endswith(("\n", "\r")):
            body += "\n"
    if preserved_fragments:
        body += "\n"
    body += content
    if not body.endswith(("\n", "\r")):
        body += "\n"
    return body


def render_watchpoint_matrix(
    text: str,
    *,
    section_marker: str = "⑥",
    segment: str | None = None,
    coverage_limited: bool = False,
    value_payload: WatchpointValuePayload | None = None,
) -> str:
    """Compatibility string view with no default segmented production caller."""

    if not text:
        return text
    return render_watchpoint_matrix_result(
        text,
        section_marker=section_marker,
        segment=segment,
        coverage_limited=coverage_limited,
        value_payload=value_payload,
    ).markdown


__all__ = [
    "CONFIDENCE_LABELS",
    "DATA_LIMITED_CONFIDENCE",
    "DATA_LIMITED_NOTE",
    "MATRIX_COLUMNS",
    "MAX_VISIBLE_ROWS",
    "ConfidenceLabel",
    "WatchpointItemSnapshot",
    "WatchpointRenderResult",
    "WatchpointRenderState",
    "WatchpointRow",
    "WatchpointValuePayload",
    "build_watchpoint_rows",
    "matching_watchpoint_row_count",
    "matching_watchpoint_rows",
    "render_matrix_table",
    "render_watchpoint_matrix",
    "render_watchpoint_matrix_result",
    "render_watchpoint_rows_result",
    "resolve_watchpoint_currents",
]
