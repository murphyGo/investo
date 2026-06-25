"""Offline replay checks for generated briefing artifacts.

The replay harness reads already-published archive markdown and metadata.
It never calls sources, never calls an LLM, and never mutates archive files.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, Literal

from investo._internal.summary_quality import (
    SummaryQualityError,
    validate_first_viewport_summary,
)
from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment
from investo.publisher.quality_consistency import (
    build_canonical_snapshot,
    check_quality_consistency,
    load_quality_history_row,
)
from investo.publisher.reader_format import check_watchpoint_actionability

ReplaySeverity = Literal["error", "warning"]

_SEGMENTS: Final[tuple[MarketSegment, ...]] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
_BODY_USED_ZERO_RE: Final[re.Pattern[str]] = re.compile(r"본문 사용 0")
_TRACE_OR_SOURCE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:##\s*Trace|trace_id|source=|출처|https?://)",
    re.IGNORECASE,
)
_NAV_LABELS: Final[dict[MarketSegment, str]] = {
    DOMESTIC_EQUITY: "국내 증시",
    US_EQUITY: "미국 증시",
    CRYPTO: "크립토",
}
_BTC_BTM_RE: Final[re.Pattern[str]] = re.compile(r"\bBTC\b[^;\n]*\bBTM\b|\bBTM\b[^;\n]*\bBTC\b")

# u70 — cross-surface anchor parity. The anchor table renders one row per
# core symbol as ``| <ticker> | <price> | <pct> | <note> |``; the compact
# chart card carries ``data-ticker="<ticker>" ... data-close="<price>"``.
# These two surfaces consume the same reconciled payload, so for any
# symbol present in both the numeric close must match. A mismatch means a
# surface re-formatted or re-derived the value independently — exactly the
# drift u70 forbids.
_ANCHOR_ROW_RE: Final[re.Pattern[str]] = re.compile(
    r"^\|\s*(?P<ticker>[\^A-Za-z][\w\-^=]*)\s*\|\s*(?P<price>[\d,]+(?:\.\d+)?)\s*\|",
    re.MULTILINE,
)
_CHART_DIV_RE: Final[re.Pattern[str]] = re.compile(
    r'data-ticker="(?P<ticker>[^"]+)"[^>]*?data-close="(?P<close>[^"]+)"',
)
# u75 — the externalised chart-history sidecar reference. The compact card
# still renders from the inline summary attributes even when the sidecar
# file is absent, so a missing sidecar is a payload *warning*, not an error.
_CHART_SIDECAR_RE: Final[re.Pattern[str]] = re.compile(r'data-history-src="(?P<src>[^"]+)"')
# Nasdaq Composite (^IXIC) must never be labelled Nasdaq 100.
_IXIC_MISLABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"\^IXIC[^\n]{0,80}(?:Nasdaq\s*100|나스닥\s*100)"
)


@dataclass(frozen=True, slots=True)
class ReplayFinding:
    severity: ReplaySeverity
    segment: MarketSegment | None
    code: str
    message: str


def replay_generated_briefing_quality(
    target_date: date,
    *,
    archive_root: Path = Path("archive"),
    segments: tuple[MarketSegment, ...] = _SEGMENTS,
    quality_history_path: Path | None = None,
    quality_page_path: Path | None = None,
) -> tuple[ReplayFinding, ...]:
    """Replay offline quality checks for a generated bundle.

    u69 — when ``quality_page_path`` points at a generated
    ``site_docs/quality.md`` the canonical cross-surface consistency
    validator runs too; if the artifact is absent the consistency
    subset still compares segment status blocks against the
    quality-history row and records ``quality.quality_page_missing`` as
    *skipped* (not a failure). Pure read; never mutates archive files.
    """
    findings: list[ReplayFinding] = []
    present: dict[MarketSegment, str] = {}
    for segment in segments:
        path = _segment_path(archive_root, target_date, segment)
        if not path.exists():
            findings.append(
                ReplayFinding(
                    "warning",
                    segment,
                    "segment-missing",
                    f"{target_date.isoformat()} {segment} artifact is missing",
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        present[segment] = text
        findings.extend(_check_markdown(segment, text, markdown_path=path))

    findings.extend(_check_navigation(target_date, present))
    resolved_history_path = (
        quality_history_path
        if quality_history_path is not None
        else archive_root / "_meta" / "quality_history.jsonl"
    )
    findings.extend(
        _check_quality_history(
            target_date,
            quality_history_path=resolved_history_path,
        )
    )
    findings.extend(
        _check_quality_consistency(
            target_date,
            segment_texts=present,
            quality_history_path=resolved_history_path,
            quality_page_path=quality_page_path,
        )
    )
    return tuple(findings)


def _check_quality_consistency(
    target_date: date,
    *,
    segment_texts: dict[MarketSegment, str],
    quality_history_path: Path,
    quality_page_path: Path | None,
) -> tuple[ReplayFinding, ...]:
    """u69 — run the canonical cross-surface consistency validator."""
    if not segment_texts:
        return ()
    history_row = load_quality_history_row(target_date, quality_history_path)
    snapshot = build_canonical_snapshot(
        target_date,
        segment_texts=segment_texts,
        history_row=history_row,
    )
    quality_page_text: str | None = None
    if quality_page_path is not None and quality_page_path.exists():
        quality_page_text = quality_page_path.read_text(encoding="utf-8")
    consistency = check_quality_consistency(snapshot, quality_page_text=quality_page_text)
    findings: list[ReplayFinding] = []
    for finding in consistency:
        if finding.skipped:
            findings.append(
                ReplayFinding("warning", finding.segment, finding.code, finding.message)
            )
            continue
        findings.append(ReplayFinding("error", finding.segment, finding.code, finding.message))
    return tuple(findings)


def _check_markdown(
    segment: MarketSegment,
    text: str,
    *,
    markdown_path: Path,
) -> tuple[ReplayFinding, ...]:
    findings: list[ReplayFinding] = []
    try:
        validate_first_viewport_summary(text)
    except SummaryQualityError as exc:
        findings.append(ReplayFinding("error", segment, "first-viewport", str(exc)))
    if _BODY_USED_ZERO_RE.search(text) and _TRACE_OR_SOURCE_RE.search(text):
        findings.append(
            ReplayFinding(
                "warning",
                segment,
                "body-used-zero-with-evidence",
                "`본문 사용 0` appears alongside trace/source evidence",
            )
        )
    if _BTC_BTM_RE.search(text):
        findings.append(
            ReplayFinding(
                "error",
                segment,
                "watchlist-btc-btm",
                "BTC appears to be associated with BTM in watchlist text",
            )
        )
    for _bullet in check_watchpoint_actionability(text, segment=segment):
        findings.append(
            ReplayFinding(
                "warning",
                segment,
                "watchpoint-actionability",
                "watchpoint lacks source/trigger/implication structure",
            )
        )
        break
    findings.extend(_check_anchor_cross_surface(segment, text))
    findings.extend(_check_chart_sidecars(segment, text, markdown_path=markdown_path))
    return tuple(findings)


def _check_chart_sidecars(
    segment: MarketSegment,
    text: str,
    *,
    markdown_path: Path,
) -> tuple[ReplayFinding, ...]:
    """u75 — every ``data-history-src`` must resolve to a staged sidecar file.

    A missing sidecar is a *warning* (``chart-sidecar-missing``): the
    compact card still renders ticker/price/change from the inline summary
    attributes, so the page degrades gracefully rather than failing the
    publish gate. Reachability is checked by resolving the relative URL
    against the markdown file's directory — exactly how the browser
    resolves ``data-history-src`` on GitHub Pages.
    """
    findings: list[ReplayFinding] = []
    for match in _CHART_SIDECAR_RE.finditer(text):
        src = match.group("src")
        sidecar_path = (markdown_path.parent / src).resolve()
        if not sidecar_path.is_file():
            findings.append(
                ReplayFinding(
                    "warning",
                    segment,
                    "chart-sidecar-missing",
                    f"chart sidecar {src} is not staged next to the briefing",
                )
            )
    return tuple(findings)


def _normalise_price(raw: str) -> str:
    """Canonicalise a displayed price for cross-surface comparison.

    Strips thousands separators and a trailing ``.0`` / ``.00`` so the
    table's ``26,274.13`` and the chart card's ``26274.13`` compare equal
    without depending on either surface's formatting choices.
    """
    cleaned = raw.replace(",", "").strip()
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned or "0"


def _check_anchor_cross_surface(segment: MarketSegment, text: str) -> tuple[ReplayFinding, ...]:
    """u70 — table close, chart-card close, and ^IXIC label must agree."""
    findings: list[ReplayFinding] = []
    if _IXIC_MISLABEL_RE.search(text):
        findings.append(
            ReplayFinding(
                "error",
                segment,
                "anchor-ixic-mislabel",
                "^IXIC labelled as Nasdaq 100 (it is the Nasdaq Composite)",
            )
        )
    table_close = {
        m.group("ticker"): _normalise_price(m.group("price")) for m in _ANCHOR_ROW_RE.finditer(text)
    }
    for m in _CHART_DIV_RE.finditer(text):
        ticker = m.group("ticker")
        chart_close = _normalise_price(m.group("close"))
        table_value = table_close.get(ticker)
        if table_value is not None and table_value != chart_close:
            findings.append(
                ReplayFinding(
                    "error",
                    segment,
                    "anchor-close-divergence",
                    f"{ticker} close differs: table={table_value} chart={chart_close}",
                )
            )
    return tuple(findings)


def _check_navigation(
    target_date: date,
    present: dict[MarketSegment, str],
) -> tuple[ReplayFinding, ...]:
    if not present:
        return ()
    findings: list[ReplayFinding] = []
    partial = len(present) < len(_SEGMENTS)
    for segment, text in present.items():
        for expected_segment, label in _NAV_LABELS.items():
            if label not in text:
                findings.append(
                    ReplayFinding(
                        "warning" if partial else "error",
                        segment,
                        "segment-nav-missing",
                        f"{target_date.isoformat()} nav omits {expected_segment}",
                    )
                )
    return tuple(findings)


def _check_quality_history(
    target_date: date,
    *,
    quality_history_path: Path,
) -> tuple[ReplayFinding, ...]:
    if not quality_history_path.exists():
        return (
            ReplayFinding(
                "warning",
                None,
                "quality-history-missing",
                f"{quality_history_path} is missing",
            ),
        )
    row = _quality_history_row(target_date, quality_history_path)
    if row is None:
        return (
            ReplayFinding(
                "warning",
                None,
                "quality-history-date-missing",
                f"{target_date.isoformat()} has no quality-history row",
            ),
        )
    return ()


def _quality_history_row(target_date: date, path: Path) -> dict[str, object] | None:
    wanted = target_date.isoformat()
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("date") == wanted:
                return parsed
    return None


def _segment_path(archive_root: Path, target_date: date, segment: MarketSegment) -> Path:
    return (
        archive_root
        / segment
        / f"{target_date.year:04d}"
        / f"{target_date.month:02d}"
        / f"{target_date.isoformat()}.md"
    )


__all__ = [
    "ReplayFinding",
    "replay_generated_briefing_quality",
]
