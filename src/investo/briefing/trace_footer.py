"""u32 Step 3 — traceability footer + hashed signatures.

Each segment's archived markdown gains a collapsed ``<details>`` footer
that expands to:

* three SHA-256 12-char prefixes, computed deterministically over the
  Stage 1 candidate JSON, the parsed ClassificationResult, and the
  Stage 2 body markdown — `input_hash` / `stage1_hash` / `stage2_hash`;
* a tabular Stage 1 classification snapshot listing every published
  item's source, category, section assignment, and a short title
  excerpt.

The footer is *signed*, not interactive — readers expand it to verify
"this briefing was built from these items, classified into these
sections, and hashed under this signature". A future tooling layer can
re-derive the hashes from the same input + parsed classification +
Stage 2 body and compare; mismatches indicate either silent edit of
the archive markdown or an LLM regeneration that wasn't fixture-
recorded.

Pure: no I/O. The footer is a function of (items, classification,
stage2_text) only, so the briefing pipeline can fold it into the
archive bytes deterministically.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any, Final

from investo.models import NormalizedItem

_HASH_PREFIX_LEN: Final[int] = 12


def _serialise_items_for_hash(items: Sequence[NormalizedItem]) -> str:
    """Render a deterministic JSON serialization of the input items."""
    return json.dumps(
        [
            {
                "source_name": item.source_name,
                "category": item.category,
                "title": item.title,
                "summary": item.summary,
                "published_at": item.published_at.isoformat(),
                "raw_metadata": dict(sorted(item.raw_metadata.items())),
            }
            for item in items
        ],
        ensure_ascii=False,
        sort_keys=True,
    )


def _sha256_prefix(payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()
    return digest[:_HASH_PREFIX_LEN]


def compute_input_hash(items: Sequence[NormalizedItem]) -> str:
    return _sha256_prefix(_serialise_items_for_hash(items))


def compute_stage1_hash(classification: dict[str, Any]) -> str:
    """Hash a Stage 1 classification snapshot.

    ``classification`` is a plain dict shaped like
    ``{"assignments": {item_id: section_id}, "unassigned": [...]}``.
    The pipeline passes the result of
    ``ClassificationResult.model_dump()`` so the hash matches whatever
    the LLM actually produced (post-validation), not the raw stdout.
    """
    payload = json.dumps(classification, ensure_ascii=False, sort_keys=True)
    return _sha256_prefix(payload)


def compute_stage2_hash(stage2_text: str) -> str:
    return _sha256_prefix(stage2_text)


def render_traceability_footer(
    items: Sequence[NormalizedItem],
    classification: dict[str, Any],
    stage2_text: str,
) -> str:
    """Render the ``<details>`` traceability footer markdown."""
    input_hash = compute_input_hash(items)
    stage1_hash = compute_stage1_hash(classification)
    stage2_hash = compute_stage2_hash(stage2_text)

    lines: list[str] = []
    lines.append("<details>")
    lines.append("<summary>📑 트레이스 + 서명 (Stage 1/2)</summary>")
    lines.append("")
    lines.append(f"- `input_hash`: `{input_hash}`")
    lines.append(f"- `stage1_hash`: `{stage1_hash}`")
    lines.append(f"- `stage2_hash`: `{stage2_hash}`")
    lines.append("")
    assignments = _normalise_assignments(classification.get("assignments", {}))
    lines.append("| 항목 ID | 소스 | 카테고리 | 섹션 | 제목 |")
    lines.append("|---------|------|----------|------|------|")
    for idx, item in enumerate(items):
        section_id = assignments.get(idx, "—")
        title_short = item.title.replace("|", " ").strip()
        if len(title_short) > 60:
            title_short = title_short[:57].rstrip() + "…"
        lines.append(
            f"| {idx} | {item.source_name} | {item.category} | {section_id} | {title_short} |"
        )
    lines.append("")
    lines.append("</details>")
    lines.append("")
    return "\n".join(lines)


def _normalise_assignments(raw: object) -> dict[int, int]:
    if not isinstance(raw, dict):
        return {}
    out: dict[int, int] = {}
    for key, value in raw.items():
        try:
            k = int(key)
            v = int(value)
        except (TypeError, ValueError):
            continue
        out[k] = v
    return out


__all__ = [
    "compute_input_hash",
    "compute_stage1_hash",
    "compute_stage2_hash",
    "render_traceability_footer",
]
