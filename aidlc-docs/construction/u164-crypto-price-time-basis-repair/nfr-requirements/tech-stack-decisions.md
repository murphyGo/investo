# u164 technology decisions

Reuse the existing frozen dataclass FetchWindow, httpx/retry/parser, NormalizedItem and public finalization pipeline. No new dependency, persistence or service. Existing pure helpers and Hypothesis support numeric omission and serialization invariants. NFR Design reuses u1/u54/u95 patterns; infrastructure design is skipped because the runtime/workflow owner and deployment remain unchanged. Optional free Demo environment wiring adds no infrastructure or secret value.
