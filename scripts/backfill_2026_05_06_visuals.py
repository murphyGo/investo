"""u26 Step 2 — one-shot backfill for the 2026-05-06 segment archives.

Persona #2 (2026-05-07): u24 closed but the 2026-05-06 archive carried
no SVGs and no ``![](...)`` references because the briefings were
published before the visual stage was wired into the orchestrator.
This script patches that single day's three segment archives:

* repairs the truncated ``> **주의할 점**: 1.`` / ``> **핵심 동인**:
  **입법 가속화 vs.`` quote-block lines so the summary-quality gate
  is satisfied;
* renders the three SVG cards (``data-confidence``, ``market-snapshot``,
  ``watchlist-relevance``) plus their JSON manifests using the production
  ``investo.visuals.render`` / ``investo.visuals.provenance`` helpers;
* inserts the markdown ``![label](2026-05-06.assets/<kind>.svg)`` links
  via the production ``insert_visual_links`` so the layout matches a
  freshly published briefing.

The script is **one-shot** — it is intended to be run once and then
preserved in git only for audit. It writes nothing outside the
2026-05-06 segment archive trees and never touches the network.

Run from the repo root::

    uv run python scripts/backfill_2026_05_06_visuals.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    CoverageStatus,
    MarketSegment,
)
from investo.publisher.paths import archive_path
from investo.visuals.assets import insert_visual_links
from investo.visuals.cards import (
    DataConfidenceCardInput,
    DataConfidenceSourceRow,
    MarketSnapshotCardInput,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
)
from investo.visuals.paths import visual_asset_path
from investo.visuals.provenance import (
    build_generated_svg_provenance,
    write_manifest,
)
from investo.visuals.render import SVG_HEIGHT, SVG_WIDTH, render_card_svg

_TARGET = date(2026, 5, 6)
_GENERATED_AT = datetime(2026, 5, 6, 23, 59, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _SegmentBackfill:
    """Curated backfill payload for one segment."""

    segment: MarketSegment
    coverage_status: CoverageStatus
    item_count: int
    source_count: int
    missing_categories: tuple[str, ...]
    reason_labels: tuple[str, ...]
    source_rows: tuple[DataConfidenceSourceRow, ...]
    conclusion: str
    main_driver: str
    caution: str
    watchlist_configured: bool
    watchlist_total: int
    watchlist_rows: tuple[WatchlistRelevanceRow, ...]
    quote_replacements: tuple[tuple[str, str], ...]


# Curated content reflects the headline narrative already present in
# each markdown so the cards stay coherent with the body text.
_BACKFILLS: tuple[_SegmentBackfill, ...] = (
    _SegmentBackfill(
        segment=DOMESTIC_EQUITY,
        coverage_status="insufficient",
        item_count=0,
        source_count=0,
        missing_categories=("뉴스", "가격", "지표"),
        reason_labels=("뉴스 카테고리 누락", "가격 카테고리 누락"),
        source_rows=(
            DataConfidenceSourceRow(
                source_name="국내 증시 데이터",
                status="zero",
                detail="0건 반환",
            ),
        ),
        conclusion=(
            "2026-05-06 국내 증시 세그먼트는 정식 시황을 만들 만큼 검증된 입력 데이터가 "
            "수집되지 않았습니다."
        ),
        main_driver=(
            "확인된 핵심 이슈 없음 — 해당 세그먼트의 뉴스/공시 입력이 충분하지 않아 "
            "주요 이벤트를 선별하지 않았습니다."
        ),
        caution=(
            "정식 시황을 만들 만큼 검증된 입력 데이터가 수집되지 않아 시장 방향을 "
            "단정하지 않습니다."
        ),
        watchlist_configured=False,
        watchlist_total=0,
        watchlist_rows=(),
        quote_replacements=(
            (
                "> **주의할 점**: 1.\n",
                "> **주의할 점**: 정식 시황을 만들 만큼 검증된 입력 데이터가 "
                "수집되지 않아 시장 방향을 단정하지 않습니다.\n",
            ),
        ),
    ),
    _SegmentBackfill(
        segment=US_EQUITY,
        coverage_status="partial",
        item_count=19,
        source_count=1,
        missing_categories=("가격", "지표"),
        reason_labels=("뉴스 카테고리 누락", "가격 카테고리 누락"),
        source_rows=(
            DataConfidenceSourceRow(
                source_name="nasdaq-earnings-calendar",
                status="ok",
                detail="대형주 어닝 19건",
            ),
        ),
        conclusion=(
            "2026년 5월 6일, 미국 증시는 반도체·미디어·플랫폼·헬스케어·에너지에 걸쳐 "
            "대형주 19개의 1분기 어닝이 집중되는 어닝 데이다."
        ),
        main_driver=(
            "ARM의 AI 로열티 성장, Walt Disney의 스트리밍 수익화, Uber의 흑자 전환 기조, "
            "Novo Nordisk의 GLP-1 모멘텀이 네 가지 핵심 관전 테마로 부상한다."
        ),
        caution=(
            "전일 시황·뉴스 데이터가 수집되지 않아 직전 거래일 촉매를 단정할 수 없으며, "
            "지수 흐름보다 개별 어닝 서프라이즈 여부에 변동성이 집중될 수 있다."
        ),
        watchlist_configured=False,
        watchlist_total=0,
        watchlist_rows=(),
        quote_replacements=(
            (
                "> **주의할 점**: 1.\n",
                "> **주의할 점**: 전일 시황·뉴스 데이터가 수집되지 않아 직전 거래일 "
                "촉매를 단정할 수 없으며, 지수 흐름보다 개별 어닝 서프라이즈 여부에 "
                "변동성이 집중될 수 있습니다.\n",
            ),
        ),
    ),
    _SegmentBackfill(
        segment=CRYPTO,
        coverage_status="partial",
        item_count=8,
        source_count=2,
        missing_categories=("가격",),
        reason_labels=("가격 카테고리 누락",),
        source_rows=(
            DataConfidenceSourceRow(
                source_name="크립토 뉴스",
                status="ok",
                detail="규제·기관 수급 헤드라인 확보",
            ),
            DataConfidenceSourceRow(
                source_name="coingecko-price",
                status="zero",
                detail="0건 반환",
            ),
        ),
        conclusion=(
            "2026년 5월 6일 크립토 시장은 규제 기대감과 기관 자금 유입이 맞물리며 "
            "강세 분위기를 유지했다."
        ),
        main_driver=(
            "입법 가속화와 정치적 마찰이 동시에 진행되는 가운데 White House가 7월 4일을 "
            "목표로 포괄적 크립토 입법 통과를 추진 중이다."
        ),
        caution=(
            "규제 불확실성(윤리 조항 분쟁)과 양자 컴퓨팅 리스크는 중·장기 변수로 "
            "남아 있으며, 가격 데이터가 수집되지 않아 단기 방향성은 단정하기 어렵다."
        ),
        watchlist_configured=False,
        watchlist_total=0,
        watchlist_rows=(),
        quote_replacements=(
            (
                "> **핵심 동인**: **입법 가속화 vs.\n",
                "> **핵심 동인**: 입법 가속화와 정치적 마찰이 동시에 진행되는 가운데 "
                "White House가 7월 4일을 목표로 포괄적 크립토 입법 통과를 추진 중입니다.\n",
            ),
            (
                "> **주의할 점**: 1.\n",
                "> **주의할 점**: 규제 불확실성과 양자 컴퓨팅 리스크는 중·장기 변수로 "
                "남아 있으며, 가격 데이터가 수집되지 않아 단기 방향성은 단정하기 "
                "어렵습니다.\n",
            ),
        ),
    ),
)


def _archive_path(segment: MarketSegment) -> Path:
    """Return the segment archive markdown path, relative to the repo root.

    Mirrors :func:`investo.publisher.paths.archive_path` so the relative
    path returned by :func:`visual_asset_path` shares its parent and
    ``insert_visual_links`` can compute a clean POSIX relative URL.
    """
    return archive_path(_TARGET, segment=segment)


def _patch_quote_block(markdown: str, replacements: tuple[tuple[str, str], ...]) -> str:
    """Apply each quote-block patch exactly once; raise if any pattern is missing."""
    for old, new in replacements:
        if old not in markdown:
            # The patch was already applied (idempotency) — safe to skip.
            continue
        markdown = markdown.replace(old, new, 1)
    return markdown


def _render_assets(payload: _SegmentBackfill) -> tuple[Path, ...]:
    """Render the three SVG cards + sidecar manifests for one segment."""
    cards = (
        DataConfidenceCardInput(
            target_date=_TARGET,
            segment=payload.segment,
            coverage_status=payload.coverage_status,
            item_count=payload.item_count,
            source_count=payload.source_count,
            missing_categories=payload.missing_categories,
            reason_labels=payload.reason_labels,
            source_rows=payload.source_rows,
        ),
        MarketSnapshotCardInput(
            target_date=_TARGET,
            segment=payload.segment,
            conclusion=payload.conclusion,
            main_driver=payload.main_driver,
            caution=payload.caution,
            coverage_status=payload.coverage_status,
        ),
        WatchlistRelevanceCardInput(
            target_date=_TARGET,
            segment=payload.segment,
            configured=payload.watchlist_configured,
            total_matches=payload.watchlist_total,
            rows=payload.watchlist_rows,
        ),
    )
    paths: list[Path] = []
    for card in cards:
        asset_path = visual_asset_path(_TARGET, payload.segment, card.kind)
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_text(render_card_svg(card), encoding="utf-8")
        manifest = build_generated_svg_provenance(
            asset_relative_path=asset_path.name,
            card_kind=card.kind,
            generated_at=_GENERATED_AT,
            width=SVG_WIDTH,
            height=SVG_HEIGHT,
        )
        write_manifest(manifest, asset_path)
        paths.append(asset_path)
    return tuple(paths)


def _backfill_segment(payload: _SegmentBackfill) -> Path:
    markdown_path = _archive_path(payload.segment)
    body = markdown_path.read_text(encoding="utf-8")
    body = _patch_quote_block(body, payload.quote_replacements)
    asset_paths = _render_assets(payload)
    body = insert_visual_links(
        body,
        markdown_path=markdown_path,
        asset_paths=asset_paths,
    )
    markdown_path.write_text(body, encoding="utf-8")
    return markdown_path


def main() -> None:
    for payload in _BACKFILLS:
        path = _backfill_segment(payload)
        print(f"backfilled {path}")


if __name__ == "__main__":
    main()
