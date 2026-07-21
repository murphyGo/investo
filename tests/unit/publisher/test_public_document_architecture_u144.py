"""U144 Step 1 construction and pre-production-use architecture guards."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from investo.publisher.public_document import PublicDocumentDraft
from investo.publisher.writer import write_finalized_document

_SRC = Path(__file__).parents[3] / "src" / "investo"
_PUBLIC_DOCUMENT = Path("publisher/public_document.py")
_WATCHPOINT_MODULE = Path("publisher/watchpoint_matrix.py")
_CANONICAL_SYMBOLS = {
    "investo.models.Briefing": "Briefing",
    "investo.models.briefing.Briefing": "Briefing",
    "investo.publisher.FinalizedPublicDocument": "FinalizedPublicDocument",
    "investo.publisher.write_finalized_document": "write_finalized_document",
    "investo.publisher.public_document.FinalizedPublicDocument": "FinalizedPublicDocument",
    "investo.publisher.public_document.PublicDocumentDraft": "PublicDocumentDraft",
    "investo.publisher.public_document._seal_document": "_seal_document",
    "investo.publisher.writer.write_finalized_document": "write_finalized_document",
    "investo.publisher.watchpoint_matrix.render_watchpoint_matrix": ("render_watchpoint_matrix"),
    "investo.publisher.watchpoint_matrix.render_watchpoint_matrix_result": (
        "render_watchpoint_matrix_result"
    ),
}
_CANONICAL_MODULES = {
    "investo.models",
    "investo.models.briefing",
    "investo.publisher",
    "investo.publisher.public_document",
    "investo.publisher.writer",
    "investo.publisher.watchpoint_matrix",
}
_PUBLIC_DOCUMENT_LOCALS = {
    "FinalizedPublicDocument": "FinalizedPublicDocument",
    "PublicDocumentDraft": "PublicDocumentDraft",
    "_seal_document": "_seal_document",
}
_WATCHPOINT_LOCALS = {
    "render_watchpoint_matrix": "render_watchpoint_matrix",
    "render_watchpoint_matrix_result": "render_watchpoint_matrix_result",
}


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _call_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


class _ConstructionVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: Path) -> None:
        self.relative_path = relative_path
        self.scope: list[str] = []
        self.symbol_aliases: dict[str, str] = {}
        self.module_aliases: dict[str, str] = {}
        self.constructor_calls: list[tuple[Path, str, str]] = []
        self.seal_calls: list[tuple[Path, str]] = []
        self.finalized_writer_calls: list[tuple[Path, str]] = []
        self.rendered_markdown_writes: list[tuple[Path, str, str]] = []
        self.watchpoint_legacy_calls: list[tuple[Path, str]] = []
        self.watchpoint_result_calls: list[tuple[Path, str]] = []

    @property
    def function_name(self) -> str:
        return self.scope[-1] if self.scope else "<module>"

    def _canonical_symbol(self, node: ast.expr) -> str | None:
        raw_name = _call_name(node)
        if raw_name is None:
            return None
        if raw_name in self.symbol_aliases:
            return self.symbol_aliases[raw_name]
        head, separator, tail = raw_name.partition(".")
        if separator and head in self.module_aliases:
            return _CANONICAL_SYMBOLS.get(f"{self.module_aliases[head]}.{tail}")
        if self.relative_path == _PUBLIC_DOCUMENT:
            return _PUBLIC_DOCUMENT_LOCALS.get(raw_name)
        if self.relative_path == _WATCHPOINT_MODULE:
            return _WATCHPOINT_LOCALS.get(raw_name)
        return _CANONICAL_SYMBOLS.get(raw_name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname is not None:
                self.module_aliases[alias.asname] = alias.name
        self.generic_visit(node)

    def _absolute_import_module(self, node: ast.ImportFrom) -> str | None:
        if node.level == 0:
            return node.module
        package_parts = ["investo", *self.relative_path.parent.parts]
        ascend = node.level - 1
        if ascend >= len(package_parts):
            return None
        absolute_parts = package_parts[: len(package_parts) - ascend]
        if node.module:
            absolute_parts.extend(node.module.split("."))
        return ".".join(absolute_parts)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        absolute_module = self._absolute_import_module(node)
        if absolute_module is not None:
            for alias in node.names:
                absolute_target = f"{absolute_module}.{alias.name}"
                local_name = alias.asname or alias.name
                canonical = _CANONICAL_SYMBOLS.get(absolute_target)
                if canonical is not None:
                    self.symbol_aliases[local_name] = canonical
                elif absolute_target in _CANONICAL_MODULES:
                    self.module_aliases[local_name] = absolute_target
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        call_symbol = self._canonical_symbol(node.func)
        if call_symbol == "Briefing" and any(
            keyword.arg == "rendered_markdown" for keyword in node.keywords
        ):
            self.rendered_markdown_writes.append(
                (self.relative_path, self.function_name, "construction")
            )
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "model_copy"
            and any(
                keyword.arg == "update" and _updates_rendered_markdown(keyword.value)
                for keyword in node.keywords
            )
        ):
            self.rendered_markdown_writes.append(
                (self.relative_path, self.function_name, "model_copy")
            )
        if call_symbol in {"FinalizedPublicDocument", "PublicDocumentDraft"}:
            self.constructor_calls.append((self.relative_path, self.function_name, call_symbol))
        if _call_name(node.func) == "object.__new__" and node.args:
            constructed = self._canonical_symbol(node.args[0])
            if constructed in {"FinalizedPublicDocument", "PublicDocumentDraft"}:
                self.constructor_calls.append((self.relative_path, self.function_name, constructed))
        if call_symbol == "_seal_document":
            self.seal_calls.append((self.relative_path, self.function_name))
        if call_symbol == "write_finalized_document":
            self.finalized_writer_calls.append((self.relative_path, self.function_name))
        if call_symbol == "render_watchpoint_matrix":
            self.watchpoint_legacy_calls.append((self.relative_path, self.function_name))
        if call_symbol == "render_watchpoint_matrix_result":
            self.watchpoint_result_calls.append((self.relative_path, self.function_name))
        self.generic_visit(node)


def _production_construction_snapshot() -> _ConstructionVisitor:
    aggregate = _ConstructionVisitor(Path("<aggregate>"))
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC)
        visitor = _ConstructionVisitor(relative)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        aggregate.constructor_calls.extend(visitor.constructor_calls)
        aggregate.seal_calls.extend(visitor.seal_calls)
        aggregate.finalized_writer_calls.extend(visitor.finalized_writer_calls)
        aggregate.rendered_markdown_writes.extend(visitor.rendered_markdown_writes)
        aggregate.watchpoint_legacy_calls.extend(visitor.watchpoint_legacy_calls)
        aggregate.watchpoint_result_calls.extend(visitor.watchpoint_result_calls)
    return aggregate


def _visit_source(
    source: str,
    *,
    relative_path: Path = Path("synthetic.py"),
) -> _ConstructionVisitor:
    visitor = _ConstructionVisitor(relative_path)
    visitor.visit(ast.parse(source))
    return visitor


def _updates_rendered_markdown(node: ast.expr) -> bool:
    """Recognize the bounded direct-update spellings covered by AC-144.4."""

    if isinstance(node, ast.Dict):
        return any(
            isinstance(key, ast.Constant) and key.value == "rendered_markdown" for key in node.keys
        )
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "dict"
        and any(keyword.arg == "rendered_markdown" for keyword in node.keywords)
    )


def test_draft_and_final_document_construction_is_single_owned() -> None:
    snapshot = _production_construction_snapshot()

    assert snapshot.constructor_calls == [
        (_PUBLIC_DOCUMENT, "_construct_draft", "PublicDocumentDraft"),
        (_PUBLIC_DOCUMENT, "_seal_document", "FinalizedPublicDocument"),
    ]
    assert snapshot.seal_calls == [
        (_PUBLIC_DOCUMENT, "_finalize_segment_skeleton"),
    ]


def test_sealed_writer_has_no_production_call_before_step_five_switch() -> None:
    snapshot = _production_construction_snapshot()

    assert snapshot.finalized_writer_calls == []


def test_rendered_markdown_construction_and_mutation_sites_are_allowlisted() -> None:
    snapshot = _production_construction_snapshot()

    assert snapshot.rendered_markdown_writes == [
        (Path("briefing/pipeline.py"), "_finalize_briefing", "construction"),
        (
            _PUBLIC_DOCUMENT,
            "_assemble_phase_one_presentation_briefing",
            "model_copy",
        ),
        (_PUBLIC_DOCUMENT, "_assemble_phase_one_body_evidence", "model_copy"),
        (_PUBLIC_DOCUMENT, "_apply_pre_finalization_supplements", "model_copy"),
        (_PUBLIC_DOCUMENT, "_seal_document", "model_copy"),
        (
            Path("publisher/segment_reader_format.py"),
            "apply_reader_format_to_segments",
            "model_copy",
        ),
        (
            Path("visuals/assets.py"),
            "prepare_segment_visual_assets",
            "model_copy",
        ),
    ]
    assert [
        write for write in snapshot.rendered_markdown_writes if write[1] == "_seal_document"
    ] == [(_PUBLIC_DOCUMENT, "_seal_document", "model_copy")]


def test_rendered_markdown_guard_covers_direct_update_spellings() -> None:
    snapshot = _visit_source(
        '''
"""briefing.model_copy(update={"rendered_markdown": ignored})"""

from investo.models import Briefing

Briefing(rendered_markdown=markdown)
briefing.model_copy(update={"rendered_markdown": markdown})
briefing.model_copy(update=dict(rendered_markdown=markdown))
briefing.model_copy(update={"market_summary": summary})
'''
    )

    assert snapshot.rendered_markdown_writes == [
        (Path("synthetic.py"), "<module>", "construction"),
        (Path("synthetic.py"), "<module>", "model_copy"),
        (Path("synthetic.py"), "<module>", "model_copy"),
    ]


def test_default_segmented_path_uses_typed_watchpoint_renderer_only() -> None:
    snapshot = _production_construction_snapshot()

    assert snapshot.watchpoint_legacy_calls == []
    assert snapshot.watchpoint_result_calls == [
        (
            Path("publisher/segment_reader_format.py"),
            "apply_reader_format_to_segments",
        ),
        (_WATCHPOINT_MODULE, "render_watchpoint_matrix"),
    ]


def test_watchpoint_renderer_guard_resolves_direct_and_module_aliases() -> None:
    direct = _visit_source(
        """
