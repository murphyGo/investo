"""U144 Step 4.4 neutral daily-thesis ownership regressions."""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from investo._internal.daily_thesis_decision import (
    redecide_daily_thesis_for_active_segments,
)
from investo.models.bundle_context import (
    BundleContext,
    DailyThesisDecision,
    DailyThesisSignal,
)
from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.orchestrator.bundle_context import (
    redecide_daily_thesis_for_successful_segments,
)

_TARGET_DATE = date(2026, 7, 21)


def _base_context() -> BundleContext:
    signals = tuple(
        DailyThesisSignal(
            segment=segment,
            key="ust_yield",
            tier="core",
            evidence_label="미 국채 수익률",
        )
        for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
    )
    return BundleContext(
        bundle_id="u144-neutral-owner",
        target_kst_date=_TARGET_DATE,
        daily_thesis_signals=signals,
        daily_thesis_decision=DailyThesisDecision(
            mode="strong",
            line="> **오늘의 큰 그림:** 원본 문구",
            per_segment_lines={segment: "원본" for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)},
            supporting_segments=(DOMESTIC_EQUITY, US_EQUITY, CRYPTO),
            reason="shared_core_signal",
        ),
    )


def test_neutral_owner_removes_non_survivor_from_all_thesis_state() -> None:
    base = _base_context()

    active = redecide_daily_thesis_for_active_segments(
        base,
        (DOMESTIC_EQUITY, US_EQUITY),
    )

    assert {signal.segment for signal in active.daily_thesis_signals} == {
        DOMESTIC_EQUITY,
        US_EQUITY,
    }
    assert active.daily_thesis_decision.supporting_segments == (
        DOMESTIC_EQUITY,
        US_EQUITY,
    )
    assert tuple(active.daily_thesis_decision.per_segment_lines) == (
        DOMESTIC_EQUITY,
        US_EQUITY,
    )
    rendered = "\n".join(
        (
            active.daily_thesis_decision.line,
            *active.daily_thesis_decision.per_segment_lines.values(),
        )
    )
    assert "가상자산" not in rendered
    assert "BTC" not in rendered
    assert "ETH" not in rendered
    assert CRYPTO in base.daily_thesis_decision.supporting_segments


def test_orchestrator_compatibility_name_is_the_neutral_owner() -> None:
    assert (
        redecide_daily_thesis_for_successful_segments is redecide_daily_thesis_for_active_segments
    )


def test_publisher_has_no_orchestrator_import() -> None:
    source = (Path(__file__).parents[3] / "src/investo/publisher/public_document.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(module.startswith("investo.orchestrator") for module in imported_modules)
