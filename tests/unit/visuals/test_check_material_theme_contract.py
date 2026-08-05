"""Tests for the built Material image-theme contract gate (u143 AC-143.1)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_material_theme_contract.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_material_theme_contract", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_stylesheet(site_root: Path, text: str) -> None:
    stylesheet = site_root / "assets" / "stylesheets" / "palette.test.min.css"
    stylesheet.parent.mkdir(parents=True)
    stylesheet.write_text(text, encoding="utf-8")


def test_gate_accepts_built_material_fragment_rules(tmp_path: Path) -> None:
    _write_stylesheet(
        tmp_path,
        '[data-md-color-scheme=slate] img[src$="#gh-light-mode-only"],'
        '[data-md-color-scheme=slate] img[src$="#only-light"]{display:none}'
        '[data-md-color-scheme=default] img[src$="#gh-dark-mode-only"],'
        '[data-md-color-scheme=default] img[src$="#only-dark"]{display:none}',
    )

    exit_code, messages = _load_script().check(tmp_path, verify_rendered_html=False)

    assert exit_code == 0
    assert any("contract OK" in message for message in messages)


def test_gate_rejects_missing_dark_fragment_rule(tmp_path: Path) -> None:
    _write_stylesheet(
        tmp_path,
        '[data-md-color-scheme=slate] img[src$="#gh-light-mode-only"],'
        '[data-md-color-scheme=slate] img[src$="#only-light"]{display:none}',
    )

    exit_code, messages = _load_script().check(tmp_path, verify_rendered_html=False)

    assert exit_code == 1
    assert any("dark asset hidden in default mode" in message for message in messages)


def test_gate_rejects_site_without_built_stylesheets(tmp_path: Path) -> None:
    exit_code, messages = _load_script().check(tmp_path, verify_rendered_html=False)

    assert exit_code == 1
    assert any("no built Material stylesheets" in message for message in messages)


def test_rendered_pair_contract_accepts_both_exact_fragment_sources() -> None:
    script = _load_script()
    html = (
        '<img alt="카드" src="card.svg#gh-light-mode-only">'
        '<img alt="카드" src="card-dark.svg#gh-dark-mode-only">'
    )

    assert script._check_rendered_pair(html) == []


def test_rendered_pair_contract_rejects_rewritten_or_missing_fragment() -> None:
    script = _load_script()
    html = '<img alt="카드" src="card.svg"><img alt="카드" src="card-dark.svg#gh-dark-mode-only">'

    assert script._check_rendered_pair(html) == ['src="card.svg#gh-light-mode-only"']
