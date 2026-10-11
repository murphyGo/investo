# u177 Tech decisions

Existing site_index hero owns pure HTML and marker migration; driver builds existing bundle state tuple once and passes it. Canonical quality parser is reused before history/dashboard generation, so stale quality.md is never read for badges. Existing quality_consistency parses home and existing pipeline gate reads/passes current home before git; snapshots already cover paths. Standard html.escape and canonical href helpers; no daily runtime Markdown renderer/dependency; existing MkDocs processes only canonical primary Markdown links.

Separate NFR Design SKIP: renderer/state/atomic writes and exact gate inputs/failure rules are fully specified here, with no new storage/network boundary. Infrastructure SKIP. Exact future v3 presentation fields are optional for summaries and do not fake missing owner implementations; surface selection/hash/provenance remains u171. Read-only rendered views only.
