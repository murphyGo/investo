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
    assert "stooq-price" in source_names_for_market_window("us-equity")
    assert "treasury-rates" in source_names_for_market_window("us-equity")
    assert "theblock-crypto" in source_names_for_market_window("crypto")
    assert "stooq-kr-market" in source_names_for_market_window("domestic-equity")


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

    stooq = SOURCE_SPECS_BY_NAME["stooq-price"]
    assert stooq.market_window_segment == "us-equity"
    assert stooq.item_routing == "us-with-crypto-signal"
    assert stooq.item_segments == {"us-equity"}
    assert stooq.outcome_segments == {"us-equity", "crypto"}


def test_outcome_views_preserve_cross_segment_relevance() -> None:
    assert "cftc-cot-positioning" in source_names_for_outcome_segment("us-equity")
    assert "cftc-cot-positioning" in source_names_for_outcome_segment("crypto")
    assert "stooq-price" in source_names_for_outcome_segment("crypto")
    assert "stooq-price" not in source_names_for_item_segment("crypto")


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
