"""Integration smoke test — u3 publisher end-to-end.

Exercises the realistic orchestrator flow:

1. Construct a valid ``Briefing`` (with the canonical DISCLAIMER from u2).
2. Call ``write_briefing(briefing, target_date)`` — verify the
   archive file lands at the FR-006 path with the expected content.
3. Call ``commit_and_push(message, files=[path])`` with a fake git
   runner — verify exactly 3 invocations (``add``, ``commit``,
   ``push origin HEAD``) fire with the expected argv shapes.
4. Confirm cross-unit imports resolve: u3 successfully consumes
   ``Briefing`` from ``investo.models`` and ``DISCLAIMER`` from
   ``investo.briefing.disclaimer``.

Pure stub-based (no real git, no real filesystem outside ``tmp_path``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.publisher import (
    ARCHIVE_ROOT,
    PublisherDisclaimerError,
    PublisherError,
    PublisherGitError,
    PublisherIOError,
    archive_path,
    commit_and_push,
    verify_disclaimer,
    write_briefing,
)
from investo.publisher import paths as paths_module
from tests._helpers.briefings import DEFAULT_TARGET_DATE, build_briefing

_TARGET_DATE = DEFAULT_TARGET_DATE


def test_publisher_end_to_end_write_then_commit_and_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Realistic orchestrator flow: write → stage path → commit/push.

    Uses ``monkeypatch`` to redirect ``ARCHIVE_ROOT`` to ``tmp_path``
    + inject a fake git runner. No real filesystem state outside
    ``tmp_path``; no real ``git`` invocations.
    """
    monkeypatch.setattr(paths_module, "ARCHIVE_ROOT", tmp_path / "archive")

    briefing = build_briefing()

    # Step 1 — write briefing.
    path = write_briefing(briefing, _TARGET_DATE)

    expected_path = tmp_path / "archive" / "2026" / "04" / "2026-04-25.md"
    assert path == expected_path
    assert path.read_text(encoding="utf-8") == briefing.rendered_markdown
    # Sanity: the disclaimer landed in the written file.
    assert verify_disclaimer(path.read_text(encoding="utf-8"))

    # Step 2 — fake git runner records argv shapes; all 3 calls succeed.
    captured: list[list[str]] = []

    def fake_runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        captured.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    commit_and_push(
        message=f"publish {_TARGET_DATE.isoformat()}",
        files=[path],
        runner=fake_runner,
    )

    assert len(captured) == 3
    assert captured[0][:3] == ["git", "add", "--"]
    assert captured[1] == ["git", "commit", "-m", "publish 2026-04-25"]
    assert captured[2] == ["git", "push", "origin", "HEAD"]


def test_publisher_public_surface_is_importable() -> None:
    """Pin the package's public re-exports against accidental drift.

    ``from investo.publisher import X`` must succeed for every name
    the orchestrator + cross-unit consumers depend on.
    """
    # The imports at the top of THIS file would have failed already
    # if any name were missing, so the assertions below are mostly
    # documentation. Keep them for grep-ability.
    assert callable(write_briefing)
    assert callable(commit_and_push)
    assert callable(verify_disclaimer)
    assert callable(archive_path)
    assert isinstance(ARCHIVE_ROOT, Path)
    # All 4 error classes are importable + subclass PublisherError.
    assert issubclass(PublisherDisclaimerError, PublisherError)
    assert issubclass(PublisherIOError, PublisherError)
    assert issubclass(PublisherGitError, PublisherError)


def test_publisher_uses_canonical_disclaimer_from_u2() -> None:
    """Cross-unit boundary: u3's `verify_disclaimer` references the
    same `DISCLAIMER` constant u2's `briefing.disclaimer` exports.
    A regression that copied the constant locally into u3 would not
    desync u2 vs u3 silently — it would either flunk this test or
    flunk the verifier-side `test_verifier_uses_u2_disclaimer_constant`
    grep.
    """
    assert verify_disclaimer(DISCLAIMER) is True
