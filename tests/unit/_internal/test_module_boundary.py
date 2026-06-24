"""Enforced module-boundary test (u78, Wave 14).

CLAUDE.md "Critical Project Rules" #3: the adapter packages
(``sources`` / ``briefing`` / ``publisher`` / ``notifier`` / ``visuals``)
may share only ``models/`` and ``_internal/``. u78 homed ``ArchiveLayout``
and the atomic-write helpers in ``_internal/`` specifically to **dissolve
the former ``visuals → publisher`` sibling edge**, so this test pins that
the edge stays gone (regression guard, not convention).

u114 moved the shared briefing vocabulary into ``models`` / ``_internal``.
The remaining allowed ``briefing`` edges are behavior calls owned by the
briefing unit, not shared value objects.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ADAPTERS = frozenset({"sources", "briefing", "publisher", "notifier", "visuals"})
_SRC = Path(__file__).resolve().parents[3] / "src" / "investo"
_SHARED_BRIEFING_MODULES = frozenset(
    {
        "investo.briefing.extract",
        "investo.briefing.market_anchor",
        "investo.briefing.segments",
        "investo.briefing.time_state",
        "investo.briefing.watchlist",
        "investo.briefing.watchlist_impact",
    }
)


def _top_level_adapter_edges(package: str) -> dict[str, set[str]]:
    """Return {target_adapter: {file, ...}} for module-level imports of a
    *different* adapter package found in ``package``."""
    edges: dict[str, set[str]] = {}
    for path in (_SRC / package).rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:  # module-level statements only
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules = [node.module]
            for module in modules:
                parts = module.split(".")
                if (
                    len(parts) >= 2
                    and parts[0] == "investo"
                    and parts[1] in _ADAPTERS
                    and parts[1] != package
                ):
                    edges.setdefault(parts[1], set()).add(path.name)
    return edges


def _absolute_import_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
            if node.module == "investo.briefing":
                modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def test_visuals_has_no_top_level_publisher_import() -> None:
    """The ``visuals → publisher`` edge u78 dissolved must stay gone."""
    edges = _top_level_adapter_edges("visuals")
    assert "publisher" not in edges, (
        f"visuals must not import publisher at module level; found: "
        f"{sorted(edges.get('publisher', set()))}"
    )


def test_publisher_has_no_top_level_visuals_import() -> None:
    """The reverse pairing stays edge-free too (publisher's few visuals
    uses are lazy in-function imports, by design)."""
    edges = _top_level_adapter_edges("publisher")
    assert "visuals" not in edges, (
        f"publisher must not import visuals at module level; found: "
        f"{sorted(edges.get('visuals', set()))}"
    )


def test_publisher_visuals_pair_has_zero_sibling_edges() -> None:
    """Combined assertion: the publisher⇄visuals pair u78 owns has zero
    top-level sibling edges in either direction."""
    pub = _top_level_adapter_edges("publisher")
    vis = _top_level_adapter_edges("visuals")
    assert "visuals" not in pub
    assert "publisher" not in vis


def test_models_do_not_import_briefing_modules() -> None:
    """Foundation models must not depend on the briefing adapter package."""
    offenders: list[str] = []
    for path in sorted((_SRC / "models").rglob("*.py")):
        imports = _absolute_import_modules(path)
        has_briefing_import = any(
            module == "investo.briefing" or module.startswith("investo.briefing.")
            for module in imports
        )
        if has_briefing_import:
            offenders.append(str(path.relative_to(_SRC)))
    assert not offenders


def test_sibling_units_do_not_import_briefing_shared_vocabulary() -> None:
    """Shared vocabulary must flow from models/_internal, not briefing."""
    offenders: list[str] = []
    for package in ("publisher", "notifier", "visuals", "sources"):
        for path in sorted((_SRC / package).rglob("*.py")):
            imports = _absolute_import_modules(path)
            banned = sorted(imports & _SHARED_BRIEFING_MODULES)
            if banned:
                offenders.append(f"{path.relative_to(_SRC)} -> {', '.join(banned)}")
    assert not offenders
