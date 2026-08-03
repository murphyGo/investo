# Business Rules - u146 Trusted Curated Image Supply Workbench

| Rule | Contract |
| --- | --- |
| R1 | The workbench may emit at most `READY_FOR_REVIEW`; it cannot approve or file. |
| R2 | Phase 1 accepts only exact Wikimedia Commons file records with a current page revision and selected binary variant. |
| R3 | Only file-specific Public Domain or CC0 maps to a clean manifest token. CC BY/SA and discovery-only sources are blocked in Phase 1. |
| R4 | Empty restrictions are required; missing license/revision/dimensions/author, contradictions, or embedded restriction signals block review readiness. |
| R5 | Snapshot/evidence/binary/manifest digests are lowercase SHA-256 of exact stored bytes. |
| R6 | Actual binary signature, MIME, width, height, byte cap, and digest must match the snapshot/evidence variant. |
| R7 | Output paths are repository-relative, normalized, and confined; duplicate JSON keys and traversal fail closed. |
| R8 | New filed assets require E1 + approved E2 + binary + existing seven-field manifest + registry reachability. |
| R9 | The current 15 assets are exempt only through the fixed E3 path/hash seal; legacy-v0 cannot gain a 16th entry. |
| R10 | Filed or rights-artifact orphans are CI failures, not warnings. |
| R11 | The workbench performs no network call and refuses protected output roots. |
| R12 | u137 clearances/store and runtime scraping flags remain byte-identical and unmodified. |
| R13 | Secret-shaped fields or unsafe raw metadata never enter evidence/decision output or error messages. |

## Blocker Codes

- `NO_LICENSE_EVIDENCE`
- `SOURCE_POLICY_METADATA_ONLY`
- `MISSING_REVISION`
- `MISSING_DIMENSIONS`
- `TOO_SMALL`
- `LICENSE_CONTRADICTION`
- `RESTRICTION_SIGNAL`
- `BINARY_MISMATCH`
