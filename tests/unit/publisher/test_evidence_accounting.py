"""u123 rendered-body evidence accounting tests."""

from __future__ import annotations

from investo.models.coverage import SourceOutcome
from investo.publisher.evidence_accounting import (
    count_rendered_evidence,
    render_body_used_count,
)


def test_counts_only_public_body_known_source_links() -> None:
    markdown = (
        "# title\n\n"
        "**세그먼트**: [미국 증시](https://example.com/nav)\n\n"
        "<details><summary>수집/품질 진단</summary>\n"
        "[FRED 진단](https://fred.stlouisfed.org/series/DGS10)\n"
        "</details>\n\n"
        "## ① 요약\n\n"
        "[FRED](https://fred.stlouisfed.org/series/DGS10)와 "
        "[일반 링크](https://example.com/story)를 확인했습니다.\n"
    )

    counts = count_rendered_evidence(markdown, segment="us-equity")

    assert counts.markdown_links == 2
    assert counts.known_source_links == 1
    assert counts.verified_figure_mentions == 0
    assert counts.body_used_count == 1


def test_source_name_label_can_identify_known_link() -> None:
    markdown = (
        "## ② 전일 핵심 이슈\n\n"
        "[nasdaq-stocks-news](https://static.example.test/item) 링크입니다.\n"
    )
    counts = count_rendered_evidence(
        markdown,
        segment="us-equity",
        source_outcomes=(SourceOutcome.ok("nasdaq-stocks-news", "news", 1, tier="A"),),
    )

    assert counts.known_source_links == 1
    assert counts.body_used_count == 1


def test_verified_figures_contribute_to_body_used_count() -> None:
    counts = count_rendered_evidence(
        "## ① 요약\n\n본문입니다.\n",
        segment="domestic-equity",
        verified_facts=("kospi_close", "kosdaq_close"),
    )

    assert counts.markdown_links == 0
    assert counts.known_source_links == 0
    assert counts.verified_figure_mentions == 2
    assert counts.body_used_count == 2


def test_body_used_count_caps_to_successful_source_outcomes_when_available() -> None:
    counts = count_rendered_evidence(
        "## ① 요약\n\n"
        "[FRED](https://fred.stlouisfed.org/series/DGS10)와 "
        "[CFTC](https://www.cftc.gov/PressRoom/PressReleases/9000-26)를 확인했습니다.\n",
        segment="us-equity",
        source_outcomes=(SourceOutcome.ok("fred-macro", "macro", 1, tier="A"),),
    )

    assert counts.known_source_links == 2
    assert counts.body_used_count == 1


def test_source_registry_label_identifies_offline_known_link() -> None:
    counts = count_rendered_evidence(
        "## ② 전일 핵심 이슈\n\n"
        "[nasdaq-stocks-news](https://static.example.test/item) 링크입니다.\n",
        segment="us-equity",
    )

    assert counts.known_source_links == 1
    assert counts.body_used_count == 1


def test_render_body_used_count_replaces_untracked_marker() -> None:
    markdown = "> **소스 카운트**: 수집 대상 5 / 성공 2 / 0건 0 / 실패 0 / 본문 사용 미집계\n"
    counts = count_rendered_evidence(
        "## ① 요약\n\n[FRED](https://fred.stlouisfed.org/series/DGS10)\n",
        segment="us-equity",
    )

    assert "본문 사용 1" in render_body_used_count(markdown, counts)


def test_render_body_used_count_only_rewrites_source_count_line() -> None:
    markdown = (
        "본문 사용 미집계라는 표현이 본문에 먼저 나옵니다.\n"
        "> **소스 카운트**: 수집 대상 5 / 성공 2 / 0건 0 / 실패 0 / 본문 사용 미집계\n"
    )
    counts = count_rendered_evidence(
        "## ① 요약\n\n[FRED](https://fred.stlouisfed.org/series/DGS10)\n",
        segment="us-equity",
    )
    out = render_body_used_count(markdown, counts)

    assert out.startswith("본문 사용 미집계라는 표현")
    assert "실패 0 / 본문 사용 1" in out
