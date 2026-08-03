# Business Logic Model - u146 Trusted Curated Image Supply Workbench

## Review preparation

1. Operator saves an exact Commons `imageinfo|revisions` response and downloads the exact original/thumbnail URL named in that response.
2. The offline workbench parses JSON with duplicate-key rejection, verifies the expected file title/provider host, and checks the local binary against the selected variant.
3. License/revision/author/restriction rules produce either blocked diagnostics or E1 `READY_FOR_REVIEW` evidence.
4. The workbench writes snapshot bytes, canonical evidence JSON, and a completion seal into a new unprotected pending directory. Existing output is never overwritten.
5. No manifest, registry, approved decision, curated binary, or u137 clearance is created.

## Operator filing

1. A reviewer inspects the image subject and E1 evidence, including non-copyright and endorsement risks.
2. The reviewer files the binary and existing seven-field manifest, adds one registry reference, and authors E2 with exact-byte evidence/binary/manifest hashes.
3. CI loads the library, validates registry integrity, then validates either the E3 legacy seal or the complete E1/E2 graph.
4. Any mismatch is RED. No partial graph degrades to a warning.

## Failure behavior

- Workbench parse/validation errors create no completed packet.
- CI graph failures stop the curated gate but do not mutate files.
- Daily briefing runtime performs no u146 work and therefore has no new network or failure mode.
