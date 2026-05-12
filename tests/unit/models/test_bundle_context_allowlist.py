"""Pin :data:`CROSS_MARKET_CORE_ALLOWED` (u57 Step 4).

The frozenset is a single source of truth shared between the Stage-2
prompt builders and the cross-segment lint. Adding new themes is the
remit of a *separate* unit — these tests fail loudly on accidental
mutation so the regression catches the wider impact.
"""

from __future__ import annotations

from investo.models.bundle_context import CROSS_MARKET_CORE_ALLOWED, BundleContext


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
