"""Match actual client fetch URLs to real directory/flat MkDocs assets."""

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from mkdocs.commands.build import build
from mkdocs.config import load_config

ROOT = Path(__file__).parents[2]
STEM = "2026-10-08"
ARTICLE = Path("archive/us-equity/2026/10") / f"{STEM}.md"


@pytest.mark.parametrize("directory", [True, False])
def test_client_fetch_matches_copied_source_sidecar(tmp_path: Path, directory: bool) -> None:
    site = tmp_path / "site"
    original = (ROOT / ARTICLE).read_bytes()
    config = load_config(
        config_file=str(ROOT / "mkdocs.yml"),
        site_dir=str(site),
        use_directory_urls=directory,
        strict=True,
    )
    build(config)
    page_path = (
        ARTICLE.with_suffix("") / "index.html" if directory else ARTICLE.with_suffix(".html")
    )
    html = (site / page_path).read_text()
    sources = re.findall(r'data-history-src="([^"]+)"', html)
    assert sources
    node = shutil.which("node")
    assert node is not None, "Node is required; CI explicitly installs Node 22"
    for prefix in ("investo", "demo", ""):
        url = f"https://example.test/{prefix}/".replace("test//", "test/") + page_path.as_posix()
        for src in sources:
            output = subprocess.run(
                [node, str(ROOT / "tests/js/resolve_chart_sidecar_u175.cjs"), url, src],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            result = json.loads(output.stdout)
            resolved = urlsplit(result["url"]).path.lstrip("/")
            if prefix:
                assert resolved.startswith(prefix + "/")
                resolved = resolved[len(prefix) + 1 :]
            assert (site / resolved).is_file()
            assert (site / resolved).read_bytes() == (ROOT / resolved).read_bytes()
            assert result["requests"] == 1 and result["charts"] == 1
    assert (ROOT / ARTICLE).read_bytes() == original
