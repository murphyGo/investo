"""Regression checks for SVG broken by md_in_html, including historical input."""

from datetime import date
from types import SimpleNamespace

import pytest
from scripts.check_calendar_render_contract import check_calendar_html
from scripts.mkdocs_render_hooks import on_page_markdown, preserve_calendar_svg_markdown

from investo.publisher.site_index._constants import HEATMAP_BEGIN, HEATMAP_END
from investo.publisher.site_index.archive_sections import _render_heatmap_block
from investo.visuals.calendar_heatmap import CalendarCell, render_publish_heatmap

DAY = date(2026, 10, 8)
SVG = render_publish_heatmap([CalendarCell(DAY, "normal")], today=DAY)
RAW = _render_heatmap_block(SVG)
LEGACY = RAW.replace('markdown="0"', 'markdown="1"')
DOCUMENT = f"before\n{HEATMAP_BEGIN}\n{LEGACY}{HEATMAP_END}\nafter"


def test_only_known_calendar_attribute_changes_and_is_idempotent() -> None:
    repaired = preserve_calendar_svg_markdown(DOCUMENT)
    assert repaired == DOCUMENT.replace('markdown="1"', 'markdown="0"')
    assert preserve_calendar_svg_markdown(repaired) == repaired


@pytest.mark.parametrize(
    "markdown",
    [
        "no calendar",
        LEGACY,
        DOCUMENT.replace(HEATMAP_END, ""),
        DOCUMENT + DOCUMENT,
        DOCUMENT.replace("u29-heatmap", "other"),
        DOCUMENT.replace("</svg>", ""),
        DOCUMENT.replace("</text>", ""),
        f"```html\n{DOCUMENT}\n```\n",
        f"~~~html\n{DOCUMENT}\n~~~\n",
        "\n".join("    " + line for line in f"```html\n{DOCUMENT}\n```".splitlines()),
        DOCUMENT.replace("</svg>", '<div xmlns="http://www.w3.org/1999/xhtml">bad</div></svg>'),
        f"{HEATMAP_BEGIN}\n```html\n{LEGACY}\n```\n{HEATMAP_END}",
    ],
)
def test_unknown_incomplete_and_fenced_examples_are_unchanged(markdown: str) -> None:
    assert preserve_calendar_svg_markdown(markdown) == markdown


def test_hook_is_archive_index_only() -> None:
    for uri in ("index.md", "archive/us-equity/index.md", "example.md"):
        page = SimpleNamespace(file=SimpleNamespace(src_uri=uri))
        assert on_page_markdown(DOCUMENT, page=page, config=None, files=None) == DOCUMENT
    page = SimpleNamespace(file=SimpleNamespace(src_uri="archive/index.md"))
    assert on_page_markdown(DOCUMENT, page=page, config=None, files=None) != DOCUMENT


def test_guard_accepts_generated_grid_and_empty_message() -> None:
    assert check_calendar_html(RAW) == []
    assert check_calendar_html(_render_heatmap_block(render_publish_heatmap([], today=DAY))) == []


@pytest.mark.parametrize(
    "broken",
    [
        "<h1>archive</h1>",
        '<figure class="u29-heatmap"><svg></svg><figcaption>caption</figcaption></figure>',
        RAW.replace("</svg>", "</svg><rect>"),
        RAW.replace("<style>", "<div>").replace("</style>", "</div>"),
        RAW + RAW,
        RAW.replace("</figure>", ""),
        RAW.replace("</svg>", "<div>breakout</div></svg>"),
    ],
)
def test_guard_rejects_split_missing_and_incomplete_output(broken: str) -> None:
    assert check_calendar_html(broken)
