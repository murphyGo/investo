"""Every static archive link resolves with real MkDocs directory/flat outputs."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from mkdocs.commands.build import build
from mkdocs.config import load_config

ROOT = Path(__file__).parents[2]


class ArchiveLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.months = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and "investo-archive-link" in (values.get("class") or "").split():
            self.links.append(values["href"])
        if tag == "h2" and (values.get("id") or "").startswith("month-"):
            self.months.append(values["id"])


@pytest.mark.parametrize("directory", [True, False])
def test_all_archive_links_resolve_with_actual_config(tmp_path, directory):
    config = load_config(
        config_file=str(ROOT / "mkdocs.yml"),
        site_dir=str(tmp_path),
        strict=True,
        use_directory_urls=directory,
    )
    build(config)
    for segment in ["domestic-equity", "us-equity", "crypto"]:
        html = tmp_path / "archive" / segment / "index.html"
        parser = ArchiveLinks()
        parser.feed(html.read_text())
        expected = list((ROOT / "archive" / segment).glob("[0-9][0-9][0-9][0-9]/*/*.md"))
        assert len(parser.links) == len(expected) > 1
        assert parser.months and len(set(parser.months)) == len(parser.months)
        for href in parser.links:
            path = unquote(urlsplit(href).path)
            assert not path.endswith(".md")
            output = html.parent / path
            assert (output / "index.html" if output.is_dir() else output).is_file(), href
