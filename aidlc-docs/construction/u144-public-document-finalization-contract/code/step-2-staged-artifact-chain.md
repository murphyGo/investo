# Step 2.4 Staged Artifact Chain

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

File-backed public-document supplements now have one neutral immutable
descriptor contract in `models.public_artifact`:
`StagedArtifact(artifact_id, segment, kind, relative_public_path, staged_path,
sha256)`. The model submodule is shared by publisher and visuals without
adding a sibling adapter import or widening the `investo.models` package
export list. `temporary_artifact_staging_root()` owns a private run root and
removes it after both normal and exceptional context exits.

Visual preparation accepts a staging root, mirrors the public archive shape
below it, and returns descriptors for every image and provenance manifest.
Each `VisualMarkdownBlock` carries the exact descriptor IDs referenced by its
typed supplement. Chart injection has a compatible staging overload: legacy
production calls still return public `Path` values, while staging calls write
only below the run root, return `StagedArtifact` values, and attach those IDs
to the chart supplement. Current carryover remains text-only and performs no
file I/O; the shared kind union already supports a future file-backed
carryover producer.

E5 selection is an identity join over E1 typed supplements, indexed marker
regions, and explicit block outcomes. The finalizer skeleton always computes
that canonical selection and rejects a phase handler whose result differs, so
an omitted marker shell cannot be used to revive an artifact. E6 continues to
build its ordered promotion manifest from the sealed E5 IDs and the original
E1 descriptor objects; no Markdown URL is parsed.

`promote_finalized_bundle_artifacts()` accepts only an E6
`FinalizedPublicBundle`. Before its first public write it validates the entire
manifest: lexical staging ownership, exact descriptor path, every source and
destination path component for symlinks, resolved containment, regular-file
status, and SHA-256. It snapshots each destination and atomically promotes
only the E6 manifest, leaving rollback to the existing surrounding pre-git
publish transaction.

The default segmented pipeline intentionally remains on its legacy public
writers in this slice. Step 5 installs the concrete finalizer and owns the
single production switch to the run staging context plus post-E6 promotion;
activating staging earlier would create files that no production E6
transaction can yet promote. Fresh-eyes review explicitly approved this
sequencing boundary.

Validation: scoped Ruff/format and strict mypy over 239 source files passed;
1,638 internal/model/visual/publisher/orchestrator/integration tests passed.
Fresh-eyes review first found and then verified fixes for an omitted-artifact
handler bypass and parent-directory symlink aliases. Final re-review approved
with no remaining findings.
