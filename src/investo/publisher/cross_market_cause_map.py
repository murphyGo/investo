"""Cross-market cause-map guard — u74 Step 4.

A reader wants to know *why* domestic / US / crypto moves rhyme on a
given day — but an ad-hoc "BTC fell because AAPL fell" line is exactly
the cross-segment leakage the u57 lint chain forbids. u74 renders a
single compact, **observational** cause-map line and only when the u57
:class:`BundleContext` already proves the linkage at the shared-macro
tier.

Grounding rule
~~~~~~~~~~~~~~
The only admissible evidence is a u57 shared-macro key that the
bundle-context detector already promoted (i.e. it appeared in ≥ 2
segments — that two-segment threshold is enforced by
``orchestrator.bundle_context._detect_shared_macros`` before the block
is rendered). u74 re-derives the allowed cause-map *type* from that
rendered block; it never invents a linkage and never reads tickers.

Cause-map types (plan Step 4 table):

* ``geopolitical_oil_macro`` ← shared ``국제 유가`` macro line.
* ``fed_policy_event`` ← shared ``FOMC 일정`` / ``미 국채 수익률`` line.
* ``global_systemic_risk`` ← only when an explicit allow-listed systemic
  key is present (no current detector emits one, so it stays dormant
  until u57 adds the key — never fabricated here).

Every cause-map type must also be in
:data:`BundleContext.cross_market_core_allowed`; an unapproved type is
omitted (and reported via the returned diagnostics), never demoted into
public prose.

Module boundary: imports only :mod:`investo.models`. Pure str/struct →
str. Does NOT import from ``orchestrator`` / ``sources`` / ``notifier``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from investo.models.bundle_context import BundleContext

CAUSE_MAP_HEADER: Final[str] = "> **크로스마켓 연결 고리**:"

# Macro-key labels exactly as ``orchestrator.bundle_context`` renders
# them in ``shared_macro_block``. Matching the rendered label is how u74
# stays a pure consumer of u57's existing output without adding a model
# field. (Single source of these strings is ``_MACRO_KEY_LABELS`` in
# bundle_context; mirrored here as the consumption contract.)
_OIL_LABEL: Final[str] = "국제 유가"
_FOMC_LABEL: Final[str] = "FOMC 일정"
_UST_LABEL: Final[str] = "미 국채 수익률"

# Cause-map type -> (evidence labels that ground it, observational wording).
# Wording is taken verbatim from the plan Step 4 allowed-wording column;
# it is observational ("관찰" / "점검") and never predictive.
_CAUSE_MAP_WORDING: Final[dict[str, str]] = {
    "geopolitical_oil_macro": ("유가/지정학 이슈가 여러 자산군의 변동성 연결 고리로 관찰됩니다."),
    "fed_policy_event": ("금리 이벤트가 할인율/달러 경로의 공통 변수로 남아 있습니다."),
    "global_systemic_risk": ("공통 위험 요인으로 변동성 확대 여부를 점검합니다."),
}

# Deterministic emission order when multiple types qualify on the same run.
_CAUSE_MAP_ORDER: Final[tuple[str, ...]] = (
    "geopolitical_oil_macro",
    "fed_policy_event",
    "global_systemic_risk",
)


@dataclass(frozen=True)
class CauseMapDecision:
    """Outcome of the cause-map guard for one run.

    ``rendered`` is the markdown line (empty when nothing qualified).
    ``emitted`` / ``suppressed`` carry the cause-map type ids for replay
    reporting — a suppressed type is one whose evidence was present but
    which is not in ``cross_market_core_allowed`` (logged, never
    demoted into prose).
    """

    rendered: str
    emitted: tuple[str, ...]
    suppressed: tuple[str, ...]


def _candidate_types(block: str) -> list[str]:
    """Map a rendered shared-macro block to candidate cause-map types."""
    candidates: list[str] = []
    if _OIL_LABEL in block:
        candidates.append("geopolitical_oil_macro")
    if _FOMC_LABEL in block or _UST_LABEL in block:
        candidates.append("fed_policy_event")
    return candidates


def evaluate_cause_map(ctx: BundleContext | None) -> CauseMapDecision:
    """Decide the cross-market cause-map line for a run.

    Returns an empty-rendered decision when:
    * ``ctx`` is ``None`` or has no ``shared_macro_block`` (no u57
      two-segment macro evidence), or
    * no candidate type maps to the rendered block, or
    * the only candidates are not in ``cross_market_core_allowed``.

    Approved candidates render one compact ``> **크로스마켓 연결 고리**``
    line carrying the observational wording for each emitted type, joined
    by ``/``. Forbidden candidates are reported in ``suppressed`` and are
    never written into the prose.
    """
    if ctx is None or not ctx.shared_macro_block:
        return CauseMapDecision(rendered="", emitted=(), suppressed=())

    allowed = ctx.cross_market_core_allowed
    candidates = _candidate_types(ctx.shared_macro_block)
    emitted: list[str] = []
    suppressed: list[str] = []
    for cause_type in _CAUSE_MAP_ORDER:
        if cause_type not in candidates:
            continue
        if cause_type in allowed:
            emitted.append(cause_type)
        else:
            suppressed.append(cause_type)

    if not emitted:
        return CauseMapDecision(rendered="", emitted=(), suppressed=tuple(suppressed))

    wording = " / ".join(_CAUSE_MAP_WORDING[t] for t in emitted)
    rendered = f"{CAUSE_MAP_HEADER} {wording}\n"
    return CauseMapDecision(
        rendered=rendered,
        emitted=tuple(emitted),
        suppressed=tuple(suppressed),
    )


def inject_cause_map_line(text: str, decision: CauseMapDecision) -> str:
    """Insert the cause-map line (idempotent).

    Placed before the first ``## ①`` section, after the macro / channel
    anchor blocks. Re-injection is a no-op (sentinel guard). An
    empty-rendered decision leaves the text unchanged.
    """
    if not decision.rendered:
        return text
    if CAUSE_MAP_HEADER in text:
        return text
    rendered = f"{decision.rendered.strip()}\n\n"
    first_section = text.find("## ①")
    if first_section != -1:
        return text[:first_section] + rendered + text[first_section:]
    return f"{text.rstrip()}\n\n{rendered}"


__all__ = [
    "CAUSE_MAP_HEADER",
    "CauseMapDecision",
    "evaluate_cause_map",
    "inject_cause_map_line",
]
