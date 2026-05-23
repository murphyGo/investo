"""Tests for the u74 cross-market cause-map guard (Step 4).

The cause-map line is rendered only when the u57 BundleContext already
proves the linkage at the shared-macro tier AND the cause-map type is in
``cross_market_core_allowed``. Forbidden / ungrounded linkages are
omitted and reported as ``suppressed`` — never demoted into prose.
"""

from __future__ import annotations

from datetime import date

from investo.models.bundle_context import BundleContext
from investo.publisher.cross_market_cause_map import (
    CAUSE_MAP_HEADER,
    evaluate_cause_map,
    inject_cause_map_line,
)


def _ctx(
    shared_macro_block: str | None,
    *,
    allowed: frozenset[str] | None = None,
) -> BundleContext:
    kwargs: dict[str, object] = {
        "bundle_id": "2026-05-24-bundle",
        "target_kst_date": date(2026, 5, 24),
        "shared_macro_block": shared_macro_block,
    }
    if allowed is not None:
        kwargs["cross_market_core_allowed"] = allowed
    return BundleContext(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Allowed linkages (AC-74.5)
# ---------------------------------------------------------------------------


def test_oil_macro_emits_observational_line() -> None:
    ctx = _ctx("- **국제 유가** — Brent crude jumps on supply fears")
    decision = evaluate_cause_map(ctx)
    assert decision.emitted == ("geopolitical_oil_macro",)
    assert CAUSE_MAP_HEADER in decision.rendered
    assert "관찰됩니다" in decision.rendered  # observational
    # Not predictive / no trade language.
    assert "매수" not in decision.rendered
    assert "전망" not in decision.rendered


def test_fomc_macro_emits_fed_policy_line() -> None:
    ctx = _ctx("- **FOMC 일정** — Fed rate decision Wednesday")
    decision = evaluate_cause_map(ctx)
    assert decision.emitted == ("fed_policy_event",)
    assert "공통 변수" in decision.rendered


def test_ust_yield_also_maps_to_fed_policy() -> None:
    ctx = _ctx("- **미 국채 수익률** — 10Y yield rises")
    decision = evaluate_cause_map(ctx)
    assert decision.emitted == ("fed_policy_event",)


def test_multiple_types_emit_deterministically() -> None:
    ctx = _ctx(
        "- **국제 유가** — oil\n- **FOMC 일정** — fed",
    )
    decision = evaluate_cause_map(ctx)
    # geopolitical_oil_macro before fed_policy_event (fixed order).
    assert decision.emitted == ("geopolitical_oil_macro", "fed_policy_event")
    assert decision.rendered.count(CAUSE_MAP_HEADER) == 1
    assert " / " in decision.rendered


# ---------------------------------------------------------------------------
# Forbidden / ungrounded linkages
# ---------------------------------------------------------------------------


def test_no_shared_macro_means_no_line() -> None:
    decision = evaluate_cause_map(_ctx(None))
    assert decision.rendered == ""
    assert decision.emitted == ()
    assert decision.suppressed == ()


def test_none_context_means_no_line() -> None:
    decision = evaluate_cause_map(None)
    assert decision.rendered == ""


def test_ticker_only_block_does_not_ground_a_cause_map() -> None:
    # A block mentioning only a ticker (no shared-macro label) yields no
    # cause-map type -> forbidden ad-hoc ticker linkage is omitted.
    ctx = _ctx("- **AAPL** — Apple earnings beat")
    decision = evaluate_cause_map(ctx)
    assert decision.rendered == ""
    assert decision.emitted == ()


def test_type_not_in_allowlist_is_suppressed_not_demoted() -> None:
    # Oil evidence present, but the allow-list excludes the oil type:
    # it must be suppressed (reported) and never appear in prose.
    ctx = _ctx(
        "- **국제 유가** — oil",
        allowed=frozenset({"fed_policy_event"}),
    )
    decision = evaluate_cause_map(ctx)
    assert decision.rendered == ""
    assert decision.emitted == ()
    assert decision.suppressed == ("geopolitical_oil_macro",)


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------


def test_inject_idempotent_before_first_section() -> None:
    ctx = _ctx("- **국제 유가** — oil")
    decision = evaluate_cause_map(ctx)
    text = "## 한눈에 보기\n\n요약.\n\n## ① 요약\n\n본문.\n"
    once = inject_cause_map_line(text, decision)
    assert CAUSE_MAP_HEADER in once
    assert once.index(CAUSE_MAP_HEADER) < once.index("## ①")
    twice = inject_cause_map_line(once, decision)
    assert twice == once


def test_inject_empty_decision_noop() -> None:
    decision = evaluate_cause_map(_ctx(None))
    text = "## ① 요약\n"
    assert inject_cause_map_line(text, decision) == text
