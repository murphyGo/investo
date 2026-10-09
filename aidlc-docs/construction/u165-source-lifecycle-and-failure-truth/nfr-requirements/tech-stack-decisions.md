# u165 technology decisions

Reuse Python frozen dataclasses, canonical source specs, asyncio/httpx/shared retry, append-only coverage ledger and existing reader/ops consumers. The lifecycle resolver is pure and per-run; no persistent circuit breaker or second registry. NFR Design reuses u1/u31/u54/u95 patterns with the explicit deadline/state rules above; a separate NFR Design stage is skipped because no new logical component. Infrastructure Design is skipped: existing public/private workflow variables only, no new compute/storage/messaging/network service.