from investo.publisher.watchpoint_matrix import (
    render_watchpoint_matrix as legacy,
    render_watchpoint_matrix_result as typed,
)

legacy(markdown)
typed(markdown)
"""
    )
    module = _visit_source(
        """
import investo.publisher.watchpoint_matrix as watchpoints

watchpoints.render_watchpoint_matrix(markdown)
watchpoints.render_watchpoint_matrix_result(markdown)
"""
    )

    assert direct.watchpoint_legacy_calls == [(Path("synthetic.py"), "<module>")]
    assert direct.watchpoint_result_calls == [(Path("synthetic.py"), "<module>")]
    assert module.watchpoint_legacy_calls == [(Path("synthetic.py"), "<module>")]
    assert module.watchpoint_result_calls == [(Path("synthetic.py"), "<module>")]


def test_sealed_writer_rejects_publisher_private_draft() -> None:
    draft = object.__new__(PublicDocumentDraft)

    with pytest.raises(TypeError, match="requires FinalizedPublicDocument"):
        write_finalized_document(draft)  # type: ignore[arg-type]


def test_architecture_guard_resolves_direct_import_aliases() -> None:
    snapshot = _visit_source(
        """
from investo.publisher.public_document import (
    FinalizedPublicDocument as FinalDoc,
    _seal_document as seal,
)

