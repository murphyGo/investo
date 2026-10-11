"""Source-bound asset relations from a fixed parent selection, without prices or I/O."""

from __future__ import annotations

import re
from collections.abc import Sequence

from investo._internal.event_context import resolve_context_ref
from investo._internal.event_v3_contract import fact_source_map
from investo.models.event_asset_impact import EventAssetImpact
from investo.models.event_document import EventEditionDraft


def _explicit_relation(text: str, asset: str, actors: Sequence[str]) -> bool:
    relation = (
        r"(?:affects?|impacts?|supplies|partners with|"
        r"is (?:a |the )?(?:supplier to|customer of|partner of))"
    )
    target = r"(?<![\w])" + re.escape(asset) + r"(?![\w])"
    for clause in re.split(r"[.!?;,\n]|\bwhile\b|\bwhereas\b", text):
        if re.search(
            r"\b(?:no|not|never|without|unrelated|if|may|might)\b|않|아니|무관|경우|가능성",
            clause,
            re.I,
        ):
            continue
        for actor in actors:
            owner = r"(?<![\w])" + re.escape(actor) + r"(?![\w])"
            if re.search(owner + r"\s+" + relation + r"\s+" + target, clause, re.I):
                return True
            if re.search(target + r"\s+" + relation + r"\s+" + owner, clause, re.I):
                return True
            if re.search(
                owner
                + r"(?:의|은|는|가|이)?\s*(?:발표|결정|공급|수요)?\s*"
                + target
                + r"(?:에|에게)\s*(?:영향|공급)",
                clause,
            ):
                return True
    return False


def match_event_assets(
    draft: EventEditionDraft, terms: Sequence[str]
) -> tuple[EventAssetImpact, ...]:
    impacts: list[EventAssetImpact] = []
    bindings = {b.identity.event_id: b for b in draft.bindings}
    plans = {p.event_id: p for p in draft.editorial_plan.events}
    for article in draft.articles:
        binding = bindings[article.event_id]
        labels = {e.entity.entity_id: e.entity.source_labels for e in binding.entities}
        sources = fact_source_map(binding, plans[article.event_id].source_event, draft.documents)
        for term in dict.fromkeys(terms):
            if not 1 <= len(term) <= 80:
                continue
            entity_ids = {
                eid
                for eid, names in labels.items()
                if term.casefold() in {name.casefold() for name in names}
            }
            fact = next(
                (
                    f
                    for f in binding.facts
                    if f.fact_id in article.fact_ids and f.canonical.subject_id in entity_ids
                ),
                None,
            )
            if fact is not None:
                source = sources[fact.fact_id]
                label = " ".join(
                    resolve_context_ref(r, draft.documents) for r in source.metric_refs
                )
                mechanism = " · ".join(
                    value
                    for value in (
                        term,
                        label or fact.canonical.predicate,
                        fact.original_value,
                        fact.canonical.unit,
                        fact.canonical.period,
                        {
                            "actual": "실제",
                            "forecast": "예상",
                            "scheduled": "예정",
                            "quoted_opinion": "인용 발언",
                        }[fact.canonical.status],
                    )
                    if value
                )
                if len(mechanism) > 180 or len(fact.source_refs) > 16:
                    continue
                impacts.append(
                    EventAssetImpact(
                        event_id=article.event_id,
                        asset_id=term,
                        relation="direct",
                        mechanism=mechanism,
                        fact_ids=(fact.fact_id,),
                        source_refs=fact.source_refs,
                    )
                )
            elif article.meaning.mode == "source_reported":
                actors = [name for eid in binding.identity.actor_ids for name in labels[eid]]
                spans = [(r, resolve_context_ref(r, draft.documents)) for r in article.meaning.refs]
                match = next(
                    (
                        (r, text)
                        for r, text in spans
                        if re.search(r"(?<![\w])" + re.escape(term) + r"(?![\w])", text, re.I)
                        and _explicit_relation(text, term, actors)
                        and not re.search(
                            r"\b(?:no|not|never|without|unrelated|if|may|might)\b|않|아니|무관|경우|가능성",
                            text,
                            re.I,
                        )
                        and len(text) <= 180
                        and re.search(
                            r"\b(?:affects?|impact|supplier|customer|partner|supply|demand)\b|영향|공급|수요|협력|고객",
                            text,
                            re.I,
                        )
                    ),
                    None,
                )
                if match is not None:
                    ref, mechanism = match
                    impacts.append(
                        EventAssetImpact(
                            event_id=article.event_id,
                            asset_id=term,
                            relation="related",
                            mechanism=mechanism,
                            fact_ids=(article.fact_ids[0],),
                            source_refs=(ref,),
                        )
                    )
            if len(impacts) == 16:
                return tuple(impacts)
    return tuple(impacts)
