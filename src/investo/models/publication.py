"""Immutable publication transaction inputs and evidence (E11)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PublicationStatus = Literal[
    "pending", "remote_confirmed", "definitely_unpublished", "outcome_unknown"
]


def _valid_digest(value: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True, slots=True)
class PublicationRequest:
    """Opt-in remote confirmation; the caller owns file/index snapshots.

    ``baseline_metadata_hash`` must come from the fixed remote tree used
    to generate this publication. The budget must not exceed the caller's
    remaining publish deadline. This request never changes legacy mode.
    """

    run_id: str
    baseline_metadata_hash: str
    metadata_paths: tuple[Path, ...] = (Path("archive/_meta/event_receipts.json"),)
    remote_ref: str = "refs/heads/main"
    total_budget_s: float = 60.0

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", self.run_id) is None:
            raise ValueError("invalid publication run_id")
        if not _valid_digest(self.baseline_metadata_hash):
            raise ValueError("baseline_metadata_hash must be a SHA256 digest")
        if (
            re.fullmatch(r"refs/heads/[A-Za-z0-9_/-][A-Za-z0-9_./-]*", self.remote_ref) is None
            or ".." in self.remote_ref
            or "//" in self.remote_ref
            or any(
                part.startswith(".") or part.endswith(".lock")
                for part in self.remote_ref.split("/")
            )
            or self.remote_ref.endswith(("/", "."))
        ):
            raise ValueError("remote_ref must be a literal branch ref")
        if not math.isfinite(self.total_budget_s) or self.total_budget_s <= 0:
            raise ValueError("publication budget must be finite and positive")
        paths = tuple(Path(path) for path in self.metadata_paths)
        if not paths or len(paths) > 32:
            raise ValueError("publication requires 1..32 metadata paths")
        if any(path.is_absolute() or ".." in path.parts or not path.parts for path in paths):
            raise ValueError("metadata paths must be repository-relative files")
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate metadata paths")
        object.__setattr__(self, "metadata_paths", paths)


@dataclass(frozen=True, slots=True)
class PublishReceipt:
    """One immutable observation; no source text, stderr or remote URL."""

    run_id: str
    local_sha: str | None
    remote_ref: str
    baseline_metadata_hash: str
    status: PublicationStatus
    content_hash: str | None = None

    def __post_init__(self) -> None:
        PublicationRequest(
            run_id=self.run_id,
            baseline_metadata_hash=self.baseline_metadata_hash,
            remote_ref=self.remote_ref,
        )
        if (
            self.local_sha is not None
            and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", self.local_sha) is None
        ):
            raise ValueError("local_sha must be a Git object id")
        if self.status not in {
            "pending",
            "remote_confirmed",
            "definitely_unpublished",
            "outcome_unknown",
        }:
            raise ValueError("invalid publication status")
        if self.status in {"pending", "remote_confirmed"} and self.local_sha is None:
            raise ValueError("committed receipt requires local_sha")
        if not _valid_digest(self.baseline_metadata_hash):
            raise ValueError("baseline_metadata_hash must be a SHA256 digest")
        if self.content_hash is not None and not _valid_digest(self.content_hash):
            raise ValueError("content_hash must be a SHA256 digest")
