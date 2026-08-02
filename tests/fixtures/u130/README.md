# u130 rendered regression fixtures

These fixtures preserve the minimum domestic Stage-2 shapes needed to reproduce
the 2026-06-30 unsupported KOSPI level incident.

- Public source names and market values unrelated to the regression are replaced
  with deterministic placeholders.
- No collected payloads, credentials, notification destinations, or private
  metadata are included.
- The fixture keeps the four affected public surfaces: 오늘의 결론, 핵심 동인,
  section ①, and section ②.
- Tests append the canonical disclaimer at runtime so the fixture cannot drift
  into a second copy of the compliance contract.
