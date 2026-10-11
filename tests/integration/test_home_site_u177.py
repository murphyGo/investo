"""Primary card links must resolve to actual directory and flat site artifacts."""

from datetime import date
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
        self.cards: list[dict[str, str | None]] = []
        self.headings = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h1":
            self.headings += 1
        if tag == "article" and "investo-market-card" in (values.get("class") or "").split():
            self.cards.append(values)
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
    # Scheduled publications advance the committed home. Compare actual archive
    # dates rather than pinning acceptance to the initial Oct 8 snapshot.
    segments = ("domestic-equity", "us-equity", "crypto")
    archives = {
        segment: sorted((ROOT / "archive" / segment).glob("20??/??/20??-??-??.md"))
        for segment in segments
    }
    current = max(date.fromisoformat(page.stem) for pages in archives.values() for page in pages)
    assert [card["data-segment"] for card in parser.cards] == list(segments)
    for card, href in zip(parser.cards, parser.links, strict=True):
        segment = card["data-segment"]
        assert segment is not None
        latest = archives[segment][-1]
        generated = latest.stem == current.isoformat()
        assert card["data-target-date"] == current.isoformat()
        assert card["data-generated"] == str(generated).lower()
        assert f"archive/{segment}/{latest.parent.parent.name}/{latest.parent.name}/" in href
        assert latest.stem in href
        if not generated:
            assert card["data-quality"] == "absent"
            assert f"{current.isoformat()} 미발행" in text
            assert f"최근 발행 {latest.stem}" in text
        elif "수집 근거가 제한적입니다." in latest.read_text():
            assert "수집 근거가 제한적입니다." in text
