"""u100 surface-quality shared helper tests."""

from __future__ import annotations

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

from investo._internal.surface_quality import (
    SurfaceQualityIssue,
    extract_first_viewport,
    find_glossary_collision_issues,
    find_surface_quality_issues,
    has_blocking_surface_issue,
    looks_truncated_caution_continuation,
    repair_surface_artifacts,
    repair_surface_link_targets,
)


def test_extract_first_viewport_stops_before_section_one() -> None:
    text = "# title\n\nintro\n\n## ① 요약\n본문"

    assert extract_first_viewport(text) == "# title\n\nintro\n\n"


def _issues_with_code(text: str, code: str) -> list[SurfaceQualityIssue]:
    return [issue for issue in find_surface_quality_issues(text) if issue.code == code]


def test_surface_quality_issue_four_argument_construction_remains_compatible_u150() -> None:
    issue = SurfaceQualityIssue("trace.fragment", "block", "trace", "body")

    assert issue.link_shape is None


def test_surface_quality_issue_rejects_an_incompatible_link_shape_u150() -> None:
    with pytest.raises(ValueError, match="link_shape must be compatible"):
        SurfaceQualityIssue(
            "markdown.unmatched_link",
            "block",
            "fragment",
            "body",
            "autolink",
        )


_U153_RESIDUES = (
    "매수세가 본문 참고.",
    "기관의 본문 참고.",
    "이번 문서는 본문 참고.",
    "반등하며 본문 참고.",
    "상승...본문 참고.",
    "상승… 본문 참고.",
    "본문 참고.",
    "상승했습니다. 본문 참고. 본문 참고.",
    "지수는 3.14. 본문 참고.",
)


@pytest.mark.parametrize("value", _U153_RESIDUES)
@pytest.mark.parametrize(
    "prefix", ["> **오늘의 결론**: ", "> **핵심 동인**: ", "## 한눈에 보기\n- ", "## 한눈에 보기\n"]
)
def test_u153_scanner_rejects_owned_continuation(value: str, prefix: str) -> None:
    line = f"{prefix}{value}"
    issues = _issues_with_code(f"# 제목\n{line}\n## ① 요약\n본문", "summary.truncated_mid_token")
    assert len(issues) == 1
    assert issues[0].severity == "block"
    assert issues[0].evidence == line.splitlines()[-1]
    assert looks_truncated_caution_continuation(value, require_complete=True)


@pytest.mark.parametrize(
    "prefix", [">**오늘의 결론**:", "> **오늘의 결론** :", ">\t**핵심 동인**\t:"]
)
def test_u153_scanner_owns_existing_callout_whitespace_variants(prefix: str) -> None:
    text = f"{prefix} 기관의 본문 참고.\n## ① 요약\n본문"
    assert len(_issues_with_code(text, "summary.truncated_mid_token")) == 1


@pytest.mark.parametrize(
    "value",
    [
        "금리와 실적",
        "입법 가속화 vs. 정치적 마찰",
        "지수는 3.14% 상승했습니다. 본문 참고.",
        "**지수**는 상승했습니다. 본문 참고.",
        "[지수](https://example.com/a) 상승입니다. 본문 참고.",
        "추가 확인 필요! 본문 참고.",
        "확인 필요? 본문 참고.",
        "상승했습니다。 본문 참고.",
        "확인된 요약이 부족합니다.",
        "핵심 동인은 추가 확인이 필요합니다.",
        "요약은 본문을 참고하세요.",
    ],
)
def test_u153_scanner_accepts_short_headings_and_complete_continuations(value: str) -> None:
    text = f"> **오늘의 결론**: {value}\n## 한눈에 보기\n{value}\n## ① 요약\n본문"
    assert not _issues_with_code(text, "summary.truncated_mid_token")
    assert not looks_truncated_caution_continuation(value, require_complete=True)


@pytest.mark.parametrize(
    "region",
    [
        "기관의 본문 참고.",  # unowned preamble prose
        "## 거시\n기관의 본문 참고.",
        "## 한눈에 보기\n## 거시\n기관의 본문 참고.",
        "## 한눈에 보기\n##\t거시\n기관의 본문 참고.",
        "## 한눈에 보기\n##\u00a0거시\n기관의 본문 참고.",
        "## 한눈에 보기\n##\n기관의 본문 참고.",
        "## 한눈에 보기\n## 한눈에 보기\n기관의 본문 참고.",
        "## 거시\n## 한눈에 보기\n기관의 본문 참고.",
        "## 한눈에 보기\n| 기관의 본문 참고.",
        "## 한눈에 보기\n[ref]: https://example.com 기관의 본문 참고.",
        "## 한눈에 보기\n> **소스 카운트**: 기관의 본문 참고.",
        "## 한눈에 보기\n**세그먼트**: 기관의 본문 참고.",
        "## 한눈에 보기\n투자 자문이 아닙니다 기관의 본문 참고.",
        "## 한눈에 보기\n수집/품질 진단: 기관의 본문 참고.",
        "## 한눈에 보기\n    기관의 본문 참고.",
        "## 한눈에 보기\n\t기관의 본문 참고.",
        "## 한눈에 보기\n```text\n기관의 본문 참고.\n```",
        "## 한눈에 보기\n~~~text\n기관의 본문 참고.\n~~~",
        "## 한눈에 보기\n<details>\n기관의 본문 참고.\n</details>",
        "## 한눈에 보기\n<details>\n<details>\n</details>\n기관의 본문 참고.\n</details>",
    ],
)
def test_u153_scanner_does_not_expand_to_unowned_regions(region: str) -> None:
    text = f"# 제목\n{region}\n## ① 요약\n기관의 본문 참고.\n> **오늘의 결론**: 기관의 본문 참고."
    assert not _issues_with_code(text, "summary.truncated_mid_token")


