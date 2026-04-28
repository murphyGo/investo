"""Disclaimer constant + idempotent appender (NFR-004, FR-002 compliance).

Per FD R5 (`u2-briefing/functional-design/business-rules.md`), the
disclaimer text is fixed as a module-level constant. ``append_disclaimer``
is idempotent — anchored on the literal section header
``## ⑦ 면책조항``. The complementary check lives in u3 publisher:
``publisher.verify_disclaimer`` does an exact-substring match on the
full ``DISCLAIMER`` constant immediately before publish (NFR-004
defense-in-depth).

DEBT-001 tracks moving the substring guarantee one layer earlier into
the ``Briefing`` model itself; for now the boundary is enforced at u3.

Why anchor on the header (not the full body): FD R5 deliberately allows
the body wording to drift via future ADR while keeping the section
header as the canonical idempotence detect. The pathological case
(input already contains the anchor but with wrong body text — e.g. a
hallucinated LLM section ⑦) is caught by u3's stricter
``verify_disclaimer`` check, which blocks publish on drift.
"""

from __future__ import annotations

from typing import Final

# Exact text per FD R5. This MUST stay byte-identical with what u3's
# ``verify_disclaimer`` substring-checks. Any wording change is an
# audit-logged event (per NFR drift AC-D.4).
DISCLAIMER: Final[str] = (
    "## ⑦ 면책조항\n"
    "본 시황은 일반 정보 제공을 목적으로 자동 생성된 자료이며,\n"
    "특정 종목·자산에 대한 매매 권유나 투자 자문이 아닙니다.\n"
    "투자 결정과 그 결과에 대한 책임은 전적으로 본인에게 있으며,\n"
    "본 시황의 내용에 따라 발생한 손실에 대해 작성자는 일체의 책임을 지지 않습니다."
)

# The idempotence anchor. Body wording inside ``DISCLAIMER`` may drift
# via future ADR; this header is the canonical detect.
_ANCHOR: Final[str] = "## ⑦ 면책조항"


def append_disclaimer(markdown: str) -> str:
    """Append ``DISCLAIMER`` to ``markdown`` if not already present.

    Idempotence is anchored on the literal substring ``## ⑦ 면책조항``.
    When the anchor is present, the input is returned unchanged. When
    absent, ``\\n\\n`` plus the full ``DISCLAIMER`` block is appended.

    The two-newline separator guarantees the disclaimer header is
    rendered as a top-level markdown section even when the input ends
    without a trailing newline.

    The function is pure: same input → same output, no mutation, no
    timestamp, no per-call variation.
    """
    if _ANCHOR in markdown:
        return markdown
    return markdown + "\n\n" + DISCLAIMER


__all__ = ["DISCLAIMER", "append_disclaimer"]
