"""Tests for the canonical production source descriptor registry."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from investo._internal.source_specs import (
    SOURCE_SPECS,
    SOURCE_SPECS_BY_NAME,
    source_names_for_item_routing,
    source_names_for_item_segment,
    source_names_for_market_window,
    source_names_for_outcome_segment,
)


def test_source_specs_have_unique_names() -> None:
    names = [spec.name for spec in SOURCE_SPECS]

    assert len(names) == len(set(names))
    assert set(SOURCE_SPECS_BY_NAME) == set(names)


def test_source_specs_by_name_points_to_canonical_objects() -> None:
    for spec in SOURCE_SPECS:
        assert SOURCE_SPECS_BY_NAME[spec.name] is spec


def test_source_specs_have_valid_segments_and_nonempty_outcome_membership() -> None:
    valid_segments = {"domestic-equity", "us-equity", "crypto"}
    for spec in SOURCE_SPECS:
        assert spec.market_window_segment in valid_segments
        assert spec.item_segments <= valid_segments
        assert spec.outcome_segments <= valid_segments
        assert spec.outcome_segments


def test_market_window_views_are_descriptor_derived() -> None:
    assert "yfinance-price" in source_names_for_market_window("us-equity")
    assert "treasury-rates" in source_names_for_market_window("us-equity")
    assert "theblock-crypto" in source_names_for_market_window("crypto")
    assert "yonhap-index-close" in source_names_for_market_window("domestic-equity")
    assert "fred-fx-close" in source_names_for_market_window("domestic-equity")


def test_segment_item_views_preserve_special_case_semantics() -> None:
    assert "treasury-rates" in source_names_for_item_segment(
        "us-equity",
        routing="shared-segments",
    )
    assert "treasury-rates" in source_names_for_item_segment(
        "crypto",
        routing="shared-segments",
    )
    assert source_names_for_item_routing("cftc-contract-group") == {"cftc-cot-positioning"}

    cftc_policy = SOURCE_SPECS_BY_NAME["cftc-policy-rss"]
    assert cftc_policy.tier == "S"
    assert cftc_policy.market_window_segment == "us-equity"
    assert cftc_policy.item_routing == "single-segment"
    assert cftc_policy.item_segments == {"us-equity"}
    assert cftc_policy.outcome_segments == {"us-equity"}

    yonhap = SOURCE_SPECS_BY_NAME["yonhap-index-close"]
    assert yonhap.tier == "B"
    assert yonhap.market_window_segment == "domestic-equity"
    assert yonhap.item_segments == {"domestic-equity"}
    assert yonhap.outcome_segments == {"domestic-equity"}

    fred_fx = SOURCE_SPECS_BY_NAME["fred-fx-close"]
    assert fred_fx.tier == "S"
    assert fred_fx.market_window_segment == "domestic-equity"
    assert fred_fx.item_segments == {"domestic-equity"}
    assert fred_fx.outcome_segments == {"domestic-equity"}


def test_outcome_views_preserve_cross_segment_relevance() -> None:
    assert "cftc-cot-positioning" in source_names_for_outcome_segment("us-equity")
    assert "cftc-cot-positioning" in source_names_for_outcome_segment("crypto")
    assert "yfinance-price" not in source_names_for_outcome_segment("crypto")


def test_retired_stooq_sources_are_absent_from_all_registry_views() -> None:
    retired = {"stooq-price", "stooq-kr-market"}
    assert retired.isdisjoint(SOURCE_SPECS_BY_NAME)
    for segment in ("domestic-equity", "us-equity", "crypto"):
        assert retired.isdisjoint(source_names_for_market_window(segment))
        assert retired.isdisjoint(source_names_for_item_segment(segment))
        assert retired.isdisjoint(source_names_for_outcome_segment(segment))


def test_source_specs_module_does_not_import_work_units() -> None:
    path = Path("src/investo/_internal/source_specs.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = {
        module
        for module in imports
        if module.startswith("investo.sources") or module.startswith("investo.briefing")
    }
    assert forbidden == set()


def test_importing_sources_package_discovers_every_source_spec() -> None:
    code = """
import json
import investo.sources
from investo._internal.source_specs import SOURCE_SPECS_BY_NAME
from investo.sources import list_sources
print(json.dumps({
    "registered": sorted(adapter.name for adapter in list_sources()),
    "specs": sorted(SOURCE_SPECS_BY_NAME),
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["registered"] == payload["specs"]
