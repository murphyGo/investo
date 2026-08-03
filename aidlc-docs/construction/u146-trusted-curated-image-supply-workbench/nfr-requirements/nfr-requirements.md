# NFR Requirements - u146 Trusted Curated Image Supply Workbench

| ID | Requirement | Acceptance |
| --- | --- | --- |
| AC-1.1 | Compliance | Only exact-file PD/CC0 can become `READY_FOR_REVIEW`; approval stays human-authored. |
| AC-1.2 | Integrity | One-byte changes to snapshot/evidence/binary/manifest break the graph. |
| AC-1.3 | Determinism | Identical inputs create byte-identical evidence packets. |
| AC-2.1 | Isolation | The workbench has no network calls and refuses protected output roots. |
| AC-2.2 | Compatibility | Existing `ExternalAssetManifest`, u137 clearance/store, and runtime flags are unchanged. |
| AC-3.1 | Security | Duplicate keys, traversal, unsafe hosts, secret-shaped values, and unscoped digest exemptions fail closed. |
| AC-3.2 | Reliability | Partial packets are not consumable; existing outputs are never overwritten. |
| AC-4.1 | Cost | No paid source, API key, dependency, or daily runtime request is introduced. |
| AC-4.2 | Performance | CI work is bounded by the small committed library and local file hashing. |
