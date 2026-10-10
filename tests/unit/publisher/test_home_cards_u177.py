"""Current-bundle truth, escaped text, migration and canonical-gate failures."""

from datetime import date
from html import unescape
from pathlib import Path

import pytest

from investo.models import Briefing
from investo.models.segments import COVERAGE_STATUS_LABELS, DOMESTIC_EQUITY
from investo.publisher.quality_consistency import (
    CODE_HOME_MISMATCH,
    build_canonical_snapshot,
    check_quality_consistency,
)
from investo.publisher.site_index import HERO_BEGIN, HERO_END, update_index_hero
from investo.publisher.site_index.archive_sections import SegmentBundleState
from investo.publisher.site_index.hero import _render_hero_block

DAY = date(2026, 10, 8)


def briefing(status: str | None, summary: str = "마감 근거. 수집 근거가 제한적입니다.") -> Briefing:
    text = f"> **오늘의 결론**: {summary}\n"
    if status:
        text += f"> **데이터 상태**: {status}\n"
    return Briefing.model_construct(target_date=DAY, rendered_markdown=text)


@pytest.mark.parametrize("status", [*COVERAGE_STATUS_LABELS.values(), None, "알 수 없음"])
def test_home_uses_same_canonical_status_and_keeps_absence_independent(status: str | None) -> None:
    current = briefing(status)
    text = _render_hero_block(DAY, {DOMESTIC_EQUITY: current})
    snapshot = build_canonical_snapshot(
        DAY,
        segment_texts={DOMESTIC_EQUITY: current.rendered_markdown},
        history_row=None,
    )
    findings = check_quality_consistency(snapshot, quality_page_text=None, home_page_text=text)
    assert not [f for f in findings if f.code == CODE_HOME_MISMATCH]
    assert text.count('class="investo-market-card"') == 3
    assert 'data-generated="false" data-quality="absent"' in text
    assert "수집 근거가 제한적입니다." in text


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.replace('data-target-date="2026-10-08"', 'data-target-date="2026-10-09"', 1),
        lambda s: s.replace('data-quality="failed"', 'data-quality="normal"', 1),
        lambda s: s.replace("근거 상태: 실패", "근거 상태: 정상", 1),
        lambda s: s.replace('data-generated="false"', 'data-generated="true"', 1),
        lambda s: s.replace('data-investo-field="date"', 'data-investo-field="missing"', 1),
        lambda s: s + s,
        lambda s: "",
    ],
)
def test_home_gate_rejects_attribute_and_visible_text_contradictions(change) -> None:
    current = briefing("실패")
    text = _render_hero_block(DAY, {DOMESTIC_EQUITY: current})
    snapshot = build_canonical_snapshot(
        DAY,
        segment_texts={DOMESTIC_EQUITY: current.rendered_markdown},
        history_row=None,
    )
    findings = check_quality_consistency(
        snapshot, quality_page_text=None, home_page_text=change(text)
    )
    assert any(f.code == CODE_HOME_MISMATCH and f.is_failure for f in findings)
    assert not any(
        f.code == CODE_HOME_MISMATCH
        for f in check_quality_consistency(
            snapshot,
            quality_page_text=None,
        )
    )


def test_terminal_plain_text_bypasses_legacy_extraction_and_escapes_html() -> None:
    selected = '뉴스 제목 <script>alert(1)</script> & "완료" **표시**' + "긴 요약 " * 100
    original = briefing("부분", "기존 결론.")
    text = _render_hero_block(
        DAY,
        {DOMESTIC_EQUITY: original},
        terminal_summaries={DOMESTIC_EQUITY: selected},
    )
    assert selected in unescape(text)
    assert "<script>" not in text and "기존 결론." not in text
    assert original.rendered_markdown.endswith("**데이터 상태**: 부분\n")


def test_fallback_link_uses_discovered_path_without_reconstructing_date_folder() -> None:
    states = (
        SegmentBundleState(
            DOMESTIC_EQUITY,
            DAY,
            False,
            "unused",
            date(2026, 10, 7),
            "domestic-equity/2026/09/2026-10-07.md",
        ),
    )
    text = _render_hero_block(DAY, {}, bundle_states=states)
    assert "archive/domestic-equity/2026/09/2026-10-07.md" in text
    assert "archive/domestic-equity/2026/10/2026-10-07.md" not in text


def test_bootstrap_migration_and_footer_are_idempotent(tmp_path: Path) -> None:
    page = tmp_path / "site_docs/index.md"
    page.parent.mkdir()
    protected = "\n---\n\n> 정보 제공 면책.\n\n## 사용자 섹션\n보존 bytes\n"
    page.write_text(
        f"{HERO_BEGIN}\n# old\n{HERO_END}\n\n## 최신 시황\nold\n"
        "\n## 사이트 안내\nold links\n" + protected
    )
    update_index_hero(DAY, {}, site_index_path=page)
    first = page.read_bytes()
    update_index_hero(DAY, {}, site_index_path=page)
    assert page.read_bytes() == first
    assert protected in page.read_text()
    assert page.read_text().count("# 최신 발행 시황") == 1
    fresh = tmp_path / "fresh/index.md"
    update_index_hero(DAY, {}, site_index_path=fresh)
    assert fresh.read_text().count(HERO_BEGIN) == 1


def test_direct_migration_failure_leaves_original_bytes(tmp_path: Path, monkeypatch) -> None:
    from investo.publisher.site_index import _blocks

    page = tmp_path / "index.md"
    original = f"{HERO_BEGIN}\n# old\n{HERO_END}\n\n## 최신 시황\nold\n"
    page.write_text(original)

    def fail_write(path: Path, content: str) -> None:
        raise OSError("injected atomic write failure")

    monkeypatch.setattr(_blocks, "_write_text_atomic", fail_write)
    with pytest.raises(OSError):
        update_index_hero(DAY, {}, site_index_path=page)
    assert page.read_text() == original


def test_multiline_terminal_summary_is_never_treated_as_owned_home_section(tmp_path: Path) -> None:
    page = tmp_path / "index.md"
    summary = "첫 줄\n## 최신 시황\n둘째 줄\n## 사이트 안내\n마지막 줄"
    values = {DOMESTIC_EQUITY: briefing("부분")}
    update_index_hero(
        DAY, values, site_index_path=page, terminal_summaries={DOMESTIC_EQUITY: summary}
    )
    first = page.read_bytes()
    update_index_hero(
        DAY, values, site_index_path=page, terminal_summaries={DOMESTIC_EQUITY: summary}
    )
    assert page.read_bytes() == first
    assert summary in page.read_text()
    assert page.read_text().count(HERO_BEGIN) == 1
