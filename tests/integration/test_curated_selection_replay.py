"""U-147 fixed archive replay for semantic fit and variant reachability."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "audit_curated_selection_diversity.py"


def _load_audit_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("curated_selection_audit", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixed_archive_replay_preserves_fit_and_avoids_narrow_asset_misuse() -> None:
    report = _load_audit_script().audit(repo_root=_REPO_ROOT)
    summary = report["summary"]
    assert isinstance(summary, dict)
    assert summary["rows"] == summary["expected_rows"] == 33
    assert summary["missing_paths"] == []
    assert summary["selected"] == 32
    assert summary["fit_rows"] == 33
    assert summary["fit_mismatches"] == []
    assert summary["person_selections"] == 0
    assert summary["passes_gate"] is True
    counts = summary["asset_counts"]
    assert isinstance(counts, dict)
    assert counts["bitcoin"] == 11
    assert "bitcoin-miner" not in counts
    assert "kospi-history" not in counts
    assert not any(asset_id.startswith(("jerome-", "kevin-")) for asset_id in counts)
