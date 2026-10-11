"""Build historical/current/empty calendars with the actual MkDocs configuration."""

from datetime import date
from pathlib import Path

import pytest
from mkdocs.commands.build import build
from mkdocs.config import load_config
from scripts.check_calendar_render_contract import CalendarParser, check_calendar_html

from investo.publisher.site_index._constants import HEATMAP_BEGIN, HEATMAP_END
from investo.publisher.site_index.archive_sections import _render_heatmap_block
from investo.visuals.calendar_heatmap import CalendarCell, render_publish_heatmap

ROOT = Path(__file__).parents[2]
DAY = date(2026, 10, 8)


@pytest.mark.parametrize("legacy,empty", [(True, False), (False, False), (True, True)])
def test_real_build_preserves_svg_and_source_bytes(
    tmp_path: Path, legacy: bool, empty: bool
) -> None:
    cells = (
        []
        if empty
        else [
            CalendarCell(date(2026, 10, d), s)
            for d, s in [(5, "normal"), (6, "partial"), (7, "insufficient"), (8, "absent")]
        ]
    )
    svg = render_publish_heatmap(cells, today=DAY)
    document = _render_heatmap_block(svg)
    if legacy:
        document = document.replace('markdown="0"', 'markdown="1"')
    document = f"# Archive\n\n{HEATMAP_BEGIN}\n{document}{HEATMAP_END}\n"
    docs = tmp_path / "docs"
    source = docs / "archive/index.md"
    source.parent.mkdir(parents=True)
    source.write_text(document)
    original = source.read_bytes()
    site = tmp_path / "site"
    config = load_config(
        config_file=str(ROOT / "mkdocs.yml"),
        docs_dir=str(docs),
        site_dir=str(site),
        nav=[{"Archive": "archive/index.md"}],
        strict=True,
    )
    build(config)
    html = (site / "archive/index.html").read_text()
    assert check_calendar_html(html) == []
    parsed = CalendarParser()
    parsed.feed(html)
    assert parsed.rects == svg.count("<rect")
    assert parsed.texts == svg.count("<text")
    assert parsed.escaped_rects == 0
    assert source.read_bytes() == original
