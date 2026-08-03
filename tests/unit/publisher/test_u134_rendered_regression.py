"""Rendered regressions for the four 2026-06-29/30 u134 defects."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from investo._internal.crypto_indicators import render_crypto_indicator_block
from investo.briefing._assembly.summary_extraction import _driver_summary
from investo.briefing._reader_enhance.enhancement import _render_public_conclusion
from investo.models import NormalizedItem
from investo.publisher.channel_anchor_block import render_channel_anchor_block
from investo.publisher.reader_format import apply_reader_format, reflow_first_viewport

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "u134"
    / "2026-06-29-30-composition-shapes.json"
)


def _fixture() -> dict[str, str]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) and isinstance(value, str) for key, value in payload.items())
    return payload


def _funding_item(rate: str) -> NormalizedItem:
    return NormalizedItem(
        source_name="bybit-derivatives",
        category="price",
        title="BTC funding",
        published_at=datetime(2026, 6, 29, tzinfo=UTC),
        raw_metadata={
            "indicator": "btc_funding",
            "btc_funding_rate": rate,
        },
    )


def _render_diagnostics(document: str) -> str:
    return reflow_first_viewport(
        apply_reader_format(document, segment="us-equity"),
        segment="us-equity",
    )


def test_u134_reproduced_shapes_render_repaired_values() -> None:
    fixture = _fixture()

    driver = _driver_summary(fixture["driver_section"], fallback="fallback")
    conclusion = _render_public_conclusion(fixture["tagged_conclusion"])
    diagnostic_document = _render_diagnostics(fixture["diagnostic_document"])
    public_prefix = diagnostic_document.split("<details", 1)[0]
    details = diagnostic_document.split("<summary>수집/품질 진단</summary>", 1)[1].split(
        "</details>", 1
    )[0]
    item = _funding_item(fixture["funding_rate"])
    indicator_block = render_crypto_indicator_block((item,))
    channel_block = render_channel_anchor_block("crypto", crypto_items=(item,))

    assert driver == fixture["expected_driver"]
    assert "마감 나스닥 기사" not in driver
    assert conclusion == fixture["expected_conclusion"]
    assert "관찰된다. 수집 근거가 제한적입니다" not in conclusion
    assert fixture["expected_source_count"] in details
    assert "수집 상세는 진단 섹션에서 확인할 수 있습니다." not in details
    assert fixture["expected_source_count"] not in public_prefix
    assert "0건 2" not in public_prefix
    assert "실패 3" not in public_prefix
    assert "본문 사용 미집계" not in public_prefix
    assert (
        "> **데이터 상태**: 부분 · 이번 문서는 수집 근거가 제한적입니다. "
        "· 수집 상세는 진단 섹션에서 확인할 수 있습니다."
    ) in public_prefix
    expected_rate = fixture["expected_funding_rate"]
    assert f"| BTC 펀딩비 | {expected_rate} |" in indicator_block
    assert f"| 펀딩/OI/청산 | 펀딩 {expected_rate} |" in channel_block
    assert fixture["funding_rate"] not in indicator_block
    assert fixture["funding_rate"] not in channel_block


def test_u134_repaired_rendering_is_byte_idempotent() -> None:
    fixture = _fixture()
    driver = _driver_summary(fixture["driver_section"], fallback="fallback")
    conclusion = _render_public_conclusion(fixture["tagged_conclusion"])
    once = _render_diagnostics(fixture["diagnostic_document"])
    twice = _render_diagnostics(once)
    noisy_item = _funding_item(fixture["funding_rate"])
    repaired_item = _funding_item(fixture["expected_funding_rate"])

    assert _driver_summary(driver, fallback="fallback") == driver
    assert _render_public_conclusion(conclusion) == conclusion
    assert twice == once
    assert render_crypto_indicator_block((noisy_item,)) == render_crypto_indicator_block(
        (repaired_item,)
    )
    assert render_channel_anchor_block("crypto", crypto_items=(noisy_item,)) == (
        render_channel_anchor_block("crypto", crypto_items=(repaired_item,))
    )
