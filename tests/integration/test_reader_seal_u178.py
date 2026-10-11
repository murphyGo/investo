"""Real producer supplements survive terminal validation and seal unchanged."""

from hashlib import sha256
from pathlib import Path

from tests._helpers.reader_fixture_u178 import build_reader_fixture


def test_three_markets_keep_four_html_cards_and_their_surviving_artifacts(tmp_path: Path) -> None:
    bundle = build_reader_fixture(tmp_path, repeated_labels=True)
    assert len(bundle.documents) == 3
    for document in bundle.documents:
        text = document.briefing.rendered_markdown
        assert text.count('class="investo-data-card"') == 4
        assert text.count('class="investo-data-visual"') == 4
        assert text.count("<td>") == 12 * 7
        assert "<td>+1.01%</td>" in text
        assert (
            "<td>$100.00</td>" in text
            if document.segment == "crypto"
            else "<td>100.00</td>" in text
        )
        assert "<td>**" not in text
        assert text.count(" · 조회시점(UTC)</td>") == 12
        assert sha256(text.encode()).hexdigest() == document.markdown_sha256
        assert len(document.staged_artifact_ids) == 12
        assert len(set(document.staged_artifact_ids)) == 12


def test_ampersand_claim_from_actual_card_is_contained_before_terminal_seal(tmp_path: Path) -> None:
    bundle = build_reader_fixture(tmp_path, unsupported_html=True)
    assert {document.segment for document in bundle.documents} == {"domestic-equity", "crypto"}
    outcome = next(o for o in bundle.segment_outcomes if o.segment == "us-equity")
    assert outcome.state == "trust_blocked" and "numeric.anchor_assertion" in outcome.issue_codes
    for document in bundle.documents:
        text = document.briefing.rendered_markdown
        assert "10% 급락" not in text
        assert sha256(text.encode()).hexdigest() == document.markdown_sha256
