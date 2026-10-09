"""Expose the observed price clock in text-only public briefings."""

import re
from collections.abc import Sequence

from investo._internal.price_time_basis import price_snapshot_label
from investo.models import NormalizedItem
from investo.publisher.reader_format.public_projection import _is_closing_fence, _opening_fence

_NOTE_RE = re.compile(r"^> \*\*가격 기준\*\*: .*?$", re.MULTILINE)


def insert_price_time_basis(markdown: str, items: Sequence[NormalizedItem]) -> str:
    labels: list[str] = []
    for item in items:
        if item.category != "price":
            continue
        label = price_snapshot_label(item.raw_metadata)
        symbol = item.raw_metadata.get("symbol")
        if (
            label is None
            or not isinstance(symbol, str)
            or not re.fullmatch(r"[A-Za-z\d-]{1,24}", symbol)
        ):
            continue
        rendered = f"{symbol.upper()}: {label}"
        if rendered not in labels:
            labels.append(rendered)
        if len(labels) == 12:
            break
    if not labels:
        return markdown
    note = "> **가격 기준**: " + " / ".join(labels)
    fence: tuple[str, int] | None = None
    heading_end: int | None = None
    offset = 0
    for raw_line in markdown.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        end = offset + len(raw_line)
        if fence is not None:
            if _is_closing_fence(line, fence):
                fence = None
        elif (opening := _opening_fence(line)) is not None:
            fence = opening
        elif _NOTE_RE.fullmatch(line):
            return markdown[:offset] + note + raw_line[len(line) :] + markdown[end:]
        elif heading_end is None and line.startswith("## ④"):
            heading_end = end
        offset = end
    if heading_end is None:
        return markdown
    return markdown[:heading_end] + "\n" + note + "\n" + markdown[heading_end:]