@pytest.mark.parametrize(
    "protected",
    [
        "    ## 가짜 제목\n",
        "~~~text\n## 가짜 제목\n~~~\n",
        "````text\n```\n## 가짜 제목\n````\n",
        "<details>\n<details>\n</details>\n## 가짜 제목\n    </details>\n",
        "```text`oops\n",
        "~~~text\n```\n~~~\n",
    ],
)
def test_u153_owned_prose_resumes_after_protected_content(protected: str) -> None:
    text = f"## 한눈에 보기\n{protected}기관의 본문 참고.\n## ① 요약\n본문"
    issues = _issues_with_code(text, "summary.truncated_mid_token")
    assert len(issues) == 1
    assert issues[0].evidence == "기관의 본문 참고."


@pytest.mark.parametrize("length", [1575, 1585, 1590, 1599, 1600, 1700, 3200])
@pytest.mark.parametrize("ending", ["", "\n## ① 요약\n본문"])
def test_u153_scanner_keeps_full_cross_window_summary_evidence(length: int, ending: str) -> None:
    line = "> **오늘의 결론**: " + "가" * length + " 기관의 본문 참고."
    issues = _issues_with_code(line + ending, "summary.truncated_mid_token")
    assert len(issues) == 1
    assert issues[0].evidence == line
    assert issues[0].region == "segment_first_viewport"


def test_u153_no_anchor_split_preserves_owned_and_unowned_boundaries() -> None:
    # The artificial split must not re-read a partial line as a new callout.
    text = "일반 본문 " + "가" * 1594 + "> **오늘의 결론**: 기관의 본문 참고."
    assert not _issues_with_code(text, "summary.truncated_mid_token")


@pytest.mark.parametrize("length", [100, 1600, 2400])
def test_u153_summary_finding_never_impersonates_bounded_body_rule(length: int) -> None:
    text = "일반 본문 " + "가" * length + "\n> **오늘의 결론**: 기관의 본문 참고."
    issues = _issues_with_code(text, "summary.truncated_mid_token")
    assert len(issues) == 1
    assert issues[0].region == "segment_first_viewport"


def test_u153_tldr_without_section_one_and_original_link_findings() -> None:
    text = "## 한눈에 보기\n- [링크](https://example.com/...) 기관의 본문 참고.\n## 거시\n본문"
    codes = {issue.code for issue in find_surface_quality_issues(text)}
    assert {"summary.truncated_mid_token", "markdown.href_ellipsis"} <= codes


@pytest.mark.parametrize("value", _U153_RESIDUES)
def test_u153_caution_default_remains_legacy(value: str) -> None:
    retained = value.removesuffix("본문 참고.").rstrip()
    expected = bool(retained) and not retained.endswith((".", "!", "?", "。"))
    assert looks_truncated_caution_continuation(value) is expected


@seed(15320260907)
@settings(max_examples=80, print_blob=True)
@given(
    number=st.decimals(
        min_value="0.01", max_value="999.99", places=2, allow_nan=False, allow_infinity=False
    ),
    fragment=st.sampled_from(("매수세가", "기관의", "이번 문서는", "반등하며")),
    marker=st.sampled_from(("- ", "* ", "+ ", "1. ", "1) ", "")),
)
def test_u153_scanner_complete_sentence_and_fragment_property(
    number: object, fragment: str, marker: str
) -> None:
    sentence = f"지수는 {number}% 상승했습니다."
    safe = f"{sentence} 본문 참고."
    unsafe = f"{sentence} {fragment} 본문 참고."
    for value, rejected in ((safe, False), (unsafe, True)):
        text = f"## 한눈에 보기\n{marker}{value}\n## ① 요약\n{unsafe}"
        issues = _issues_with_code(text, "summary.truncated_mid_token")
        assert bool(issues) is rejected
        assert find_surface_quality_issues(text) == find_surface_quality_issues(text)


def test_repair_bad_token_and_dangling_ellipsis() -> None:
    text = "# title\n\n불강한성 확대 ...\n...\n\n## ① 요약\n본문"

    repaired = repair_surface_artifacts(text)

    assert "불강한성" not in repaired
    assert "불확실성 확대" in repaired
    assert "\n...\n" not in repaired
    assert repair_surface_artifacts(repaired) == repaired


def test_repairs_trace_fragments_without_mutating_unmatched_link_markers() -> None:
    text = "# title\n\n[broken link\nstage1_hash=abc\n\n## ① 요약"

    repaired = repair_surface_artifacts(text)
    assert "stage1_hash" not in repaired
    assert "[broken link" in repaired

    issues = find_surface_quality_issues(text)
    codes = {issue.code for issue in issues if issue.severity == "block"}

    assert "markdown.unmatched_link" in codes
    assert "trace.fragment" in codes
    assert has_blocking_surface_issue(text)

    repaired_issues = find_surface_quality_issues(repaired)
    assert {issue.code for issue in repaired_issues if issue.severity == "block"} == {
        "markdown.unmatched_link",
    }


def test_owned_link_transform_repairs_recoverable_markdown_link_fragment() -> None:
    text = "# title\n\n> **오늘의 결론**: [broken link](https://example.com\n\n## ① 요약"

    cosmetically_repaired = repair_surface_artifacts(text)
    repaired = repair_surface_link_targets(text)

    assert "[broken link](" in cosmetically_repaired
    assert "[broken link](" not in repaired
    assert "broken link" in repaired
    assert not has_blocking_surface_issue(repaired)
    assert [
        issue.code for issue in find_surface_quality_issues(text) if issue.severity == "block"
    ] == ["markdown.unmatched_link"]


