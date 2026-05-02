"""AST helpers shared by source-shape tests."""

from __future__ import annotations

import ast
import inspect
from types import ModuleType


def executable_source(module: ModuleType) -> str:
    """Return module source with docstrings and comments stripped."""
    source = inspect.getsource(module)
    tree = ast.parse(source)

    def strip_docstring(body: list[ast.stmt]) -> None:
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)

    strip_docstring(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            strip_docstring(node.body)

    return ast.unparse(tree)
