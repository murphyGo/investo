#!/usr/bin/env python3
"""Replay curated semantic selection over the fixed U-147 archive corpus."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from investo.visuals.curated import (  # noqa: E402
    LIBRARY_ROOT,
    default_registry,
    load_library,
    select_curated_asset,
)
from investo.visuals.image_selection import build_image_narrative_context  # noqa: E402

_DATES = (
    "2026-07-17",
    "2026-07-18",
    "2026-07-21",
    "2026-07-22",
    "2026-07-23",
    "2026-07-24",
    "2026-07-27",
    "2026-07-28",
    "2026-07-29",
    "2026-07-30",
    "2026-07-31",
)
_SEGMENTS = ("domestic-equity", "us-equity", "crypto")
_MIN_UNIQUE_ASSETS = 5
_MAX_ASSET_SHARE = 0.35
_MAX_TOP4_SHARE = 0.97


def audit(*, repo_root: Path, fit_fixture: Path | None = None) -> dict[str, object]:
    """Return deterministic replay rows plus concentration metrics."""

    library = load_library(repo_root / LIBRARY_ROOT)
    registry = default_registry()
    rows: list[dict[str, object]] = []
    asset_counts: Counter[str] = Counter()
    key_counts: Counter[str] = Counter()
    missing_paths: list[str] = []
    for target in _DATES:
        year, month, _day = target.split("-")
        for segment in _SEGMENTS:
            path = repo_root / "archive" / segment / year / month / f"{target}.md"
            if not path.is_file():
                missing_paths.append(path.relative_to(repo_root).as_posix())
                continue
            context = build_image_narrative_context(
                segment,  # type: ignore[arg-type]
                path.read_text(encoding="utf-8"),
            )
            selection = select_curated_asset(
                segment,  # type: ignore[arg-type]
                context,
                library,
                registry,
            )
            asset_id = selection.asset.asset_id if selection.asset is not None else None
            if asset_id is not None:
                asset_counts[asset_id] += 1
            if selection.matched_key is not None:
                key_counts[selection.matched_key] += 1
            rows.append(
                {
                    "asset_id": asset_id,
                    "date": target,
                    "matched_key": selection.matched_key,
                    "semantic_offset": selection.semantic_offset,
                    "semantic_rank": selection.semantic_rank,
                    "segment": segment,
                    "variant_count": selection.variant_count,
                    "variant_index": selection.variant_index,
                }
            )

    fit_path = fit_fixture or repo_root / "tests" / "fixtures" / "u147" / "semantic-fit.json"
    expected_payload = json.loads(fit_path.read_text(encoding="utf-8"))
    expected_rows = expected_payload.get("rows", [])
    expected_by_scope = {
        (expected["date"], expected["segment"]): expected for expected in expected_rows
    }
    actual_by_scope = {(row["date"], row["segment"]): row for row in rows}
    fit_mismatches: list[str] = []
    if set(expected_by_scope) != set(actual_by_scope):
        fit_mismatches.append("fixture scope does not exactly match replay scope")
    for scope, expected in sorted(expected_by_scope.items()):
        actual = actual_by_scope.get(scope)
        if actual is None:
            continue
        matched_key = actual["matched_key"]
        allowed_keys = expected.get("allowed_keys", [])
        abstain = expected.get("abstain") is True
        if (abstain and matched_key is not None) or (
            not abstain and matched_key not in allowed_keys
        ):
            fit_mismatches.append(
                f"{scope[0]} {scope[1]}: expected {allowed_keys or ['abstain']}, got {matched_key}"
            )

    selected = sum(asset_counts.values())
    sorted_counts = sorted(asset_counts.values(), reverse=True)
    max_asset_share = max(sorted_counts) / selected if selected else 0.0
    top4_asset_share = sum(sorted_counts[:4]) / selected if selected else 0.0
    person_selections = sum(
        1
        for row in rows
        if isinstance(row["matched_key"], str) and row["matched_key"].startswith("person:")
    )
    passes_gate = (
        not missing_paths
        and not fit_mismatches
        and len(rows) == len(_DATES) * len(_SEGMENTS)
        and selected == 32
        and person_selections == 0
        and len(asset_counts) >= _MIN_UNIQUE_ASSETS
        and max_asset_share <= _MAX_ASSET_SHARE
        and top4_asset_share <= _MAX_TOP4_SHARE
    )
    return {
        "contract": "u147-fixed-11-date-33-segment-v1",
        "summary": {
            "asset_counts": dict(sorted(asset_counts.items())),
            "expected_rows": len(_DATES) * len(_SEGMENTS),
            "key_counts": dict(sorted(key_counts.items())),
            "fit_mismatches": fit_mismatches,
            "fit_rows": len(expected_by_scope),
            "max_asset_share": max_asset_share,
            "missing_paths": missing_paths,
            "passes_gate": passes_gate,
            "person_selections": person_selections,
            "rows": len(rows),
            "selected": selected,
            "top4_asset_share": top4_asset_share,
            "unique_assets": len(asset_counts),
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--fit-fixture", type=Path)
    args = parser.parse_args()
    report = audit(
        repo_root=args.repo_root.resolve(),
        fit_fixture=args.fit_fixture.resolve() if args.fit_fixture else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    summary = report["summary"]
    assert isinstance(summary, dict)
    return 0 if summary["passes_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
