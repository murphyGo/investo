"""Rendered-body evidence accounting for quality metadata.

The helper is intentionally post-render: it looks at the markdown that
will be archived, removes first-viewport diagnostics/navigation, and
counts only evidence visible in the public body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

from investo._internal.source_specs import SOURCE_SPECS_BY_NAME
from investo.models import SourceOutcome
from investo.models.coverage import SOURCE_SKIP_REASON_LABELS
from investo.models.segments import MarketSegment


@dataclass(frozen=True, slots=True)
class RenderedEvidenceCounts:
    markdown_links: int
    known_source_links: int
    verified_figure_mentions: int
    body_used_count: int


_NUMBERED_SECTION_RE: Final[re.Pattern[str]] = re.compile(r"(?m)^##\s*[①-⑥]\s+")
_DETAILS_RE: Final[re.Pattern[str]] = re.compile(
    r"<details\b[^>]*>.*?</details>",
    re.IGNORECASE | re.DOTALL,
)
_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!!)\[(?P<label>[^\]\n]+)\]\((?P<url>https?://[^)\s]+)\)"
)
_HTML_HREF_RE: Final[re.Pattern[str]] = re.compile(
    r"""href=["'](?P<url>https?://[^"']+)["']""",
    re.IGNORECASE,
)
_BODY_USED_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?m)^(?P<prefix>>\s*\*\*소스 카운트\*\*:\s*.*?\b본문 사용\s+)(?:미집계|\d+)"
)

_KNOWN_SOURCE_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "alternative.me",
        "api.stlouisfed.org",
        "bea.gov",
        "binance.com",
        "bls.gov",
        "bybit.com",
        "cboe.com",
        "cftc.gov",
        "cnbc.com",
        "coingecko.com",
        "defillama.com",
        "eia.gov",
        "federalreserve.gov",
        "finance.yahoo.com",
        "fred.stlouisfed.org",
        "home.treasury.gov",
        "nasdaq.com",
        "okx.com",
        "sec.gov",
        "stooq.com",
        "theblock.co",
        "treasury.gov",
    }
)


def count_rendered_evidence(
    markdown: str,
    *,
    segment: MarketSegment,
    source_outcomes: tuple[SourceOutcome, ...] = (),
    verified_facts: tuple[object, ...] = (),
) -> RenderedEvidenceCounts:
    """Count public-body evidence links and verified core figure mentions."""
    del segment  # reserved for segment-specific evidence rules.
    body = _public_body(markdown)
    links = tuple(_iter_links(body))
    known_source_names = {name.lower() for name in SOURCE_SPECS_BY_NAME}
    known_source_names.update(outcome.source_name.lower() for outcome in source_outcomes)
    known_source_links = sum(
        1 for label, url in links if _is_known_source_link(label, url, known_source_names)
    )
    verified_figure_mentions = len({str(fact) for fact in verified_facts})
    if source_outcomes:
        skipped_sources = {
            outcome.source_name for outcome in source_outcomes if outcome.status == "skipped"
        }
        healthy_sources = {
            outcome.source_name for outcome in source_outcomes if outcome.status == "ok"
        }
    else:
        skipped_sources, healthy_sources = _public_source_lifecycle(markdown)
    skipped_names = {_normalize_token(name) for name in skipped_sources}
    eligible_links = sum(
        1
        for label, url in links
        if not any(name and name in _normalize_token(label) for name in skipped_names)
        and not _link_has_only_skipped_provider(url, skipped_sources, healthy_sources)
        and _is_known_source_link(label, url, known_source_names)
    )
    raw_body_used_count = max(eligible_links, verified_figure_mentions)
    succeeded_count = sum(1 for outcome in source_outcomes if outcome.status == "ok")
    body_used_count = (
        min(raw_body_used_count, succeeded_count)
        if source_outcomes and succeeded_count > 0
        else raw_body_used_count
    )
    return RenderedEvidenceCounts(
        markdown_links=len(links),
        known_source_links=known_source_links,
        verified_figure_mentions=verified_figure_mentions,
        body_used_count=0
        if source_outcomes and all(outcome.status == "skipped" for outcome in source_outcomes)
        else body_used_count,
    )


def render_body_used_count(markdown: str, counts: RenderedEvidenceCounts) -> str:
    """Replace an untracked/zero body-used marker when rendered evidence exists."""
    if counts.body_used_count <= 0:
        return markdown
    return _BODY_USED_LINE_RE.sub(rf"\g<prefix>{counts.body_used_count}", markdown, count=1)


def _public_body(markdown: str) -> str:
    match = _NUMBERED_SECTION_RE.search(markdown)
    body = markdown[match.start() :] if match is not None else markdown
    body = _DETAILS_RE.sub("", body)
    return "\n".join(
        line
        for line in body.splitlines()
        if not line.lstrip().startswith("> **소스 카운트**:")
        and not line.lstrip().startswith("> **데이터 상태**:")
        and not line.lstrip().startswith("**세그먼트**:")
    )


def _iter_links(body: str) -> tuple[tuple[str, str], ...]:
    links: list[tuple[str, str]] = []
    for match in _MARKDOWN_LINK_RE.finditer(body):
        links.append((match.group("label"), match.group("url")))
    for match in _HTML_HREF_RE.finditer(body):
        links.append(("", match.group("url")))
    return tuple(links)


def _is_known_source_link(label: str, url: str, source_names: set[str]) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if any(host == domain or host.endswith(f".{domain}") for domain in _KNOWN_SOURCE_DOMAINS):
        return True
    normalized_label = _normalize_token(label)
    normalized_host = _normalize_token(host)
    for source_name in source_names:
        normalized_source = _normalize_token(source_name)
        if not normalized_source:
            continue
        if normalized_source in normalized_label or normalized_source in normalized_host:
            return True
    return False


def _public_source_lifecycle(markdown: str) -> tuple[set[str], set[str]]:
    """Read only closed names/labels from the producer's unfenced diagnostic record."""
    skipped: set[str] = set()
    healthy: set[str] = set()
    fence: tuple[str, int] | None = None
    labels = set(SOURCE_SKIP_REASON_LABELS.values())
    for line in markdown.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is not None:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", line):
                fence = None
            continue
        if marker is not None:
            fence = (marker.group(1)[0], len(marker.group(1)))
            continue
        if not line.startswith("> **소스별 상태**: ") or len(line) > 16000:
            continue
        for name, label in re.findall(r"([a-z0-9-]+) 비활성 \(([^()]+)\)", line):
            if name in SOURCE_SPECS_BY_NAME and label in labels:
                skipped.add(name)
        healthy.update(
            name for name in re.findall(r"([a-z0-9-]+) 정상", line) if name in SOURCE_SPECS_BY_NAME
        )
    return skipped, healthy


def _link_has_only_skipped_provider(url: str, skipped: set[str], healthy: set[str]) -> bool:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")

    def matches(name: str) -> bool:
        spec = SOURCE_SPECS_BY_NAME.get(name)
        return spec is not None and any(
            host == domain or host.endswith(f".{domain}") for domain in spec.evidence_domains
        )

    return any(matches(name) for name in skipped) and not any(matches(name) for name in healthy)


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", value.lower())


__all__ = [
    "RenderedEvidenceCounts",
    "count_rendered_evidence",
    "render_body_used_count",
]
