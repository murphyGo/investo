"""u100 surface-quality shared helper tests."""

from __future__ import annotations

from investo._internal.surface_quality import (
    extract_first_viewport,
    find_surface_quality_issues,
    has_blocking_surface_issue,
    repair_surface_artifacts,
)


def test_extract_first_viewport_stops_before_section_one() -> None:
    text = "# title\n\nintro\n\n## ① 요약\n본문"

    assert extract_first_viewport(text) == "# title\n\nintro\n\n"


def _issues_with_code(text: str, code: str) -> list[object]:
    return [issue for issue in find_surface_quality_issues(text) if issue.code == code]


def test_repair_bad_token_and_dangling_ellipsis() -> None:
    text = "# title\n\n불강한성 확대 ...\n...\n\n## ① 요약\n본문"

    repaired = repair_surface_artifacts(text)

    assert "불강한성" not in repaired
    assert "불확실성 확대" in repaired
    assert "\n...\n" not in repaired
    assert repair_surface_artifacts(repaired) == repaired


def test_repairs_trace_fragments_and_unmatched_link_markers() -> None:
    text = "# title\n\n[broken link\nstage1_hash=abc\n\n## ① 요약"

    repaired = repair_surface_artifacts(text)
    assert "stage1_hash" not in repaired
    assert "[broken link" not in repaired
    assert "broken link" in repaired

    issues = find_surface_quality_issues(text)
    codes = {issue.code for issue in issues if issue.severity == "block"}

    assert "markdown.unmatched_link" in codes
    assert "trace.fragment" in codes
    assert has_blocking_surface_issue(text)

    repaired_issues = find_surface_quality_issues(repaired)
    assert [issue for issue in repaired_issues if issue.severity == "block"] == []


def test_repairs_recoverable_markdown_link_fragment() -> None:
    text = "# title\n\n> **오늘의 결론**: [broken link](https://example.com\n\n## ① 요약"

    repaired = repair_surface_artifacts(text)

    assert "[broken link](" not in repaired
    assert "broken link" in repaired
    assert not has_blocking_surface_issue(repaired)


def test_repairs_plain_unmatched_bracket_marker() -> None:
    text = "# title\n\n> **오늘의 결론**: [국내 증시 변동성 확대\n\n## ① 요약"

    repaired = repair_surface_artifacts(text)

    assert "[국내 증시" not in repaired
    assert "국내 증시 변동성 확대" in repaired
    assert not has_blocking_surface_issue(repaired)


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


def test_public_diagnostics_block_in_segment_body() -> None:
    text = "# title\n\n## ① 요약\n본문 사용 미집계\n"

    issues = find_surface_quality_issues(text)

    public = [issue for issue in issues if issue.code == "public_diagnostic.raw_label"]
    assert public
    assert public[0].evidence == "본문 사용 미집계"
    assert public[0].region == "segment_body"


def test_watermark_window_bracket_validation_u112() -> None:
    valid = (
        "# title\n\n"
        "**기준 시각**: 2026-06-24 07:30 KST · 수집창 [2026-06-23T22:00Z, 2026-06-24T07:00Z)]\n\n"
        "## ① 요약"
    )
    missing = "# title\n\n**기준 시각**: 2026-06-24 07:30 KST · 수집창 없음\n\n## ① 요약"
    extra = "# title\n\n**기준 시각**: 2026-06-24 07:30 KST · 수집창 [[중첩]]\n\n## ① 요약"
    ignored = "# title\n\n기준 시각: 수집창 없음\n\n## ① 요약"

    assert _issues_with_code(valid, "watermark.window_bracket") == []
    assert any(i.code == "watermark.window_bracket" for i in find_surface_quality_issues(missing))
    assert any(i.code == "watermark.window_bracket" for i in find_surface_quality_issues(extra))
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
    for text in (inline, image, ref, autolink):
        assert any(i.code == "markdown.href_ellipsis" for i in find_surface_quality_issues(text))
    assert _issues_with_code(code, "markdown.href_ellipsis") == []


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
