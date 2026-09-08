"""u151: real generated-to-sealed regression, with synthetic offline source items.

No matcher, finalization phase, trust gate, seal or notification derivation is
stubbed. This bounds deterministic promotion, not arbitrary LLM causal prose.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

import pytest
from hypothesis import given, note, seed, settings
from hypothesis import strategies as st

from investo._internal.disclaimer import DISCLAIMER
from investo.models import Briefing, NormalizedItem
from investo.models.bundle_context import BundleContext, SharedMacroKey
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.orchestrator.bundle_context import compute_bundle_context
from investo.publisher.public_document import (
    FinalizedPublicBundle,
    PublicDocumentContext,
    finalize_public_bundle,
)
from tests._helpers.bundle_context_u151 import KEY_SUBSETS, SEGMENTS

_DATE = date(2026, 9, 4)
_NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
_SOURCE = "cftc-cot-positioning"
_CONCLUSION = "시장별 관측 자료를 확인했습니다."
_SHARED_HEADER = "## ⓪ 오늘의 매크로"
_CAUSE_HEADER = "> **크로스마켓 연결 고리**:"
_OIL_CAUSE = "유가/지정학 이슈가 여러 자산군의 변동성 연결 고리로 관찰됩니다."
_FED_CAUSE = "금리 이벤트가 할인율/달러 경로의 공통 변수로 남아 있습니다."
_US_GROUPS = ("equity_index", "rates", "fx", "energy", "metals", "volatility")
_REQUIRED_FIELDS = (
    "contract_group",
    "contract_label",
    "net_contracts",
    "net_pct_open_interest",
    "as_of_date",
    "release_date",
)
_KEY_LABELS: dict[SharedMacroKey, str] = {
    "fomc": "FOMC 일정",
    "oil": "국제 유가",
    "ust_yield": "미 국채 수익률",
}
_BODY = (
    "# 합성 시황\n\n"
    f"> **오늘의 결론**: {_CONCLUSION}\n"
    "> **핵심 동인**: 수급 자료를 확인했습니다.\n"
    "> **주의할 점**: 관측 시차를 확인해야 합니다.\n\n"
    "## 한눈에 보기\n\n"
    "- 시장별 관측 자료를 확인했습니다.\n"
    "- 수급 자료를 확인했습니다.\n"
    "- 관측 시차를 확인해야 합니다.\n\n"
    "## ① 요약\n\n시장별 관측 자료를 확인했습니다.\n\n"
    "## ② 전일 핵심 이슈\n\n관측 자료의 기준 시각을 확인했습니다.\n\n"
    "> **그래서 의미는?** 시장별 관측 시차를 함께 확인해야 합니다.\n\n"
    "## ③ 섹터/수급 동향\n\n수급 자료를 확인했습니다.\n\n"
    "## ④ 지표·이벤트\n\n발표 일정을 확인했습니다.\n\n"
    "## ⑤ 주요 종목\n\n시장별 주요 자산을 확인했습니다.\n\n"
    "## ⑥ 오늘의 관전 포인트\n\n관측 시차를 확인해야 합니다.\n\n"
    "<details><summary>수집/품질 진단</summary>\n정상 수집\n</details>\n\n"
    f"{DISCLAIMER}\n"
)


def _briefing() -> Briefing:
    return Briefing(
        target_date=_DATE,
        # A generated field is deliberately different from terminal Markdown.
        market_summary="GENERATED_ONLY_SENTINEL CFTC 유가 상승",
        key_issues="관측 자료",
        sector_flow="수급 자료",
        indicators_events="발표 일정",
        notable_tickers="주요 자산",
        today_watch="관측 시차",
        disclaimer=DISCLAIMER,
        rendered_markdown=_BODY,
    )


def _position(
    *,
    group: str = "energy",
    label: str = "WTI",
    title: str = "CFTC WTI crude oil managed_money net +94281 contracts",
    metadata: dict[str, str | int | float] | None = None,
) -> NormalizedItem:
    values: dict[str, str | int | float] = {
        "contract_group": group,
        "contract_label": label,
        "net_contracts": "+94281",
        "net_pct_open_interest": "12.50",
        "as_of_date": "2026-09-01",
        "release_date": "2026-09-04",
    }
    return NormalizedItem(
        source_name=_SOURCE,
        category="macro",
        title=title,
        published_at=_NOW,
        raw_metadata=values if metadata is None else metadata,
    )


def _positions() -> tuple[NormalizedItem, ...]:
    return (_position(), _position(group="crypto", label="Bitcoin CME"))


def _eligible(key: SharedMacroKey) -> NormalizedItem:
    source, title = {
        "oil": ("synthetic-oil-news", "Brent oil market observation"),
        "fomc": ("fomc-calendar", "FOMC meeting statement"),
        "ust_yield": ("treasury-rates", "미 국채 수익률 관찰 자료"),
    }[key]
    return NormalizedItem(source_name=source, category="macro", title=title, published_at=_NOW)


def _routed(
    positions: tuple[NormalizedItem, ...] | None = None,
    *,
    keys: frozenset[SharedMacroKey] = frozenset(),
    supporting: tuple[MarketSegment, ...] = (US_EQUITY, CRYPTO),
) -> dict[MarketSegment, tuple[NormalizedItem, ...]]:
    rows = _positions() if positions is None else positions
    evidence = tuple(_eligible(key) for key in sorted(keys))
    return {segment: rows + (evidence if segment in supporting else ()) for segment in SEGMENTS}


def _context(
    routed: dict[MarketSegment, tuple[NormalizedItem, ...]],
    *,
    bundle: BundleContext | None = None,
) -> PublicDocumentContext:
    return PublicDocumentContext(
        target_date=_DATE,
        expected_segments=SEGMENTS,
        input_absences={},
        anchors_by_segment={},
        items_by_segment=routed,
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="normal",
                item_count=len(items),
                source_count=len({item.source_name for item in items}),
                categories=("macro",),
                missing_categories=(),
            )
            for segment, items in routed.items()
        },
        source_outcomes=(),
        bundle_context=(compute_bundle_context(routed, now_kst=_NOW) if bundle is None else bundle),
        fact_bundle=VerifiedFactBundle(target_date=_DATE),
        entity_observed_at_utc=_NOW,
    )


def _finalize(context: PublicDocumentContext) -> FinalizedPublicBundle:
    return finalize_public_bundle({segment: _briefing() for segment in SEGMENTS}, context=context)


def _assert_sealed(result: FinalizedPublicBundle) -> dict[MarketSegment, str]:
    assert tuple(document.segment for document in result.documents) == SEGMENTS
    assert tuple(outcome.state for outcome in result.segment_outcomes) == ("finalized",) * 3
    markdowns: dict[MarketSegment, str] = {}
    for document in result.documents:
        markdown = document.briefing.rendered_markdown
        markdowns[document.segment] = markdown
        assert document.markdown_sha256 == sha256(markdown.encode()).hexdigest()
        assert document.numeric_containment_outcomes == ()
        summary = document.notification_summary
        assert summary.segment == document.segment
        assert summary.target_date == _DATE
        assert summary.coverage_status == "normal"
        assert summary.conclusion == _CONCLUSION
        assert "GENERATED_ONLY_SENTINEL" not in repr(summary)
        assert "CFTC" not in repr(summary)
        assert "유가 상승" not in repr(summary)
        assert f"> **오늘의 결론**: {_CONCLUSION}" in markdown
        assert "면책" in markdown
    return markdowns


def _assert_unpromoted(markdowns: dict[MarketSegment, str]) -> None:
    for markdown in markdowns.values():
        assert _SHARED_HEADER not in markdown
        assert _CAUSE_HEADER not in markdown
        assert "유가와 지정학 변수" not in markdown
        assert "금리와 달러 변수" not in markdown


def _row(label: str) -> str:
    return f"{label} 순포지션 +94281계약 (12.50% OI), 2026-09-01 기준/2026-09-04 공개"


def _positioning_row(markdown: str, segment: MarketSegment) -> str:
    prefix = {US_EQUITY: "| CFTC 포지셔닝 |", CRYPTO: "| CFTC 코인 포지셔닝 |"}[segment]
    rows = [line for line in markdown.splitlines() if line.startswith(prefix)]
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize(
    "title",
    (
        "CFTC WTI crude oil managed_money net +94281 contracts",
        "CFTC FOMC WTI UST yield positioning",
    ),
)
def test_cftc_only_finalizes_three_segments_without_shared_promotion(title: str) -> None:
    positions = (
        _position(title=title),
        _position(group="crypto", label="Bitcoin CME", title=title),
    )
    routed = _routed(positions)
    before = {
        segment: tuple(item.model_dump() for item in items) for segment, items in routed.items()
    }
    context = _context(routed)
    assert context.bundle_context is not None
    assert context.bundle_context.detected_macro_keys == frozenset()
    assert context.bundle_context.daily_thesis_signals == ()
    assert context.bundle_context.daily_thesis_decision.mode == "data_limited"
    result = _finalize(context)
    markdowns = _assert_sealed(result)
    _assert_unpromoted(markdowns)
    assert f"| CFTC 포지셔닝 | {_row('WTI')} · 주간 지연 |" in markdowns[US_EQUITY]
    assert f"| CFTC 코인 포지셔닝 | {_row('Bitcoin CME')} · 주간 지연 |" in markdowns[CRYPTO]
    assert "순포지션" not in markdowns[DOMESTIC_EQUITY]
    assert "주간 지연" not in markdowns[DOMESTIC_EQUITY]
    assert before == {
        segment: tuple(item.model_dump() for item in items) for segment, items in routed.items()
    }
    repeated = finalize_public_bundle(
        {document.segment: document.briefing for document in result.documents}, context=context
    )
    assert _assert_sealed(repeated) == markdowns
    assert tuple(d.notification_summary for d in repeated.documents) == tuple(
        d.notification_summary for d in result.documents
    )


@pytest.mark.parametrize("supporting", SEGMENTS)
def test_one_eligible_oil_segment_plus_positioning_cannot_promote(
    supporting: MarketSegment,
) -> None:
    context = _context(_routed(keys=frozenset({"oil"}), supporting=(supporting,)))
    assert context.bundle_context is not None
    assert context.bundle_context.detected_macro_keys == frozenset()
    _assert_unpromoted(_assert_sealed(_finalize(context)))


@pytest.mark.parametrize("keys", KEY_SUBSETS)
def test_eligible_selected_key_subsets_survive_real_finalization(
    keys: frozenset[SharedMacroKey],
) -> None:
    context = _context(_routed(keys=keys))
    assert context.bundle_context is not None
    assert context.bundle_context.detected_macro_keys == keys
    decision = context.bundle_context.daily_thesis_decision
    assert decision.mode == ("strong" if keys else "data_limited")
    assert decision.macro_keys == tuple(sorted(keys)[:1])
    assert all(
        _SOURCE not in signal.source_ids for signal in context.bundle_context.daily_thesis_signals
    )
    markdowns = _assert_sealed(_finalize(context))
    for markdown in markdowns.values():
        assert (_SHARED_HEADER in markdown) == bool(keys)
        for key, label in _KEY_LABELS.items():
            assert (f"**{label}**" in markdown) == (key in keys)
        assert markdown.count(_OIL_CAUSE) == int("oil" in keys)
        assert markdown.count(_FED_CAUSE) == int(bool(keys & {"fomc", "ust_yield"}))
        assert "공통 위험 요인으로 변동성 확대 여부를 점검합니다." not in markdown
    assert _row("WTI") in markdowns[US_EQUITY]
    assert _row("Bitcoin CME") in markdowns[CRYPTO]
    if keys:
        driver = "유가와 지정학 변수" if sorted(keys)[0] == "oil" else "금리와 달러 변수"
        assert driver in markdowns[US_EQUITY]
        assert driver in markdowns[CRYPTO]


def test_finalized_relabel_and_legacy_empty_keys_keep_distinct_cause_contracts() -> None:
    context = _context(_routed(keys=frozenset({"oil"})))
    bundle = context.bundle_context
    assert bundle is not None
    renamed = bundle.model_copy(update={"shared_macro_block": "- **에너지 관측** — 합성 자료"})
    renamed_context = replace(context, bundle_context=renamed)
    for markdown in _assert_sealed(_finalize(renamed_context)).values():
        assert "**에너지 관측**" in markdown
        assert _OIL_CAUSE in markdown
    legacy = renamed.model_copy(update={"detected_macro_keys": frozenset()})
    for markdown in _assert_sealed(_finalize(replace(context, bundle_context=legacy))).values():
        assert "**에너지 관측**" in markdown
        assert _CAUSE_HEADER not in markdown
    # Legacy compatibility must not reset caller-provided thesis evidence.
    assert legacy.daily_thesis_signals == bundle.daily_thesis_signals


@pytest.mark.parametrize("field", _REQUIRED_FIELDS)
@pytest.mark.parametrize("defect", (None, "", "   ", 17))
def test_missing_blank_or_non_string_position_fields_are_not_reconstructed(
    field: str, defect: str | int | None
) -> None:
    rows: list[NormalizedItem] = []
    for original in _positions():
        metadata = dict(original.raw_metadata)
        if defect is None:
            del metadata[field]
        else:
            metadata[field] = defect
        rows.append(_position(metadata=metadata, title="CFTC FOMC WTI UST yield positioning"))
    context = _context(_routed(tuple(rows)))
    markdowns = _assert_sealed(_finalize(context))
    _assert_unpromoted(markdowns)
    for markdown in markdowns.values():
        assert "순포지션" not in markdown
        assert "주간 지연" not in markdown


def test_nonblank_malformed_strings_keep_existing_presence_only_row_contract() -> None:
    rows = []
    for original in _positions():
        metadata = dict(original.raw_metadata)
        metadata.update(
            net_contracts="unknown",
            net_pct_open_interest="not-a-number",
            as_of_date="invalid-as-of",
            release_date="invalid-release",
        )
        rows.append(_position(metadata=metadata))
    markdowns = _assert_sealed(_finalize(_context(_routed(tuple(rows)))))
    _assert_unpromoted(markdowns)
    for segment in (US_EQUITY, CRYPTO):
        assert (
            "순포지션 unknown계약 (not-a-number% OI), "
            "invalid-as-of 기준/invalid-release 공개 · 주간 지연"
        ) in markdowns[segment]
    assert "순포지션" not in markdowns[DOMESTIC_EQUITY]


@pytest.mark.parametrize("group", _US_GROUPS)
def test_existing_us_groups_stay_us_only_and_crypto_stays_crypto(group: str) -> None:
    positions = (
        _position(group=group, label="미국 관측"),
        _position(group="crypto", label="가상자산 관측"),
        _position(group="unknown", label="미분류 관측"),
    )
    markdowns = _assert_sealed(_finalize(_context(_routed(positions))))
    _assert_unpromoted(markdowns)
    assert _row("미국 관측") in markdowns[US_EQUITY]
    assert _row("가상자산 관측") not in markdowns[US_EQUITY]
    assert _row("가상자산 관측") in markdowns[CRYPTO]
    assert _row("미국 관측") not in markdowns[CRYPTO]
    for markdown in markdowns.values():
        assert "미분류 관측" not in markdown
    assert "순포지션" not in markdowns[DOMESTIC_EQUITY]


def test_positioning_row_order_and_cap_apply_after_group_filtering() -> None:
    positions = tuple(
        item
        for index in range(4)
        for item in (
            _position(group="unknown", label=f"미분류-{index}"),
            _position(group="crypto", label=f"가상자산-{index}"),
            _position(label=f"미국-{index}"),
        )
    )
    markdowns = _assert_sealed(_finalize(_context(_routed(positions))))
    _assert_unpromoted(markdowns)
    for segment, label in ((US_EQUITY, "미국"), (CRYPTO, "가상자산")):
        expected = " · ".join(_row(f"{label}-{index}") for index in range(3))
        row = _positioning_row(markdowns[segment], segment)
        assert expected + " · 주간 지연" in row
        assert f"{label}-3" not in row
        assert row.count("순포지션") == 3
        assert row.count("주간 지연") == 1


def test_delayed_watchpoint_is_allowed_beside_the_bounded_channel_row() -> None:
    # Shrunk seed-15120260908 oracle failure: a rates item also feeds an
    # existing legitimate watchpoint, so a document-wide row count is wrong.
    rows = []
    for label, net, pct in (("미국 관측-0", "+4", "24.29"), ("미국 관측-1", "-1840", "-18.40")):
        metadata = dict(_position(group="rates", label=label).raw_metadata)
        metadata.update(net_contracts=net, net_pct_open_interest=pct)
        rows.append(_position(metadata=metadata))
    rows.append(_position(group="crypto", label="가상자산 관측-0"))
    markdowns = _assert_sealed(_finalize(_context(_routed(tuple(rows)))))
    _assert_unpromoted(markdowns)
    channel = _positioning_row(markdowns[US_EQUITY], US_EQUITY)
    assert channel.count("순포지션") == 2
    watchpoints = markdowns[US_EQUITY].split("## ⑥ 오늘의 관전 포인트", 1)[1]
    assert "미국 관측-1 포지셔닝" in watchpoints
    assert "순포지션 -1,840계약" in watchpoints
    assert "주간 지연" in watchpoints


def test_equal_zero_positions_keep_both_percentages_on_fixed_input_repeats() -> None:
    # Shrunk seed-15120260908 boundary. Replaying sealed output as a new
    # generated draft is a different input and outside this repeat contract.
    rows = []
    for group, label in (
        ("equity_index", "미국 관측-0"),
        ("crypto", "가상자산 관측-0"),
        ("crypto", "가상자산 관측-1"),
    ):
        metadata = dict(_position(group=group, label=label).raw_metadata)
        metadata.update(net_contracts="+0", net_pct_open_interest="0.00")
        rows.append(_position(metadata=metadata))
    context = _context(_routed(tuple(rows)))
    first = _assert_sealed(_finalize(context))
    assert _assert_sealed(_finalize(context)) == first
    _assert_unpromoted(first)
    row = _positioning_row(first[CRYPTO], CRYPTO)
    assert row.count("순포지션 +0계약 (0.00% OI)") == 2


def test_forbidden_cause_is_not_demoted_into_final_public_prose() -> None:
    context = _context(_routed(keys=frozenset({"oil"})))
    assert context.bundle_context is not None
    blocked = context.bundle_context.model_copy(
        update={"cross_market_core_allowed": frozenset({"fed_policy_event"})}
    )
    markdowns = _assert_sealed(_finalize(replace(context, bundle_context=blocked)))
    for markdown in markdowns.values():
        assert "**국제 유가**" in markdown  # Evidence can still display.
        assert _CAUSE_HEADER not in markdown
        assert _OIL_CAUSE not in markdown
    # Thesis retains its approved independent global allowlist, not this gate.
    assert "유가와 지정학 변수" in markdowns[US_EQUITY]


@dataclass(frozen=True)
class _PositionBatch:
    items: tuple[NormalizedItem, ...]
    us_rows: tuple[str, ...]
    crypto_rows: tuple[str, ...]


@st.composite
def _position_batches(draw: st.DrawFn) -> _PositionBatch:
    """Valid synthetic dates/counts; expected rows independent of production rendering."""
    counts = draw(st.tuples(st.integers(1, 5), st.integers(1, 5)))
    as_of = _DATE - timedelta(days=draw(st.integers(min_value=3, max_value=28)))
    release = as_of + timedelta(days=3)
    items: list[NormalizedItem] = []
    expected: list[list[str]] = [[], []]
    for channel, count in enumerate(counts):
        for index in range(count):
            group = draw(st.sampled_from(_US_GROUPS)) if channel == 0 else "crypto"
            label = f"{'미국' if channel == 0 else '가상자산'} 관측-{index}"
            net = f"{draw(st.integers(-999999, 999999)):+d}"
            percent = f"{Decimal(draw(st.integers(-10000, 10000))) / 100:.2f}"
            metadata: dict[str, str | int | float] = {
                "contract_group": group,
                "contract_label": label,
                "net_contracts": net,
                "net_pct_open_interest": percent,
                "as_of_date": as_of.isoformat(),
                "release_date": release.isoformat(),
            }
            items.append(
                _position(
                    metadata=metadata,
                    title=draw(
                        st.sampled_from(
                            ("CFTC WTI positioning", "CFTC FOMC UST yield WTI", "CFTC positions")
                        )
                    ),
                )
            )
            expected[channel].append(
                f"{label} 순포지션 {net}계약 ({percent}% OI), "
                f"{as_of.isoformat()} 기준/{release.isoformat()} 공개"
            )
    return _PositionBatch(tuple(items), tuple(expected[0]), tuple(expected[1]))


@seed(15120260908)
# Six real segment finalizations per example exceeded Hypothesis's default
# 200 ms on cold runs (450 ms observed). Keep a finite one-second deadline;
# no disabled shrinking, retry suppression or production performance change.
@settings(max_examples=30, deadline=1000)
@given(batch=_position_batches())
def test_property_finalized_delayed_rows_and_repeatability(batch: _PositionBatch) -> None:
    note("u151 seed=15120260908")
    context = _context(_routed(batch.items))
    originals = {segment: _briefing() for segment in SEGMENTS}
    before = {segment: briefing.model_dump() for segment, briefing in originals.items()}
    result = finalize_public_bundle(originals, context=context)
    markdowns = _assert_sealed(result)
    _assert_unpromoted(markdowns)
    assert "순포지션" not in markdowns[DOMESTIC_EQUITY]
    for segment, expected in ((US_EQUITY, batch.us_rows), (CRYPTO, batch.crypto_rows)):
        row = _positioning_row(markdowns[segment], segment)
        assert " · ".join(expected[:3]) + " · 주간 지연" in row
        assert row.count("순포지션") == min(3, len(expected))
        for excluded in expected[3:]:
            assert excluded not in row
    # Approved AC-151.6 fixes generated drafts as well as source/state inputs.
    repeated = finalize_public_bundle(originals, context=context)
    assert _assert_sealed(repeated) == markdowns
    assert tuple(d.notification_summary for d in repeated.documents) == tuple(
        d.notification_summary for d in result.documents
    )
    assert {segment: briefing.model_dump() for segment, briefing in originals.items()} == before


@st.composite
def _permuted_routed(draw: st.DrawFn) -> dict[MarketSegment, tuple[NormalizedItem, ...]]:
    keys = draw(st.sampled_from(KEY_SUBSETS))
    routed = _routed(keys=keys)
    result: dict[MarketSegment, tuple[NormalizedItem, ...]] = {}
    for segment in draw(st.permutations(SEGMENTS)):
        positions = routed[segment][:2]  # Channel row order is intentionally fixed.
        evidence = draw(st.permutations(routed[segment][2:]))
        result[segment] = (*positions, *evidence)
    return result


@seed(15120260908)
@settings(max_examples=30, deadline=1000)
@given(routed=_permuted_routed())
def test_property_equivalent_candidates_preserve_final_bytes_and_dto(
    routed: dict[MarketSegment, tuple[NormalizedItem, ...]],
) -> None:
    note("u151 seed=15120260908")
    canonical = {
        segment: (*routed[segment][:2], *sorted(routed[segment][2:], key=lambda item: item.title))
        for segment in SEGMENTS
    }
    original = _context(canonical)
    permuted = _context(routed)
    assert original.bundle_context == permuted.bundle_context
    first = _finalize(original)
    again = _finalize(permuted)
    assert _assert_sealed(first) == _assert_sealed(again)
    assert tuple(d.notification_summary for d in first.documents) == tuple(
        d.notification_summary for d in again.documents
    )
