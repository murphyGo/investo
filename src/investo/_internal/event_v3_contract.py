"""Source ownership and original-claim validation shared by both v3 boundaries."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from datetime import datetime
from itertools import pairwise

from investo._internal.event_context import (
    context_lookup,
    event_context_refs,
    resolve_context_ref,
    text_fact_frame,
    validate_context_event,
)
from investo._internal.event_identity import normalize_fact_bindings, source_receipt
from investo._internal.event_text_proof import (
    SOURCE_SENTENCE_BREAK,
    SOURCE_STATEMENT_BREAK,
    action_equivalents,
    display_matches_frame,
    performed_actions,
    prove_text_assertion,
)
from investo._internal.korean_subjects import is_source_role_subject, korean_entity_subjects
from investo._internal.text import bound_at_sentence
from investo.models.event_context import (
    ContextEventDraft,
    ContextFactDraft,
    ContextRef,
    EventContextDocument,
)
from investo.models.event_document import EventEditionDraft, NumericFollowUpEntry
from investo.models.event_identity import CanonicalEventBinding
from investo.models.event_story import StoryRecord

_NUMBERS = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
_UNSAFE = re.compile(r"https?://|www\.|<!--|[<>{}`\r\n]|\]\(", re.I)
_CONDITIONAL = re.compile(r"경우|라면|다면|수\s*있|가능성|조건|\b(?:if|could|may)\b", re.I)
_IDENTIFIERS = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Z][A-Za-z0-9_.-]*|[a-z][a-z0-9]*_[a-z0-9_]+)(?![A-Za-z0-9_])"
)
_ROLE_STATUS = {
    "실제": "actual",
    "actual": "actual",
    "예상": "forecast",
    "전망": "forecast",
    "forecast": "forecast",
    "expected": "forecast",
    "guidance": "forecast",
    "예정": "scheduled",
    "scheduled": "scheduled",
}
_ORDINARY_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "it",
        "its",
        "this",
        "these",
        "that",
        "actual",
        "forecast",
        "expected",
        "scheduled",
    }
)


class EventEditionValidationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _number(text: str) -> str:
    return _normal(text).replace(",", "").rstrip("%")


def validate_claim(text: str, refs: Sequence[ContextRef], draft: EventEditionDraft) -> None:
    if not text or text != text.strip() or _UNSAFE.search(text):
        raise EventEditionValidationError("event.narrative_invalid")
    source = " ".join(resolve_context_ref(ref, draft.documents) for ref in refs)
    numbers = {_number(match.group()) for match in _NUMBERS.finditer(source)}
    if any(_number(match.group()) not in numbers for match in _NUMBERS.finditer(text)):
        raise EventEditionValidationError("event.fact_unsupported")
    source_words = set(re.findall(r"[A-Za-z0-9_.-]+", _normal(source).casefold()))
    source_normal = _normal(source).casefold()
    if any(
        label.casefold() not in source_normal and not is_source_role_subject(label, source_words)
        for label in korean_entity_subjects(text)
    ):
        raise EventEditionValidationError("event.entity_unsupported")
    if any(
        match.group().rstrip(".").casefold() not in source_words | _ORDINARY_WORDS
        for match in _IDENTIFIERS.finditer(text)
    ):
        raise EventEditionValidationError("event.entity_unsupported")


def validate_text_actions(
    text: str,
    source: ContextEventDraft,
    documents: Sequence[EventContextDocument],
    *,
    require_assertion: bool = False,
    proof_refs: Sequence[ContextRef] = (),
) -> None:
    """Keep literal actions and modality bound to source assertion frames."""
    lookup = context_lookup(documents)

    def whole_assertion(ref: ContextRef) -> bool:
        doc = lookup[(ref.document_id, ref.revision_id)]
        chunk = next(c for c in doc.chunks if c.chunk_id == ref.chunk_id)
        if chunk.source_locator == "source_metadata":
            return False
        separators = tuple(SOURCE_SENTENCE_BREAK.finditer(chunk.text))
        start = max((m.end() for m in separators if m.end() <= ref.start), default=0)
        end = min((m.end() for m in separators if m.end() >= ref.end), default=len(chunk.text))
        enclosing = chunk.text[start:end].strip().rstrip(".!。")
        return resolve_context_ref(ref, documents).strip().rstrip(".!。") == enclosing

    # Optional context has its own assigned evidence, independently of facts.
    # A literal full-span source statement preserves its attribution/modality;
    # it does not need to repeat the article's primary action.
    if (
        not require_assertion
        and proof_refs
        and any(
            whole_assertion(ref)
            and text.strip().rstrip(".!。")
            == resolve_context_ref(ref, documents).strip().rstrip(".!。")
            for ref in proof_refs
        )
    ):
        return
    text_frames = []
    for fact in source.facts:
        if fact.value_kind == "text" and fact.status_refs:
            frame = text_fact_frame(fact, lookup)
            if frame is not None:
                text_frames.append(frame)
    if text_frames and (require_assertion or performed_actions(text)):
        clauses = [part.strip() for part in SOURCE_STATEMENT_BREAK.split(text) if part.strip()]
        if not clauses or any(
            not any(display_matches_frame(clause, frame) for frame in text_frames)
            for clause in clauses
        ):
            raise EventEditionValidationError("event.fact_unsupported")
    if text_frames:
        return
    allowed_actions: set[str] = set()
    # Identity actions can independently prove an announcement, e.g. an
    # earnings release whose canonical facts are numeric results.
    for ref in source.object_refs:
        doc = lookup[(ref.document_id, ref.revision_id)]
        chunk = next(c for c in doc.chunks if c.chunk_id == ref.chunk_id)
        actor = " ".join(resolve_context_ref(r, documents) for r in source.actor_refs)
        actor_refs = sorted(source.actor_refs, key=lambda r: r.start)
        if (
            actor_refs
            and all(
                (r.document_id, r.revision_id, r.chunk_id)
                == (ref.document_id, ref.revision_id, ref.chunk_id)
                for r in actor_refs
            )
            and all(
                re.fullmatch(r"\s*(?:and|및|와|과|,|·|&)\s*", chunk.text[a.end : b.start])
                for a, b in pairwise(actor_refs)
            )
        ):
            actor = chunk.text[actor_refs[0].start : actor_refs[-1].end]
        action = " ".join(resolve_context_ref(r, documents) for r in source.action_refs)
        obj = resolve_context_ref(ref, documents)
        for predicate in ("statement", "launch", "agreement", "decision", "status_change"):
            if prove_text_assertion(
                predicate=predicate,
                status="actual",
                subject=actor,
                action=action,
                object_label=obj,
                value=obj,
                assertion=chunk.text.strip(),
                status_proofs=(action,),
            ):
                allowed_actions.update(action_equivalents(action))
    if any(action not in allowed_actions for action in performed_actions(text)):
        raise EventEditionValidationError("event.fact_unsupported")


def validate_fact_roles(
    text: str,
    binding: CanonicalEventBinding,
    source: ContextEventDraft,
    documents: Sequence[EventContextDocument],
    *,
    require_assertion: bool = False,
    check_actions: bool = True,
) -> None:
    """Bind each numeric assertion to its metric, status, unit and period slot."""
    if check_actions:
        validate_text_actions(text, source, documents, require_assertion=require_assertion)
    normalized = _normal(text).casefold().replace(",", "")
    sources = fact_source_map(binding, source, documents)
    metric_labels = {
        fact.fact_id: " ".join(
            resolve_context_ref(r, documents) for r in sources[fact.fact_id].metric_refs
        ).casefold()
        for fact in binding.facts
    }
    role_pattern = re.compile(
        r"실제|actual|예상|전망|forecast|expected|guidance|예정|scheduled", re.I
    )
    for clause in SOURCE_STATEMENT_BREAK.split(normalized):
        for number in _NUMBERS.finditer(clause):
            candidates = [
                f
                for f in binding.facts
                if _number(f.original_value).casefold() == number.group().rstrip("%")
                and (
                    number.group().endswith("%") == f.original_value.strip().endswith("%")
                    or (number.group().endswith("%") and f.canonical.unit in {"%", "percent"})
                )
            ]
            if not candidates and any(
                _number(f.original_value).casefold() == number.group().rstrip("%")
                for f in binding.facts
            ):
                raise EventEditionValidationError("event.fact_unsupported")
            if not candidates:
                continue  # Publication/reference dates are checked by their own refs.
            positions = [
                (abs(match.start() - number.start()), f)
                for f in candidates
                if metric_labels[f.fact_id]
                for match in re.finditer(re.escape(metric_labels[f.fact_id]), clause)
            ]
            if not positions:
                raise EventEditionValidationError("event.fact_unsupported")
            nearest = min(distance for distance, _ in positions)
            metric_facts = [f for distance, f in positions if distance == nearest]
            subjects = {
                e.entity.entity_id: e.entity.source_labels
                for e in binding.entities
                if e.entity.entity_id in {f.canonical.subject_id for f in binding.facts}
            }
            subject_positions = [
                (abs(match.start() - number.start()), subject_id)
                for subject_id, labels in subjects.items()
                for label in labels
                for match in re.finditer(re.escape(_normal(label).casefold()), clause)
            ]
            if not subject_positions:
                raise EventEditionValidationError("event.fact_unsupported")
            nearest_subject = min(distance for distance, _ in subject_positions)
            subject_ids = {
                sid for distance, sid in subject_positions if distance == nearest_subject
            }
            metric_facts = [f for f in metric_facts if f.canonical.subject_id in subject_ids]
            if not metric_facts:
                raise EventEditionValidationError("event.fact_unsupported")
            roles = list(role_pattern.finditer(clause))
            if not roles:
                raise EventEditionValidationError("event.fact_unsupported")
            role = min(roles, key=lambda match: abs(match.start() - number.start()))
            claimed_status = _ROLE_STATUS[role.group().casefold()]
            if not any(
                f.canonical.status == claimed_status
                and (f.canonical.unit is None or f.canonical.unit.casefold() in clause)
                and (f.canonical.period is None or f.canonical.period.casefold() in clause)
                for f in metric_facts
            ):
                raise EventEditionValidationError("event.fact_unsupported")


def fact_source_map(
    binding: CanonicalEventBinding,
    source: ContextEventDraft,
    documents: Sequence[EventContextDocument],
) -> dict[str, ContextFactDraft]:
    registry = {
        label: entity.registry_key
        for entity in binding.entities
        if entity.registry_key is not None
        for label in entity.entity.source_labels
    }
    return {
        normalized.fact_id: fact
        for fact in source.facts
        for normalized in normalize_fact_bindings(documents, (fact,), approved_registry=registry)
    }


def validate_event_edition(
    draft: EventEditionDraft,
    *,
    observed_at: datetime,
    story_baseline: Sequence[StoryRecord] = (),
) -> None:
    """Validate every original claim, including digests that may later be omitted."""
    plans = draft.editorial_plan.events
    ids = tuple(p.event_id for p in plans if p.placement == "article")
    if tuple(a.event_id for a in draft.articles) != ids or len(set(ids)) != len(ids):
        raise EventEditionValidationError("event.selection_mismatch")
    bindings = {b.identity.event_id: b for b in draft.bindings}
    if set(bindings) != {p.event_id for p in plans} or len(draft.support) != len(plans):
        raise EventEditionValidationError("event.selection_mismatch")
    plan_by_id = {p.event_id: p for p in plans}
    lookup = context_lookup(draft.documents)
    if draft.content_contract_version == 2:
        from investo._internal.event_article import validate_terminal_articles

        try:
            for plan in plans:
                validate_context_event(plan.source_event, draft.documents, observed_at=observed_at)
            validate_terminal_articles(draft, observed_at=observed_at)
        except ValueError:
            raise EventEditionValidationError("event.evidence_invalid") from None
    for article in draft.articles:
        try:
            article.check_display()  # Also reject model_copy mutations at E1.
        except ValueError:
            raise EventEditionValidationError("event.schema_invalid") from None
        binding = bindings[article.event_id]
        plan = plan_by_id[article.event_id]
        validate_context_event(plan.source_event, draft.documents, observed_at=observed_at)
        identity_refs = {
            *binding.identity.stage_refs,
            *binding.story_hint.explicit_thread_refs,
            *binding.delta.evidence_refs,
        }
        if draft.content_contract_version == 1 and (
            not set(plan.assigned_refs)
            <= set(event_context_refs(plan.source_event)) | identity_refs
        ):
            # Source time refs are protected too and may live outside fact spans.
            time_refs = {
                ref
                for doc in draft.documents
                for point in (doc.time.occurred_at, doc.time.announced_at)
                for ref in point.source_refs
            }
            if (
                not set(plan.assigned_refs)
                <= set(event_context_refs(plan.source_event)) | time_refs | identity_refs
            ):
                raise EventEditionValidationError("event.evidence_invalid")
        registry = {
            label: entity.registry_key
            for entity in binding.entities
            if entity.registry_key is not None
            for label in entity.entity.source_labels
        }
        facts = normalize_fact_bindings(
            draft.documents, plan.source_event.facts, approved_registry=registry
        )
        if facts != binding.facts:
            raise EventEditionValidationError("event.fact_unsupported")
        fact_ids = {f.fact_id for f in facts}
        if (
            len(set(article.fact_ids)) != len(article.fact_ids)
            or not set(article.fact_ids) <= fact_ids
            or not set(plan.required_fact_ids) <= set(article.fact_ids)
        ):
            raise EventEditionValidationError("event.fact_unsupported")
        assigned = set(plan.assigned_refs)
        refs = (
            *article.source_refs,
            *article.background_refs,
            *article.meaning.refs,
            *article.reaction.refs,
        )
        if not set(refs) <= assigned:
            raise EventEditionValidationError("event.evidence_invalid")
        if draft.content_contract_version == 1:
            validate_claim(article.headline, article.source_refs, draft)
            validate_claim(article.what_changed, article.source_refs, draft)
            validate_fact_roles(article.headline, binding, plan.source_event, draft.documents)
            validate_fact_roles(
                article.what_changed,
                binding,
                plan.source_event,
                draft.documents,
                require_assertion=True,
            )
            entities = {e.entity.entity_id: e.entity for e in binding.entities}
            for entity_id in (*binding.identity.actor_ids, *binding.identity.object_ids):
                if not any(
                    _normal(label) in _normal(article.what_changed)
                    for label in entities[entity_id].source_labels
                ):
                    raise EventEditionValidationError("event.entity_unsupported")
        for fact in facts:
            if fact.fact_id not in article.fact_ids:
                continue
            if not set(fact.source_refs) <= set(article.source_refs):
                raise EventEditionValidationError("event.evidence_invalid")
        if article.background is not None:
            if not article.background_refs or not set(article.background_refs) <= set(
                plan.source_event.background_refs
            ):
                raise EventEditionValidationError("event.evidence_invalid")
            validate_claim(article.background, article.background_refs, draft)
            if any(f.value_kind == "text" for f in plan.source_event.facts):
                validate_text_actions(
                    article.background,
                    plan.source_event,
                    draft.documents,
                    proof_refs=article.background_refs,
                )
        elif article.background_refs:
            raise EventEditionValidationError("event.evidence_invalid")
        meaning = article.meaning
        if meaning.mode != "unavailable":
            if not set(meaning.refs) <= set(plan.source_event.meaning_refs):
                raise EventEditionValidationError("event.evidence_invalid")
            validate_claim(meaning.text or "", meaning.refs, draft)
            if any(f.value_kind == "text" for f in plan.source_event.facts):
                for text in (meaning.text, meaning.mechanism, *meaning.assumptions):
                    if text:
                        validate_text_actions(
                            text, plan.source_event, draft.documents, proof_refs=meaning.refs
                        )
            if meaning.mechanism is not None:
                validate_claim(meaning.mechanism, meaning.refs, draft)
            for assumption in meaning.assumptions:
                validate_claim(assumption, meaning.refs, draft)
            if meaning.mode == "conditional" and not _CONDITIONAL.search(meaning.text or ""):
                raise EventEditionValidationError("event.meaning_unbound")
        reaction = article.reaction
        if reaction.status != "unavailable":
            if not set(reaction.refs) <= set(plan.source_event.reaction_refs):
                raise EventEditionValidationError("event.evidence_invalid")
            validate_claim(reaction.text or "", reaction.refs, draft)
            if any(f.value_kind == "text" for f in plan.source_event.facts):
                validate_text_actions(
                    reaction.text or "",
                    plan.source_event,
                    draft.documents,
                    proof_refs=reaction.refs,
                )
            if reaction.observed_at is not None and reaction.observed_at > observed_at:
                raise EventEditionValidationError("event.reaction_unbound")
            if reaction.status == "observed":
                proof = " ".join(resolve_context_ref(r, lookup) for r in reaction.refs)
                if reaction.asset_id is None or reaction.asset_id not in proof:
                    raise EventEditionValidationError("event.reaction_unbound")
                for stamp in (reaction.window_start, reaction.window_end, reaction.observed_at):
                    if stamp is None or not any(
                        value in proof
                        for value in (stamp.isoformat(), stamp.isoformat().replace("+00:00", "Z"))
                    ):
                        raise EventEditionValidationError("event.reaction_unbound")
                assert reaction.baseline_ref is not None and reaction.value_ref is not None

                def source_unit(ref: ContextRef) -> str | None:
                    doc = lookup[(ref.document_id, ref.revision_id)]
                    chunk = next(c for c in doc.chunks if c.chunk_id == ref.chunk_id)
                    literal = chunk.text[ref.start : min(len(chunk.text), ref.end + 16)]
                    match = re.match(r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?\s*(%|[A-Z]{3}\b)", literal)
                    return match.group(1) if match else None

                baseline_unit = source_unit(reaction.baseline_ref)
                if baseline_unit is None or baseline_unit != source_unit(reaction.value_ref):
                    raise EventEditionValidationError("event.reaction_unbound")
        for ref in refs:
            resolve_context_ref(ref, lookup)
    reference_ids = {p.event_id for p in plans if p.placement == "reference"}
    if {r.event_id for r in draft.reference_panels} != reference_ids:
        raise EventEditionValidationError("event.context_unbound")
    for reference in draft.reference_panels:
        plan = plan_by_id[reference.event_id]
        binding = bindings[reference.event_id]
        validate_context_event(plan.source_event, draft.documents, observed_at=observed_at)
        if (
            set(reference.fact_ids) != {f.fact_id for f in binding.facts}
            or not set(reference.source_refs) <= set(plan.assigned_refs)
            or not {r for f in binding.facts for r in f.source_refs} <= set(reference.source_refs)
        ):
            raise EventEditionValidationError("event.context_unbound")
    if draft.content_contract_version == 2 and (draft.digests or draft.context_panels):
        raise EventEditionValidationError("event.evidence_invalid")
    for digest in draft.digests:
        digest_article = next((a for a in draft.articles if a.event_id == digest.event_id), None)
        if (
            digest_article is None
            or not set(digest.fact_ids) <= set(digest_article.fact_ids)
            or not set(digest.source_refs) <= set(digest_article.source_refs)
        ):
            raise EventEditionValidationError("event.digest_unbound")
        validate_claim(digest.text, digest.source_refs, draft)
        validate_fact_roles(
            digest.text,
            bindings[digest.event_id],
            plan_by_id[digest.event_id].source_event,
            draft.documents,
            require_assertion=True,
        )
    if len({d.event_id for d in draft.digests}) != len(draft.digests):
        raise EventEditionValidationError("event.digest_unbound")
    for panel in draft.context_panels:
        if panel.event_id not in plan_by_id or not set(panel.source_refs) <= set(
            plan_by_id[panel.event_id].assigned_refs
        ):
            raise EventEditionValidationError("event.context_unbound")
        validate_claim(panel.text, panel.source_refs, draft)
    for impact in draft.asset_impacts:
        if (
            impact.event_id not in bindings
            or not set(impact.fact_ids) <= {f.fact_id for f in bindings[impact.event_id].facts}
            or not set(impact.source_refs) <= set(plan_by_id[impact.event_id].assigned_refs)
        ):
            raise EventEditionValidationError("event.asset_unbound")
        validate_claim(impact.mechanism, impact.source_refs, draft)
        if impact.condition is not None:
            validate_claim(impact.condition, impact.source_refs, draft)
    if len(
        {f.story_id for f in draft.follow_ups if not isinstance(f, NumericFollowUpEntry)}
    ) != sum(not isinstance(f, NumericFollowUpEntry) for f in draft.follow_ups) or len(
        {p.story_id for p in draft.story_proposals}
    ) != len(draft.story_proposals):
        raise EventEditionValidationError("event.follow_up_unbound")
    for follow_up in draft.follow_ups:
        if isinstance(follow_up, NumericFollowUpEntry):
            numeric_binding = bindings.get(follow_up.event_id)
            numeric_plan = plan_by_id.get(follow_up.event_id)
            if (
                numeric_binding is None
                or numeric_plan is None
                or not set(follow_up.source_refs) <= set(numeric_plan.assigned_refs)
            ):
                raise EventEditionValidationError("event.follow_up_unbound")
            numeric_facts = {f.fact_id: f for f in numeric_binding.facts}
            if not set(follow_up.fact_ids) <= set(numeric_facts) or any(
                numeric_facts[f].canonical.status != "actual"
                or numeric_facts[f].canonical.metric_key_hash is None
                for f in follow_up.fact_ids
            ):
                raise EventEditionValidationError("event.follow_up_unbound")
            if not any(
                numeric_facts[f].original_value.replace(",", "")
                in follow_up.numeric_values.current.replace(",", "")
                for f in follow_up.fact_ids
            ):
                raise EventEditionValidationError("event.follow_up_unbound")
            continue  # Numeric owner also checks the complete seven-field E1 value.
        proposal = next(
            (p for p in draft.story_proposals if p.story_id == follow_up.story_id), None
        )
        prior = next(
            (
                r
                for r in story_baseline
                if r.story_id == follow_up.story_id and r.segment == draft.segment
            ),
            None,
        )
        if proposal is None:
            if (
                prior is None
                or follow_up.event_id not in prior.event_ids
                or follow_up.event_id not in bindings
                or prior.latest_state != follow_up.reader_state
                or prior.last_evidence_at != follow_up.last_evidence_at
                or follow_up.basis != "committed_history"
                or follow_up.question != (prior.open_question.text if prior.open_question else None)
                or follow_up.next_check != prior.next_check
                or follow_up.verified_delta_text
                != (prior.verified_delta.reader_text if prior.verified_delta else None)
                or not set(follow_up.source_refs)
                <= set(plan_by_id[follow_up.event_id].assigned_refs)
                or bindings[follow_up.event_id].story_hint.story_key_hash != prior.story_id
                or bindings[follow_up.event_id].identity.actor_ids != prior.subject_ids
                or bindings[follow_up.event_id].identity.object_ids != prior.object_ids
            ):
                raise EventEditionValidationError("event.follow_up_unbound")
            continue
        if (
            follow_up.event_id not in bindings
            or follow_up.basis != "current_delta"
            or follow_up.last_evidence_at != proposal.next_record.last_evidence_at
            or proposal.next_record.latest_state != follow_up.reader_state
            or follow_up.event_id not in proposal.event_ids
            or not set(follow_up.source_refs) <= set(plan_by_id[follow_up.event_id].assigned_refs)
        ):
            raise EventEditionValidationError("event.follow_up_unbound")
        if follow_up.verified_delta_text != (
            proposal.next_record.verified_delta.reader_text
            if proposal.next_record.verified_delta
            else None
        ):
            raise EventEditionValidationError("event.follow_up_unbound")
        if follow_up.verified_delta_text is not None:
            validate_claim(follow_up.verified_delta_text, follow_up.source_refs, draft)
        prior = next(
            (
                r
                for r in story_baseline
                if r.story_id == follow_up.story_id and r.segment == draft.segment
            ),
            None,
        )
        if follow_up.question is not None:
            if (
                proposal.next_record.open_question is None
                or proposal.next_record.open_question.text != follow_up.question
            ):
                raise EventEditionValidationError("event.follow_up_unbound")
            if prior is None or prior.open_question != proposal.next_record.open_question:
                validate_claim(follow_up.question, follow_up.source_refs, draft)
        if follow_up.next_check != proposal.next_record.next_check:
            raise EventEditionValidationError("event.follow_up_unbound")
        trusted_history = set(prior.source_refs) if prior is not None else set()
        for receipt in proposal.next_record.source_refs:
            if receipt in trusted_history:
                continue
            if source_receipt(receipt.context_ref, draft.documents) != receipt:
                raise EventEditionValidationError("event.follow_up_unbound")


def usable_digest(text: str) -> bool:
    return len(text) <= 140 and bound_at_sentence(text, 140, require_complete=True) == text
