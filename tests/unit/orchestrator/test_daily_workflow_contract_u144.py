"""U-144 control-flow contract for the daily briefing workflow."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "daily-briefing.yml"


def _workflow_text() -> str:
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def _step_block(workflow: str, name: str) -> str:
    marker = f"      - name: {name}"
    start = workflow.index(marker)
    next_step = workflow.find("\n      - name:", start + len(marker))
    return workflow[start:] if next_step == -1 else workflow[start:next_step]


def test_pipeline_step_captures_exit_code_without_short_circuiting_job() -> None:
    block = _step_block(_workflow_text(), "Run pipeline (python -m investo)")

    assert "id: pipeline" in block
    assert "set +e" in block
    assert "uv run python -m investo" in block
    assert "pipeline_rc=$?" in block
    assert 'echo "process_exit_code=$pipeline_rc" >> "$GITHUB_OUTPUT"' in block
    assert block.rstrip().endswith("exit 0")


def test_pages_dispatch_is_gated_only_by_publication_commit() -> None:
    workflow = _workflow_text()
    pipeline_start = workflow.index("      - name: Run pipeline (python -m investo)")
    pages_start = workflow.index("      - name: Trigger Pages deploy")
    final_start = workflow.index("      - name: Re-emit pipeline exit code")
    block = _step_block(workflow, "Trigger Pages deploy")

    assert pipeline_start < pages_start < final_start
    assert "if: steps.pipeline.outputs.publication_committed == 'true'" in block
    assert 'gh workflow run pages.yml --ref "$GITHUB_REF_NAME"' in block


def test_final_step_always_reemits_bounded_pipeline_exit_code() -> None:
    block = _step_block(_workflow_text(), "Re-emit pipeline exit code")

    assert "if: always()" in block
    assert "PIPELINE_RC: ${{ steps.pipeline.outputs.process_exit_code }}" in block
    assert "0) exit 0 ;;" in block
    assert '1|2) exit "$PIPELINE_RC" ;;' in block
    assert '*) echo "Invalid or missing pipeline exit code" >&2; exit 1 ;;' in block
