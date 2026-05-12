"""u56 — retail tone caps (sentence-ending dominance + filler density)."""

from __future__ import annotations

import logging

import pytest

from investo.publisher.reader_format import (
    FILLER_DENSITY_PER_1000_THRESHOLD,
    SENTENCE_ENDING_DOMINANCE_THRESHOLD,
    check_filler_phrase_density,
    check_sentence_ending_diversity,
)


def test_homogeneous_did_endings_warns(caplog: pytest.LogCaptureFixture) -> None:
    body = "\n".join(
        [
            "오늘 시장은 상승했다.",
            "거래량은 증가했다.",
            "변동성은 확대됐다.",
            "지수는 사상 최고치를 경신했다.",
            "투자자들은 환호했다.",
        ]
    )
    with caplog.at_level(logging.WARNING):
        report = check_sentence_ending_diversity(body)
    assert report.dominant == "했다"
    assert report.dominant_ratio > SENTENCE_ENDING_DOMINANCE_THRESHOLD
    assert any("tone.sentence_ending_dominance" in r.message for r in caplog.records)


def test_diverse_endings_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    body = "\n".join(
        [
            "오늘 시장은 상승했다.",
            "거래량은 증가된다.",
            "전망은 긍정적이다.",
            "투자 환경 개선이 보인다.",
        ]
    )
    with caplog.at_level(logging.WARNING):
        report = check_sentence_ending_diversity(body)
    # The dominant ratio is at most 1/4 = 0.25 (each ending appears
    # roughly once), which is below 0.6.
    assert report.dominant_ratio <= 0.6
    assert not any("tone.sentence_ending_dominance" in r.message for r in caplog.records)


def test_empty_body_does_not_warn() -> None:
    report = check_sentence_ending_diversity("")
    assert report.total == 0
    assert report.dominant is None


def test_filler_density_above_threshold_warns(caplog: pytest.LogCaptureFixture) -> None:
    # 5 filler words in ~200 chars → density 25 / 1000 chars
    body = "전망 가능성 우려 작용 여부에 대한 분석이 필요하다. " * 3
    with caplog.at_level(logging.WARNING):
        report = check_filler_phrase_density(body)
    assert report.density_per_1000 > FILLER_DENSITY_PER_1000_THRESHOLD
    assert any("tone.filler_density" in r.message for r in caplog.records)


def test_filler_density_below_threshold_does_not_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = (
        "오늘 미국 시장은 강한 상승 마감을 기록했다. "
        "S&P 500 지수가 1% 상승하며 사상 최고치를 갱신했다. "
        "기술주 주도의 랠리였다는 점이 특징이다. "
        "거래량은 평균 대비 소폭 증가에 그쳤다. "
        "투자자들은 다음 주 FOMC 회의를 주시한다. "
    ) * 4
    with caplog.at_level(logging.WARNING):
        report = check_filler_phrase_density(body)
    assert report.density_per_1000 <= FILLER_DENSITY_PER_1000_THRESHOLD
    assert not any("tone.filler_density" in r.message for r in caplog.records)


def test_disclaimer_footer_is_excluded() -> None:
    body = (
        "오늘 시장은 상승했다.\n\n"
        "## ⑦ 면책조항\n"
        "본 시황은 매매 권유가 아닙니다.\n"
        "여부 여부 여부 여부 여부 여부\n"  # huge filler in footer region
    )
    report = check_filler_phrase_density(body)
    # The footer-region 여부 should NOT have inflated the density —
    # masking excludes from the anchor onwards.
    assert "여부" not in report.counts


def test_code_block_is_excluded_from_sentence_ending() -> None:
    body = "## ① 요약\n오늘은 상승했다.\n\n```\n했다 했다 했다 했다 했다 했다 했다 했다.\n```\n"
    report = check_sentence_ending_diversity(body)
    # Code-block contents are not counted.
    assert report.total <= 1


def test_table_row_excluded_from_filler() -> None:
    body = "## ① 요약\n정상 prose.\n\n| 종목 | 전망 |\n| --- | --- |\n| AAPL | 여부 우려 가능성 |\n"
    report = check_filler_phrase_density(body)
    assert "여부" not in report.counts
