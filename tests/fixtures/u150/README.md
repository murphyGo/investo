# u150 incident fixtures

These fixtures freeze the bounded production metadata and synthetic Markdown
shapes used to characterize the pre-u150 link-containment gap.

- Production records contain only the Actions run ID, target date, workflow and
  pipeline result, segment state, and canonical issue codes.
- They contain no generated Markdown, scanner evidence, URLs, head SHAs,
  notification IDs, claim digests, source payloads, or secrets.
- Markdown examples are private test-only strings built with the reserved
  `example.invalid` domain. They are not reconstructed from production prose or
  blocked targets.
- The six synthetic cases cover the approved closed shape set exactly once.

Characterization tests may be updated when the u150 implementation deliberately
changes the pre-u150 policy outcome, but this fixture remains the immutable
incident and input-shape baseline for later scanner, policy, and finalizer tests.
