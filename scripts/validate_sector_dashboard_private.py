#!/usr/bin/env python3
"""Run the private NAV-only sector radar; not market OHLCV or public evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final, Never

from investo.models import SectorCoverageStatus
from investo.sector_dashboard import (
    PrivateInputError,
    PrivateOutputRejectedError,
    PrivateTransactionError,
    compute_sector_snapshot,
    load_private_nav_workbooks,
    open_private_output_session,
    read_private_workbook_manifest,
)

_REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


class _CliArgumentError(ValueError):
    pass


class _RedactedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        del message
        raise _CliArgumentError


def _parser() -> argparse.ArgumentParser:
    parser = _RedactedArgumentParser(
        description=(
            "Private NAV-only US sector validation. This is not actual market OHLCV "
            "and does not provide public-use evidence."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="explicit absolute path to the private 12-workbook manifest",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="explicit absolute owner-only directory outside the repository",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace a different existing valid private pair",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except _CliArgumentError:
        print(
            "sector-dashboard-private status=rejected issue=manifest.schema",
            file=sys.stderr,
        )
        return 2
    try:
        with open_private_output_session(
            args.output_dir,
            repository_root=_REPOSITORY_ROOT,
        ) as output:
            manifest = read_private_workbook_manifest(
                args.manifest,
                repository_root=_REPOSITORY_ROOT,
            )
            output.validate_input_paths((args.manifest, *manifest.workbooks.values()))
            bundle = load_private_nav_workbooks(
                manifest,
                repository_root=_REPOSITORY_ROOT,
            )
            snapshot = compute_sector_snapshot(bundle)
            result = output.commit(snapshot, replace=args.replace)
        disposition = "written" if result.changed else "no-op"
        print(
            "sector-dashboard-private "
            f"status={snapshot.coverage.status.value} "
            f"sectors={snapshot.coverage.available_sector_count}/11 "
            f"policy={snapshot.primary_policy.policy_id} result={disposition}"
        )
        if snapshot.coverage.status is SectorCoverageStatus.INSUFFICIENT:
            return 3
        return 0
    except (PrivateInputError, PrivateOutputRejectedError) as exc:
        issue_code = (
            exc.issue_code.value if isinstance(exc, PrivateInputError) else "output.forbidden_path"
        )
        print(
            f"sector-dashboard-private status=rejected issue={issue_code}",
            file=sys.stderr,
        )
        return 2
    except PrivateTransactionError:
        print("sector-dashboard-private status=failed", file=sys.stderr)
        return 4
    except OSError:
        print("sector-dashboard-private status=failed", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
