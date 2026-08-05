"""u148 architecture contract for the raw/public domestic trust boundary."""

from __future__ import annotations

import ast
import inspect
import textwrap

from investo.orchestrator import pipeline


def _call_names(function: object) -> list[tuple[str, ast.Call]]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    calls: list[tuple[str, ast.Call]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.append((node.func.id, node))
        elif isinstance(node.func, ast.Attribute):
            calls.append((node.func.attr, node))
    return calls


def _argument_name(call: ast.Call, position: int) -> str | None:
    if len(call.args) <= position:
        return None
    value = call.args[position]
    return value.id if isinstance(value, ast.Name) else None


def _keyword_name(call: ast.Call, keyword: str) -> str | None:
    value = next((entry.value for entry in call.keywords if entry.arg == keyword), None)
    return value.id if isinstance(value, ast.Name) else None


def test_generate_stage_computes_one_projection_and_routes_only_public_items() -> None:
    calls = _call_names(pipeline.GenerateStage.execute)
    by_name: dict[str, list[ast.Call]] = {}
    for name, call in calls:
        by_name.setdefault(name, []).append(call)

    assert len(by_name["project_domestic_public_items"]) == 1
    assert "domestic_anchor_verdicts" not in by_name
    assert "trusted_domestic_price_items" not in by_name

    positional_public_consumers = {
        "_stage_generate_segments": 1,
        "_stage_prepare_segment_visual_assets": 1,
        "_snapshot_close_by_ticker": 0,
        "_append_daily_coverage_line": 1,
    }
    for name, position in positional_public_consumers.items():
        assert len(by_name[name]) == 1
        assert _argument_name(by_name[name][0], position) == "public_items"

    image_stage = next(
        call
        for call in by_name["to_thread"]
        if _argument_name(call, 0) == "_run_image_candidate_stage"
    )
    assert _argument_name(image_stage, 2) == "public_items"

    assert len(by_name["_build_public_document_context"]) == 1
    assert _keyword_name(by_name["_build_public_document_context"][0], "items") == "public_items"


def test_publish_and_notify_keep_diagnostic_raw_items_separate() -> None:
    publish_calls = dict(_call_names(pipeline.PublishStage.execute))
    publish = publish_calls["_stage_publish_segments"]
    assert _keyword_name(publish, "items") == "public_items"
    assert _keyword_name(publish, "raw_items") == "raw_items"
    assert _keyword_name(publish, "domestic_item_verdicts") == "domestic_item_verdicts"

    notify_calls = dict(_call_names(pipeline.NotifyStage.execute))
    notify = notify_calls["_stage_notify_segmented_briefing"]
    assert _keyword_name(notify, "items") == "public_items"
    assert "trusted_domestic_price_items" not in notify_calls
