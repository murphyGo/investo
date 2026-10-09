"""Render sealed documents through the real MkDocs Markdown extension set."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import markdown
import pytest
import yaml

from investo._internal.data_limited_segment import build_data_limited_briefing
from investo.models.segments import MarketSegment
from investo.publisher.public_document import finalize_public_bundle
from tests.unit.publisher.test_canonical_preamble_u154 import DAY, SEGMENTS, context


class ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.details: list[str] = []
        self.numeric_tables = 0
        self.visible_preamble_tables = 0
        self.titles = 0
        self.panel_count = 0
        self.tags: list[str] = []
        self.text: list[str] = []
        self.expanded = False
        self.heading = ""
        self.body = False
        self.summary_items = 0
        self.in_summary = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.tags.append(tag)
        if tag == "details":
            kind = attributes.get("class", "") or ""
            self.details.append(kind)
            if kind == "investo-market-data":
                self.panel_count += 1
                self.expanded |= "open" in attributes
                assert attributes.get("markdown") is None
        if tag == "h1":
            self.titles += 1
        if tag == "h2":
            self.heading = ""
        if tag == "li" and self.in_summary and not self.details:
            self.summary_items += 1
        if tag == "table":
            if "investo-market-data" in self.details:
                self.numeric_tables += 1
            elif not self.body:
                self.visible_preamble_tables += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "details":
            self.details.pop()
        if tag == "h2":
            if "① 요약" in self.heading:
                self.body = True
            self.in_summary = "한눈에 보기" in self.heading
        if tag in self.tags:
            index = len(self.tags) - 1 - self.tags[::-1].index(tag)
            del self.tags[index:]

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self.tags and self.tags[-1] in ("h2", "a"):
            self.heading += data


@pytest.mark.parametrize("segment", SEGMENTS)
def test_actual_configuration_renders_closed_numeric_tables_after_visible_summary(
    segment: MarketSegment,
) -> None:
    config = yaml.safe_load((Path(__file__).parents[2] / "mkdocs.yml").read_text())
    extensions: list[str] = []
    options = {}
    for entry in config["markdown_extensions"]:
        if isinstance(entry, str):
            extensions.append(entry)
        else:
            extensions.extend(entry)
            options.update(entry)
    doc = finalize_public_bundle(
        {segment: build_data_limited_briefing(DAY, segment)}, context=context((segment,))
    ).documents[0]
    rendered = markdown.markdown(
        doc.briefing.rendered_markdown, extensions=extensions, extension_configs=options
    )
    parsed = ArticleParser()
    parsed.feed(rendered)
    assert parsed.titles == 1
    assert parsed.panel_count == 1 and not parsed.expanded
    # Some native-anchor producers legitimately render no second table.
    expected_tables = len(
        re.findall(
            r"(?m)^\|(?:\s*:?-+:?\s*\|)+\s*$",
            doc.briefing.rendered_markdown.split("## ① 요약")[0],
        )
    )
    assert parsed.numeric_tables >= 1
    assert expected_tables == parsed.numeric_tables
    assert parsed.visible_preamble_tables == 0
    assert parsed.summary_items == 3
    assert parsed.details == []
    assert "1,234.50" in "".join(parsed.text)
    assert (
        rendered.index("한눈에 보기")
        < rendered.index("시장 지표 자세히 보기")
        < rendered.index("① 요약")
    )