def test_both_repair_helpers_leave_unmatched_residual_unchanged() -> None:
    text = "# title\n\n> **오늘의 결론**: [국내 증시 변동성 확대\n\n## ① 요약"

    cosmetically_repaired = repair_surface_artifacts(text)
    link_repaired = repair_surface_link_targets(text)

    assert "[국내 증시" in cosmetically_repaired
    assert link_repaired == text
    residual = _issues_with_code(link_repaired, "markdown.unmatched_link")
    assert len(residual) == 1
    assert residual[0].link_shape == "unmatched_residual"


def test_repairs_first_viewport_trace_assignment_lines() -> None:
    text = (
        "# title\n\n"
        "> **오늘의 결론**: 금리 민감도가 커졌습니다.\n"
        "- `input_hash`: `1ee42e89b281`\n"
        "stage2_hash=abcdef123456\n\n"
        "## ① 요약"
    )

    repaired = repair_surface_artifacts(text)

    assert "input_hash" not in repaired
    assert "stage2_hash" not in repaired
    assert "> **오늘의 결론**: 금리 민감도가 커졌습니다." in repaired
    assert not has_blocking_surface_issue(repaired)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_u153_integration_preserves_separators_but_removes_trace_lines(newline: str) -> None:
    clean = newline.join(
        [
            "# 제목",
            "",
            "**세그먼트**: 국내 증시",
            " ",
            "> **오늘의 결론**: 흐름을 확인했다.",
            "",
            "## ① 요약",
        ]
    )
    contaminated = clean.replace(
        "**세그먼트**: 국내 증시", "stage2_hash=redacted" + newline + "**세그먼트**: 국내 증시"
    )

    assert repair_surface_artifacts(clean) == clean
    assert repair_surface_artifacts(contaminated) == clean
    assert repair_surface_artifacts(repair_surface_artifacts(contaminated)) == clean
    assert not has_blocking_surface_issue(clean)


def test_escaped_trace_assignment_cannot_bypass_surface_gate_u150() -> None:
    text = "# title\n\ninput\\_hash=private\n\n## ① 요약"

    issues = find_surface_quality_issues(text)
    repaired = repair_surface_artifacts(text)

    assert any(issue.code == "trace.fragment" for issue in issues)
    assert "input\\_hash" not in repaired


def test_cosmetic_repair_never_erases_a_link_finding_before_policy_u150() -> None:
    text = "[ref]: https://example.invalid/... stage1_hash=private"

    assert repair_surface_artifacts(text) == text
    issues = find_surface_quality_issues(text)
    assert [(issue.code, issue.link_shape) for issue in issues] == [
        ("trace.fragment", None),
        ("markdown.href_ellipsis", "reference_definition"),
    ]


def test_preserves_protected_regions() -> None:
    text = (
        "# title\n\n"
        "```text\n불강한성 ...\n```\n"
        "| 컬럼 |\n| 불강한성 ... |\n"
        "<details><summary>수집/품질 진단</summary>\n"
        "stage1_hash=abc\n"
        "</details>\n"
        "## ① 요약\n본문"
    )

    repaired = repair_surface_artifacts(text)
    issues = find_surface_quality_issues(repaired)

    assert "```text\n불강한성 ...\n```" in repaired
    assert "| 불강한성 ... |" in repaired
    assert "stage1_hash=abc" in repaired
    assert [issue for issue in issues if issue.severity == "block"] == []


def test_repeated_template_phrase_warns_only() -> None:
    text = "# title\n\n본문을 참고하세요 본문을 참고하세요 본문을 참고하세요\n\n## ① 요약"

    issues = find_surface_quality_issues(text)

    assert any(issue.code == "template.repeated_phrase" for issue in issues)
    assert [issue for issue in issues if issue.severity == "block"] == []


def test_balanced_bracket_status_label_is_public_diagnostic_not_unmatched_link() -> None:
    text = "# title\n\n> **데이터 상태**: [데이터부족]\n\n## ① 요약"

    issues = find_surface_quality_issues(text)

    assert [issue for issue in issues if issue.code == "markdown.unmatched_link"] == []
    public = [issue for issue in issues if issue.code == "public_diagnostic.raw_label"]
    assert public
    assert public[0].severity == "block"
    assert public[0].region == "segment_first_viewport"


def test_public_diagnostics_allowed_inside_collapsed_details() -> None:
    text = (
        "# title\n\n"
        "## ① 요약\n본문\n\n"
        "<details><summary>수집/품질 진단</summary>\n\n"
        "> **소스 카운트**: 수집 대상 6 / 성공 4 / 0건 1 / 실패 1 / 본문 사용 미집계\n"
        "</details>\n"
    )

    issues = find_surface_quality_issues(text)

    assert [issue for issue in issues if issue.code == "public_diagnostic.raw_label"] == []


def test_watchlist_matcher_reason_blocks_public_surface_u111() -> None:
    text = (
        "# title\n\n"
        "> **내 관심 자산 영향**: 1건 확인 — BTC: [alias:Bitcoin] Bitcoin ETF flow\n\n"
        "## ① 요약\n본문"
    )

    issues = find_surface_quality_issues(text)

    public = [issue for issue in issues if issue.code == "watchlist.matcher_reason.public"]
    assert public
    assert public[0].severity == "block"
    assert public[0].evidence == "[alias:Bitcoin]"


