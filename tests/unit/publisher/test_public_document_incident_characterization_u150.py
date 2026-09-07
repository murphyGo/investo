"""u150 incident baseline plus staged scanner and transform regressions."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from investo._internal.surface_quality import (
    find_surface_quality_issues,
    repair_surface_artifacts,
    repair_surface_link_targets,
)
from investo.models import Briefing
from investo.models.facts import VerifiedFactBundle
from investo.models.public_notification import PublicNotificationSummary
from investo.models.segments import DOMESTIC_EQUITY, SegmentCoverage
from investo.publisher._public_document_policy import (
    PublicBlockKind,
    surface_issue_disposition,
)
from investo.publisher.public_document import (
    _REGION_SAFE_FALLBACK_TEXT,
    PublicDocumentContext,
    PublicDocumentDraft,
    PublicDocumentLayout,
    PublicRegionExpectation,
    _new_generated_draft,
    _repair_projected_draft,
    _seal_document,
    _transition_draft,
)

_FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "u150" / "link-containment-incidents.json"
_TARGET_DATE = date(2026, 8, 28)
_SHAPES = (
    "inline_link",
    "image",
    "autolink",
    "reference_definition",
    "incomplete_inline",
    "unmatched_residual",
)


def _fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _canonical_markdown(fragment: str, *, block: PublicBlockKind) -> str:
    first_viewport = fragment if block == "first_viewport" else ""
    section_one = fragment if block == "section_body" else "요약 본문"
    watchpoints = fragment if block == "watchpoints" else "- 확인할 조건"
    return (
        f"# {_TARGET_DATE.isoformat()} 국내 증시 시황\n\n"
        "**세그먼트**: [국내](/domestic)\n\n"
        "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다.\n\n"
        f"{first_viewport}\n\n"
        "## ① 요약\n\n"
        f"{section_one}\n\n"
        "## ② 전일 핵심 이슈\n\n이슈 본문\n\n"
        "## ③ 섹터/수급 동향\n\n수급 본문\n\n"
        "## ④ 지표·이벤트\n\n이벤트 본문\n\n"
        "## ⑤ 주요 종목\n\n종목 본문\n\n"
        f"## ⑥ 오늘의 관전 포인트\n\n{watchpoints}\n\n"
        "<details><summary>수집/품질 진단</summary>\n정상 수집\n</details>\n\n"
        "## ⑦ 면책조항\n\n본 문서는 정보 제공용입니다.\n"
    )


def _projected_draft(markdown: str) -> tuple[PublicDocumentDraft, PublicDocumentContext]:
    expectation = PublicRegionExpectation(
        target_date=_TARGET_DATE,
        segment=DOMESTIC_EQUITY,
        segmented_mode=True,
        supplement_ids=(),
        shared_macro_required=False,
        crypto_indicators_required=False,
        channel_anchors_required=False,
        daily_thesis_required=False,
        anchor_table_required=False,
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=expectation)
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약 본문",
        key_issues="이슈 본문",
        sector_flow="수급 본문",
        indicators_events="이벤트 본문",
        notable_tickers="종목 본문",
        today_watch="확인할 조건",
        disclaimer="본 문서는 정보 제공용입니다.",
        rendered_markdown=markdown,
    )
    generated = _new_generated_draft(
        briefing,
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    assembled = _transition_draft(generated, next_phase="assembled")
    projected = _transition_draft(assembled, next_phase="projected")
    context = PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=(DOMESTIC_EQUITY,),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            DOMESTIC_EQUITY: SegmentCoverage(
                segment=DOMESTIC_EQUITY,
                status="normal",
                item_count=1,
                source_count=1,
                categories=("news",),
                missing_categories=(),
            )
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 8, 28, tzinfo=UTC),
    )
    return projected, context


def test_bounded_run_metadata_matches_the_six_observed_workflow_results() -> None:
    runs = _fixture()["run_metadata"]
    observed = {
        run["github_actions_run_id"]: (
            run["target_date"],
            run["workflow_conclusion"],
            run["pipeline_status"],
            tuple(
                (outcome["segment"], outcome["state"], tuple(outcome["issue_codes"]))
                for outcome in run["segment_outcomes"]
            ),
        )
        for run in runs
    }
    expected = {
        32784998097: (
            "2026-08-24",
            "failure",
            "partial",
            (
                ("domestic-equity", "finalized_degraded", ("numeric.anchor_assertion",)),
                ("us-equity", "trust_blocked", ("document.fallback_exhausted",)),
                ("crypto", "finalized", ()),
            ),
        ),
        33035060796: (
            "2026-08-26",
            "failure",
            "partial",
            (
                ("domestic-equity", "finalized", ()),
                ("us-equity", "trust_blocked", ("document.fallback_exhausted",)),
                ("crypto", "trust_blocked", ("markdown.href_ellipsis",)),
            ),
        ),
        33146560495: (
            "2026-08-27",
            "failure",
            "partial",
            (
                ("domestic-equity", "finalized_degraded", ("numeric.anchor_assertion",)),
                ("us-equity", "finalized", ()),
                ("crypto", "trust_blocked", ("markdown.href_ellipsis",)),
            ),
        ),
        33238048642: (
            "2026-08-28",
            "failure",
            "partial",
            (
                ("domestic-equity", "trust_blocked", ("markdown.unmatched_link",)),
                ("us-equity", "finalized", ()),
                ("crypto", "finalized", ()),
            ),
        ),
        33344214754: (
            "2026-08-28",
            "failure",
            "partial",
            (
                ("domestic-equity", "finalized_degraded", ("numeric.anchor_assertion",)),
                ("us-equity", "finalized", ()),
                ("crypto", "trust_blocked", ("markdown.href_ellipsis",)),
            ),
        ),
        33457514796: (
            "2026-08-31",
            "success",
            "success",
            (
                ("domestic-equity", "finalized_degraded", ("numeric.anchor_assertion",)),
                ("us-equity", "finalized", ()),
                ("crypto", "finalized", ()),
            ),
        ),
    }
    assert observed == expected


def test_run_metadata_excludes_production_content_and_identifiers() -> None:
    runs = _fixture()["run_metadata"]
    forbidden_keys = {
        "markdown",
        "evidence",
        "url",
        "head_sha",
        "message_id",
        "claim_digest",
        "region_id",
        "source_payload",
        "secret",
    }
    allowed_run_keys = {
        "github_actions_run_id",
        "target_date",
        "workflow_conclusion",
        "pipeline_status",
        "segment_outcomes",
    }
    allowed_outcome_keys = {"segment", "state", "issue_codes"}

    assert all(set(run) == allowed_run_keys for run in runs)
    assert all(
        set(outcome) == allowed_outcome_keys and forbidden_keys.isdisjoint(outcome)
        for run in runs
        for outcome in run["segment_outcomes"]
    )
    assert "https://" not in json.dumps(runs)


@pytest.mark.parametrize("case_index", range(6))
def test_synthetic_fixture_covers_each_canonical_link_issue(case_index: int) -> None:
    cases = _fixture()["synthetic_markdown"]
    case = cases[case_index]
    issues = find_surface_quality_issues(case["markdown"])

    assert tuple(item["shape"] for item in cases) == _SHAPES
    assert "example.invalid" in case["markdown"] or case["shape"] == "unmatched_residual"
    matched = [issue for issue in issues if issue.code == case["expected_issue_code"]]
    assert len(matched) == 1
    assert matched[0].link_shape == case["shape"]


@pytest.mark.parametrize("issue_code", ("markdown.href_ellipsis", "markdown.unmatched_link"))
@pytest.mark.parametrize("block", ("first_viewport", "section_body", "watchpoints"))
def test_link_policy_without_scanner_shape_fails_closed(
    issue_code: str,
    block: PublicBlockKind,
) -> None:
    assert surface_issue_disposition(issue_code, block) == "block_segment"


@pytest.mark.parametrize(
    ("case_index", "expected_disposition"),
    (
        (0, "repaired"),
        (1, "repaired"),
        (2, "repaired"),
        (3, "replaced"),
        (4, "repaired"),
        (5, "replaced"),
    ),
)
def test_step3_required_section_link_shapes_use_one_owned_action(
    case_index: int,
    expected_disposition: str,
) -> None:
    case = _fixture()["synthetic_markdown"][case_index]
    projected, context = _projected_draft(
        _canonical_markdown(case["markdown"], block="section_body")
    )

    repaired = _repair_projected_draft(projected, context)

    assert repaired.layout.markdown.count("## ① 요약") == 1
    assert "## ② 전일 핵심 이슈\n\n이슈 본문" in repaired.layout.markdown
    assert case["markdown"] not in repaired.layout.markdown
    assert "example.invalid" not in repaired.layout.markdown
    assert not any(
        issue.code == case["expected_issue_code"]
        for issue in find_surface_quality_issues(repaired.layout.markdown)
    )
    outcome = next(
        outcome for outcome in repaired.block_outcomes if outcome.region_id == "section:1"
    )
    assert outcome.disposition == expected_disposition
    if expected_disposition == "replaced":
        assert _REGION_SAFE_FALLBACK_TEXT["section_body"] in repaired.layout.markdown


def test_step3_repaired_link_bytes_and_redacted_outcome_survive_the_existing_seal() -> None:
    case = _fixture()["synthetic_markdown"][0]
    projected, context = _projected_draft(
        _canonical_markdown(case["markdown"], block="section_body")
    )
    repaired = _repair_projected_draft(projected, context)
    validated = _transition_draft(
        repaired,
        next_phase="validated",
        notification_summary=PublicNotificationSummary(
            segment=DOMESTIC_EQUITY,
            target_date=_TARGET_DATE,
            conclusion="[관망] 확인된 결론",
            coverage_status="normal",
            coverage_label="정상",
        ),
    )

    document = _seal_document(validated)

    assert document.briefing.rendered_markdown == repaired.layout.markdown
    assert document.markdown_sha256 == sha256(repaired.layout.markdown.encode("utf-8")).hexdigest()
    assert document.block_outcomes == repaired.block_outcomes
    assert "example.invalid" not in document.briefing.rendered_markdown
    assert "link_shape" not in repr(document.block_outcomes)


@pytest.mark.parametrize("case_index", (0, 1, 2))
def test_step3_owned_first_viewport_closed_links_use_target_specific_repair(
    case_index: int,
) -> None:
    case = _fixture()["synthetic_markdown"][case_index]
    projected, context = _projected_draft(
        _canonical_markdown(case["markdown"], block="first_viewport")
    )

    repaired = _repair_projected_draft(projected, context)

    assert "example.invalid" not in repaired.layout.markdown
    assert not any(
        issue.code == case["expected_issue_code"]
        for issue in find_surface_quality_issues(repaired.layout.markdown)
    )


@pytest.mark.parametrize("case_index", (3, 5))
def test_step3_unrecoverable_first_viewport_link_shape_replaces_only_its_owner(
    case_index: int,
) -> None:
    case = _fixture()["synthetic_markdown"][case_index]
    projected, context = _projected_draft(
        _canonical_markdown(case["markdown"], block="first_viewport")
    )

    repaired = _repair_projected_draft(projected, context)

    assert case["markdown"] not in repaired.layout.markdown
    assert _REGION_SAFE_FALLBACK_TEXT["first_viewport"] in repaired.layout.markdown
    assert "## ① 요약\n\n요약 본문" in repaired.layout.markdown
    outcome = next(
        outcome for outcome in repaired.block_outcomes if outcome.block == "first_viewport"
    )
    assert outcome.disposition == "replaced"


def test_step3_incomplete_inline_uses_owned_target_specific_repair() -> None:
    case = _fixture()["synthetic_markdown"][4]
    projected, context = _projected_draft(
        _canonical_markdown(case["markdown"], block="first_viewport")
    )

    repaired = _repair_projected_draft(projected, context)

    assert "example.invalid" not in repaired.layout.markdown
    assert case["visible_text"] in repaired.layout.markdown
    assert not any(
        issue.code == case["expected_issue_code"]
        for issue in find_surface_quality_issues(repaired.layout.markdown)
    )


@pytest.mark.parametrize("case_index", range(6))
def test_step3_watchpoint_link_shapes_replace_the_body_and_preserve_the_heading(
    case_index: int,
) -> None:
    case = _fixture()["synthetic_markdown"][case_index]
    projected, context = _projected_draft(
        _canonical_markdown(case["markdown"], block="watchpoints")
    )

    repaired = _repair_projected_draft(projected, context)

    assert repaired.layout.markdown.count("## ⑥ 오늘의 관전 포인트") == 1
    assert case["markdown"] not in repaired.layout.markdown
    assert _REGION_SAFE_FALLBACK_TEXT["watchpoints"] in repaired.layout.markdown
    outcome = next(
        outcome for outcome in repaired.block_outcomes if outcome.region_id == "watchpoints:section"
    )
    assert outcome.disposition == "replaced"


def test_step2_unmatched_residual_is_not_broadly_repaired() -> None:
    case = _fixture()["synthetic_markdown"][5]

    assert repair_surface_artifacts(case["markdown"]) == case["markdown"]
    assert repair_surface_link_targets(case["markdown"]) == case["markdown"]
    issues = find_surface_quality_issues(case["markdown"])
    assert [issue.link_shape for issue in issues if issue.code == "markdown.unmatched_link"] == [
        "unmatched_residual"
    ]
