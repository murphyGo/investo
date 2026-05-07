"""DEBT-060 chokepoint regression — every surface routes through one helper.

The five rendered-markdown anchor consumers
(``publisher.site_index``, ``publisher.weekly_digest``,
``visuals.og_card``, ``visuals.assets``, ``briefing.context``) used to
duplicate the conclusion / driver / watermark prefix matching logic.
This test pins that they now all route through the
:mod:`investo.briefing.extract` chokepoint so a future change to the
prefix shape lands in exactly one place.

Three shape pins:

1. **Direct helper contract** — ``extract_conclusion`` / ``extract_key_drivers`` /
   ``extract_caution`` / ``extract_watermark`` agree on present / missing /
   empty / multiple-line shapes.
2. **Prefix constants exported from summary_quality** — five-surface
   chokepoint that prevents future drift.
3. **No surface re-declares the literal** — grep guard that catches
   regressions where a new feature adds a sixth duplicate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from investo.briefing.extract import (
    extract_caution,
    extract_conclusion,
    extract_key_drivers,
    extract_watermark,
)
from investo.briefing.summary_quality import (
    CAUTION_PREFIX,
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    WATERMARK_PREFIX,
)


def _briefing(*lines: str) -> str:
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize(
    "extractor,prefix,expected",
    [
        (extract_conclusion, CONCLUSION_PREFIX, "오늘은 상승 마감"),
        (extract_key_drivers, DRIVER_PREFIX, "AI 투자 사이클"),
        (extract_caution, CAUTION_PREFIX, "FOMC 경계감"),
        (
            extract_watermark,
            WATERMARK_PREFIX,
            "2026-05-08 KST · [2026-05-07T15:00Z, 2026-05-08T15:00Z)",
        ),
    ],
)
def test_extract_returns_value_when_present(
    extractor: object,
    prefix: str,
    expected: str,
) -> None:
    markdown = _briefing(
        "# 제목",
        "",
        f"{prefix} {expected}",
        "",
        "## 본문",
    )
    assert extractor(markdown) == expected  # type: ignore[operator]


@pytest.mark.parametrize(
    "extractor",
    [extract_conclusion, extract_key_drivers, extract_caution, extract_watermark],
)
def test_extract_returns_none_when_missing(extractor: object) -> None:
    markdown = "# 제목\n\n본문에 anchor 가 없음.\n"
    assert extractor(markdown) is None  # type: ignore[operator]


@pytest.mark.parametrize(
    "extractor,prefix",
    [
        (extract_conclusion, CONCLUSION_PREFIX),
        (extract_key_drivers, DRIVER_PREFIX),
        (extract_caution, CAUTION_PREFIX),
        (extract_watermark, WATERMARK_PREFIX),
    ],
)
def test_extract_returns_none_when_value_is_blank(
    extractor: object,
    prefix: str,
) -> None:
    """A prefix line with empty / whitespace-only value yields None."""
    markdown = _briefing(f"{prefix}   ")
    assert extractor(markdown) is None  # type: ignore[operator]


@pytest.mark.parametrize(
    "extractor,prefix",
    [
        (extract_conclusion, CONCLUSION_PREFIX),
        (extract_key_drivers, DRIVER_PREFIX),
        (extract_caution, CAUTION_PREFIX),
        (extract_watermark, WATERMARK_PREFIX),
    ],
)
def test_extract_returns_first_match_when_duplicated(
    extractor: object,
    prefix: str,
) -> None:
    """First-match-wins. Defensive against malformed archive duplicates."""
    markdown = _briefing(f"{prefix} 첫 번째", f"{prefix} 두 번째")
    assert extractor(markdown) == "첫 번째"  # type: ignore[operator]


def test_summary_quality_exports_canonical_prefixes() -> None:
    """The five DEBT-060 surfaces all import these literals from one place."""
    assert CONCLUSION_PREFIX == "> **오늘의 결론**:"
    assert DRIVER_PREFIX == "> **핵심 동인**:"
    assert CAUTION_PREFIX == "> **주의할 점**:"
    assert WATERMARK_PREFIX == "**기준 시각**:"


def test_no_surface_redeclares_prefix_literal() -> None:
    """Grep guard: only summary_quality / extract / pipeline carry the literal.

    Five surfaces (publisher/site_index, publisher/weekly_digest,
    visuals/og_card, visuals/assets, briefing/context) used to declare
    ``"> **오늘의 결론**:"`` locally. After the DEBT-060 consolidation
    they import :data:`CONCLUSION_PREFIX` from summary_quality. This
    test fails the moment a sixth consumer inlines the literal again
    instead of importing the constant.

    Allowed sites:

    * ``briefing/summary_quality.py`` — canonical declaration,
    * ``briefing/pipeline.py`` — the canonical *emitter*
      (``_enhance_reader_experience`` writes the line),
    * ``briefing/extract.py`` — docstring references only.
    """
    src_root = Path(__file__).resolve().parents[3] / "src" / "investo"
    allowed = {
        src_root / "briefing" / "summary_quality.py",
        src_root / "briefing" / "pipeline.py",
        src_root / "briefing" / "extract.py",
    }
    offenders: list[str] = []
    for path in src_root.rglob("*.py"):
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        # Look for the literal that pins the conclusion prefix shape.
        # Whitespace + emoji-free Korean is unique enough that a stray
        # match in a docstring example is OK if it's not in a string
        # literal context — but the safe rule is "do not let any new
        # site grow the literal".
        if '"> **오늘의 결론**:"' in text or "'> **오늘의 결론**:'" in text:
            offenders.append(str(path.relative_to(src_root)))
    assert not offenders, (
        "DEBT-060 regression: a non-allowed site re-declared the conclusion "
        "prefix literal. Import CONCLUSION_PREFIX from "
        "investo.briefing.summary_quality instead. "
        f"offenders={offenders}"
    )