def test_watchlist_matcher_reason_allowed_inside_collapsed_details_u111() -> None:
    text = (
        "# title\n\n"
        "## ① 요약\n본문\n\n"
        "<details><summary>진단: 보류/제외된 후보</summary>\n\n"
        "- BTC · yahoo-finance-news [boundary-term]\n"
        "</details>\n"
    )

    issues = find_surface_quality_issues(text)

    assert [issue for issue in issues if issue.code == "watchlist.matcher_reason.public"] == []


def test_glossary_collision_blocks_wrong_esma_futures_gloss_u125() -> None:
    text = (
        "# title\n\n"
        "> **용어 가이드**: 이번 시황에서 처음 등장한 용어 — ESMA(미니S&P선물)\n\n"
        "## ① 요약\n본문"
    )

    issues = find_surface_quality_issues(text)

    collision = [issue for issue in issues if issue.code == "glossary.collision.forbidden_pair"]
    assert collision
    assert collision[0].severity == "block"
    assert collision[0].evidence == "ESMA(미니S&P선물)"
    assert has_blocking_surface_issue(text)


def test_glossary_collision_allows_valid_esma_and_futures_glosses_u125() -> None:
    text = (
        "# title\n\n"
        "> **용어 가이드**: ESMA(유럽증권시장청), ESU26(미니 S&P 500 선물)\n\n"
        "## ① 요약\n본문"
    )

    assert find_glossary_collision_issues(text) == ()
    assert _issues_with_code(text, "glossary.collision.forbidden_pair") == []


def test_public_diagnostics_block_in_segment_body() -> None:
    text = "# title\n\n## ① 요약\n본문 사용 미집계\n"

    issues = find_surface_quality_issues(text)

    public = [issue for issue in issues if issue.code == "public_diagnostic.raw_label"]
    assert public
    assert public[0].evidence == "본문 사용 미집계"
    assert public[0].region == "segment_body"


def test_watermark_window_contract_alignment_u132() -> None:
    valid_lines = (
        "**기준 시각**: 2026-06-30 KST · "
        "수집창 2026-06-29T15:00Z ~ 2026-06-30T15:00Z (종료 미포함)",
        "**기준 시각**: 2026-06-30 NY · 수집창 2026-06-30T04:00Z ~ 2026-07-01T04:00Z (종료 미포함)",
        "**기준 시각**: 2026-06-30 UTC · "
        "수집창 2026-06-30T00:00Z ~ 2026-07-01T00:00Z (종료 미포함)",
    )
    missing = (
        "# title\n\n"
        "**기준 시각**: 2026-06-30 NY · "
        "2026-06-30T04:00Z ~ 2026-07-01T04:00Z (종료 미포함)\n\n"
        "## ① 요약"
    )
    legacy = (
        "# title\n\n"
        "**기준 시각**: 2026-06-30 NY · "
        "2026-06-30T04:00Z, 2026-07-01T04:00Z)\n\n"
        "## ① 요약"
    )
    unbalanced = (
        "# title\n\n"
        "**기준 시각**: 2026-06-30 NY · "
        "수집창 2026-06-30T04:00Z ~ 2026-07-01T04:00Z (종료 미포함\n\n"
        "## ① 요약"
    )
    ignored = "# title\n\n기준 시각: 수집창 없음\n\n## ① 요약"

    for line in valid_lines:
        assert (
            _issues_with_code(
                f"# title\n\n{line}\n\n## ① 요약",
                "watermark.window_bracket",
            )
            == []
        )
    for text in (missing, legacy, unbalanced):
        assert any(i.code == "watermark.window_bracket" for i in find_surface_quality_issues(text))
    assert _issues_with_code(ignored, "watermark.window_bracket") == []


def test_repairs_broken_numeric_bold_and_blocks_leftovers_u112() -> None:
    text = (
        "# title\n\n"
        "> **오늘의 결론**: **-**0.04%**p**와 $2.30**T, "
        "**+0.74달러(**+0.97%**)** 확인\n\n"
        "## ① 요약"
    )

    repaired = repair_surface_artifacts(text)

    assert "**-0.04%p**" in repaired
    assert "**$2.30T**" in repaired
    assert "**+0.74달러(+0.97%)**" in repaired
    assert _issues_with_code(repaired, "markdown.broken_numeric_bold") == []
    broken = "# title\n\n> **오늘의 결론**: **-**0.04% 남음\n\n## ① 요약"
    assert any(
        i.code == "markdown.broken_numeric_bold" for i in find_surface_quality_issues(broken)
    )


def test_href_ellipsis_blocks_targets_but_not_visible_text_u112() -> None:
    visible = "# title\n\n[긴 제목...](https://example.com/full)\n\n## ① 요약"
    inline = "# title\n\n[긴 제목](https://example.com/...)\n\n## ① 요약"
    image = "# title\n\n![alt](https://example.com/…/img.png)\n\n## ① 요약"
    ref = "# title\n\n[id]: https://example.com/...\n\n## ① 요약"
    autolink = "# title\n\n<https://example.com/...>\n\n## ① 요약"
    code = "# title\n\n`[x](https://example.com/...)`\n\n## ① 요약"

    assert _issues_with_code(visible, "markdown.href_ellipsis") == []
    expected_shapes = ("inline_link", "image", "reference_definition", "autolink")
    for text, expected_shape in zip((inline, image, ref, autolink), expected_shapes, strict=True):
        issues = _issues_with_code(text, "markdown.href_ellipsis")
        assert len(issues) == 1
        assert issues[0].link_shape == expected_shape
    assert _issues_with_code(code, "markdown.href_ellipsis") == []


