"""Enforced module-boundary test (u78, Wave 14).

CLAUDE.md "Critical Project Rules" #3: the adapter packages
(``sources`` / ``briefing`` / ``publisher`` / ``notifier`` / ``visuals``)
may share only ``models/`` and ``_internal/``. u78 homed ``ArchiveLayout``
and the atomic-write helpers in ``_internal/`` specifically to **dissolve
the former ``visuals → publisher`` sibling edge**, so this test pins that
the edge stays gone (regression guard, not convention).

Scope note (honest about the codebase reality): a *full* "zero sibling
adapter→adapter edges" invariant is not yet achievable — ``publisher``,
``notifier``, ``sources`` and ``visuals`` all statically import
``briefing`` (shared domain vocabulary: ``segments`` / ``market_anchor`` /
``extract`` / ``watchlist``). Collapsing those is out of u78's scope and
is tracked as deferred Wave-14 TECH-DEBT. What u78 *does* guarantee, and
what this test enforces, is that the ``publisher`` ⇄ ``visuals`` pair has
**zero top-level import edges in either direction** — the pair u78 owns.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ADAPTERS = frozenset({"sources", "briefing", "publisher", "notifier", "visuals"})
_SRC = Path(__file__).resolve().parents[3] / "src" / "investo"


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
