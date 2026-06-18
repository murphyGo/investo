from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from investo.models.facts import FactSnapshot, VerifiedFactBundle
from investo.publisher.entity_fact_guard import scan_entity_fact_claims


def _bundle(*, status: str = "fresh") -> VerifiedFactBundle:
    observed = datetime(2026, 6, 18, tzinfo=UTC)
    fact = FactSnapshot(
        fact_id="fed.current_chair",
        value="Kevin Warsh",
        label_ko="케빈 워시",
        aliases=(),
        role="Chairman",
        source_name="fed-board-leadership",
        source_url="https://www.federalreserve.gov/aboutthefed/bios/board/default.htm",
        source_tier="S",
        observed_at=observed,
        expires_at=observed + timedelta(hours=24),
        status=status,  # type: ignore[arg-type]
        raw_evidence_label="Kevin Warsh, Chairman",
    )
    return VerifiedFactBundle(target_date=date(2026, 6, 18), facts=(fact,))


def test_fresh_warsh_fact_blocks_powell_current_chair_claims() -> None:
    violations = scan_entity_fact_claims(
        "## ④ 지표·이벤트\n파월 의장 기자회견이 예정돼 있다.",
        _bundle(),
        date(2026, 6, 18),
        datetime(2026, 6, 18, 1, tzinfo=UTC),
        segment="us-equity",
    )

    assert len(violations) == 1
    assert violations[0].expected_value == "Kevin Warsh"
    assert violations[0].offending_term == "파월 의장"


def test_fresh_warsh_fact_blocks_english_powell_press_conference() -> None:
    violations = scan_entity_fact_claims(
        "Chair Powell press conference is the main FOMC event.",
        _bundle(),
        date(2026, 6, 18),
        datetime(2026, 6, 18, 1, tzinfo=UTC),
        segment="us-equity",
    )

    assert violations


def test_historical_powell_reference_is_allowed() -> None:
    violations = scan_entity_fact_claims(
        "전임 의장 Powell 발언과 달리 이번 FOMC는 문구 변화를 봅니다.",
        _bundle(),
        date(2026, 6, 18),
        datetime(2026, 6, 18, 1, tzinfo=UTC),
        segment="us-equity",
    )

    assert violations == ()


def test_stale_fact_blocks_current_person_names() -> None:
    now = datetime(2026, 6, 19, 1, tzinfo=UTC)
    violations = scan_entity_fact_claims(
        "Kevin Warsh 의장 기자회견과 파월 의장 발언을 확인한다.",
        _bundle(),
        date(2026, 6, 18),
        now,
        segment="us-equity",
    )

    assert {violation.offending_term for violation in violations} >= {
        "Kevin Warsh 의장",
        "파월 의장",
    }


def test_missing_fact_allows_generic_fomc_press_conference() -> None:
    violations = scan_entity_fact_claims(
        "FOMC 기자회견 일정만 확인한다.",
        VerifiedFactBundle(target_date=date(2026, 6, 18)),
        date(2026, 6, 18),
        datetime(2026, 6, 18, 1, tzinfo=UTC),
        segment="us-equity",
    )

    assert violations == ()