def test_closed_invalid_links_emit_one_finding_per_occurrence_in_span_order_u150() -> None:
    line = (
        "[첫째](https://example.invalid/a/...) 뒤 "
        "![둘째](https://example.invalid/b/…) 뒤 "
        "<https://example.invalid/c/...>"
    )

    issues = _issues_with_code(line, "markdown.href_ellipsis")

    assert [issue.link_shape for issue in issues] == ["inline_link", "image", "autolink"]
    assert [issue.evidence for issue in issues] == [
        "https://example.invalid/a/...",
        "https://example.invalid/b/…",
        "https://example.invalid/c/...",
    ]
    assert repair_surface_link_targets(line) == "첫째 뒤 둘째 뒤 "


@pytest.mark.parametrize(
    "target",
    (
        "https://example.invalid/a/.../(tail)",
        "https://example.invalid/a/(x)/.../tail",
        r"https://example.invalid/a/\(...\)/tail",
    ),
)
def test_inline_invalid_target_balances_unescaped_parentheses_u150(target: str) -> None:
    line = f"[표시 이름]({target})"

    issues = _issues_with_code(line, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == "inline_link"
    assert issues[0].evidence == target
    assert repair_surface_link_targets(line) == "표시 이름"


@pytest.mark.parametrize(
    ("text", "shape", "replacement"),
    (
        (
            "[표시 이름](<https://example.invalid/a/...>)",
            "inline_link",
            "표시 이름",
        ),
        (
            "![대체문구](<https://example.invalid/a/...>)",
            "image",
            "대체문구",
        ),
        (
            "[바깥 [안쪽]](https://example.invalid/a/...)",
            "inline_link",
            "바깥 [안쪽]",
        ),
        (
            "![바깥 [안쪽]](https://example.invalid/a/...)",
            "image",
            r"바깥 \[안쪽\]",
        ),
    ),
)
def test_closed_inline_shapes_support_angle_targets_and_nested_labels_u150(
    text: str,
    shape: str,
    replacement: str,
) -> None:
    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == shape
    assert repair_surface_link_targets(text) == replacement


@pytest.mark.parametrize(
    ("text", "shape", "replacement"),
    (
        (
            '[표시 이름](<https://example.invalid/a/...> "title")',
            "inline_link",
            "표시 이름",
        ),
        (
            '![대체문구](<https://example.invalid/a/...> "title")',
            "image",
            "대체문구",
        ),
    ),
)
def test_angle_destination_with_optional_title_keeps_one_owner_u150(
    text: str,
    shape: str,
    replacement: str,
) -> None:
    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == shape
    assert repair_surface_link_targets(text) == replacement


@pytest.mark.parametrize(
    ("text", "shape", "replacement"),
    (
        (
            r"[표시](<https://example.invalid/a\>/...>)",
            "inline_link",
            "표시",
        ),
        (
            r"[표시](<https://example.invalid/a/...\>/tail>)",
            "inline_link",
            "표시",
        ),
        (
            r"![대체](<https://example.invalid/a\>/...>)",
            "image",
            "대체",
        ),
    ),
)
def test_angle_destination_escaped_close_keeps_outer_owner_u150(
    text: str,
    shape: str,
    replacement: str,
) -> None:
    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == shape
    assert repair_surface_link_targets(text) == replacement


@pytest.mark.parametrize(
    "text",
    (
        '[표시](https://example.com/full "more...")',
        '![대체](https://example.com/image.png "설명…")',
        '[표시](<https://example.com/full> "more...")',
        '![대체](<https://example.com/image.png> "설명…")',
    ),
)
def test_ellipsis_in_optional_title_does_not_invalidate_destination_u150(text: str) -> None:
    assert _issues_with_code(text, "markdown.href_ellipsis") == []
    assert repair_surface_link_targets(text) == text


@pytest.mark.parametrize(
    "text",
    (
        '[표시](https://example.com/full "<https://example.invalid/a/...>")',
        '![대체](https://example.com/image.png "<https://example.invalid/a/...>")',
        '[표시](<https://example.com/full> "<https://example.invalid/a/...>")',
        '[id]: https://example.com/full "<https://example.invalid/a/...>"',
        '[id]: <https://example.com/full> "<https://example.invalid/a/...>"',
    ),
)
def test_angle_text_in_optional_title_is_not_a_top_level_autolink_u150(text: str) -> None:
    assert _issues_with_code(text, "markdown.href_ellipsis") == []
    assert repair_surface_link_targets(text) == text


@pytest.mark.parametrize(
    "target",
    (
        "<HTTPS://example.invalid/a/...>",
        "<HttpS://example.invalid/a/…>",
    ),
)
def test_autolink_scheme_is_ascii_case_insensitive_u150(target: str) -> None:
    issues = _issues_with_code(target, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == "autolink"
    assert repair_surface_link_targets(target) == ""


def test_mixed_closed_and_incomplete_links_share_one_ordered_transform_u150() -> None:
    line = (
        "[닫힌 링크](https://example.invalid/...) / "
        "[불완전 링크](https://example.invalid/incomplete"
    )

    issues = [
        issue
        for issue in find_surface_quality_issues(line)
        if issue.code in {"markdown.href_ellipsis", "markdown.unmatched_link"}
    ]

    assert [(issue.code, issue.link_shape) for issue in issues] == [
        ("markdown.href_ellipsis", "inline_link"),
        ("markdown.unmatched_link", "incomplete_inline"),
    ]
    assert repair_surface_link_targets(line) == "닫힌 링크 / 불완전 링크"


@pytest.mark.parametrize(
    "text",
    (
        "[<https://example.invalid/inner/...>](https://example.invalid/outer/...)",
        "[[안쪽](https://example.invalid/inner/...)](https://example.invalid/outer/...)",
        "![<https://example.invalid/inner/...>](https://example.invalid/outer/...)",
    ),
)
def test_nested_invalid_targets_fail_closed_without_partial_transform_u150(text: str) -> None:
    repaired = repair_surface_link_targets(text)

    assert repaired == text
    assert repair_surface_link_targets(repaired) == repaired
    assert _issues_with_code(repaired, "markdown.href_ellipsis")
    unmatched = _issues_with_code(repaired, "markdown.unmatched_link")
    assert len(unmatched) == 1
    assert unmatched[0].link_shape == "unmatched_residual"


def test_link_transform_escapes_unicode_image_alt_in_fixed_order_u150() -> None:
    text = r"![한글 & <위험> \`*_\[\]()!](https://example.invalid/image/…)"

    repaired = repair_surface_link_targets(text)

    assert repaired == r"한글 &amp; &lt;위험&gt; \\\`\*\_\\\[\\\]\(\)\!"
    assert repair_surface_link_targets(repaired) == repaired
    assert [
        issue
        for issue in find_surface_quality_issues(repaired)
        if issue.code in {"markdown.href_ellipsis", "markdown.unmatched_link"}
    ] == []


def test_reference_definition_is_signaled_but_never_rewritten_u150() -> None:
    text = "[합성-참조]: https://example.invalid/source/..."

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == "reference_definition"
    assert repair_surface_link_targets(text) == text


@pytest.mark.parametrize(
    "prefix",
    (
        "[](https://example.invalid/first/...)",
        "<https://example.invalid/first/...>",
    ),
)
def test_transform_fails_closed_when_reference_definition_is_newly_exposed_u150(
    prefix: str,
) -> None:
    text = f"{prefix}[id]: https://example.invalid/second/..."

    repaired = repair_surface_link_targets(text)

    assert repaired == text
    assert repair_surface_link_targets(repaired) == repaired
    assert len(_issues_with_code(repaired, "markdown.href_ellipsis")) == 1


@pytest.mark.parametrize(
    "target",
    (
        r"https://example.invalid/\_/.../tail",
        r"https://example.invalid/.../\_/tail",
    ),
)
def test_reference_definition_escape_keeps_full_target_evidence_u150(target: str) -> None:
    text = f"[합성-참조]: {target}"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == "reference_definition"
    assert issues[0].evidence == target
    assert repair_surface_link_targets(text) == text


def test_legacy_cosmetic_repair_does_not_mutate_either_link_code_u150() -> None:
    samples = (
        "[닫힌 링크](https://example.invalid/...)",
        "[불완전 링크](https://example.invalid/incomplete",
        "[잔여 조각",
    )

    assert all(repair_surface_artifacts(sample) == sample for sample in samples)


@pytest.mark.parametrize(
    "text",
    (
        r"\[리터럴 괄호]",
        r"\[링크가 아님](https://example.invalid/...)",
        r"\<https://example.invalid/...>",
    ),
)
def test_escaped_link_like_literals_remain_byte_identical_u150(text: str) -> None:
    issues = find_surface_quality_issues(text)

    assert [
        issue
        for issue in issues
        if issue.code in {"markdown.href_ellipsis", "markdown.unmatched_link"}
    ] == []
    assert repair_surface_link_targets(text) == text


def test_backslash_before_autolink_close_does_not_hide_invalid_target_u150() -> None:
    text = r"<https://example.invalid/...\>"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == "autolink"
    assert repair_surface_link_targets(text) == ""


@pytest.mark.parametrize("escaped_uri_text", (r"\[x", r"\_x", r"\*x"))
def test_backslash_punctuation_inside_autolink_remains_part_of_target_u150(
    escaped_uri_text: str,
) -> None:
    text = f"<https://example.invalid/.../{escaped_uri_text}>"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == "autolink"
    assert repair_surface_link_targets(text) == ""


def test_mixed_unmatched_line_is_residual_and_not_delimiter_stripped_u150() -> None:
    text = "[잔여 [읽을 수 있는 이름](https://example.invalid/incomplete"

    issues = _issues_with_code(text, "markdown.unmatched_link")

    assert len(issues) == 1
    assert issues[0].link_shape == "unmatched_residual"
    assert repair_surface_link_targets(text) == text


@pytest.mark.parametrize("escaped_target_part", (r"\_", r"\*", r"\)", r"\["))
def test_incomplete_link_removes_the_full_escaped_target_u150(
    escaped_target_part: str,
) -> None:
    text = f"[표시 이름](https://example.invalid/{escaped_target_part}/incomplete"

    issues = _issues_with_code(text, "markdown.unmatched_link")

    assert len(issues) == 1
    assert issues[0].link_shape == "incomplete_inline"
    assert repair_surface_link_targets(text) == "표시 이름"


def test_link_transform_preserves_protected_and_inline_code_bytes_u150() -> None:
    text = (
        "`[코드](https://example.invalid/...)`\n"
        "``[다중 코드](https://example.invalid/...)``\n"
        "```markdown [펜스 경계](https://example.invalid/...)\n"
        "[펜스](https://example.invalid/...)\n```\n"
        "~~~markdown\n[물결 펜스](https://example.invalid/...)\n~~~\n"
        "````markdown\n``` nested\n[긴 펜스](https://example.invalid/...)\n````\n"
        "<details data-link='[태그](https://example.invalid/...)'><summary>진단</summary>\n"
        "[세부](https://example.invalid/...)\n</details>\n"
        "열 A | 열 B\n"
        "--- | ---\n"
        "값 | [표](https://example.invalid/...)\n"
        "```markdown\n[펜스](https://example.invalid/...)\n```\n"
        "| [표](https://example.invalid/...) |\n"
        "[일반](https://example.invalid/...)\n"
        "## ⑦ 면책조항\n[면책](https://example.invalid/...)\n"
        "투자 자문이 아닙니다 [고지](https://example.invalid/...)\n"
    )

    repaired = repair_surface_link_targets(text)

    assert repaired == text.replace("[일반](https://example.invalid/...)", "일반")


@pytest.mark.parametrize(
    "text",
    (
        "| 열 | [표](https://example.invalid/table/...) |\n",
        "열 A | 열 B\n--- | ---\n값 | [표](https://example.invalid/table/...)\n",
        "<details><summary>진단</summary>\n[진단](https://example.invalid/diag/...)\n</details>\n",
        "<details><summary>[진단](https://example.invalid/diag/...)</summary>\n내용\n</details>\n",
        "<details> [진단](https://example.invalid/diag/...)\n내용\n</details>\n",
        "<details><summary>진단</summary>\n내용\n</details> [진단](https://example.invalid/diag/...)\n",
        "투자 자문이 아닙니다 [고지](https://example.invalid/disclaimer/...)\n",
    ),
)
def test_protected_markdown_links_are_scanned_but_never_rewritten_u150(text: str) -> None:
    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].region == "protected"
    assert repair_surface_link_targets(text) == text


def test_incomplete_image_is_unmatched_residual_and_never_leaks_bang_u150() -> None:
    text = "![대체문구](https://example.invalid/image/..."

    issues = _issues_with_code(text, "markdown.unmatched_link")

    assert len(issues) == 1
    assert issues[0].link_shape == "unmatched_residual"
    assert repair_surface_link_targets(text) == text


@pytest.mark.parametrize(
    "text",
    (
        "``[표시](https://example.invalid/a/...)```",
        "```[표시](https://example.invalid/a/...)``",
    ),
)
def test_unequal_inline_code_delimiters_do_not_hide_link_findings_u150(text: str) -> None:
    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].link_shape == "inline_link"


