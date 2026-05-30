"""Tests for u86 curated-asset pipeline hero injection (R9 / AC-1.4 / AC-1.5)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import build_segment_coverage
from investo.briefing.watchlist import WatchlistConfig, match_watchlist_items
from investo.models import Briefing, NormalizedItem
from investo.visuals.assets import prepare_segment_visual_assets
from investo.visuals.curated import CuratedSelection, load_library
from tests.unit.visuals._image_bytes import VALID_PNG_BYTES

_TARGET = date(2026, 5, 7)


def _briefing() -> Briefing:
    rendered = (
        "# 2026-05-07 미국 증시 시황\n\n"
        "> **데이터 상태**: 정상 — 수집 1건 / 소스 1개 / 누락: 없음\n"
        "> **오늘의 결론**: 미국 증시는 반등했습니다.\n\n"
        "## ① 요약\n반등.\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n"
        f"{DISCLAIMER}"
    )
    return Briefing(
        target_date=_TARGET,
        market_summary="미국 증시는 반등했습니다.",
        key_issues="이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered,
    )


def _item(title: str) -> NormalizedItem:
    return NormalizedItem(
        source_name="news",
        category="news",
        title=title,
        url="https://example.com/x",
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        raw_metadata={},
    )


def _seed_filed_library(tmp_path: Path) -> dict:
    folder = tmp_path / "library" / "person"
    folder.mkdir(parents=True)
    payload = {
        "kind": "curated-licensed",
        "source_url": "https://www.federalreserve.gov/x.png",
        "license": "public-domain",
        "attribution": "Federal Reserve official portrait",
        "author": "Federal Reserve Board",
        "fetched_on": "2026-05-28",
        "allowed_use": "public republish",
    }
    (folder / "jerome-powell.manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    (folder / "jerome-powell.png").write_bytes(VALID_PNG_BYTES)
    return load_library(tmp_path / "library")


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection: CuratedSelection | None,
) -> object:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    items = (_item("Powell signals patience at FOMC"),)
    coverage = build_segment_coverage("us-equity", items)
    impact = match_watchlist_items(items, WatchlistConfig())
    return prepare_segment_visual_assets(
        _briefing(),
        target_date=_TARGET,
        segment="us-equity",
        items=items,
        coverage=coverage,
        watchlist_impact=impact,
        curated_selection=selection,
    )


def test_curated_hero_rendered_with_caption_and_disclaimer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = _seed_filed_library(tmp_path)
    selection = CuratedSelection(
        asset=library["jerome-powell"],
        matched_key="person:jerome-powell",
        match_reason="boundary-term",
    )
    prepared = _prepare(tmp_path, monkeypatch, selection)
    markdown = prepared.briefing.rendered_markdown
    # The curated image is rendered as a hero with a provenance caption.
    assert "![큐레이션 시황 이미지]" in markdown
    assert "출처: 외부 라이선스 이미지" in markdown
    # Disclaimer remains intact (R9).
    assert DISCLAIMER in markdown
    # A copied binary + provenance sidecar landed under the asset dir.
    copied = [p for p in prepared.asset_paths if p.stem == "curated-context-image"]
    assert copied and copied[0].exists()


def test_curated_hero_outranks_ai_but_caption_no_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = _seed_filed_library(tmp_path)
    selection = CuratedSelection(asset=library["jerome-powell"], matched_key="person:jerome-powell")
    prepared = _prepare(tmp_path, monkeypatch, selection)
    markdown = prepared.briefing.rendered_markdown
    # Hero is above the reader-status block (above the fold).
    assert markdown.index("![큐레이션 시황 이미지]") < markdown.index("> **데이터 상태**")
    assert "[REDACTED" not in markdown  # nothing secret-shaped to redact here


def test_no_selection_falls_back_no_curated_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepare(tmp_path, monkeypatch, None)
    markdown = prepared.briefing.rendered_markdown
    assert "큐레이션 시황 이미지" not in markdown
    assert DISCLAIMER in markdown
    # data-confidence remains the guaranteed fallback hero.
    assert "![데이터 신뢰도]" in markdown


def test_deferred_selection_does_not_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A selection carrying asset=None (deferred / no-match) renders nothing.
    prepared = _prepare(tmp_path, monkeypatch, CuratedSelection(asset=None))
    assert "큐레이션 시황 이미지" not in prepared.briefing.rendered_markdown


def test_curated_path_makes_no_http_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # AC-1.5 — guard: any httpx call on the curated path explodes the test.
    import httpx

    def _boom(*_a: object, **_k: object) -> object:
        raise AssertionError("curated path must not perform any network call (AC-1.5)")

    monkeypatch.setattr(httpx.Client, "get", _boom)
    library = _seed_filed_library(tmp_path)
    selection = CuratedSelection(asset=library["jerome-powell"], matched_key="person:jerome-powell")
    prepared = _prepare(tmp_path, monkeypatch, selection)
    assert "![큐레이션 시황 이미지]" in prepared.briefing.rendered_markdown
