"""Site-only compatibility for committed calendar SVGs (u174, FR-003)."""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import quote

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.files import Files
    from mkdocs.structure.pages import Page

_BEGIN = "<!-- u29 heatmap begin -->"
_END = "<!-- u29 heatmap end -->"
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
_FIGURE = re.compile(
    r'<figure class="u29-heatmap" markdown="(?P<mode>[01])">\s*'
    r"(?P<svg><svg\b[^>]*>.*?</svg>)\s*"
    r"<figcaption>[^<]*</figcaption>\s*</figure>",
    re.DOTALL,
)


def preserve_calendar_svg_markdown(markdown: str) -> str:
    """Make one complete known calendar raw, without touching fenced examples."""
    markers: list[tuple[str, int]] = []
    fence: str | None = None
    offset = 0
    for line in markdown.splitlines(keepends=True):
        match = _FENCE.match(line.rstrip("\r\n"))
        if match:
            token, suffix = match.groups()
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not suffix.strip():
                fence = None
        elif fence is None and line.strip() in (_BEGIN, _END):
            markers.append((line.strip(), offset + line.index("<!--")))
        offset += len(line)
    if len(markers) != 2 or [m[0] for m in markers] != [_BEGIN, _END]:
        return markdown
    start, end = markers[0][1] + len(_BEGIN), markers[1][1]
    block = markdown[start:end]
    if any(_FENCE.match(line) for line in block.splitlines()):
        return markdown
    figures = list(_FIGURE.finditer(block))
    if len(figures) != 1 or block.count("<figure") != 1 or block.count("<svg") != 1:
        return markdown
    figure = figures[0]
    try:
        svg = fromstring(figure["svg"])
    except (DefusedXmlException, ValueError, SyntaxError):
        return markdown
    if svg.tag != "{http://www.w3.org/2000/svg}svg" or figure["mode"] == "0":
        return markdown
    allowed = {f"{{http://www.w3.org/2000/svg}}{tag}" for tag in ("style", "rect", "text", "title")}
    if any(node.tag not in allowed for node in svg.iter() if node is not svg):
        return markdown
    # Only the mode byte changes; captions, data, and surrounding text survive.
    position = start + figure.start("mode")
    return markdown[:position] + "0" + markdown[position + 1 :]


def on_page_markdown(markdown: str, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    """Repair the archive calendar at build time, never the source on disk."""
    if page.file.src_uri != "archive/index.md":
        return markdown
    return preserve_calendar_svg_markdown(markdown)


class _SectionHeadings(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.html = html
        self.line_starts = [0]
        for line in html.splitlines(keepends=True):
            self.line_starts.append(self.line_starts[-1] + len(line))
        self.headings: list[tuple[str, str, int, str]] = []
        self.current: tuple[str, int, str] | None = None
        self.text = ""
        self.permalink = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h2" and values.get("id"):
            line, column = self.getpos()
            self.current = (
                values["id"] or "",
                self.line_starts[line - 1] + column,
                self.get_starttag_text(),
            )
            self.text = ""
        if self.current and tag == "a" and "headerlink" in (values.get("class") or "").split():
            self.permalink = True

    def handle_data(self, text: str) -> None:
        if self.current and not self.permalink:
            self.text += text

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.permalink = False
        if tag == "h2" and self.current:
            identifier, position, start_tag = self.current
            self.headings.append((identifier, self.text.strip(), position, start_tag))
            self.current = None


def add_section_navigation(html: str) -> str:
    """Use real built headings, never a schema-specific heading list (u178)."""
    if 'class="investo-section-nav"' in html:
        return html
    parser = _SectionHeadings(html)
    parser.feed(html)
    seen: set[str] = set()
    headings = []
    for heading in parser.headings:
        if heading[0] not in seen and heading[1]:
            headings.append(heading)
            seen.add(heading[0])
    if not headings:
        return html
    for _, _, position, start_tag in reversed(headings):
        if "tabindex=" not in start_tag:
            updated = start_tag[:-1] + ' tabindex="-1">'
            html = html[:position] + updated + html[position + len(start_tag) :]
    links = "".join(
        f'<a href="#{quote(identifier, safe="")}">{escape(label)}</a>'
        for identifier, label, _, _ in headings
    )
    navigation = (
        '<details class="investo-section-nav"><summary>본문 목차</summary>'
        f'<nav aria-label="본문 목차">{links}</nav></details>'
    )
    end = html.find("</h1>")
    position = end + len("</h1>") if end >= 0 else 0
    return html[:position] + navigation + html[position:]


def on_page_content(html: str, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    if re.fullmatch(
        r"archive/(?:[a-z-]+/)?\d{4}/\d{2}/\d{4}-\d{2}-\d{2}\.md",
        page.file.src_uri,
    ):
        return add_section_navigation(html)
    return html
