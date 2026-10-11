"""Bounded readable views preserve existing models, projections and exact fields."""

from datetime import date
from html import unescape

import pytest

from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.visuals.cards import (
    DataConfidenceCardInput,
    DataConfidenceSourceRow,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    PriceSnapshotRow,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
)
from investo.visuals.html_cards import render_card_html

DAY = date(2026, 10, 8)


def cards(segment):
    return (
        DataConfidenceCardInput(
            target_date=DAY,
            segment=segment,
            coverage_status="limited",
            item_count=17,
            source_count=3,
            reason_labels=("핵심 가격 근거 제한",),
            source_rows=(
                DataConfidenceSourceRow(
                    source_name="PRIVATE", status="failed", detail="NEVER_PUBLIC"
                ),
            ),
        ),
        MarketSnapshotCardInput(
            target_date=DAY,
            segment=segment,
            coverage_status="partial",
            conclusion="길고 정확한 결론 <script> & 내용 " * 5,
            main_driver="본문 사용 미집계",
            caution="제한 고지 전체 문장.",
        ),
        PriceSnapshotCardInput(
            target_date=DAY,
            segment=segment,
            rows=tuple(
                PriceSnapshotRow(
                    symbol=f"ROW{n}",
                    label="조회 시점 가격 · 시각 미확인",
                    price="1,234.5600 USD",
                    percent_change="-2.34%",
                    source_name="verified-source",
                )
                for n in range(12)
            ),
        ),
        WatchlistRelevanceCardInput(
            target_date=DAY,
            segment=segment,
            configured=True,
            is_default_bundle=True,
            total_matches=5,
            rows=tuple(
                WatchlistRelevanceRow(
                    term=f"자산{n}",
                    kind="직접 관련",
                    source_name="뉴스",
                    title="기사 제목 " * 30,
                    url="https://example.invalid/article?q=a&x=(b)",
                )
                for n in range(5)
            ),
        ),
    )


@pytest.mark.parametrize("segment", [DOMESTIC_EQUITY, US_EQUITY, CRYPTO])
def test_maximum_cards_are_exact_escaped_bounded_and_have_truthful_time(segment) -> None:
    inputs = cards(segment)
    original = tuple(card.model_dump_json() for card in inputs)
    rendered = tuple(render_card_html(card) for card in inputs)
    assert original == tuple(card.model_dump_json() for card in inputs)
    assert all(len(text.encode()) < 32 * 1024 for text in rendered)
    assert sum(len(text.encode()) for text in rendered) < 96 * 1024
    assert "PRIVATE" not in rendered[0] and "NEVER_PUBLIC" not in rendered[0]
    assert "본문 사용 미집계" not in rendered[1] and "<script>" not in rendered[1]
    assert "<script>" in unescape(rendered[1])
    assert rendered[2].count("1,234.5600 USD") == 12
    assert rendered[2].count("-2.34%") == 12
    assert "미확인" in rendered[2] and "대상일 2026-10-08" in rendered[2]
    assert rendered[3].count("기사 제목") == 150
    assert "https://example.invalid/article?q=a&x=%28b%29" in rendered[3]


@pytest.mark.parametrize("configured", [True, False])
def test_watchlist_empty_states_do_not_invent_matches(configured) -> None:
    card = WatchlistRelevanceCardInput(
        target_date=DAY, segment=CRYPTO, configured=configured, total_matches=0
    )
    html = render_card_html(card)
    assert ("공개 연결 항목 없음" if configured else "관심 목록 미설정") in html
    assert "[원문" not in html


def test_related_matches_are_not_promoted_to_direct_relationships() -> None:
    card = WatchlistRelevanceCardInput(
        target_date=DAY,
        segment=US_EQUITY,
        configured=True,
        total_matches=1,
        rows=(
            WatchlistRelevanceRow(term="섹터", kind="관련 맥락", source_name="출처", title="기사"),
        ),
    )
    html = render_card_html(card)
    assert "관심 자산 공개 매칭 1건" in html and "관련 맥락" in html
    assert "직접 연결" not in html


def test_narrative_inline_markdown_renders_without_exposing_markup_or_dropping_links() -> None:
    import markdown

    card = MarketSnapshotCardInput(
        target_date=DAY,
        segment=US_EQUITY,
        coverage_status="normal",
        conclusion="가격 **100.00**과 [기사](https://example.invalid/article)를 확인합니다.",
        main_driver="<script> & 입력",
        caution="제한 고지.",
    )
    raw = render_card_html(card)
    html = markdown.markdown(raw, extensions=["md_in_html"])
    assert "<strong>100.00</strong>" in raw
    assert (
        "<strong>100.00</strong>" in html and '<a href="https://example.invalid/article">' in html
    )
    assert "<script>" not in html and "&lt;script&gt;" in html


@pytest.mark.parametrize(
    "value",
    [
        "[표시](javascript:alert%281%29)",
        "[표시](data:text/html,x)",
        "[표시](vbscript:msgbox%281%29)",
        "![표시](https://example.invalid/unregistered.png)",
        "<https://example.invalid/auto>",
    ],
)
@pytest.mark.parametrize("kind", ["market", "watchlist"])
def test_untrusted_narrative_cannot_create_active_elements(value, kind) -> None:
    import markdown

    if kind == "market":
        card = cards(US_EQUITY)[1].model_copy(update={"conclusion": value})
    else:
        card = WatchlistRelevanceCardInput(
            target_date=DAY,
            segment=US_EQUITY,
            configured=True,
            total_matches=1,
            rows=(
                WatchlistRelevanceRow(
                    term="자산", kind="직접 관련", source_name="출처", title=value
                ),
            ),
        )
    html = markdown.markdown(render_card_html(card), extensions=["md_in_html"])
    assert "<a " not in html and "<img " not in html


def test_caption_is_once_outside_native_svg_fallback_and_artifact_ids_are_unchanged(
    tmp_path, monkeypatch
) -> None:
    from investo.visuals import assets

    light = tmp_path / "2026-10-08.assets/price-snapshot.svg"
    dark = light.with_name("price-snapshot-dark.svg")
    caption = "*출처: 검증된 입력 · 라이선스: synthetic*"
    monkeypatch.setattr(assets, "_provenance_caption_for", lambda path: caption)
    blocks = assets.build_visual_markdown_blocks(
        markdown_path=tmp_path / "2026-10-08.md",
        asset_paths=(light,),
        dark_variants={light: dark},
        artifact_ids_by_path={light: ("light", "dark", "manifest")},
        html_by_kind={"price-snapshot": "<section>정확한 텍스트</section>"},
    )
    block = blocks[0]
    assert block.artifact_ids == ("light", "dark", "manifest")
    assert block.markdown.count(caption) == 1
    assert block.markdown.index(caption) > block.markdown.index("</details>")
    assert "#gh-light-mode-only" in block.markdown and "#gh-dark-mode-only" in block.markdown
