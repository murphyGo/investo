#!/usr/bin/env python3
"""Deterministic closeout benchmark for the u144 public finalizer."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import statistics
import sys
import time
from datetime import UTC, date, datetime
from typing import Final

from investo._internal.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO
from investo.models import Briefing
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher.public_document import PublicDocumentContext, finalize_public_bundle

_TARGET_DATE: Final[date] = date(2026, 7, 17)
_CANONICAL_SEGMENTS: Final[tuple[MarketSegment, ...]] = (
    DOMESTIC_EQUITY,
    US_EQUITY,
    CRYPTO,
)
_SEGMENT_TITLES: Final[dict[MarketSegment, str]] = {
    DOMESTIC_EQUITY: "국내 증시",
    US_EQUITY: "미국 증시",
    CRYPTO: "크립토",
}


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segments", type=_positive_int, choices=range(1, 4), default=3)
    parser.add_argument("--bytes-per-segment", type=_positive_int, default=204_800)
    parser.add_argument("--warmup", type=_positive_int, default=1)
    parser.add_argument("--iterations", type=_positive_int, default=5)
    return parser.parse_args()


def _pad_utf8(template: str, target_bytes: int) -> str:
    marker = "{payload}"
    base = template.replace(marker, "")
    remaining = target_bytes - len(base.encode("utf-8"))
    if remaining < 0:
        raise ValueError(f"bytes-per-segment must be at least {len(base.encode('utf-8'))}")
    payload = "가" * (remaining // 3) + "a" * (remaining % 3)
    rendered = template.replace(marker, payload)
    if len(rendered.encode("utf-8")) != target_bytes:
        raise AssertionError("fixture byte target was not met")
    return rendered


def _build_briefing(segment: MarketSegment, target_bytes: int) -> Briefing:
    title = _SEGMENT_TITLES[segment]
    disclaimer = DISCLAIMER_CRYPTO if segment == CRYPTO else DISCLAIMER
    template = "\n".join(
        (
            f"# {_TARGET_DATE.isoformat()} {title} 시황",
            "",
            "> **오늘의 결론**: [관망] 공개 근거를 차분히 점검합니다.",
            "> **핵심 동인**: 확인 가능한 시장 흐름을 함께 봅니다.",
            "> **주의할 점**: 새 신호가 확인되면 판단을 갱신합니다.",
            "",
            "<details><summary>수집/품질 진단</summary>",
            "정상 수집",
            "</details>",
            "",
            "## ① 요약",
            "공개 근거를 바탕으로 현재 흐름을 요약합니다.",
            "",
            "## ② 전일 핵심 이슈",
            "{payload}",
            "",
            "## ③ 섹터/수급 동향",
            "수급 흐름을 차분히 확인합니다.",
            "",
            "## ④ 지표·이벤트",
            "주요 지표와 일정을 확인합니다.",
            "",
            "## ⑤ 주요 종목",
            "주요 자산의 공개 근거를 확인합니다.",
            "",
            "## ⑥ 오늘의 관전 포인트",
            "- 새 신호가 확인되는지 점검합니다.",
            "",
            disclaimer,
            "",
        )
    )
    rendered = _pad_utf8(template, target_bytes)
    return Briefing(
        target_date=_TARGET_DATE,
        market_summary="[관망] 공개 근거를 차분히 점검합니다.",
        key_issues="확인 가능한 시장 흐름을 함께 봅니다.",
        sector_flow="수급 흐름을 차분히 확인합니다.",
        indicators_events="주요 지표와 일정을 확인합니다.",
        notable_tickers="주요 자산의 공개 근거를 확인합니다.",
        today_watch="새 신호가 확인되는지 점검합니다.",
        disclaimer=disclaimer,
        rendered_markdown=rendered,
    )


def _build_inputs(
    segment_count: int,
    target_bytes: int,
) -> tuple[dict[MarketSegment, Briefing], PublicDocumentContext, str]:
    segments = _CANONICAL_SEGMENTS[:segment_count]
    briefings = {segment: _build_briefing(segment, target_bytes) for segment in segments}
    context = PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=segments,
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="normal",
                item_count=1,
                source_count=1,
                categories=("news",),
                missing_categories=(),
            )
            for segment in segments
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 17, 12, tzinfo=UTC),
    )
    digest = hashlib.sha256()
    for segment in segments:
        digest.update(segment.encode("utf-8"))
        digest.update(b"\0")
        digest.update(briefings[segment].rendered_markdown.encode("utf-8"))
    return briefings, context, digest.hexdigest()


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def main() -> int:
    args = _parse_args()
    briefings, context, input_digest = _build_inputs(
        args.segments,
        args.bytes_per_segment,
    )
    rss_before = _peak_rss_bytes()

    output_digest: str | None = None
    for _ in range(args.warmup):
        bundle = finalize_public_bundle(briefings, context=context)
        output_digest = hashlib.sha256(
            "".join(document.markdown_sha256 for document in bundle.documents).encode()
        ).hexdigest()

    durations_ns: list[int] = []
    for _ in range(args.iterations):
        started_ns = time.perf_counter_ns()
        bundle = finalize_public_bundle(briefings, context=context)
        durations_ns.append(time.perf_counter_ns() - started_ns)
        current_digest = hashlib.sha256(
            "".join(document.markdown_sha256 for document in bundle.documents).encode()
        ).hexdigest()
        if output_digest is not None and current_digest != output_digest:
            raise RuntimeError("finalizer output changed across identical benchmark runs")
        output_digest = current_digest

    rss_after = _peak_rss_bytes()
    result = {
        "bytes_per_segment": args.bytes_per_segment,
        "input_sha256": input_digest,
        "iterations": args.iterations,
        "max_duration_ms": round(max(durations_ns) / 1_000_000, 3),
        "median_duration_ms": round(statistics.median(durations_ns) / 1_000_000, 3),
        "output_sha256": output_digest,
        "peak_rss_delta_bytes": max(0, rss_after - rss_before),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "segments": args.segments,
        "warmup": args.warmup,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
