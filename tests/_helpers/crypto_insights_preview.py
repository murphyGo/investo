"""Build explicitly synthetic public-dashboard previews; no production writes."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from shutil import copytree

from mkdocs.commands.build import build
from mkdocs.config import load_config

from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.store import prepare_bundle
from tests._helpers.crypto_insights import NOW, module, qualifications, rows


def history_fixture():
    history = None
    current = None
    for offset in range(7, -1, -1):
        stamp = NOW - timedelta(days=offset)
        values = tuple(
            r.model_copy(update={"value": r.value - Decimal(offset)})
            if r.metric_id == "fear_greed_index"
            else r
            for r in rows(stamp)
        )
        current = module(values, now=stamp)
        history = update_history(current, history, qualifications())
    return current, history


def build_preview(root: Path) -> Path:
    docs = root / "docs"
    site = root / "site"
    copytree(Path("site_docs"), docs, dirs_exist_ok=True)
    current, history = history_fixture()
    for relative, data in prepare_bundle((current,), {"crypto": history}).files:
        target = docs / relative.relative_to("site_docs")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    page = docs / "insights/crypto/index.md"
    page.write_text(
        "> **합성 크립토 검증 화면입니다. 실제 시세·권리 승인·운영 게시 자료가 아닙니다.**\n\n"
        + page.read_text()
    )
    build(load_config("mkdocs.yml", docs_dir=str(docs), site_dir=str(site), strict=True))
    return site
