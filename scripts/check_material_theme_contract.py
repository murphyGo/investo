#!/usr/bin/env python3
"""Fail when built Material CSS drops Investo's image-theme fragment contract.

Run this after ``mkdocs build --strict``.  The check intentionally targets the
built site rather than mkdocs-material's Python package so it covers the exact
CSS that GitHub Pages will publish.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SITE_ROOT = _REPO_ROOT / "site"
_REQUIRED_RULES: tuple[tuple[str, str], ...] = (
    (
        "light asset hidden in slate mode",
        '[data-md-color-scheme=slate] img[src$="#gh-light-mode-only"],'
        '[data-md-color-scheme=slate] img[src$="#only-light"]{display:none}',
    ),
    (
        "dark asset hidden in default mode",
        '[data-md-color-scheme=default] img[src$="#gh-dark-mode-only"],'
        '[data-md-color-scheme=default] img[src$="#only-dark"]{display:none}',
    ),
)
_REQUIRED_RENDERED_SOURCES: tuple[str, ...] = (
    'src="card.svg#gh-light-mode-only"',
    'src="card-dark.svg#gh-dark-mode-only"',
)


def _check_rendered_pair(html: str) -> list[str]:
    """Return missing exact pair fragments from built HTML."""
    return [source for source in _REQUIRED_RENDERED_SOURCES if source not in html]


def _check_mkdocs_render_contract() -> tuple[int, list[str]]:
    """Build an exact pair through MkDocs Material and verify emitted HTML."""
    with tempfile.TemporaryDirectory(prefix="investo-u143-theme-") as temporary:
        root = Path(temporary)
        docs_root = root / "docs"
        site_root = root / "site"
        docs_root.mkdir()
        (docs_root / "index.md").write_text(
            "# Theme contract\n\n"
            "![카드](card.svg#gh-light-mode-only)\n"
            "![카드](card-dark.svg#gh-dark-mode-only)\n",
            encoding="utf-8",
        )
        (docs_root / "card.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>\n',
            encoding="utf-8",
        )
        (docs_root / "card-dark.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>\n',
            encoding="utf-8",
        )
        config_path = root / "mkdocs.yml"
        config_path.write_text(
            "site_name: Investo u143 theme contract\n"
            f'docs_dir: "{docs_root.as_posix()}"\n'
            f'site_dir: "{site_root.as_posix()}"\n'
            "theme:\n"
            "  name: material\n"
            "  palette:\n"
            "    - scheme: default\n"
            "    - scheme: slate\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mkdocs",
                "build",
                "--strict",
                "--config-file",
                str(config_path),
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            suffix = detail[-1] if detail else f"exit {result.returncode}"
            return 1, [f"ephemeral MkDocs theme-contract build failed: {suffix}"]

        html = (site_root / "index.html").read_text(encoding="utf-8")
        missing = _check_rendered_pair(html)
        if missing:
            return 1, ["built HTML missing exact theme fragment source(s): " + ", ".join(missing)]
    return 0, ["MkDocs rendered-pair contract OK — both exact fragment sources preserved"]


def check(
    site_root: Path = _DEFAULT_SITE_ROOT, *, verify_rendered_html: bool = True
) -> tuple[int, list[str]]:
    """Return an exit code and actionable messages for built ``site_root``."""
    stylesheet_root = site_root / "assets" / "stylesheets"
    stylesheets = sorted(stylesheet_root.glob("*.min.css"))
    if not stylesheets:
        return 1, [f"no built Material stylesheets found under {stylesheet_root}"]

    combined = "\n".join(path.read_text(encoding="utf-8") for path in stylesheets)
    missing = [label for label, rule in _REQUIRED_RULES if rule not in combined]
    if missing:
        return 1, [
            "missing Material image-theme rule(s): " + ", ".join(missing),
            "run `uv run --extra docs mkdocs build --strict` and inspect the "
            "mkdocs-material upgrade before publishing",
        ]

    messages = [
        "Material theme contract OK — light/dark fragment rules present in "
        f"{len(stylesheets)} built stylesheet(s)"
    ]
    if verify_rendered_html:
        render_code, render_messages = _check_mkdocs_render_contract()
        messages.extend(render_messages)
        if render_code:
            return render_code, messages
    return 0, messages


def main() -> int:
    exit_code, messages = check()
    stream = sys.stderr if exit_code else sys.stdout
    for message in messages:
        print(message, file=stream)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
