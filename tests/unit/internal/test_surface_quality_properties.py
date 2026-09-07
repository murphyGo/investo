"""Partial-mode properties for the u150 canonical link transform."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from investo._internal.surface_quality import (
    find_surface_quality_issues,
    repair_surface_link_targets,
)

_LABEL = st.text(
    alphabet="abcXYZ012 한글日本語🚀",
    min_size=1,
    max_size=24,
)
_PATH = st.text(
    alphabet="abcXYZ0123456789/_-.",
    min_size=1,
    max_size=24,
).filter(lambda value: "..." not in value)
_ELLIPSIS = st.sampled_from(("...", "…"))
_ESCAPED_TARGET_PART = st.sampled_from((r"\_", r"\*", r"\)", r"\["))
_RECOVERABLE_SHAPE = st.sampled_from(("inline_link", "image", "autolink", "incomplete_inline"))


def _invalid_target(prefix: str, ellipsis: str, suffix: str) -> str:
    return f"https://example.invalid/{prefix}/{ellipsis}/{suffix}"


def _recoverable_fragment(shape: str, label: str, target: str) -> str:
    if shape == "inline_link":
        return f"[{label}]({target})"
    if shape == "image":
        return f"![{label}]({target})"
    if shape == "autolink":
        return f"<{target}>"
    if shape == "incomplete_inline":
        return f"[{label}]({target}"
    raise AssertionError(f"unsupported test shape: {shape}")


def _expected_visible_text(shape: str, label: str) -> str:
    return "" if shape == "autolink" else label


@settings(max_examples=100)
@given(
    shape=_RECOVERABLE_SHAPE,
    label=_LABEL,
    target_prefix=_PATH,
    target_suffix=_PATH,
    ellipsis=_ELLIPSIS,
    escaped_target_part=_ESCAPED_TARGET_PART,
)
def test_recoverable_transform_is_exact_idempotent_and_closes_scanner(
    shape: str,
    label: str,
    target_prefix: str,
    target_suffix: str,
    ellipsis: str,
    escaped_target_part: str,
) -> None:
    target = _invalid_target(
        f"{target_prefix}/{escaped_target_part}",
        ellipsis,
        target_suffix,
    )
    fragment = _recoverable_fragment(shape, label, target)
    text = f"문맥 시작 {fragment} 문맥 끝"

    repaired = repair_surface_link_targets(text)

    assert repaired == f"문맥 시작 {_expected_visible_text(shape, label)} 문맥 끝"
    assert target not in repaired
    assert repair_surface_link_targets(repaired) == repaired
    assert not any(
        issue.code in {"markdown.href_ellipsis", "markdown.unmatched_link"}
        for issue in find_surface_quality_issues(repaired)
    )


@settings(max_examples=100)
@given(label=_LABEL, target_path=_PATH)
def test_valid_links_remain_byte_identical(label: str, target_path: str) -> None:
    target = f"https://example.invalid/{target_path}"
    text = f"[{label}]({target})\r\n![{label}]({target})\r\n<{target}>\r\n[{label}]: {target}\r\n"

    assert repair_surface_link_targets(text) == text


@settings(max_examples=100)
@given(
    shapes=st.lists(_RECOVERABLE_SHAPE, min_size=1, max_size=8),
    ellipsis=_ELLIPSIS,
)
def test_findings_and_transform_follow_stable_left_to_right_order(
    shapes: list[str],
    ellipsis: str,
) -> None:
    closed_shapes = [shape for shape in shapes if shape != "incomplete_inline"]
    fragments = [
        _recoverable_fragment(
            shape,
            f"라벨{index}",
            _invalid_target(f"p{index}", ellipsis, f"s{index}"),
        )
        for index, shape in enumerate(closed_shapes)
    ]
    text = " / ".join(fragments)

    issues = [
        issue
        for issue in find_surface_quality_issues(text)
        if issue.code == "markdown.href_ellipsis"
    ]

    assert [issue.link_shape for issue in issues] == closed_shapes
    repaired = repair_surface_link_targets(text)
    assert repair_surface_link_targets(repaired) == repaired
    assert "example.invalid" not in repaired


@settings(max_examples=100)
@given(shape=_RECOVERABLE_SHAPE, label=_LABEL, ellipsis=_ELLIPSIS)
def test_protected_regions_remain_byte_identical(
    shape: str,
    label: str,
    ellipsis: str,
) -> None:
    fragment = _recoverable_fragment(
        shape,
        label,
        _invalid_target("protected", ellipsis, "target"),
    )
    protected_documents = (
        f"`{fragment}`\n",
        f"``{fragment}``\n",
        f"```markdown\n{fragment}\n```\n",
        f"```markdown {fragment}\n{fragment}\n```\n",
        f"~~~markdown\n{fragment}\n~~~\n",
        f"````markdown\n``` nested\n{fragment}\n````\n",
        f"| {fragment} |\n",
        f"열 A | 열 B\n--- | ---\n값 | {fragment}\n",
        f"<details><summary>진단</summary>\n{fragment}\n</details>\n",
        f"<details data-value='{fragment}'><summary>진단</summary>\n{fragment}\n</details>\n",
        f"## ⑦ 면책조항\r\n{fragment}\r\n",
        f"투자 자문이 아닙니다 {fragment}\n",
        f"수집/품질 진단 {fragment}\n",
    )

    assert all(repair_surface_link_targets(text) == text for text in protected_documents)


@settings(max_examples=100)
@given(label=_LABEL, target_prefix=_PATH, target_suffix=_PATH, ellipsis=_ELLIPSIS)
def test_nested_invalid_targets_fail_closed_without_partial_transform(
    label: str,
    target_prefix: str,
    target_suffix: str,
    ellipsis: str,
) -> None:
    inner_target = _invalid_target(target_prefix, ellipsis, "inner")
    outer_target = _invalid_target("outer", ellipsis, target_suffix)
    text = f"[[{label}]({inner_target})]({outer_target})"

    repaired = repair_surface_link_targets(text)

    assert repaired == text
    assert repair_surface_link_targets(repaired) == repaired
