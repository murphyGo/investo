"""Render an explicitly synthetic calendar beside the existing macro preview."""

from pathlib import Path
from shutil import copytree

from mkdocs.commands.build import build
from mkdocs.config import load_config

from investo.publisher.insights.store import prepare_bundle
from tests._helpers.upcoming_insights import module


def build_preview(root: Path) -> Path:
    docs = root / "docs"
    site = root / "site"
    copytree(Path("site_docs"), docs, dirs_exist_ok=True)
    for relative, data in prepare_bundle((module(),), {}).files:
        target = docs / relative.relative_to("site_docs")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    page = docs / "insights/calendar/index.md"
    page.write_text(
        "> **합성 일정 검증 화면입니다. 실제 일정이나 운영 게시 자료가 아닙니다.**\n\n"
        + page.read_text()
    )
    config = load_config("mkdocs.yml", docs_dir=str(docs), site_dir=str(site), strict=True)
    build(config)
    return site
