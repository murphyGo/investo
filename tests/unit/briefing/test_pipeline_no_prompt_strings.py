"""AC-5.2 / AC-5.3 sentinel grep on the EXECUTABLE source of
``briefing.pipeline`` and ``briefing.claude_code``.

The sibling test ``test_prompts.py::test_prompt_sentinels_only_in_prompts``
already enforces the same boundary by reading raw file text — that
catches docstrings + comments. This test adds a complementary check
that strips docstrings + comments via AST and asserts the prompt body
sentinels never appear in EXECUTABLE code. The two tests overlap on
purpose: a regression that buries a prompt string inside e.g. a
multi-line raw string assigned to a constant must trip both.
"""

from __future__ import annotations

import ast
import inspect
from types import ModuleType

from investo.briefing import claude_code as cc_module
from investo.briefing import pipeline as pipeline_module

# Sentinel substrings drawn from the canonical Stage 1 / Stage 2 prompt
# bodies in ``src/investo/briefing/prompts.py``. If any of these appear
# in the executable AST of ``pipeline.py`` or ``claude_code.py``, a
# prompt body has leaked out of its module of record (AC-5.2 / AC-5.3).
_PROMPT_SENTINELS: tuple[str, ...] = (
    "market-briefing classifier",  # Stage 1 system role
    "market-briefing writer",  # Stage 2 system role
    "Pre-grouped items",  # Stage 2 user template anchor
    "Section ID legend",  # Stage 1 schema legend
    # NB: Stage 2 section headers like ``## ① 요약`` are now imported as
    # ``STAGE2_SECTION_HEADERS`` from ``prompts.py`` and reused by
    # ``pipeline.parse_six_sections``. The headers are part of the Stage
    # 2 OUTPUT contract that ``prompts.py`` owns; they are intentionally
    # NOT a sentinel for this test (the import is the single source of
    # truth, not a duplicated literal). The file-read sibling test in
    # ``test_prompts.py`` enforces the same rule on the raw text where
    # it matters (catching accidental re-introduction of the literal
    # string outside ``prompts.py``).
)


def _executable_source(module: ModuleType) -> str:
    """Return module source with module + class + function docstrings
    stripped, via ``ast.unparse``. Comments are dropped by the AST round
    trip too. The result is the executable code the runtime sees — not
    the prose. Mirrors the helper in ``test_claude_code.py``.
    """
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


# ---------------------------------------------------------------------------
# AC-5.2 — pipeline.py contains no prompt body strings
# ---------------------------------------------------------------------------


def test_pipeline_executable_source_has_no_prompt_sentinels() -> None:
    """AC-5.2 — none of the canonical prompt sentinel substrings appear
    in the executable source of ``investo.briefing.pipeline``.
    """
    code = _executable_source(pipeline_module)
    offenders = [s for s in _PROMPT_SENTINELS if s in code]
    assert not offenders, (
        f"Prompt body sentinel(s) leaked into pipeline.py executable "
        f"source: {offenders}. Move them to "
        f"src/investo/briefing/prompts.py and import the constant "
        f"(AC-5.2)."
    )


# ---------------------------------------------------------------------------
# AC-5.3 — claude_code.py contains no prompt body strings
# ---------------------------------------------------------------------------


def test_claude_code_executable_source_has_no_prompt_sentinels() -> None:
    """AC-5.3 — same constraint on ``investo.briefing.claude_code``.

    The runner module orchestrates the subprocess but must not encode
    the prompt body itself; prompts flow through it as opaque strings.
    """
    code = _executable_source(cc_module)
    offenders = [s for s in _PROMPT_SENTINELS if s in code]
    assert not offenders, (
        f"Prompt body sentinel(s) leaked into claude_code.py executable "
        f"source: {offenders}. ``claude_code`` only invokes the "
        f"subprocess; prompt bodies live in prompts.py (AC-5.3)."
    )


# ---------------------------------------------------------------------------
# Tautology guard — sentinels actually exist in prompts.py
# ---------------------------------------------------------------------------


def test_sentinels_exist_in_prompts_module() -> None:
    """If any sentinel disappeared from ``prompts.py``, the two tests
    above would pass for the wrong reason (no string anywhere → no
    leak detected). Pin the sentinels' presence at the source.
    """
    from investo.briefing import prompts

    code = inspect.getsource(prompts)
    missing = [s for s in _PROMPT_SENTINELS if s not in code]
    assert not missing, (
        f"Sentinel(s) {missing} not found in prompts.py — the AC-5.2 / "
        f"AC-5.3 tests above would be tautological. Update the sentinel "
        f"tuple or restore the prompt anchor."
    )
