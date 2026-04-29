"""Tests for ``scripts/check_no_anthropic_sdk.py`` (the CI Anthropic-SDK guard).

Pins NFR-002 AC-2.2 / AC-2.3 + NFR-007 AC-7.1 / AC-7.6. The guard
runs and exits 0 on the current tree (clean), exits 1 with a clear
message when any of:

- A ``src/**/*.py`` file imports ``anthropic`` (US-009 ban).
- A ``src/**/*.py`` file uses ``subprocess.run/Popen(..., shell=True)``.
- A ``src/**/*.py`` file uses ``subprocess.run("string-form first arg")``.
- ``pyproject.toml`` lists ``anthropic`` as a dependency.

Style mirrors u1's ``tests/unit/sources/test_no_paid_apis.py``.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "check_no_anthropic_sdk.py"


def _load_script_module() -> ModuleType:
    """Load the script as a module so tests can introspect / patch it."""
    spec = importlib.util.spec_from_file_location("check_no_anthropic_sdk", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Existence + clean-tree tests
# ---------------------------------------------------------------------------


def test_script_exists() -> None:
    assert _SCRIPT.exists(), f"missing CI Anthropic-SDK guard: {_SCRIPT}"


def test_subprocess_invocation_passes_on_current_tree() -> None:
    """The guard must exit 0 against the live repo (no anthropic imports,
    no shell-form subprocess usage, no anthropic dep). The subprocess
    form is what CI executes.
    """
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"check_no_anthropic_sdk.py failed unexpectedly:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_find_source_offenders_returns_empty_on_clean_tree() -> None:
    script = _load_script_module()
    assert script.find_source_offenders() == []


def test_find_pyproject_offenders_returns_empty_on_clean_tree() -> None:
    script = _load_script_module()
    assert script.find_pyproject_offenders() == []


# ---------------------------------------------------------------------------
# Detection tests — synthesize matching files into a temp src tree
# ---------------------------------------------------------------------------


def test_detects_anthropic_sdk_import(
    tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A synthetic file with ``from anthropic import X`` is flagged."""
    script = _load_script_module()

    fake_src = Path(str(tmp_path)) / "src"
    fake_src.mkdir()
    (fake_src / "leak.py").write_text(
        "from anthropic import Anthropic\nclient = Anthropic()\n", encoding="utf-8"
    )
    monkeypatch.setattr(script, "SRC_ROOT", fake_src)

    offenders = script.find_source_offenders()
    assert any(name == "anthropic_sdk_import" for _, _, name, _ in offenders)


def test_detects_import_anthropic_form(
    tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``import anthropic`` form is also flagged."""
    script = _load_script_module()

    fake_src = Path(str(tmp_path)) / "src"
    fake_src.mkdir()
    (fake_src / "leak.py").write_text("import anthropic\n", encoding="utf-8")
    monkeypatch.setattr(script, "SRC_ROOT", fake_src)

    offenders = script.find_source_offenders()
    assert any(name == "anthropic_sdk_import" for _, _, name, _ in offenders)


def test_detects_shell_true_subprocess_run(
    tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``subprocess.run(..., shell=True)`` is flagged (AC-7.6)."""
    script = _load_script_module()

    fake_src = Path(str(tmp_path)) / "src"
    fake_src.mkdir()
    (fake_src / "leak.py").write_text(
        'import subprocess\nsubprocess.run("ls", shell=True)\n', encoding="utf-8"
    )
    monkeypatch.setattr(script, "SRC_ROOT", fake_src)

    offenders = script.find_source_offenders()
    pattern_names = {name for _, _, name, _ in offenders}
    assert "shell_true" in pattern_names
    assert "string_form_subprocess" in pattern_names


def test_detects_string_form_subprocess_run(
    tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``subprocess.run("claude -p ...")`` (string-form first arg without
    shell=True) is also flagged — likely a candidate for shell=True.
    """
    script = _load_script_module()

    fake_src = Path(str(tmp_path)) / "src"
    fake_src.mkdir()
    (fake_src / "leak.py").write_text(
        'import subprocess\nsubprocess.run("claude -p hi")\n', encoding="utf-8"
    )
    monkeypatch.setattr(script, "SRC_ROOT", fake_src)

    offenders = script.find_source_offenders()
    assert any(name == "string_form_subprocess" for _, _, name, _ in offenders)


def test_does_not_flag_list_form_subprocess(
    tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The compliant ``subprocess.run(["claude", "-p", prompt])`` list
    form is the production pattern — must NOT trigger the guard.
    """
    script = _load_script_module()

    fake_src = Path(str(tmp_path)) / "src"
    fake_src.mkdir()
    (fake_src / "ok.py").write_text(
        'import subprocess\nsubprocess.run(["claude", "-p", "prompt"])\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "SRC_ROOT", fake_src)

    offenders = script.find_source_offenders()
    assert offenders == []


def test_detects_anthropic_in_pyproject_dependencies(
    tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``anthropic`` listed under ``[project.dependencies]`` is flagged."""
    script = _load_script_module()

    fake_pyproject = Path(str(tmp_path)) / "pyproject.toml"
    fake_pyproject.write_text(
        '[project]\nname = "test"\n\n[project.dependencies]\n"anthropic>=0.5"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "PYPROJECT", fake_pyproject)

    offenders = script.find_pyproject_offenders()
    assert offenders, "anthropic in [project.dependencies] should be flagged"
    assert any("[project.dependencies]" in section for _, section, _ in offenders)


def test_detects_anthropic_in_pyproject_optional_dependencies(
    tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Optional-dependencies tables are also scanned."""
    script = _load_script_module()

    fake_pyproject = Path(str(tmp_path)) / "pyproject.toml"
    fake_pyproject.write_text(
        '[project]\nname = "test"\n\n[project.optional-dependencies]\n"anthropic>=0.5"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "PYPROJECT", fake_pyproject)

    offenders = script.find_pyproject_offenders()
    assert offenders
    assert any("[project.optional-dependencies]" in section for _, section, _ in offenders)


def test_does_not_flag_anthropic_outside_dep_sections(
    tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A comment or other-section reference to "anthropic" must NOT
    trigger — only the two dep sections matter (AC-2.2).
    """
    script = _load_script_module()

    fake_pyproject = Path(str(tmp_path)) / "pyproject.toml"
    fake_pyproject.write_text(
        '[project]\nname = "test"\ndescription = "Mentions anthropic in prose"\n\n'
        "[tool.notes]\n"
        "anthropic_sdk_banned = true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "PYPROJECT", fake_pyproject)

    offenders = script.find_pyproject_offenders()
    assert offenders == []
