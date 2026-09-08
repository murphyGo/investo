"""Tests for the u74 cross-market cause-map guard (Step 4).

The cause-map line is rendered only when the u57 BundleContext already
proves the linkage through selected keys and a nonempty block AND the cause
type is in ``cross_market_core_allowed``. Forbidden candidates are reported
as ``suppressed``, never demoted into prose; ungrounded input has no candidate.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, note, seed, settings
from hypothesis import strategies as st

from investo.models.bundle_context import CROSS_MARKET_CORE_ALLOWED, BundleContext, SharedMacroKey
from investo.publisher.cross_market_cause_map import (
    CAUSE_MAP_HEADER,
    evaluate_cause_map,
    inject_cause_map_line,
)
from investo.publisher.shared_macro import SHARED_MACRO_HEADER, inject_shared_macro_block


def _ctx(
    shared_macro_block: str | None,
    *,
    allowed: frozenset[str] | None = None,
    keys: frozenset[SharedMacroKey] = frozenset(),
) -> BundleContext:
    return BundleContext(
        bundle_id="2026-05-24-bundle",
        target_kst_date=date(2026, 5, 24),
        shared_macro_block=shared_macro_block,
        detected_macro_keys=keys,
        cross_market_core_allowed=CROSS_MARKET_CORE_ALLOWED if allowed is None else allowed,
    )


# ---------------------------------------------------------------------------
# Allowed linkages (AC-74.5)
# ---------------------------------------------------------------------------


def test_oil_macro_emits_observational_line() -> None:
    ctx = _ctx("- **국제 유가** — Brent crude jumps on supply fears", keys=frozenset({"oil"}))
    decision = evaluate_cause_map(ctx)
    assert decision.emitted == ("geopolitical_oil_macro",)
    assert CAUSE_MAP_HEADER in decision.rendered
    assert "관찰됩니다" in decision.rendered  # observational
    # Not predictive / no trade language.
    assert "매수" not in decision.rendered
    assert "전망" not in decision.rendered


def test_fomc_macro_emits_fed_policy_line() -> None:
    ctx = _ctx("- **FOMC 일정** — Fed rate decision Wednesday", keys=frozenset({"fomc"}))
    decision = evaluate_cause_map(ctx)
    assert decision.emitted == ("fed_policy_event",)
    assert "공통 변수" in decision.rendered


def test_ust_yield_also_maps_to_fed_policy() -> None:
    ctx = _ctx("- **미 국채 수익률** — 10Y yield rises", keys=frozenset({"ust_yield"}))
    decision = evaluate_cause_map(ctx)
    assert decision.emitted == ("fed_policy_event",)


def test_multiple_types_emit_deterministically() -> None:
    ctx = _ctx(
        "- **국제 유가** — oil\n- **FOMC 일정** — fed",
        keys=frozenset({"oil", "fomc"}),
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
    # Display text alone proves no shared key; do not invent an ad-hoc linkage.
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
        keys=frozenset({"oil"}),
    )
    decision = evaluate_cause_map(ctx)
    assert decision.rendered == ""
    assert decision.emitted == ()
    assert decision.suppressed == ("geopolitical_oil_macro",)


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------


def test_inject_idempotent_before_first_section() -> None:
    ctx = _ctx("- **국제 유가** — oil", keys=frozenset({"oil"}))
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


# u151 Step 3: keys are evidence, rendered labels are presentation only.
U151_KEYS: tuple[SharedMacroKey, ...] = ("fomc", "oil", "ust_yield")
U151_SUBSETS: tuple[frozenset[SharedMacroKey], ...] = tuple(
    frozenset(key for index, key in enumerate(U151_KEYS) if mask & (1 << index))
    for mask in range(8)
)
U151_CAUSES = ("geopolitical_oil_macro", "fed_policy_event", "global_systemic_risk")
U151_BLOCKS = (
    "- **국제 유가** — oil",
    "- **FOMC 일정** — fed\n- **미 국채 수익률** — rates",
    "- **이름을 바꾼 항목** — 확인된 공통 자료",
    "- **AAPL** — 표시 문구는 분류 입력이 아님",
    " ",  # Preserve the existing truthiness gate, not a new whitespace parser.
)
U151_OIL_LINE = "유가/지정학 이슈가 여러 자산군의 변동성 연결 고리로 관찰됩니다."
U151_FED_LINE = "금리 이벤트가 할인율/달러 경로의 공통 변수로 남아 있습니다."


@pytest.mark.parametrize("block", U151_BLOCKS[:3])
@pytest.mark.parametrize("omit_keys", [True, False])
def test_u151_legacy_display_survives_without_cause_evidence(
    block: str,
    omit_keys: bool,
) -> None:
    if omit_keys:
        ctx = BundleContext(
            bundle_id="legacy",
            target_kst_date=date(2026, 9, 5),
            shared_macro_block=block,
        )
    else:
        ctx = _ctx(block, keys=frozenset())
    before = ctx.model_copy(deep=True)
    decision = evaluate_cause_map(ctx)
    assert decision.rendered == ""
    assert decision.emitted == decision.suppressed == ()
    displayed = inject_shared_macro_block("## ① 요약\n", ctx.shared_macro_block)
    assert SHARED_MACRO_HEADER in displayed
    assert block in displayed
    assert inject_cause_map_line(displayed, decision) == displayed
    assert ctx == before


@pytest.mark.parametrize("keys", U151_SUBSETS, ids=lambda keys: ",".join(sorted(keys)) or "empty")
@pytest.mark.parametrize("block", [None, ""])
def test_u151_keys_without_nonempty_block_produce_no_candidates(
    keys: frozenset[SharedMacroKey],
    block: str | None,
) -> None:
    # Empty allowlist distinguishes lack of evidence from forbidden evidence.
    decision = evaluate_cause_map(_ctx(block, keys=keys, allowed=frozenset()))
    assert decision.rendered == ""
    assert decision.emitted == decision.suppressed == ()


@pytest.mark.parametrize("block", U151_BLOCKS)
def test_u151_labels_cannot_remove_or_add_typed_causes(block: str) -> None:
    ctx = _ctx(block, keys=frozenset({"fomc", "ust_yield"}))
    decision = evaluate_cause_map(ctx)
    assert decision.emitted == ("fed_policy_event",)
    assert decision.suppressed == ()
    assert decision.rendered == f"{CAUSE_MAP_HEADER} {U151_FED_LINE}\n"


def test_u151_all_keys_deduplicate_fed_and_preserve_exact_wording_order() -> None:
    decision = evaluate_cause_map(_ctx("renamed macro", keys=frozenset(U151_KEYS)))
    assert decision.emitted == ("geopolitical_oil_macro", "fed_policy_event")
    assert decision.suppressed == ()
    assert decision.rendered == f"{CAUSE_MAP_HEADER} {U151_OIL_LINE} / {U151_FED_LINE}\n"
    assert "global_systemic_risk" not in decision.emitted


@pytest.mark.parametrize(
    ("allowed", "emitted", "suppressed", "wording"),
    [
        (
            frozenset({"fed_policy_event"}),
            ("fed_policy_event",),
            ("geopolitical_oil_macro",),
            U151_FED_LINE,
        ),
        (
            frozenset({"geopolitical_oil_macro"}),
            ("geopolitical_oil_macro",),
            ("fed_policy_event",),
            U151_OIL_LINE,
        ),
        (
            frozenset({"global_systemic_risk"}),
            (),
            ("geopolitical_oil_macro", "fed_policy_event"),
            "",
        ),
        (frozenset(), (), ("geopolitical_oil_macro", "fed_policy_event"), ""),
    ],
)
def test_u151_forbidden_causes_are_partitioned_not_demoted(
    allowed: frozenset[str],
    emitted: tuple[str, ...],
    suppressed: tuple[str, ...],
    wording: str,
) -> None:
    decision = evaluate_cause_map(_ctx("renamed macro", keys=frozenset(U151_KEYS), allowed=allowed))
    assert decision.emitted == emitted
    assert decision.suppressed == suppressed
    assert decision.rendered == (f"{CAUSE_MAP_HEADER} {wording}\n" if wording else "")


@st.composite
def _cause_contexts_u151(draw: st.DrawFn) -> BundleContext:
    return _ctx(
        draw(st.sampled_from((None, "", *U151_BLOCKS))),
        keys=draw(st.frozensets(st.sampled_from(U151_KEYS))),
        allowed=draw(st.frozensets(st.sampled_from((*U151_CAUSES, "unrelated")))),
    )


@seed(15120260908)
@settings(max_examples=80)
@given(ctx=_cause_contexts_u151(), renamed=st.sampled_from(U151_BLOCKS))
def test_u151_property_cause_partition_and_relabel_invariance(
    ctx: BundleContext,
    renamed: str,
) -> None:
    note("u151 seed=15120260908")
    before = ctx.model_copy(deep=True)
    decision = evaluate_cause_map(ctx)
    candidates = []
    if ctx.shared_macro_block:
        if "oil" in ctx.detected_macro_keys:
            candidates.append("geopolitical_oil_macro")
        if ctx.detected_macro_keys & {"fomc", "ust_yield"}:
            candidates.append("fed_policy_event")
    assert decision.emitted == tuple(c for c in candidates if c in ctx.cross_market_core_allowed)
    assert decision.suppressed == tuple(
        c for c in candidates if c not in ctx.cross_market_core_allowed
    )
    assert set(decision.emitted).isdisjoint(decision.suppressed)
    assert set(decision.emitted) | set(decision.suppressed) == set(candidates)
    if ctx.shared_macro_block:
        # model_copy only changes a valid presentation string, not validated keys.
        assert (
            evaluate_cause_map(ctx.model_copy(update={"shared_macro_block": renamed})) == decision
        )
    assert evaluate_cause_map(ctx) == decision
    assert ctx == before


@seed(15120260908)
@settings(max_examples=80)
@given(
    ctx=_cause_contexts_u151(),
    text=st.sampled_from(
        (
            "## 한눈에 보기\n\n요약.\n\n## ① 요약\n\n본문.\n",
            "첫 섹션 없는 문서\n",
            f"{CAUSE_MAP_HEADER} 기존 연결 고리.\n\n## ① 요약\n",
        )
    ),
)
def test_u151_property_cause_injection_is_idempotent(
    ctx: BundleContext,
    text: str,
) -> None:
    note("u151 seed=15120260908")
    decision = evaluate_cause_map(ctx)
    once = inject_cause_map_line(text, decision)
    assert inject_cause_map_line(once, decision) == once
    assert once.count(CAUSE_MAP_HEADER) <= 1
    if not decision.emitted or CAUSE_MAP_HEADER in text:
        assert once == text
    else:
        assert decision.rendered.strip() in once
        if "## ①" in text:
            assert once.index(CAUSE_MAP_HEADER) < once.index("## ①")