@pytest.mark.parametrize("newline", ("\n", "\r\n"))
def test_multiline_inline_code_link_literal_is_byte_identical_u150(newline: str) -> None:
    text = f"앞 `코드 시작{newline}[리터럴](https://example.invalid/a/...){newline}코드 끝` 뒤"

    assert _issues_with_code(text, "markdown.href_ellipsis") == []
    assert repair_surface_link_targets(text) == text


@pytest.mark.parametrize("newline", ("\n", "\r\n"))
def test_visible_link_next_to_multiline_code_literal_repairs_alone_u150(newline: str) -> None:
    hidden = "[숨김](https://example.invalid/hidden/...)"
    visible = "[표시](https://example.invalid/visible/...)"
    text = f"`코드 시작{newline}{hidden}` 뒤 {visible}"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].evidence == "https://example.invalid/visible/..."
    assert _issues_with_code(text, "markdown.unmatched_link") == []
    assert repair_surface_link_targets(text) == f"`코드 시작{newline}{hidden}` 뒤 표시"


@pytest.mark.parametrize(
    "separator",
    (
        "\n\n",
        "\n> ",
    ),
)
def test_stray_backticks_cannot_hide_link_across_block_boundary_u150(separator: str) -> None:
    invalid = "[표시](https://example.invalid/a/...)"
    text = f"문단 `열림{separator}{invalid}\n다른 문단 `닫힘"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert repair_surface_link_targets(text) != text


