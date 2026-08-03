"""U-141 final-body-centered semantic image selection contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from investo._internal.archive_layout import ArchiveLayout
from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import build_segment_coverage
from investo.briefing.watchlist import WatchlistConfig, match_watchlist_items
from investo.models import Briefing, NormalizedItem
from investo.visuals.assets import prepare_segment_visual_assets
from investo.visuals.image_library import (
    append_candidates,
    candidate_id_for_url,
    clearances_dir_for,
    store_binary_path,
    store_sidecar_path,
    update_index,
)
from investo.visuals.image_selection import (
    article_url_offset,
    build_image_narrative_context,
    filter_items_for_hero_context,
    insert_image_source_card,
    render_image_source_card,
    select_image_usage,
)
from investo.visuals.provenance import (
    build_external_provenance,
    read_manifest,
    write_manifest,
)
from tests.unit.visuals._image_bytes import make_png

_TARGET = date(2026, 8, 3)


def _item(
    *,
    item_url: str,
    image_url: str,
    title: str,
    width: int = 800,
    height: int = 450,
    segment: str = "us-equity",
    credit: str | None = None,
) -> tuple[str, NormalizedItem]:
    metadata: dict[str, str | int] = {
        "image_url": image_url,
        "image_width": width,
        "image_height": height,
        "image_mime": "image/png",
    }
    if credit is not None:
        metadata["image_credit"] = credit
    return (
        segment,
        NormalizedItem(
            source_name="test-news",
            category="news",
            title=title,
            url=item_url,
            published_at=datetime(2026, 8, 3, 8, 0, tzinfo=UTC),
            raw_metadata=metadata,
        ),
    )


def _append(root: Path, *entries: tuple[str, NormalizedItem]) -> None:
    routed: dict[str, list[NormalizedItem]] = {}
    for segment, item in entries:
        routed.setdefault(segment, []).append(item)
    append_candidates(_TARGET, routed, ledger_root=root)  # type: ignore[arg-type]


def _clear_and_store(
    ledger_root: Path,
    store_root: Path,
    *,
    image_url: str,
    width: int = 800,
    height: int = 450,
) -> str:
    candidate_id = candidate_id_for_url(image_url)
    clearance = {
        "kind": "explicit-license",
        "source_url": image_url,
        "license": "CC0",
        "attribution": "Example image",
        "author": "Example author",
        "fetched_on": _TARGET.isoformat(),
        "allowed_use": "public republish",
    }
    clearance_path = clearances_dir_for(ledger_root=ledger_root) / (f"{candidate_id}.manifest.json")
    clearance_path.parent.mkdir(parents=True, exist_ok=True)
    clearance_path.write_text(json.dumps(clearance), encoding="utf-8")

    content = make_png(width, height)
    binary_path = store_binary_path(candidate_id, ".png", store_root=store_root)
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_bytes(content)
    manifest = build_external_provenance(
        asset_relative_path=f"assets/images/{candidate_id[:2]}/{binary_path.name}",
        card_kind="external-context-image",
        generated_at=datetime(2026, 8, 3, tzinfo=UTC),
        width=width,
        height=height,
        content_type="image/png",
        license_name="CC0",
        attribution="Example image",
        author="Example author",
        allowed_use="public republish",
        fetched_from_host="img.example.com",
        additional_metadata={
            "candidate_id": candidate_id,
            "content_sha256": hashlib.sha256(content).hexdigest(),
        },
    )
    write_manifest(
        manifest,
        binary_path,
        sidecar_path=store_sidecar_path(binary_path),
    )
    return candidate_id


def _briefing(first_url: str, *, second_url: str | None = None, first_text: str = "상승") -> str:
    second = ""
    if second_url is not None:
        second = f"\n### 둘째 이슈\n\n[둘째 기사]({second_url}) 보도.\n"
    return (
        "# 미국 증시 시황\n"
        f"> **오늘의 결론**: 첫 기사가 {first_text}을 설명합니다.\n"
        f"> **핵심 동인**: [첫 기사]({first_url})가 핵심입니다.\n\n"
        "## ② 전일 핵심 이슈\n\n"
        f"### 첫 이슈\n\n[첫 기사]({first_url}) 보도.\n"
        f"{second}\n"
        "## ③ 섹터/수급 동향\n\n후속 섹션\n"
    )


def test_context_limits_hero_to_first_issue_story() -> None:
    first = "https://news.example.com/first"
    second = "https://news.example.com/second"
    context = build_image_narrative_context("us-equity", _briefing(first, second_url=second))
    assert first in context.hero_markdown
    assert second not in context.hero_markdown
    assert second in context.issue_markdown


def test_exact_body_lineage_selects_cleared_hero_and_distinct_card(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store_root = tmp_path / "store"
    hero_url = "https://news.example.com/hero"
    card_url = "https://news.example.com/card"
    hero_image = "https://img.example.com/hero.png"
    card_image = "https://img.example.com/card.png"
    _append(
        ledger_root,
        _item(item_url=hero_url, image_url=hero_image, title="Hero story", credit="CC0"),
        _item(item_url=card_url, image_url=card_image, title="Card story"),
    )
    hero_id = _clear_and_store(ledger_root, store_root, image_url=hero_image)
    update_index(_TARGET, ledger_root=ledger_root)

    context = build_image_narrative_context(
        "us-equity",
        _briefing(hero_url, second_url=card_url),
    )
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=ledger_root,
        store_root=store_root,
    )
    assert selected.hero is not None
    assert selected.hero.candidate.candidate_id == hero_id
    assert selected.card_candidate is not None
    assert selected.card_candidate.item_url == card_url


def test_cleared_but_unreferenced_candidate_is_not_selected(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store_root = tmp_path / "store"
    item_url = "https://news.example.com/unrelated"
    image_url = "https://img.example.com/unrelated.png"
    _append(ledger_root, _item(item_url=item_url, image_url=image_url, title="Unrelated"))
    _clear_and_store(ledger_root, store_root, image_url=image_url)
    update_index(_TARGET, ledger_root=ledger_root)

    context = build_image_narrative_context(
        "us-equity",
        _briefing("https://news.example.com/actual"),
    )
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=ledger_root,
        store_root=store_root,
    )
    assert selected.hero is None
    assert selected.card_candidate is None


def test_article_lineage_uses_exact_url_token_not_substring(tmp_path: Path) -> None:
    short_url = "https://news.example.com/story/12"
    long_url = "https://news.example.com/story/123"
    image_url = "https://img.example.com/short.png"
    _append(tmp_path, _item(item_url=short_url, image_url=image_url, title="Short URL"))
    update_index(_TARGET, ledger_root=tmp_path)
    context = build_image_narrative_context("us-equity", _briefing(long_url))
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=tmp_path,
        store_root=tmp_path / "store",
    )
    assert article_url_offset(context.issue_markdown, short_url) is None
    assert selected.card_candidate is None


def test_legacy_external_inputs_are_filtered_and_ordered_by_hero_body() -> None:
    first = _item(
        item_url="https://news.example.com/unrelated",
        image_url="https://img.example.com/a.png",
        title="Unrelated",
    )[1]
    second = _item(
        item_url="https://news.example.com/relevant",
        image_url="https://img.example.com/b.png",
        title="Relevant",
    )[1]
    context = build_image_narrative_context(
        "us-equity",
        _briefing("https://news.example.com/relevant"),
    )
    assert filter_items_for_hero_context(context, (first, second)) == (second,)


def test_low_resolution_candidate_cannot_be_hero_but_can_be_card(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store_root = tmp_path / "store"
    item_url = "https://news.example.com/low-res"
    image_url = "https://img.example.com/low-res.png"
    _append(
        ledger_root,
        _item(
            item_url=item_url,
            image_url=image_url,
            title="Low resolution",
            width=130,
            height=86,
        ),
    )
    _clear_and_store(ledger_root, store_root, image_url=image_url, width=130, height=86)
    update_index(_TARGET, ledger_root=ledger_root)
    context = build_image_narrative_context("us-equity", _briefing(item_url))
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=ledger_root,
        store_root=store_root,
    )
    assert selected.hero is None
    assert selected.card_candidate is not None


def test_actual_store_dimensions_must_meet_hero_minimum(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store_root = tmp_path / "store"
    item_url = "https://news.example.com/mismatched-size"
    image_url = "https://img.example.com/mismatched-size.png"
    _append(
        ledger_root,
        _item(item_url=item_url, image_url=image_url, title="Declared large"),
    )
    _clear_and_store(ledger_root, store_root, image_url=image_url, width=130, height=100)
    update_index(_TARGET, ledger_root=ledger_root)
    context = build_image_narrative_context("us-equity", _briefing(item_url))
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=ledger_root,
        store_root=store_root,
    )
    assert selected.hero is None
    assert selected.card_candidate is not None


def test_blocked_marker_added_after_index_excludes_all_usage(tmp_path: Path) -> None:
    item_url = "https://news.example.com/blocked"
    image_url = "https://img.example.com/blocked.png"
    _append(tmp_path, _item(item_url=item_url, image_url=image_url, title="Blocked"))
    update_index(_TARGET, ledger_root=tmp_path)
    candidate_id = candidate_id_for_url(image_url)
    blocked = clearances_dir_for(ledger_root=tmp_path) / f"{candidate_id}.blocked"
    blocked.parent.mkdir(parents=True, exist_ok=True)
    blocked.touch()
    context = build_image_narrative_context("us-equity", _briefing(item_url))
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=tmp_path,
        store_root=tmp_path / "store",
    )
    assert selected.hero is None
    assert selected.card_candidate is None


def test_tampered_store_binary_cannot_be_hero(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store_root = tmp_path / "store"
    item_url = "https://news.example.com/tampered"
    image_url = "https://img.example.com/tampered.png"
    _append(ledger_root, _item(item_url=item_url, image_url=image_url, title="Tampered"))
    candidate_id = _clear_and_store(ledger_root, store_root, image_url=image_url)
    update_index(_TARGET, ledger_root=ledger_root)
    store_binary_path(candidate_id, ".png", store_root=store_root).write_bytes(make_png(700, 400))
    context = build_image_narrative_context("us-equity", _briefing(item_url))
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=ledger_root,
        store_root=store_root,
    )
    assert selected.hero is None
    assert selected.card_candidate is not None


def test_selected_store_pair_becomes_hero_with_semantic_provenance(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    store_root = tmp_path / "store"
    item_url = "https://news.example.com/hero"
    image_url = "https://img.example.com/hero.png"
    entry = _item(item_url=item_url, image_url=image_url, title="Hero story", credit="CC0")
    _append(ledger_root, entry)
    candidate_id = _clear_and_store(ledger_root, store_root, image_url=image_url)
    update_index(_TARGET, ledger_root=ledger_root)
    markdown = _briefing(item_url) + "\n" + DISCLAIMER
    context = build_image_narrative_context("us-equity", markdown)
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=ledger_root,
        store_root=store_root,
    )
    assert selected.hero is not None

    briefing = Briefing(
        target_date=_TARGET,
        market_summary="상승",
        key_issues="첫 이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=markdown,
    )
    items = (entry[1],)
    prepared = prepare_segment_visual_assets(
        briefing,
        archive_layout=ArchiveLayout(tmp_path / "archive"),
        target_date=_TARGET,
        segment="us-equity",
        items=items,
        coverage=build_segment_coverage("us-equity", items),
        watchlist_impact=match_watchlist_items(items, WatchlistConfig()),
        stored_selection=selected,
    )
    hero_path = next(path for path in prepared.asset_paths if path.stem == "external-context-image")
    manifest = read_manifest(hero_path)
    assert manifest.additional_metadata["candidate_id"] == candidate_id
    assert manifest.additional_metadata["selection_contract"] == "final-body-semantic-v1"
    assert manifest.additional_metadata["narrative_sha256"] == context.narrative_sha256
    assert "![실제 시황 이미지]" in prepared.briefing.rendered_markdown


def test_source_card_never_emits_image_url_and_insertion_is_idempotent(tmp_path: Path) -> None:
    item_url = "https://news.example.com/article"
    image_url = "https://img.example.com/forbidden.png"
    _append(
        tmp_path,
        _item(item_url=item_url, image_url=image_url, title="Market image", credit=None),
    )
    update_index(_TARGET, ledger_root=tmp_path)
    context = build_image_narrative_context("us-equity", _briefing(item_url))
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=tmp_path,
        store_root=tmp_path / "store",
    )
    assert selected.card_candidate is not None
    card = render_image_source_card(selected.card_candidate)
    assert item_url in card
    assert image_url not in card
    assert "test-news" in card

    marked = (
        "<!-- investo:block visual:test.card -->\n"
        f"{card}\n"
        "<!-- /investo:block visual:test.card -->\n"
    )
    once = insert_image_source_card(_briefing(item_url, second_url="https://news/x"), (marked,))
    twice = insert_image_source_card(once, (marked,))
    assert once == twice
    assert once.index(marked) < once.index("### 둘째 이슈")


def test_source_card_escapes_metadata_markdown_html_and_urls(tmp_path: Path) -> None:
    item_url = "https://news.example.com/article"
    image_url = "https://img.example.com/candidate.png"
    entry = _item(
        item_url=item_url,
        image_url=image_url,
        title="![tracking](https://img.example.com/tracker.png)",
        credit="<img src=https://img.example.com/raw.png>",
    )
    _append(tmp_path, entry)
    update_index(_TARGET, ledger_root=tmp_path)
    context = build_image_narrative_context("us-equity", _briefing(item_url))
    selected = select_image_usage(
        context,
        target_date=_TARGET,
        ledger_root=tmp_path,
        store_root=tmp_path / "store",
    )
    assert selected.card_candidate is not None
    card = render_image_source_card(selected.card_candidate)
    assert item_url in card
    assert "![" not in card
    assert "<img" not in card
    assert "tracker.png" not in card
    assert "raw.png" not in card
    assert image_url not in card


@given(st.text(alphabet="abc 가나다", min_size=0, max_size=80))
def test_context_and_card_placement_are_deterministic(text: str) -> None:
    url = "https://news.example.com/a"
    markdown = _briefing(url, first_text=text)
    first = build_image_narrative_context("us-equity", markdown)
    second = build_image_narrative_context("us-equity", markdown)
    assert first == second
    block = (
        "<!-- investo:block visual:test.card -->\n"
        "> card\n"
        "<!-- /investo:block visual:test.card -->\n"
    )
    placed = insert_image_source_card(markdown, (block,))
    assert insert_image_source_card(placed, (block,)) == placed
