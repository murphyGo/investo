#!/usr/bin/env python3
"""Check calendar containment in built HTML; browser QA verifies namespaces."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path


class CalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.figures = 0
        self.in_figure = False
        self.in_svg = False
        self.svgs = 0
        self.rects = 0
        self.escaped_rects = 0
        self.texts = 0
        self.styles = 0
        self.captions = 0
        self.svg_text: list[str] = []
        self.unknown_svg_tags: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "figure" and "u29-heatmap" in (attributes.get("class") or "").split():
            self.figures += 1
            self.in_figure = True
        if not self.in_figure:
            return
        if tag == "svg":
            self.svgs += 1
            self.in_svg = True
        if tag == "rect":
            if self.in_svg:
                self.rects += 1
            else:
                self.escaped_rects += 1
        if self.in_svg:
            if tag not in ("svg", "style", "rect", "text", "title"):
                self.unknown_svg_tags.add(tag)
            self.texts += tag == "text"
            self.styles += tag == "style"
        self.captions += tag == "figcaption"

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "svg":
            self.in_svg = False
        if tag == "figure":
            self.in_figure = False

    def handle_data(self, data: str) -> None:
        if self.in_svg:
            self.svg_text.append(data)


def check_calendar_html(html: str) -> list[str]:
    parser = CalendarParser()
    parser.feed(html)
    errors: list[str] = []
    if parser.figures != 1 or parser.svgs != 1 or parser.captions != 1:
        errors.append("expected one calendar figure, SVG, and caption")
    if parser.escaped_rects:
        errors.append("calendar rects escaped the SVG subtree")
    if parser.unknown_svg_tags:
        errors.append("calendar SVG contains unexpected HTML or elements")
    if not parser.styles or not parser.texts:
        errors.append("calendar SVG lost its style or text")
    if not parser.rects and "발행 이력이 아직 없습니다." not in "".join(parser.svg_text):
        errors.append("calendar SVG is empty")
    if parser.in_figure or parser.in_svg:
        errors.append("calendar markup is incomplete")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-dir", type=Path, default=Path(__file__).resolve().parents[1] / "site"
    )
    args = parser.parse_args()
    path = args.site_dir / "archive/index.html"
    try:
        errors = check_calendar_html(path.read_text(encoding="utf-8"))
    except OSError as error:
        errors = [f"cannot read built archive: {error}"]
    for error in errors:
        print(f"Calendar render contract: {error}")
    if not errors:
        print("Calendar render contract passed")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
