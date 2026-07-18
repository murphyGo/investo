from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from investo.models import SectorCoverageStatus
from investo.sector_dashboard.private_render import PrivateTransactionError

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "validate_sector_dashboard_private.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_sector_dashboard_private", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cli_rejects_repository_output_before_manifest_read(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()
    called = False

    def unexpected_read(*args: object, **kwargs: object) -> None:
        del args, kwargs
        nonlocal called
        called = True

    monkeypatch.setattr(module, "read_private_workbook_manifest", unexpected_read)
    code = module.main(
        [
            "--manifest",
            "/private/sentinel-manifest.json",
            "--output-dir",
            str(_ROOT / "site_docs" / "sector-radar"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert not called
    assert captured.out == ""
    assert captured.err == (
        "sector-dashboard-private status=rejected issue=output.forbidden_path\n"
    )
    assert "sentinel-manifest" not in captured.err
    assert "Traceback" not in captured.err


def test_cli_transaction_failure_is_one_redacted_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()

    def fail_session(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise PrivateTransactionError

    monkeypatch.setattr(module, "open_private_output_session", fail_session)
    code = module.main(
        [
            "--manifest",
            "/private/sentinel-manifest.json",
            "--output-dir",
            "/private/sentinel-output",
        ]
    )

    captured = capsys.readouterr()
    assert code == 4
    assert captured.out == ""
    assert captured.err == "sector-dashboard-private status=failed\n"
    assert "sentinel" not in captured.err
    assert "Traceback" not in captured.err


def test_cli_oserror_is_one_redacted_transaction_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()

    def fail_session(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise OSError("/private/SENTINEL-workbook.xlsx")

    monkeypatch.setattr(module, "open_private_output_session", fail_session)
    code = module.main(
        [
            "--manifest",
            "/private/sentinel-manifest.json",
            "--output-dir",
            "/private/sentinel-output",
        ]
    )

    captured = capsys.readouterr()
    assert code == 4
    assert captured.out == ""
    assert captured.err == "sector-dashboard-private status=failed\n"
    assert "SENTINEL" not in captured.err
    assert "Traceback" not in captured.err


def test_cli_argument_error_never_echoes_private_argv(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()
    code = module.main(
        [
            "--manifest",
            "/private/sentinel-manifest.json",
            "--output-dir",
            "/private/sentinel-output",
            "/private/SENTINEL-workbook.xlsx",
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == ("sector-dashboard-private status=rejected issue=manifest.schema\n")
    assert "/private/" not in captured.err
    assert "SENTINEL" not in captured.err
    assert "usage:" not in captured.err


def test_cli_rejects_input_output_overlap_before_workbook_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script()
    output = tmp_path / "private-output"
    output.mkdir(mode=0o700)
    manifest_path = output / "manifest.json"
    manifest_path.touch()
    workbook_path = output / "XLC.xlsx"
    workbook_path.touch()
    loaded = False

    monkeypatch.setattr(
        module,
        "read_private_workbook_manifest",
        lambda *args, **kwargs: SimpleNamespace(workbooks={"XLC": workbook_path}),
    )

    def unexpected_load(*args: object, **kwargs: object) -> None:
        del args, kwargs
        nonlocal loaded
        loaded = True

    monkeypatch.setattr(module, "load_private_nav_workbooks", unexpected_load)
    code = module.main(
        [
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert not loaded
    assert captured.out == ""
    assert captured.err == (
        "sector-dashboard-private status=rejected issue=output.forbidden_path\n"
    )
    assert str(manifest_path) not in captured.err


def test_cli_help_states_private_nav_scope(capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_script()
    with pytest.raises(SystemExit) as caught:
        module.main(["--help"])
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert "Private NAV-only" in help_text
    assert "not actual market OHLCV" in help_text
    assert "public-use evidence" in help_text
    assert "--manifest" in help_text
    assert "--output-dir" in help_text
    assert "--replace" in help_text


@pytest.mark.parametrize(
    ("status", "expected_code"),
    (
        (SectorCoverageStatus.NORMAL, 0),
        (SectorCoverageStatus.PARTIAL, 0),
        (SectorCoverageStatus.WARMING_UP, 0),
        (SectorCoverageStatus.INSUFFICIENT, 3),
    ),
)
def test_cli_exit_codes_follow_committed_coverage_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: SectorCoverageStatus,
    expected_code: int,
) -> None:
    module = _load_script()
    snapshot = SimpleNamespace(
        coverage=SimpleNamespace(status=status, available_sector_count=8),
        primary_policy=SimpleNamespace(policy_id="sector-regime-v1"),
    )

    class FakeSession:
        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def validate_input_paths(self, paths: object) -> None:
            del paths

        def commit(self, value: object, *, replace: bool) -> SimpleNamespace:
            assert value is snapshot
            assert not replace
            return SimpleNamespace(changed=False)

    monkeypatch.setattr(
        module, "open_private_output_session", lambda *args, **kwargs: FakeSession()
    )
    monkeypatch.setattr(
        module,
        "read_private_workbook_manifest",
        lambda *args, **kwargs: SimpleNamespace(workbooks={}),
    )
    monkeypatch.setattr(module, "load_private_nav_workbooks", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "compute_sector_snapshot", lambda bundle: snapshot)

    code = module.main(
        [
            "--manifest",
            "/private/manifest.json",
            "--output-dir",
            "/private/output",
        ]
    )

    captured = capsys.readouterr()
    assert code == expected_code
    assert captured.err == ""
    assert captured.out == (
        f"sector-dashboard-private status={status.value} "
        "sectors=8/11 policy=sector-regime-v1 result=no-op\n"
    )
