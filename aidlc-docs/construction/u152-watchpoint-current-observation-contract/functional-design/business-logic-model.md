# u152 Functional Design — current observation flow

2026-09-28. Existing eight fixed contracts in the code-generation plan are adopted unchanged as the required implementation prerequisite of user-authorized u162. No separate user answer or production approval is inferred. Baseline47031596 and current origin/main04978d81 still contain the numeric passthrough. This design makes its replacement concrete before code.

1. Parse existing source/signal/current/upside/downside/implication delimiters without copying the whole bullet to a missing current slot. Keep legacy unlabelled clauses only as candidates for existing slots.
2. Snapshot already-routed anchors and item metadata in WatchpointValuePayload. Build only existing supported candidate families: price, fear/greed, BTC funding, BTC OI and allowed CFTC contracts.
3. Match signal and source to one asset and metric; ignore future conditions when determining identity. Bare assets select price; explicit unknown metrics and conflicting assets/metrics reject. Preserve specific indicator/token/source precedence within that identity. Collapse equivalent best observations and reject conflicting best values independent of input order.
4. Replace every current, including numeric LLM prose, with the candidate's canonical current. Repair an unsafe/overlong signal from the candidate label, using existing title bounding. CFTC uses date labels and confidence no higher than 보통.
5. Existing invalid-row handling removes unsupported rows. Existing deterministic fallback emits up to2 cards if none survive; existing renderer retains max6. Body evidence and owned visual fragments stay with their current owners.
6. Existing compliance and finalizer gates remain authoritative. No post-seal mutation, new IO or per-card LLM. Test generated and already-rendered input, final sealed bytes/notification and repeated conversion.
