"""Pin :data:`CROSS_MARKET_CORE_ALLOWED` (u57 Step 4).

The frozenset is a single source of truth shared between the Stage-2
prompt builders and the cross-segment lint. Adding new themes is the
remit of a *separate* unit — these tests fail loudly on accidental
mutation so the regression catches the wider impact.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, note, seed, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from investo.models.bundle_context import (
    CROSS_MARKET_CORE_ALLOWED,
    BundleContext,
    DailyThesisDecision,
    MarketStateSummary,
    SharedMacroKey,
)


class TestPinnedMembers:
    def test_geopolitical_oil_macro_present(self) -> None:
        assert "geopolitical_oil_macro" in CROSS_MARKET_CORE_ALLOWED

    def test_fed_policy_event_present(self) -> None:
        assert "fed_policy_event" in CROSS_MARKET_CORE_ALLOWED

    def test_global_systemic_risk_present(self) -> None:
        assert "global_systemic_risk" in CROSS_MARKET_CORE_ALLOWED

    def test_exactly_three_members(self) -> None:
        # New themes require a follow-up unit — this assertion enforces
        # the boundary.
        assert len(CROSS_MARKET_CORE_ALLOWED) == 3


class TestIsFrozenset:
    def test_immutable_type(self) -> None:
        assert isinstance(CROSS_MARKET_CORE_ALLOWED, frozenset)


class TestBundleContextCarriesAllowlist:
    def test_default_field_value(self) -> None:
        from datetime import date

        ctx = BundleContext(
            bundle_id="x",
            target_kst_date=date(2026, 5, 11),
            segments={},
        )
        assert ctx.cross_market_core_allowed == CROSS_MARKET_CORE_ALLOWED


U151_KEYS: tuple[SharedMacroKey, ...] = ("fomc", "oil", "ust_yield")


class TestSelectedMacroKeysU151:
    def test_legacy_block_does_not_infer_keys_or_reset_decision(self) -> None:
        decision = DailyThesisDecision(mode="data_limited", reason="caller_provided")
        ctx = BundleContext(
            bundle_id="legacy",
            target_kst_date=date(2026, 9, 5),
            shared_macro_block="- **국제 유가** — WTI rises",
            daily_thesis_decision=decision,
        )
        assert ctx.detected_macro_keys == frozenset()
        assert ctx.shared_macro_block == "- **국제 유가** — WTI rises"
        assert ctx.daily_thesis_decision == decision

    @pytest.mark.parametrize("invalid", [None, ["unknown"], ["oil", "global_systemic_risk"]])
    def test_normal_model_validation_rejects_null_or_unknown(self, invalid: object) -> None:
        with pytest.raises(ValidationError) as exc:
            BundleContext.model_validate(
                {
                    "bundle_id": "invalid",
                    "target_kst_date": "2026-09-05",
                    "detected_macro_keys": invalid,
                }
            )
        assert exc.value.errors()[0]["loc"][0] == "detected_macro_keys"

    def test_duplicate_valid_keys_collapse_and_json_order_is_canonical(self) -> None:
        ctx = BundleContext.model_validate(
            {
                "bundle_id": "duplicates",
                "target_kst_date": "2026-09-05",
                "detected_macro_keys": ["ust_yield", "oil", "fomc", "oil"],
            }
        )
        assert ctx.detected_macro_keys == frozenset(U151_KEYS)
        assert isinstance(ctx.model_dump()["detected_macro_keys"], frozenset)
        assert ctx.model_dump(mode="json")["detected_macro_keys"] == list(U151_KEYS)
        assert ctx.shared_macro_block is None  # Keys alone do not synthesize display text.
        with pytest.raises(ValidationError, match="frozen"):
            ctx.detected_macro_keys = frozenset()  # type: ignore[misc]

    def test_self_pending_copy_carries_keys_without_changing_original(self) -> None:
        summary = MarketStateSummary(
            segment="us-equity",
            target_date=date(2026, 9, 5),
            tz="America/New_York",
            close_state="close",
        )
        ctx = BundleContext(
            bundle_id="copy",
            target_kst_date=summary.target_date,
            segments={"us-equity": summary},
            detected_macro_keys=frozenset(U151_KEYS),
        )
        copied = ctx.with_self_pending("us-equity")
        assert copied.detected_macro_keys == ctx.detected_macro_keys
        assert copied.segments["us-equity"].close_state == "pending"
        assert ctx.segments["us-equity"].close_state == "close"


@seed(15120260908)
@settings(max_examples=40)
@given(
    keys=st.frozensets(st.sampled_from(U151_KEYS)),
    target_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    block=st.sampled_from((None, "", "renamed display without macro labels")),
)
def test_u151_property_ordinary_context_json_round_trip(
    keys: frozenset[SharedMacroKey], target_date: date, block: str | None
) -> None:
    note("u151 seed=15120260908")
    ctx = BundleContext(
        bundle_id="round-trip",
        target_kst_date=target_date,
        detected_macro_keys=keys,
        shared_macro_block=block,
        segments={
            "us-equity": MarketStateSummary(
                segment="us-equity",
                target_date=target_date,
                tz="America/New_York",
                close_state="close",
            )
        },
        daily_thesis_decision=DailyThesisDecision(mode="data_limited", reason="fixture"),
    )
    assert BundleContext.model_validate_json(ctx.model_dump_json()) == ctx
    assert ctx.model_dump(mode="json")["detected_macro_keys"] == sorted(keys)
    assert isinstance(ctx.model_dump()["detected_macro_keys"], frozenset)
