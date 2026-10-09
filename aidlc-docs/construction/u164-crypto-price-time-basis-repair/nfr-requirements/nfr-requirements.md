# u164 NFR Requirements

NFR-001/002/003/005/006/007/008. One existing CoinGecko batch call, existing retry/60-second adapter behavior, no additional request/provider/model call. Crypto freshness remains six hours; frozen receipt clocks verify exact stale/future edges and updates during requests. Missing metrics remain missing throughout prompt and public surfaces. Historical replay never acquires live permission implicitly.

R13: synthetic offline fixtures, no key-bearing URLs/full source payloads in published diagnostics. Optional free Demo support must use a header on fixed api.coingecko.com only, never a Pro endpoint or key echo. Scheduled GHA access, credential availability and ten-run acceptance are operational follow-up.

Current primary documentation allows keyless prototyping but warns it is unsuitable for scheduled production polling; free Demo supports the same endpoints with attribution. Preserve current access while making the qualified free header path configurable; no account/key is assumed created.

Sources checked2026-10-09: [keyless policy](https://docs.coingecko.com/docs/keyless-public-api), [Demo pricing](https://www.coingecko.com/en/api/pricing), [display/attribution](https://support.coingecko.com/hc/en-us/articles/4538761098521-Can-I-use-CoinGecko-data-and-screenshots-for-my-website-book-etc).
