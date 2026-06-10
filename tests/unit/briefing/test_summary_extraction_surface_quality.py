"""u100 summary extraction surface-quality regressions."""

from __future__ import annotations

from investo.briefing._assembly.summary_extraction import (
    _is_unsafe_summary_candidate,
    _summary_sentence,
)


def test_summary_candidate_rejects_surface_quality_blocker() -> None:
    assert _is_unsafe_summary_candidate("[broken link](https://example.com")
    assert _is_unsafe_summary_candidate("stage1_hash=abc")


def test_summary_sentence_skips_broken_artifact_candidate() -> None:
    text = "[broken link](https://example.com\n정상 문장입니다."

    assert _summary_sentence(text, fallback="fallback") == "정상 문장입니다."
