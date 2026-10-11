# u179 Tech decisions

Static Markdown URL rewriting in structural markdown=1 containers, exact snippets in markdown=0 paragraphs with stdlib html.escape. Path percent encoding prevents Markdown/attribute punctuation injection. Existing neutral extractor/projector/sentence-bound owner applies legacy only. No persistent summary cache or second filesystem walker. Current E6 DTO plumbing is minimal optional kwargs in index driver/pipeline; old default callers unchanged.

Separate NFR Design SKIP: focused design specifies filters/scan/optional sealed inputs without a new state/storage/service boundary. Infrastructure SKIP, existing MkDocs/Pages. Build actual directory/flat URL inventories and scoped filters, maximum payload and current fallback consumers together. Full program regression before final unit commit.
