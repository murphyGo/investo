# u166 tech stack decisions

Reuse httpx, asyncio.timeout, shared retry config, existing schema parser and frozen dataclasses; no library/provider dependency. Diagnostic logger/CLI outputs are allowlisted structured fields; no global HTTP logging. One manual read-only public workflow uses existing uv/Python3.11 and contents:read; no schedule, upload or publish/notify/model credentials. Existing code quality/policy/doc gates and private runtime separation retained.