def test_stray_backticks_cannot_hide_protected_table_link_u150() -> None:
    invalid = "[표시](https://example.invalid/a/...)"
    text = f"| 열 A | 열 B |\n| --- | --- |\n| `열림 | 값 |\n| {invalid} | `닫힘 |"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].region == "protected"
    assert repair_surface_link_targets(text) == text


def test_non_table_pipe_preserves_multiline_code_span_u150() -> None:
    invalid = "[리터럴](https://example.invalid/a/...)"
    text = f"`code | pipe\n{invalid}\nclose`"

    assert _issues_with_code(text, "markdown.href_ellipsis") == []
    assert repair_surface_link_targets(text) == text


def test_list_item_continuation_preserves_multiline_code_span_u150() -> None:
    invalid = "[리터럴](https://example.invalid/a/...)"
    text = f"- item `code\n  {invalid}\n  close`"

    assert _issues_with_code(text, "markdown.href_ellipsis") == []
    assert repair_surface_link_targets(text) == text


def test_list_item_code_span_cannot_escape_into_blockquote_u150() -> None:
    invalid = "[표시](https://example.invalid/a/...)"
    text = f"- item `open\n> {invalid}\n> close`"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert invalid not in repair_surface_link_targets(text)


@pytest.mark.parametrize("boundary", ("---", "***", "___"))
def test_stray_backticks_cannot_cross_setext_or_thematic_boundary_u150(
    boundary: str,
) -> None:
    invalid = "[표시](https://example.invalid/a/...)"
    text = f"문단 `열림\n제목\n{boundary}\n{invalid}\n다른 문단 `닫힘"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert invalid not in repair_surface_link_targets(text)