FinalDoc()
seal(value)
"""
    )

    assert snapshot.constructor_calls == [
        (Path("synthetic.py"), "<module>", "FinalizedPublicDocument")
    ]
    assert snapshot.seal_calls == [(Path("synthetic.py"), "<module>")]


def test_architecture_guard_resolves_module_aliases() -> None:
    snapshot = _visit_source(
        """
import investo.publisher.public_document as pd
import investo.publisher.writer as sealed_writer

object.__new__(pd.PublicDocumentDraft)
pd._seal_document(value)
sealed_writer.write_finalized_document(value)
"""
    )

    assert snapshot.constructor_calls == [(Path("synthetic.py"), "<module>", "PublicDocumentDraft")]
    assert snapshot.seal_calls == [(Path("synthetic.py"), "<module>")]
    assert snapshot.finalized_writer_calls == [(Path("synthetic.py"), "<module>")]


def test_architecture_guard_resolves_import_from_module_aliases() -> None:
    snapshot = _visit_source(
        """
from investo.publisher import public_document as pd
from investo.publisher import writer as sealed_writer

object.__new__(pd.FinalizedPublicDocument)
pd._seal_document(value)
sealed_writer.write_finalized_document(value)
"""
    )

    assert snapshot.constructor_calls == [
        (Path("synthetic.py"), "<module>", "FinalizedPublicDocument")
    ]
    assert snapshot.seal_calls == [(Path("synthetic.py"), "<module>")]
    assert snapshot.finalized_writer_calls == [(Path("synthetic.py"), "<module>")]


def test_architecture_guard_resolves_publisher_relative_imports() -> None:
    relative_path = Path("publisher/synthetic.py")
    snapshot = _visit_source(
        """
from .public_document import _seal_document as seal
from .writer import write_finalized_document as sealed_write

seal(value)
sealed_write(value)
""",
        relative_path=relative_path,
    )

    assert snapshot.seal_calls == [(relative_path, "<module>")]
    assert snapshot.finalized_writer_calls == [(relative_path, "<module>")]


def test_architecture_guard_ignores_unrelated_local_same_name_symbols() -> None:
    snapshot = _visit_source(
        """
class PublicDocumentDraft:
    pass

def _seal_document(value):
    return value

PublicDocumentDraft()
_seal_document(value)
"""
    )

    assert snapshot.constructor_calls == []
    assert snapshot.seal_calls == []
