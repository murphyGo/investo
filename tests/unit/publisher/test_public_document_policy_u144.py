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
    assert surface_issue_disposition("template.repeated_phrase", "first_viewport") == (
        "record_warning"
    )


def test_unknown_issue_or_unowned_diagnostic_fails_closed() -> None:
    assert surface_issue_disposition("new.unmapped.code", "section_body") == "block_segment"
    for issue_code in SURFACE_ISSUE_CODES:
        assert surface_issue_disposition(issue_code, "diagnostics") == "block_segment"