def test_stray_backticks_cannot_cross_details_boundary_u150() -> None:
    invalid = "[표시](https://example.invalid/a/...)"
    text = f"문단 `열림\n<details>\n{invalid}\n</details>\n다른 문단 `닫힘"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert issues[0].region == "protected"
    assert repair_surface_link_targets(text) == text


def test_unanchored_first_viewport_never_splits_markdown_at_1600_u150() -> None:
    valid_link = f"{'가' * 1590} [정상](https://example.com/full) 뒤"
    code_literal = f"{'가' * 1590} `[리터럴](https://example.invalid/a/...)` 뒤"

    assert extract_first_viewport(valid_link) == valid_link
    assert _issues_with_code(valid_link, "markdown.unmatched_link") == []
    assert _issues_with_code(code_literal, "markdown.href_ellipsis") == []
    assert repair_surface_link_targets(valid_link) == valid_link
    assert repair_surface_link_targets(code_literal) == code_literal


@pytest.mark.parametrize("indent", ("    ", "\t"))
def test_non_fence_indentation_does_not_protect_middle_link_u150(indent: str) -> None:
    invalid = "[표시](https://example.invalid/a/...)"
    text = f"{indent}```\n{invalid}\n{indent}```"

    issues = _issues_with_code(text, "markdown.href_ellipsis")

    assert len(issues) == 1
    assert invalid not in repair_surface_link_targets(text)


def test_three_space_fence_remains_protected_u150() -> None:
    invalid = "[표시](https://example.invalid/a/...)"
    text = f"   ```\n{invalid}\n   ```"

    assert _issues_with_code(text, "markdown.href_ellipsis") == []
    assert repair_surface_link_targets(text) == text


def test_first_viewport_truncation_residue_blocks_bounded_shapes_u112() -> None:
    deny = "# title\n\n> **오늘의 결론**: 금리 민\n\n## ① 요약"
    ellipsis = "# title\n\n> **오늘의 결론**: 변동성 확대...\n\n## ① 요약"
    unmatched = "# title\n\n> **오늘의 결론**: 반도체 수급(\n\n## ① 요약"
    allowed = "# title\n\n> **오늘의 결론**: 장중 변동성 확대 중\n\n## ① 요약"

    for text in (deny, ellipsis, unmatched):
        assert any(
            i.code == "summary.truncated_mid_token" for i in find_surface_quality_issues(text)
        )
    assert _issues_with_code(allowed, "summary.truncated_mid_token") == []


def test_u131_production_bounded_line_residue_is_blocking() -> None:
    production_lines = (
        (
            "> **그래서 의미는?** Ethereum 기반 DeFi TVL 집중은 ETH 생태계 수요의 "
            "구조적 기반으로 관찰되며, 인도 USDT 프리미엄 이상 급등은 특정 지역의...",
            "body",
        ),
        (
            "> **주의할 점**: 확인 소스: FOMC(연방공개시장위원회) 일정 · "
            "Kevin Warsh(케빈 워시) 연준 의장의 7월 1일 ECB(유럽중앙은행) 포럼 "
            "발언이 매파적 본문 참고.",
            "first_viewport",
        ),
        ("#### 관찰 신호: CoinGecko BTC · UTC 24h…", "body"),
    )

    for line, placement in production_lines:
        text = (
            f"# title\n\n{line}\n\n## ① 요약\n본문"
            if placement == "first_viewport"
            else f"# title\n\n## ① 요약\n본문\n\n{line}"
        )
        issues = _issues_with_code(text, "summary.truncated_mid_token")

        assert len(issues) == 1
        assert issues[0].severity == "block"
        assert issues[0].evidence == line


def test_u131_complete_bounded_lines_and_unowned_body_ellipsis_are_allowed() -> None:
    text = (
        "# title\n\n"
        "> **주의할 점**: 금리 경로 확인 필요. 본문 참고.\n\n"
        "## ① 요약\n본문\n\n"
        "> **그래서 의미는?** 수급 변화가 변동성의 핵심 변수입니다.\n\n"
        "일반 설명...\n\n"
        "#### 관찰 신호: CoinGecko BTC"
    )

    assert _issues_with_code(text, "summary.truncated_mid_token") == []


def test_u131_caution_continuation_requires_a_completed_sentence() -> None:
    assert looks_truncated_caution_continuation("발언이 매파적 본문 참고.")
    assert not looks_truncated_caution_continuation("금리 경로 확인 필요. 본문 참고.")
    assert not looks_truncated_caution_continuation("금리 경로 확인 필요.")


def test_u131_caution_blocks_non_hangul_ellipsis_endings() -> None:
    for ending in ("BTC...", "BTC…"):
        text = f"# title\n\n> **주의할 점**: {ending}\n\n## ① 요약\n본문"
        issues = _issues_with_code(text, "summary.truncated_mid_token")

        assert len(issues) == 1
        assert issues[0].severity == "block"
        assert issues[0].region == "segment_first_viewport"


def test_repairs_bad_particle_mingamdo_eul_u112() -> None:
    text = "# title\n\n시장 민감도을 다시 점검합니다.\n\n## ① 요약"

    issues_before = find_surface_quality_issues(text)
    repaired = repair_surface_artifacts(text)

    assert any(i.code == "korean.bad_particle.mingamdo_eul" for i in issues_before)
    assert "민감도을" not in repaired
    assert "민감도를" in repaired
    assert not has_blocking_surface_issue(repaired)


def test_bulganghanseong_repair_remains_u100_regression_u112() -> None:
    text = "# title\n\n불강한성 확대\n\n## ① 요약"

    repaired = repair_surface_artifacts(text)

    assert "불강한성" not in repaired
    assert "불확실성 확대" in repaired
