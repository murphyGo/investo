"""Static safety checks for u2 response handling.

Pins NFR-007 AC-7.7: briefing response parsing must not use dynamic
execution or pickle deserialization.
"""

from __future__ import annotations

import importlib
import re

from tests._helpers.ast_helpers import executable_source

_BRIEFING_MODULES = (
    "investo.briefing.claude_code",
    "investo.briefing.disclaimer",
    "investo.briefing.errors",
    "investo.briefing.leak_guard",
    "investo.briefing.pipeline",
    "investo.briefing.prompts",
)


def test_briefing_executable_code_uses_no_dynamic_execution_or_pickle() -> None:
    forbidden = re.compile(
        r"\b(eval|exec)\s*\(|\bpickle\.loads\s*\(|^\s*(import pickle|from pickle)",
        re.MULTILINE,
    )

    matches: list[str] = []
    for module_name in _BRIEFING_MODULES:
        module = importlib.import_module(module_name)
        code = executable_source(module)
        if match := forbidden.search(code):
            matches.append(f"{module_name}: {match.group(0).strip()}")

    assert not matches
