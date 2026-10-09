"""Site-only compatibility for committed calendar SVGs (u174, FR-003)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

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
