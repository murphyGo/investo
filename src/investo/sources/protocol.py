"""Public adapter contract for Source Adapters.

Exports the :class:`SourceAdapter` Protocol that every adapter
implements and the :class:`SourceFetchError` exception that adapters
raise on fetch failure. Both types form this package's stable public
surface and are re-exported from ``investo.sources.__init__`` (Step 9
of the code-generation plan tightens the surface).

References:

* aidlc-docs/construction/u1-sources/functional-design/domain-entities.md
  §E1 (SourceAdapter), §E4 (SourceFetchError)
* aidlc-docs/construction/u1-sources/functional-design/business-rules.md
  R3 (async + injected client), R6 (failure isolation contract)
"""

from __future__ import annotations

from typing import ClassVar, Protocol

import httpx

from investo.models import Category, NormalizedItem
from investo.sources._window import FetchWindow


class SourceFetchError(Exception):
    """Raised by an adapter (or the retry helper) when a fetch failed.

    ``transient=True`` flags the failure as a kind that *might* succeed
    on a future run (network glitch, exhausted 5xx/429 retries, budget
    overrun); ``transient=False`` is for terminal failures (4xx-not-429,
    malformed payload, oversize body, unsupported scheme). Per FD R6
    the aggregator catches both flavors uniformly — the flag is
    informational for logs.

    Subclasses :class:`Exception` (not :class:`RuntimeError`) so callers
    can ``pytest.raises(SourceFetchError)`` without catching unrelated
    programmer-error :class:`RuntimeError`s.
    """

    def __init__(
        self,
        source_name: str,
        message: str,
        *,
        transient: bool,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(f"source {source_name!r} failed: {message}")
        self.source_name = source_name
        self.transient = transient
        self.cause = cause


class SourceAdapter(Protocol):
    """Structural contract every Source Adapter implements.

    Adapters declare ``name`` and ``category`` as **class** attributes
    (FD R2 and §E1) so the registry keys on them at import time without
    instantiating the adapter, and so the same string is the registry
    key, the provenance value on every emitted :class:`NormalizedItem`,
    and the slug shown in operator logs.

    Adapters are stateless — instance state is forbidden (FD R3). The
    shared :class:`httpx.AsyncClient` and the pre-built
    :class:`FetchWindow` are injected into every ``fetch`` call. The
    adapter MAY raise :class:`SourceFetchError` to signal a fetch-side
    failure; any other exception is treated as a programmer error and
    propagates out of the aggregator (FD R6).

    The Protocol is intentionally *not* ``@runtime_checkable`` —
    registration uses class-attribute inspection (see ``_registry``),
    never :func:`isinstance`, so runtime structural checks would only
    invite false-positive matches.
    """

    name: ClassVar[str]
    category: ClassVar[Category]

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]: ...
