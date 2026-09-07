"""u144 Step 0 — exhaustive current surface issue disposition policy."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

from investo._internal import surface_quality
from investo.publisher._public_document_policy import (
    OPTIONAL_BLOCK_DISPOSITIONS,
    PUBLIC_BLOCK_KINDS,
    SURFACE_ISSUE_CODES,
    SURFACE_ISSUE_DISPOSITION_TABLE,
    SURFACE_LINK_ISSUE_DISPOSITION_TABLE,
    SURFACE_LINK_SHAPES_BY_CODE,
    FinalizationIssueDisposition,
    surface_issue_disposition,
)


def _emitted_surface_issue_codes() -> frozenset[str]:
    source_path = Path(surface_quality.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    codes: set[str] = set()
    dynamic_calls: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "SurfaceQualityIssue":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            dynamic_calls.append(node.lineno)
            continue
        code = node.args[0].value
        if not isinstance(code, str):
            dynamic_calls.append(node.lineno)
            continue
        codes.add(code)
    assert dynamic_calls == [], (
        "SurfaceQualityIssue code must remain a static string so u144 policy "
        f"exhaustiveness is reviewable; dynamic calls at {dynamic_calls}"
    )
    return frozenset(codes)


def test_current_surface_issue_codes_are_exhaustive() -> None:
    # Adding a scanner code without registering policy fails this test. Adding
    # only a registry value also fails module construction because every code
    # must enter an explicit policy branch before the cross-product is built.
    assert _emitted_surface_issue_codes() == SURFACE_ISSUE_CODES


def test_every_current_issue_code_has_one_disposition_for_every_owned_block() -> None:
    expected_keys = {
        (issue_code, block) for issue_code in SURFACE_ISSUE_CODES for block in PUBLIC_BLOCK_KINDS
    }
    assert set(SURFACE_ISSUE_DISPOSITION_TABLE) == expected_keys
    assert len(SURFACE_ISSUE_DISPOSITION_TABLE) == len(expected_keys)
    assert set(SURFACE_ISSUE_DISPOSITION_TABLE.values()) <= set(
        get_args(FinalizationIssueDisposition)
    )

    expected_link_keys = {
        (issue_code, block, link_shape)
        for issue_code, link_shapes in SURFACE_LINK_SHAPES_BY_CODE.items()
        for block in PUBLIC_BLOCK_KINDS
        for link_shape in link_shapes
    }
    assert set(SURFACE_LINK_ISSUE_DISPOSITION_TABLE) == expected_link_keys
    assert len(SURFACE_LINK_ISSUE_DISPOSITION_TABLE) == len(expected_link_keys)
    assert set(SURFACE_LINK_ISSUE_DISPOSITION_TABLE.values()) <= set(
        get_args(FinalizationIssueDisposition)
    )
    assert set(SURFACE_LINK_SHAPES_BY_CODE) == {
        "markdown.href_ellipsis",
        "markdown.unmatched_link",
    }
    assert {
        link_shape
        for link_shapes in SURFACE_LINK_SHAPES_BY_CODE.values()
        for link_shape in link_shapes
    } == set(get_args(surface_quality.SurfaceLinkShape))


def test_optional_block_policy_matches_functional_design() -> None:
    assert OPTIONAL_BLOCK_DISPOSITIONS == {
        "visual": "omit_optional_block",
        "chart": "omit_optional_block",
        "carryover": "omit_optional_block",
        "cause_map": "omit_optional_block",
        "shared_macro": "replace_block",
        "crypto_indicators": "replace_block",
        "channel_anchors": "replace_block",
        "daily_thesis": "replace_block",
        "watchpoints": "replace_block",
    }


def test_context_sensitive_dispositions_match_functional_design() -> None:
    assert surface_issue_disposition("ellipsis.dangling_line", "first_viewport") == "repair"
    assert surface_issue_disposition("ellipsis.dangling_line", "section_body") == ("record_warning")
    assert surface_issue_disposition("trace.fragment", "section_body") == "block_segment"
    assert surface_issue_disposition("watermark.window_bracket", "header") == "replace_block"
    assert surface_issue_disposition("summary.truncated_mid_token", "first_viewport") == (
        "replace_block"
    )
    assert surface_issue_disposition("watchlist.matcher_reason.public", "watchpoints") == (
        "replace_block"
    )
    assert surface_issue_disposition("public_diagnostic.raw_label", "watchpoints") == (
        "replace_block"
    )
    assert surface_issue_disposition("public_diagnostic.raw_label", "section_body") == (
        "block_segment"
    )
    assert surface_issue_disposition("ellipsis.dangling_line", "watchpoints") == ("record_warning")
    assert surface_issue_disposition("trace.fragment", "watchpoints") == "block_segment"
    assert surface_issue_disposition("markdown.href_ellipsis", "watchpoints") == ("block_segment")
    assert surface_issue_disposition("markdown.unmatched_link", "watchpoints") == ("block_segment")
    assert (
        surface_issue_disposition(
            "markdown.href_ellipsis",
            "watchpoints",
            link_shape="inline_link",
        )
        == "replace_block"
    )
    assert surface_issue_disposition("template.repeated_phrase", "first_viewport") == (
        "record_warning"
    )


def test_unknown_issue_or_unowned_diagnostic_fails_closed() -> None:
    assert surface_issue_disposition("new.unmapped.code", "section_body") == "block_segment"
    for issue_code in SURFACE_ISSUE_CODES:
        assert surface_issue_disposition(issue_code, "diagnostics") == "block_segment"


_EXPECTED_LINK_DISPOSITIONS = {
    "header": ("block_segment", "block_segment"),
    "navigation": ("block_segment", "block_segment"),
    "first_viewport": ("repair", "replace_block"),
    "visual": ("omit_optional_block", "omit_optional_block"),
    "anchor_table": ("block_segment", "block_segment"),
    "shared_macro": ("replace_block", "replace_block"),
    "crypto_indicators": ("replace_block", "replace_block"),
    "channel_anchors": ("replace_block", "replace_block"),
    "cause_map": ("omit_optional_block", "omit_optional_block"),
    "daily_thesis": ("replace_block", "replace_block"),
    "carryover": ("omit_optional_block", "omit_optional_block"),
    "chart": ("omit_optional_block", "omit_optional_block"),
    "section_body": ("repair", "replace_block"),
    "watchpoints": ("replace_block", "replace_block"),
    "diagnostics": ("block_segment", "block_segment"),
    "disclaimer": ("block_segment", "block_segment"),
}


def test_link_shape_policy_matches_the_complete_u150_region_matrix() -> None:
    recoverable_shapes = {"inline_link", "image", "autolink", "incomplete_inline"}

    assert tuple(_EXPECTED_LINK_DISPOSITIONS) == PUBLIC_BLOCK_KINDS
    for block, (recoverable, unrecoverable) in _EXPECTED_LINK_DISPOSITIONS.items():
        for issue_code, link_shapes in SURFACE_LINK_SHAPES_BY_CODE.items():
            for link_shape in link_shapes:
                expected = recoverable if link_shape in recoverable_shapes else unrecoverable
                assert (
                    surface_issue_disposition(
                        issue_code,
                        block,  # type: ignore[arg-type]
                        link_shape=link_shape,
                    )
                    == expected
                )


def test_link_policy_requires_a_code_compatible_scanner_shape() -> None:
    assert (
        surface_issue_disposition(
            "markdown.href_ellipsis",
            "first_viewport",
            link_shape="incomplete_inline",
        )
        == "block_segment"
    )
    assert (
        surface_issue_disposition(
            "markdown.unmatched_link",
            "first_viewport",
            link_shape="inline_link",
        )
        == "block_segment"
    )
    assert (
        surface_issue_disposition(
            "ellipsis.dangling_line",
            "first_viewport",
            link_shape="inline_link",
        )
        == "block_segment"
    )
