"""Verify scope, semantic navigation and retained Material/OG output."""

from pathlib import Path

from mkdocs.commands.build import build
from mkdocs.config import load_config

ROOT = Path(__file__).parents[2]


def test_actual_template_scopes_home_and_preserves_other_pages(tmp_path: Path) -> None:
    config = load_config(config_file=str(ROOT / "mkdocs.yml"), site_dir=str(tmp_path), strict=True)
    build(config)
    home = (tmp_path / "index.html").read_text()
    article = (tmp_path / "archive/us-equity/2026/10/2026-10-08/index.html").read_text()
    for html in (home, article):
        assert 'property="og:image"' in html and 'name="twitter:card"' in html
        assert 'data-md-component="search"' in html
        assert 'data-md-toggle="drawer"' in html
        assert "data-md-color-scheme=" in html
        assert "investo-ui.css" in html and "investo-navigation.js" in html
        assert "관심 자산" in html and "미국 섹터" in html
    assert 'data-investo-page="home"' in home
    assert 'data-investo-page="article"' in article
    assert 'data-investo-page="home"' not in article
    for relative in ("watchlist/index.html", "sectors/index.html", "quality/index.html"):
        html = (tmp_path / relative).read_text()
        assert 'data-investo-page="reference"' in html
        assert 'data-investo-page="home"' not in html
        assert 'aria-current="page"' in html
    assert (ROOT / "site_docs/assets/investo-ui.css").stat().st_size <= 16 * 1024
    assert (ROOT / "site_docs/assets/investo-navigation.js").stat().st_size <= 4 * 1024
