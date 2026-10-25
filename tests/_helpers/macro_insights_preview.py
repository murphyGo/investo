"""Build a clearly marked synthetic local preview; no production files are changed."""

from pathlib import Path
from shutil import copytree

from mkdocs.commands.build import build
from mkdocs.config import load_config

from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.store import prepare_bundle
from tests._helpers.macro_insights import module, qualifications
from tests.unit.publisher.test_macro_insights_render_u181 import history_for


def build_preview(root: Path) -> Path:
    docs = root / "docs"
    site = root / "site"
    copytree(Path("site_docs"), docs, dirs_exist_ok=True)
    current = module()
    # Only this synthetic fixture supplies extra historical points.
    history = update_history(current, None, qualifications())
    row = next(r for r in current.metrics if r.metric_id == "ust_2y")
    sample = history_for(row)
    by_key = {(r.definition_key, r.observation_key): r for r in (*history.rows, *sample.rows)}
    history = type(history)(
        module="macro", definitions=history.definitions, rows=tuple(by_key.values())
    )
    prepared = prepare_bundle((current,), {"macro": history})
    for relative, data in prepared.files:
        target = docs / relative.relative_to("site_docs")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    page = docs / "insights/macro/index.md"
    page.write_text(
        "> **합성 검증 화면입니다. 실제 시세나 운영 게시 자료가 아닙니다.**\n\n" + page.read_text()
    )
    config = load_config("mkdocs.yml", docs_dir=str(docs), site_dir=str(site), strict=True)
    build(config)
    return site
