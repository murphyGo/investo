"""Primary card links must resolve to actual directory and flat site artifacts."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from mkdocs.commands.build import build
from mkdocs.config import load_config

ROOT = Path(__file__).parents[2]


class CardLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.headings = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h1":
            self.headings += 1
        if tag == "a" and "investo-market-link" in (values.get("class") or "").split():
            self.links.append(values["href"] or "")


@pytest.mark.parametrize("directory", [True, False])
def test_all_home_primary_links_resolve_after_actual_config_build(
    tmp_path: Path, directory
) -> None:
    config = load_config(
        config_file=str(ROOT / "mkdocs.yml"),
        site_dir=str(tmp_path),
        strict=True,
        use_directory_urls=directory,
    )
    build(config)
    text = (tmp_path / "index.html").read_text()
    parser = CardLinks()
    parser.feed(text)
    assert parser.headings == 1
    assert len(parser.links) == 3
    for href in parser.links:
        path = unquote(urlsplit(href).path)
        assert not path.endswith(".md")
        output = tmp_path / path
        assert (output / "index.html" if output.is_dir() else output).is_file()
    assert "2026-10-08 미발행" in text and "최근 발행 2026-10-07" in text
    assert "수집 근거가 제한적입니다." in text
