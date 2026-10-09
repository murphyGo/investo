# u166 domain entities

| Entity | Contract |
| --- | --- |
| FetchWindow | Existing target-date and optional run clocks; basisdate never overwritten |
| IndexPage | Validated fixed response/result code, bounded row list and required finite integer declared total_count and validated pageNo/numOfRows |
| IndexDiagnostic/IndexFetchReport | Immutable allowlisted counts/status/date/exclusions; no raw payload/values/provider message |
| NormalizedItem | Existing official index schema and source date lag; valid current fields only |
| SourceFetchError | Fixed safe source/API/schema/network reason, preserves cancellation/programmer errors |
| Qualification decision | ship diagnostic only / defer credentials-provider/public rights / reject unqualified fallback |

Reuse existing source/source-spec/outcome/deadline/public-document models; no new registered provider or persistent store.
