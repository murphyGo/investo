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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_ADAPTERS = frozenset({"sources", "briefing", "publisher", "notifier", "visuals"})
_SRC = Path(__file__).resolve().parents[3] / "src" / "investo"
_EDGE_KEY = tuple[str, str, str, str]
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


@dataclass(frozen=True, slots=True, order=True)
class AdapterEdge:
    source_package: str
    target_package: str
    relative_file: str
    module: str

    @property
    def key(self) -> _EDGE_KEY:
        return (
            self.source_package,
            self.target_package,
            self.relative_file,
            self.module,
        )


_ALLOWED_ADAPTER_EDGES: Mapping[_EDGE_KEY, str] = {
    (
        "publisher",
        "briefing",
        "publisher/briefing_replay.py",
        "investo.briefing.summary_quality",
    ): "offline replay reuses the briefing summary-quality validator",
    (
        "publisher",
        "briefing",
        "publisher/crypto_indicators.py",
        "investo.briefing.crypto_indicators",
    ): "publisher injection reuses the canonical crypto indicator renderer",
    (
        "publisher",
        "briefing",
        "publisher/verifier.py",
        "investo.briefing.disclaimer",
    ): "publish-boundary disclaimer verification reads the canonical disclaimer",
    (
        "publisher",
        "briefing",
        "publisher/weekly_digest.py",
        "investo.briefing.disclaimer",
    ): "weekly digest reattaches the canonical disclaimer to retrospective pages",
    (
        "visuals",
        "briefing",
        "visuals/quality_sparkline.py",
        "investo.briefing.quality_eval",
    ): "quality sparkline consumes the established quality-history row contract",
}


def _top_level_import_modules(node: ast.stmt, relative_file: str) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return _import_from_modules(node, relative_file)
    return []


def _import_from_modules(node: ast.ImportFrom, relative_file: str) -> list[str]:
    if node.level == 0:
        if node.module == "investo":
            return [f"investo.{alias.name}" for alias in node.names]
        return [node.module] if node.module else []

    package_parts = list(Path(relative_file).with_suffix("").parent.parts)
    base_len = len(package_parts) - (node.level - 1)
    if base_len < 0:
        return []

    base_parts = package_parts[:base_len]
    if node.module:
        return [_canonical_investo_module(base_parts + node.module.split("."))]
    return [_canonical_investo_module([*base_parts, alias.name]) for alias in node.names]


def _canonical_investo_module(parts: list[str]) -> str:
    return "investo" if not parts else "investo." + ".".join(parts)


def _module_adapter(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "investo" or parts[1] not in _ADAPTERS:
        return None
    return parts[1]


def _module_level_adapter_edges(src_root: Path = _SRC) -> set[AdapterEdge]:
    """Return all module-level cross-adapter imports in the source tree."""
    edges: set[AdapterEdge] = set()
    for package in sorted(_ADAPTERS):
        package_root = src_root / package
        if not package_root.exists():
            continue
        for path in package_root.rglob("*.py"):
            relative_file = path.relative_to(src_root).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:  # module-level statements only
                for module in _top_level_import_modules(node, relative_file):
                    target_package = _module_adapter(module)
                    if target_package and target_package != package:
                        edges.add(
                            AdapterEdge(
                                source_package=package,
                                target_package=target_package,
                                relative_file=relative_file,
                                module=module,
                            )
                        )
    return edges


def _unallowed_adapter_edges(
    src_root: Path = _SRC,
    *,
    allowlist: Mapping[_EDGE_KEY, str] = _ALLOWED_ADAPTER_EDGES,
) -> list[AdapterEdge]:
    return sorted(
        edge for edge in _module_level_adapter_edges(src_root) if edge.key not in allowlist
    )


def _top_level_adapter_edges(package: str) -> dict[str, set[str]]:
    """Return {target_adapter: {file, ...}} for module-level imports of a
    *different* adapter package found in ``package``."""
    edges: dict[str, set[str]] = {}
    for edge in _module_level_adapter_edges():
        if edge.source_package != package:
            continue
        edges.setdefault(edge.target_package, set()).add(Path(edge.relative_file).name)
    return edges


def _write_module(src_root: Path, relative: str, text: str) -> None:
    path = src_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _format_edges(edges: list[AdapterEdge]) -> list[str]:
    return [
        (
            f"{edge.source_package} -> {edge.target_package}: "
            f"{edge.relative_file} imports {edge.module}"
        )
        for edge in edges
    ]


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


def test_all_top_level_adapter_sibling_imports_are_allowlisted() -> None:
    """Any new module-level import from one adapter package to another must
    declare its file/module/reason in ``_ALLOWED_ADAPTER_EDGES``."""
    unallowed = _unallowed_adapter_edges()
    assert not unallowed, _format_edges(unallowed)


def test_allowed_adapter_edges_have_reasons_and_match_current_tree() -> None:
    edges = {edge.key for edge in _module_level_adapter_edges()}

    assert set(_ALLOWED_ADAPTER_EDGES) == edges
    for reason in _ALLOWED_ADAPTER_EDGES.values():
        assert reason.strip()


def test_unallowed_adapter_edge_is_reported(tmp_path: Path) -> None:
    src_root = tmp_path / "investo"
    _write_module(
        src_root,
        "publisher/leak.py",
        "from investo.sources.aggregator import collect_sources\n",
    )

    assert _unallowed_adapter_edges(src_root) == [
        AdapterEdge(
            source_package="publisher",
            target_package="sources",
            relative_file="publisher/leak.py",
            module="investo.sources.aggregator",
        )
    ]


def test_unallowed_adapter_edge_via_investo_alias_import_is_reported(tmp_path: Path) -> None:
    src_root = tmp_path / "investo"
    _write_module(
        src_root,
        "publisher/leak.py",
        "from investo import briefing\n",
    )

    assert _unallowed_adapter_edges(src_root) == [
        AdapterEdge(
            source_package="publisher",
            target_package="briefing",
            relative_file="publisher/leak.py",
            module="investo.briefing",
        )
    ]


def test_unallowed_adapter_edge_via_relative_sibling_import_is_reported(
    tmp_path: Path,
) -> None:
    src_root = tmp_path / "investo"
    _write_module(
        src_root,
        "publisher/leak.py",
        "from ..briefing import disclaimer\n",
    )

    assert _unallowed_adapter_edges(src_root) == [
        AdapterEdge(
            source_package="publisher",
            target_package="briefing",
            relative_file="publisher/leak.py",
            module="investo.briefing",
        )
    ]


def test_allowlisted_adapter_edge_is_not_reported(tmp_path: Path) -> None:
    src_root = tmp_path / "investo"
    _write_module(
        src_root,
        "visuals/quality_sparkline.py",
        "from investo.briefing.quality_eval import QualityHistoryRow\n",
    )

    assert _unallowed_adapter_edges(src_root) == []


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
