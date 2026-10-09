"""Numeric presentation repair preserves values and protected Markdown."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from investo._internal.surface_quality import find_surface_quality_issues, repair_surface_artifacts


@pytest.mark.parametrize(
    ("broken", "expected"),
    (
        ("수익률 **+**2.3% 상승.", "수익률 +2.3% 상승."),
        ("가격 **-**$100 하락.", "가격 -$100 하락."),
        ("변화 **+** 1,234.50원.", "변화 + 1,234.50원."),
        ("변화 **-**0.04%p.", "변화 -0.04%p."),
        ("수익률 **+**2.3%상승.", "수익률 +2.3%상승."),
        ("변화 **+**0.1bp 확인.", "변화 +0.1bp 확인."),
        ("수익률 **+**2.3%.", "수익률 +2.3%."),
        ("값 **+**2.3 확인.", "값 +2.3 확인."),
        ("이전 **-**0.04%**p** 유지.", "이전 **-0.04%p** 유지."),
        ("가격 $2.30**T** 확인.", "가격 **$2.30T** 확인."),
    ),
)
def test_repair_preserves_numeric_tokens(broken: str, expected: str) -> None:
    assert any(
        i.code == "markdown.broken_numeric_bold" for i in find_surface_quality_issues(broken)
    )
    repaired = repair_surface_artifacts(broken)
    assert repaired == expected
    assert repair_surface_artifacts(repaired) == repaired
    assert not any(
        i.code == "markdown.broken_numeric_bold" for i in find_surface_quality_issues(repaired)
    )


@pytest.mark.parametrize("value", ("2..3%", "2.3.4%", "1,23원", "2.3abc", "2.3%%"))
def test_ambiguous_numeric_tokens_remain_blocked(value: str) -> None:
    original = f"값 **+**{value} 확인."
    assert repair_surface_artifacts(original) == original
    assert any(
        i.code == "markdown.broken_numeric_bold" for i in find_surface_quality_issues(original)
    )


@pytest.mark.parametrize(
    "text",
    (
        "코드 `**+**2.3%` 그대로.",
        "코드 `첫 줄\n**+**2.3%\n끝` 그대로.",
        "```text\n**+**2.3%\n```\n",
        "<details><summary>수집/품질 진단</summary>\n**+**2.3%\n</details>\n",
        "| 값 | 변동 |\n| --- | --- |\n| 가격 | **+**2.3% |\n",
        "값 | 변동\n--- | ---\n가격 | **+**2.3%\n",
        r"문자 \*\*+\*\*2.3% 그대로.",
        "[**+**2.3%](https://example.com/price) 그대로.",
        "[링크](https://example.com/**+**2.3%) 그대로.",
        "[**+**2.3%][price] 그대로.",
        "[**+**2.3%][] 그대로.",
        "[**+**2.3%]\n\n[**+**2.3%]: https://example.com\n",
        "![**+**2.3%]\n\n[**+**2.3%]: https://example.com/image.png\n",
        "[price]: https://example.com/**+**2.3%\n",
        "<https://example.com/**+**2.3%> 그대로.",
        "<HTTPS://example.com/**+**2.3%> 그대로.",
        "<Http://example.com/**+**2.3%> 그대로.",
        "<ftp://example.com/**+**2.3%> 그대로.",
        "![**+**2.3%](https://example.com/image.png) 그대로.",
        "정상 **+2.3%** 유지.",
        "## ⑦ 면책조항\n투자 자문이 아닙니다: **+**2.3%\n",
    ),
)
def test_protected_and_valid_markdown_remains_identical(text: str) -> None:
    assert repair_surface_artifacts(text) == text


def test_only_prose_outside_code_and_links_is_repaired() -> None:
    text = "**+**2.3% 확인 `**-**$100` [자료](https://example.com) 뒤 **-**$200 하락."
    expected = "+2.3% 확인 `**-**$100` [자료](https://example.com) 뒤 -$200 하락."
    assert repair_surface_artifacts(text) == expected


def test_existing_trace_repair_still_runs_outside_valid_links() -> None:
    assert repair_surface_artifacts("input_hash=abc [뉴스](https://example.com)") == (
        "[뉴스](https://example.com)"
    )


def test_early_numeric_pass_preserves_empty_summary_and_trace_for_their_owners() -> None:
    text = "> **오늘의 결론**: \n> **핵심 동인**: \n## 한눈에 보기\n- \ninput_hash=abc\n"
    assert repair_surface_artifacts(text, numeric_only=True) == text
    assert repair_surface_artifacts(text + "값 **+**2.3%\n", numeric_only=True) == (
        text + "값 +2.3%\n"
    )
    assert repair_surface_artifacts("값 **+**2.3% [뉴스](https://example.com) input_hash=abc") == (
        "값 +2.3% [뉴스](https://example.com)"
    )
    assert repair_surface_artifacts("[input_hash=abc](https://example.com)") == (
        "[input_hash=abc](https://example.com)"
    )


@given(
    sign=st.sampled_from(("+", "-")),
    whole=st.integers(min_value=0, max_value=999_999),
    fraction=st.integers(min_value=0, max_value=999_999),
    currency=st.sampled_from(("", "$")),
    unit=st.sampled_from(("", "%", "%p", "bp", "원", "달러", "T", "M", "B")),
    gap=st.sampled_from(("", " ", "\t")),
)
@settings(max_examples=150)
def test_numeric_invariant_and_idempotence(
    sign: str, whole: int, fraction: int, currency: str, unit: str, gap: str
) -> None:
    value = f"{currency}{whole:,}.{fraction:06d}{unit}"
    original = f"값 **{sign}**{gap}{value} 확인."
    expected = f"값 {sign}{gap}{value} 확인."
    repaired = repair_surface_artifacts(original)
    assert repaired == expected
    assert repair_surface_artifacts(repaired) == repaired
