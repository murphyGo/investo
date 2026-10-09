"""Canonical news-first preamble; keep detailed numeric evidence accessible."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from investo.publisher.reader_format.public_projection import _is_closing_fence, _opening_fence
from investo.publisher.reader_format.tldr import ensure_tldr_block, tldr_fallback_items

MARKET_DATA_OPEN: Final[str] = (
    '<details class="investo-market-data" markdown="1">\n<summary>시장 지표 자세히 보기</summary>'
)
MARKET_DATA_CLOSE: Final[str] = "</details>\n<!-- /investo:market-data -->"
_NUMERIC_HEADINGS = frozenset(
    ("## ⓪ 오늘의 매크로", "## ⓪-A 크립토 지표 (UTC 24h 스냅샷)", "## ⓪-B 채널 기준선")
)
_ANCHOR_HEADERS = frozenset(
    ("| 종목 | 종가 | 변동 | 비고 |", "| 종목 | 스냅샷(UTC 24h) | 구간 변동 | 비고 |")
)
_CALLOUTS = ("> **오늘의 결론**:", "> **핵심 동인**:", "> **주의할 점**:")
_SUPPLEMENT_OPEN = re.compile(r"<!-- investo:block (?:visual|chart|carryover):([^ >]+) -->$")


@dataclass(frozen=True, slots=True)
class _Block:
    kind: str
    text: str


def unwrap_market_data(markdown: str) -> str:
    """Remove exactly our complete shell, retaining every interior byte."""
    if markdown.count(MARKET_DATA_OPEN) == markdown.count(MARKET_DATA_CLOSE) == 1:
        start = markdown.index(MARKET_DATA_OPEN)
        end = markdown.index(MARKET_DATA_CLOSE)
        if start < end < markdown.find("## ① 요약"):
            return markdown.replace(MARKET_DATA_OPEN, "", 1).replace(MARKET_DATA_CLOSE, "", 1)
    return markdown


def _protected_end(lines: list[str], start: int) -> int | None:
    line = lines[start].rstrip("\r\n")
    opening = _opening_fence(line)
    marker = _SUPPLEMENT_OPEN.fullmatch(line)
    if opening is None and marker is None:
        return None
    close = line.replace("<!-- investo:block ", "<!-- /investo:block ", 1)
    for end in range(start + 1, len(lines)):
        current = lines[end].rstrip("\r\n")
        if (opening is not None and _is_closing_fence(current, opening)) or (
            marker is not None and current == close
        ):
            return end + 1
    return len(lines)


def _blocks(markdown: str) -> tuple[list[_Block], str]:
    """Read only the preamble; fences and owned supplements are indivisible."""
    lines = markdown.splitlines(keepends=True)
    blocks: list[_Block] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        if line == "## ① 요약":
            return blocks, "".join(lines[index:])
        protected_end = _protected_end(lines, index)
        if protected_end is not None:
            kind = "supplement" if _SUPPLEMENT_OPEN.fullmatch(line) else "protected"
            blocks.append(_Block(kind, "".join(lines[index:protected_end])))
            index = protected_end
            continue
        kind = "other"
        end = index + 1
        if line.startswith("# "):
            kind = "title"
        elif line.startswith("> 정보 제공용 자동 시황이며"):
            kind = "disclaimer"
        elif line.startswith("**기준 시각**:"):
            kind = "watermark"
        elif line.startswith("**세그먼트**:"):
            kind = "navigation"
        elif line.startswith((*_CALLOUTS, "> **내 관심 자산 영향**:")):
            kind = "callout"
        elif line in _ANCHOR_HEADERS:
            kind = "numeric"
            while end < len(lines) and lines[end].startswith("|"):
                end += 1
        elif line in _NUMERIC_HEADINGS:
            kind = "numeric"
            while end < len(lines):
                value = lines[end].strip()
                if value.startswith(("#", ">", "<", "![", "```", "~~~")):
                    break
                end += 1
        elif line == "## 한눈에 보기":
            kind = "summary"
            while end < len(lines):
                value = lines[end].strip()
                if value.startswith(
                    (
                        "#",
                        ">",
                        "<",
                        "![",
                        "|",
                        "```",
                        "~~~",
                        "**기준 시각**:",
                        "**세그먼트**:",
                        "**뉴스 관측기간**:",
                    )
                ):
                    break
                end += 1
        blocks.append(_Block(kind, "".join(lines[index:end])))
        index = end
    return blocks, ""


def _normalized_summary(text: str, *, fallback: Sequence[str]) -> str:
    lines = [line for line in text.splitlines()[1:] if line.strip()]
    if len(lines) > 3:
        return text
    bullets = [line.startswith("- ") and bool(line[2:].strip()) for line in lines]
    plain = [
        not line.startswith((" ", "\t", "-", "* ", "+ ", ">", "#", "|", "<")) for line in lines
    ]
    if not all(bullet or prose for bullet, prose in zip(bullets, plain, strict=True)):
        return text
    values = [line[2:] if bullet else line for line, bullet in zip(lines, bullets, strict=True)]
    # Existing summary repair can remove empty fragments. Fill only missing
    # slots from the same callouts; never discard a fourth or unsupported line.
    for value in fallback:
        if len(values) < 3 and value not in values:
            values.append(value)
    while len(values) < 3:
        values.append(fallback[len(values)])
    return "## 한눈에 보기\n\n" + "\n".join(f"- {value}" for value in values) + "\n"


def compose_canonical_preamble(markdown: str, *, title: str) -> str:
    """Move whole owned blocks; do not rewrite body, evidence or asset bytes."""
    unwrapped = unwrap_market_data(markdown)
    prepared = ensure_tldr_block(unwrapped)
    blocks, body = _blocks(prepared)
    if not body:
        return markdown
    groups: dict[str, list[str]] = {}
    fallback = tldr_fallback_items(prepared)
    canonical_seen = False
    for block in blocks:
        value = block.text
        if block.kind == "title" and value.strip() == title:
            if canonical_seen:
                continue
            canonical_seen = True
        if block.kind == "summary":
            value = _normalized_summary(value, fallback=fallback)
        groups.setdefault("other" if block.kind == "protected" else block.kind, []).append(value)
    ordered: list[str] = []
    for kind in (
        "title",
        "disclaimer",
        "watermark",
        "navigation",
        "summary",
        "callout",
        "supplement",
        "other",
    ):
        # Unknown adjacent lines retain their internal whitespace and order.
        values: Sequence[str] = groups.get(kind, ())
        if kind == "other":
            values = ("".join(values),)
        ordered.extend(value.strip("\r\n") for value in values if value.strip())
    numeric = "\n\n".join(value.strip("\r\n") for value in groups.get("numeric", ()))
    if numeric:
        ordered.append(f"{MARKET_DATA_OPEN}\n\n{numeric}\n\n{MARKET_DATA_CLOSE}")
    return "\n\n".join(ordered) + "\n\n" + body


def preamble_issue_codes(markdown: str, *, title: str) -> tuple[str, ...]:
    """Read-only final structure check; malformed content is never discarded."""
    blocks, body = _blocks(unwrap_market_data(markdown))
    codes: set[str] = set()
    titles = [block.text.strip() for block in blocks if block.kind == "title"]
    # Extra unfenced body titles are also invalid; complete supplements remain opaque.
    body_blocks, _ = _blocks(body.removeprefix("## ① 요약"))
    if titles != [title] or any(block.kind == "title" for block in body_blocks):
        codes.add("structure.header_title")
    summaries = [block.text for block in blocks if block.kind == "summary"]
    if len(summaries) != 1:
        codes.add("structure.tldr_shape")
    else:
        lines = [line for line in summaries[0].splitlines()[1:] if line.strip()]
        if len(lines) != 3 or any(
            not line.startswith("- ") or not line[2:].strip() for line in lines
        ):
            codes.add("structure.tldr_shape")
    before_body = markdown[: markdown.find("## ① 요약")]
    opens, closes = before_body.count(MARKET_DATA_OPEN), before_body.count(MARKET_DATA_CLOSE)
    numeric = any(block.kind == "numeric" for block in blocks)
    if (opens, closes) != ((1, 1) if numeric else (0, 0)):
        codes.add("structure.market_data_details")
    elif numeric:
        start, end = before_body.index(MARKET_DATA_OPEN), before_body.index(MARKET_DATA_CLOSE)
        if start >= end or "<details" in before_body[start + len(MARKET_DATA_OPEN) : end]:
            codes.add("structure.market_data_details")
        outside = before_body[:start] + before_body[end + len(MARKET_DATA_CLOSE) :]
        outside_blocks, _ = _blocks(outside)
        if any(
            block.kind == "numeric" or (block.kind == "other" and block.text.startswith("|"))
            for block in outside_blocks
        ):
            codes.add("structure.preamble_order")
    summary_at = before_body.find("## 한눈에 보기")
    earlier_visual = before_body.find("<!-- investo:block visual:")
    if summary_at < 0 or (earlier_visual >= 0 and earlier_visual < summary_at):
        codes.add("structure.preamble_order")
    if numeric and opens and before_body.find(MARKET_DATA_OPEN) < summary_at:
        codes.add("structure.preamble_order")
    return tuple(sorted(codes))
