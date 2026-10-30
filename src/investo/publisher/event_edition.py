"""Deterministic native rendering and terminal public projection; no rewriting."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import quote

from investo._internal.crypto_indicators import render_exchange_flow_reference
from investo._internal.disclaimer import DISCLAIMER_CRYPTO_V3, DISCLAIMER_V3
from investo._internal.event_context import resolve_context_ref
from investo._internal.event_identity import source_receipt
from investo._internal.event_public_text import markdown_literal as _plain
from investo._internal.event_v3_contract import fact_source_map, usable_digest
from investo._internal.market_reference import render_option_expiry_reference
from investo._internal.network_activity import render_network_activity_reference
from investo.models.event_article import SentenceClaim
from investo.models.event_context import (
    ContextFactDraft,
    ContextRef,
    EventContextDocument,
    EventSupportVector,
)
from investo.models.event_document import (
    ArticleDisplayBlock,
    EventArticle,
    EventEditionDraft,
    NumericFollowUpEntry,
    PublicAssetImpactView,
    PublicContextPanel,
    PublicDigestView,
    PublicEditionView,
    PublicEventTime,
    PublicEventView,
    PublicFactCorrection,
    PublicFactView,
    PublicFollowUpView,
    PublicMeaningView,
    PublicNumericFollowUpView,
    PublicReactionView,
    PublicReferencePanel,
    PublicTimeValue,
    PublishedEventEdition,
)
from investo.models.event_story import SealedStorySourceRef, StoryPublicationDelta
from investo.models.segments import SEGMENT_LABELS
from investo.publisher.event_quality import support_vector_reader_limits

_AVAILABILITY = {
    "normal": "검증된 사건을 중심으로 정리했습니다.",
    "quiet": "수집된 근거에서 새로운 주요 사건을 선정하지 못했습니다.",
    "source_limited": "출처 수집이 제한되어 중요 사건을 판단하기 어렵습니다.",
}
_STATUS = {"actual": "실제", "forecast": "예상", "scheduled": "예정", "quoted_opinion": "인용 발언"}


def _link(href: str) -> str:
    return quote(href, safe=":/?=&%+@;,$!~-_.")


def _fact_subject(source: ContextFactDraft, documents: tuple[EventContextDocument, ...]) -> str:
    # Fact subjects need not be one of the event's actor/object identities.
    return " ".join(resolve_context_ref(ref, documents) for ref in source.subject_refs)


@dataclass(frozen=True, slots=True)
class EventEditionRegions:
    event_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    follow_up_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArticleBody:
    markdown: str
    # Offsets are renderer-owned, independent of visible labels and grouping.
    field_ranges: tuple[tuple[str, int, int], ...]


def _reviewed_facets(
    article: EventArticle,
    draft: EventEditionDraft,
    vector: EventSupportVector,
) -> tuple[EventSupportVector, tuple[ContextRef, ...], SentenceClaim | None]:
    if article.content_contract_version == 1:
        return (
            vector.model_copy(
                update={"meaning": article.meaning.mode, "reaction": article.reaction.status}
            ),
            article.meaning.refs,
            None,
        )
    record = next(r for r in draft.article_readiness if r.composition.event_id == article.event_id)
    answered = {q.question_id for q in record.review.questions if q.verdict == "answered"}
    why_ids = {
        sid
        for answer in record.composition.answers
        if answer.question_id == "why" and "why" in answered
        for sid in answer.sentence_ids
    }
    why_claim_ids = {
        cid
        for sentence in record.composition.narrative.sentences
        if sentence.sentence_id in why_ids
        for cid in sentence.claim_ids
    }
    why_claims = tuple(c for c in record.composition.claims if c.claim_id in why_claim_ids)
    why_refs = tuple(dict.fromkeys(r for c in why_claims for r in c.source_refs))
    reaction_ids = {
        sid
        for answer in record.composition.answers
        if answer.question_id == "reaction" and "reaction" in answered
        for sid in answer.sentence_ids
    }
    reaction_claim_ids = {
        cid
        for sentence in record.composition.narrative.sentences
        if sentence.sentence_id in reaction_ids
        for cid in sentence.claim_ids
    }
    reaction = next(
        (
            c
            for c in record.composition.claims
            if c.claim_id in reaction_claim_ids and c.kind == "observation"
        ),
        None,
    )
    return (
        vector.model_copy(
            update={
                "meaning": "conditional"
                if any(c.kind == "conditional_analysis" for c in why_claims)
                else "source_reported"
                if why_claims
                else "unavailable",
                "reaction": "observed"
                if reaction is not None and reaction.kind == "observation"
                else "unavailable",
            }
        ),
        why_refs,
        reaction,
    )


def render_article_body(
    article: EventArticle,
    *,
    fact_tables: Mapping[str, tuple[str, ...]] | None = None,
    for_validation: bool = False,
) -> ArticleBody:
    """Compose checked evidence text as prose by default, without new claims."""
    article.check_display()
    if article.narrative is not None:
        narrative_pieces: list[str] = []
        sentence_ranges: list[tuple[str, int, int]] = []
        offset = 0
        for narrative_block in article.narrative.blocks:
            if narrative_block.kind == "fact_table":
                if fact_tables is None or not set(narrative_block.fact_ids) <= fact_tables.keys():
                    raise ValueError("article.fact_table_unbound")
                table_lines: list[str] = []
                if not for_validation:
                    table_lines.extend(
                        ("| 주체 | 항목 | 값 | 단위 | 기간 | 구분 |", "|---|---|---|---|---|---|")
                    )
                for fact_id in narrative_block.fact_ids:
                    row = fact_tables[fact_id]
                    table_lines.append(f"<!-- investo:fact {fact_id} -->")
                    table_lines.append(
                        "- " + " · ".join(_plain(cell) for cell in row)
                        if for_validation
                        else "| " + " | ".join(_plain(cell) for cell in row) + " |"
                    )
                piece = "\n".join(table_lines) + "\n\n"
                narrative_pieces.append(piece)
                offset += len(piece)
                continue
            for index, sentence in enumerate(narrative_block.sentences):
                prefix = "- " if narrative_block.kind == "bullets" else ""
                prefix = (" " if index and narrative_block.kind == "paragraph" else "") + prefix
                piece = prefix + _plain(sentence.text)
                sentence_ranges.append(
                    ("sentence:" + sentence.sentence_id, offset, offset + len(piece))
                )
                narrative_pieces.append(piece)
                offset += len(piece)
                if narrative_block.kind == "bullets":
                    narrative_pieces.append("\n")
                    offset += 1
            if narrative_block.sentences:
                narrative_pieces.append("\n\n")
                offset += 2
        return ArticleBody("".join(narrative_pieces).rstrip(), tuple(sentence_ranges))
    parts = article.text_parts()
    blocks = article.display_blocks or (ArticleDisplayBlock(parts=tuple(parts)),)
    labels = {
        "what_changed": "핵심 변화",
        "background": "배경",
        "meaning": "해석",
        "reaction": "관측 반응",
    }
    pieces: list[str] = []
    ranges: list[tuple[str, int, int]] = []
    length = 0

    def append(text: str, owner: str | None = None) -> None:
        nonlocal length
        if owner is not None:
            ranges.append((owner, length, length + len(text)))
        pieces.append(text)
        length += len(text)

    for block in blocks:
        for index, part in enumerate(block.parts):
            separator = (" " if block.kind == "paragraph" else "\n") if index else ""
            text = parts[part]
            if not re.search(r"[.!?。…][\"'\u2019\u201d)]*$", text):
                text += "."
            if part == "reaction" and article.reaction.attribution == "coincidence_only":
                text += " 사건과의 인과관계는 확인되지 않았습니다."
            prefix = (
                f"- {labels[part]}: "
                if block.kind == "labeled_list"
                else "- "
                if block.kind == "bullets"
                else ""
            )
            append(separator + prefix + _plain(text), part)
        append("\n\n")
        if "meaning" in block.parts and article.meaning.mode == "conditional":
            append("> 조건부 해석의 경로: " + _plain(article.meaning.mechanism), "meaning")
            append("\n>\n")
            append(
                "> 전제: " + "; ".join(_plain(a) for a in article.meaning.assumptions), "meaning"
            )
            append("\n\n")
    return ArticleBody("".join(pieces).rstrip(), tuple(ranges))


def edition_regions(markdown: str, draft: EventEditionDraft) -> EventEditionRegions:
    """Read-only identity checks against deterministic typed ownership."""
    for article in draft.articles:
        marker = f"<!-- investo:block event:{article.event_id} -->"
        close = f"<!-- /investo:block event:{article.event_id} -->"
        if markdown.count(marker) != 1 or markdown.count(close) != 1:
            raise ValueError("event.terminal_mismatch")
    if "<!-- investo:edition schema=3 -->" not in markdown or "## 면책조항" not in markdown:
        raise ValueError("event.structure_invalid")
    return EventEditionRegions(
        event_ids=tuple(a.event_id for a in draft.articles),
        fact_ids=tuple(f for a in draft.articles for f in a.fact_ids),
        follow_up_ids=tuple(
            f.story_id for f in draft.follow_ups if not isinstance(f, NumericFollowUpEntry)
        ),
    )


def render_event_edition(
    draft: EventEditionDraft,
    *,
    retain_invalid_digests: bool = False,
    for_validation: bool = False,
) -> str:
    lines = [
        f"# {draft.target_date.isoformat()} {SEGMENT_LABELS[draft.segment]} 시황",
        "",
        "<!-- investo:edition schema=3 -->",
        f"<!-- investo:availability {draft.availability.status} -->",
        "",
    ]
    if not draft.articles:
        lines.extend((_AVAILABILITY[draft.availability.status], ""))
    if draft.articles:
        digests = {
            d.event_id: d for d in draft.digests if retain_invalid_digests or usable_digest(d.text)
        }
        overview = [digests[a.event_id].text for a in draft.articles if a.event_id in digests]
        if overview:
            lines.extend(("## 주요 소식", "", " ".join(_plain(t) for t in overview), ""))
    bindings = {b.identity.event_id: b for b in draft.bindings}
    plans = {p.event_id: p for p in draft.editorial_plan.events}
    vectors = {
        p.event_id: v for p, v in zip(draft.editorial_plan.events, draft.support, strict=True)
    }
    for article in draft.articles:
        support = vectors[article.event_id]
        binding = bindings[article.event_id]
        source = plans[article.event_id].source_event
        doc = draft.documents[source.item_ids[0] - 1]
        article_opening = (
            f"<!-- investo:block event:{article.event_id} -->",
            f"## {_plain(article.headline)}",
            "",
        )
        fact_lines: list[str] = []
        fact_rows: list[tuple[str, ...]] = []
        fact_table_by_id: dict[str, tuple[str, ...]] = {}
        fact_sources = fact_source_map(binding, source, draft.documents)
        for fact in binding.facts:
            if fact.fact_id not in article.fact_ids:
                continue
            fact_source = fact_sources[fact.fact_id]
            label = (
                " ".join(resolve_context_ref(r, draft.documents) for r in fact_source.metric_refs)
                or fact.canonical.predicate
            )
            subject = _fact_subject(fact_source, draft.documents)
            detail = " · ".join(
                v
                for v in (
                    subject,
                    label,
                    fact.original_value,
                    fact.canonical.unit,
                    fact.canonical.period,
                    _STATUS[fact.canonical.status],
                )
                if v
            )
            fact_lines.extend((f"<!-- investo:fact {fact.fact_id} -->", f"- {_plain(detail)}"))
            fact_rows.append(
                (
                    subject,
                    label,
                    fact.original_value,
                    fact.canonical.unit or "—",
                    fact.canonical.period or "—",
                    _STATUS[fact.canonical.status],
                )
            )
        for fact, row in zip(
            (f for f in binding.facts if f.fact_id in article.fact_ids), fact_rows, strict=True
        ):
            fact_table_by_id[fact.fact_id] = row
        lines.extend(
            (
                *article_opening,
                render_article_body(
                    article, fact_tables=fact_table_by_id, for_validation=for_validation
                ).markdown,
                "",
            )
        )
        inline_fact_ids = (
            {fact_id for block in article.narrative.blocks for fact_id in block.fact_ids}
            if article.narrative is not None
            else set()
        )
        if for_validation:
            # Table masking and collapsed UI must never hide original hard findings.
            # This representation is used only by the sole pre-publication scanner.
            lines.extend((*fact_lines, ""))
        elif article.show_facts and article.narrative is None:
            lines.extend(
                f"<!-- investo:fact {fact.fact_id} -->"
                for fact in binding.facts
                if fact.fact_id in article.fact_ids
            )
            lines.extend(
                (
                    "",
                    "### 주요 사실",
                    "",
                    "| 주체 | 항목 | 값 | 단위 | 기간 | 구분 |",
                    "|---|---|---|---|---|---|",
                )
            )
            lines.extend(
                "| " + " | ".join(_plain(cell) for cell in row) + " |" for row in fact_rows
            )
            lines.append("")
        for correction in binding.delta.correction_claims:
            for ref in correction.source_refs:
                lines.extend(
                    ("정정 근거: " + _plain(resolve_context_ref(ref, draft.documents)), "")
                )
        point = (
            doc.time.occurred_at
            if doc.time.occurred_at.precision != "unknown"
            else doc.time.announced_at
        )
        lines.extend(
            (
                "",
                '<details markdown="1">',
                "<summary>출처·시점·확인 범위</summary>",
                "",
                f"사건 시점: {point.value.isoformat() if point.value else '확인 불가'} "
                f"({point.precision})",
                "",
            )
        )
        if doc.time.published_at.value is not None:
            lines.extend(
                (
                    f"원문 게시: {doc.time.published_at.value.isoformat()} "
                    f"({doc.time.published_at.precision})",
                    "",
                )
            )
        if not for_validation:
            if article.narrative is not None:
                for row_fact_id, row in fact_table_by_id.items():
                    if row_fact_id not in inline_fact_ids:
                        lines.extend(
                            (
                                f"<!-- investo:fact {row_fact_id} -->",
                                "- " + " · ".join(_plain(cell) for cell in row),
                            )
                        )
                lines.append("")
            elif not article.show_facts:
                lines.extend((*fact_lines, ""))
        reader_support, _, _ = _reviewed_facets(article, draft, support)
        limits = support_vector_reader_limits(reader_support)
        if article.content_contract_version == 2 and reader_support.reaction == "unavailable":
            lines.extend(("시장 반응은 확인하지 못했습니다.", ""))
        if limits:
            lines.extend(("확인 한계: " + " · ".join(limits), ""))
        lines.extend(("</details>", ""))
        links = sorted(
            {
                href
                for r in dict.fromkeys(
                    (
                        *article.source_refs,
                        *article.background_refs,
                        *article.meaning.refs,
                        *article.reaction.refs,
                        *(r for c in binding.delta.correction_claims for r in c.source_refs),
                    )
                )
                if (href := source_receipt(r, draft.documents).source_href) is not None
            }
        )
        lines.extend(
            (
                "출처: "
                + " · ".join(f"[원문 {i}]({_link(href)})" for i, href in enumerate(links, 1))
                if links
                else "출처 위치 확인 불가",
            )
        )
        for visual in draft.visual_inputs:
            if visual.event_id == article.event_id:
                lines.extend(
                    (
                        "",
                        f"![확인된 사건 근거]({visual.relative_path}#gh-light-mode-only)",
                        f"![확인된 사건 근거]({visual.dark_relative_path}#gh-dark-mode-only)",
                        "출처: 위 사건의 검증된 사실 · 자체 제작 시각 자료",
                        "",
                    )
                )
        lines.extend((f"<!-- /investo:block event:{article.event_id} -->", ""))
    for panel in draft.context_panels:
        lines.extend((f"### 관련 {panel.kind}", "", _plain(panel.text), ""))
        hrefs = sorted(
            {
                receipt.source_href
                for ref in panel.source_refs
                if (receipt := source_receipt(ref, draft.documents)).source_href is not None
            }
        )
        lines.extend(("출처: " + " · ".join(f"[원문]({_link(href)})" for href in hrefs), ""))
    if draft.asset_impacts:
        lines.extend(("## 연결된 자산", ""))
        for impact in draft.asset_impacts:
            lines.extend(
                (
                    f"- {_plain(impact.asset_id)}: {_plain(impact.mechanism)}"
                    + (f" (조건: {_plain(impact.condition)})" if impact.condition else ""),
                    "",
                )
            )
    if draft.follow_ups:
        lines.extend(("## 후속 확인", ""))
        for follow_up in draft.follow_ups:
            if isinstance(follow_up, NumericFollowUpEntry):
                card = follow_up.numeric_values
                lines.extend(
                    (
                        f"### 관찰 신호: {_plain(card.signal)}",
                        "",
                        f"출처: {_plain(card.source)}",
                        f"현재: {_plain(card.current)}",
                        f"상방 확인 조건: {_plain(card.bullish_trigger)}",
                        f"하방 확인 조건: {_plain(card.bearish_trigger)}",
                        f"신뢰도: {card.confidence}",
                        f"관심 영향: {_plain(card.implication)}",
                        "",
                    )
                )
                continue
            lines.extend(
                (
                    f"<!-- investo:story {follow_up.story_id} -->",
                    f"- 상태: {follow_up.reader_state}",
                )
            )
            if follow_up.last_evidence_at:
                lines.append(f"  마지막 근거 확인: {follow_up.last_evidence_at.isoformat()}")
            if follow_up.basis == "committed_history":
                lines.append(
                    "  이전에 확인한 상태이며 이번 관측에서 새 변화는 확인하지 못했습니다."
                )
            if follow_up.verified_delta_text:
                lines.append(f"  확인된 변화: {_plain(follow_up.verified_delta_text)}")
            if follow_up.question:
                lines.append(f"  확인할 질문: {_plain(follow_up.question)}")
            if (
                follow_up.next_check
                and follow_up.next_check.kind == "scheduled_fact"
                and follow_up.next_check.scheduled_time is not None
            ):
                lines.append(
                    f"  출처에 명시된 일정: {follow_up.next_check.scheduled_time.value} "
                    f"({follow_up.next_check.scheduled_time.precision})"
                )
            lines.append("")
    if draft.reference_panels:
        lines.extend(
            (
                "## 사건 참고 자료",
                "",
                '<details markdown="1">',
                "<summary>검증된 사건 참고 자료 펼치기</summary>",
                "",
            )
        )
        for reference in draft.reference_panels:
            binding = bindings[reference.event_id]
            fact_sources = fact_source_map(
                binding, plans[reference.event_id].source_event, draft.documents
            )
            for fact in binding.facts:
                label = " ".join(
                    resolve_context_ref(r, draft.documents)
                    for r in fact_sources[fact.fact_id].metric_refs
                )
                detail = " · ".join(
                    value
                    for value in (
                        _fact_subject(fact_sources[fact.fact_id], draft.documents),
                        label or fact.canonical.predicate,
                        fact.original_value,
                        fact.canonical.unit,
                        fact.canonical.period,
                        _STATUS[fact.canonical.status],
                    )
                    if value
                )
                lines.extend((f"<!-- investo:fact {fact.fact_id} -->", f"- {_plain(detail)}"))
            hrefs = sorted(
                {
                    r.source_href
                    for ref in reference.source_refs
                    if (r := source_receipt(ref, draft.documents)).source_href
                }
            )
            lines.append("출처: " + " · ".join(f"[원문]({_link(href)})" for href in hrefs))
            lines.append("")
        lines.extend(("</details>", ""))
    if (
        draft.market_reference.anchors
        or draft.market_reference.daily_network_activity
        or draft.market_reference.daily_exchange_flows
        or draft.market_reference.calculated_option_expiries
    ):
        lines.extend(
            (
                "## 시장 기준 자료",
                "",
                '<details markdown="1">',
                "<summary>시장 기준 자료 펼치기</summary>",
                "",
            )
        )
        for anchor in draft.market_reference.anchors:
            lines.append(
                f"- {_plain(anchor.ticker)}: {anchor.close}"
                + (f" · {anchor.pct}%" if anchor.pct is not None else "")
            )
        lines.append("")
        lines.append(render_exchange_flow_reference(draft.market_reference.daily_exchange_flows))
        lines.append(
            render_network_activity_reference(draft.market_reference.daily_network_activity)
        )
        lines.append(
            render_option_expiry_reference(draft.market_reference.calculated_option_expiries)
        )
        lines.extend(("</details>", ""))
    lines.extend(("## 자료 안내", ""))
    if draft.articles:
        lines.extend((_AVAILABILITY[draft.availability.status], ""))
    price = draft.price_reference_date.isoformat() if draft.price_reference_date else "확인 불가"
    lines.extend((f"가격 기준일: {price}", ""))
    if draft.news_window:
        lines.extend(
            (
                f"뉴스 관측창: {draft.news_window.start_utc.isoformat()} ~ "
                f"{draft.news_window.end_utc.isoformat()} (종료 미포함)",
                "",
            )
        )
    lines.extend((DISCLAIMER_CRYPTO_V3 if draft.segment == "crypto" else DISCLAIMER_V3, ""))
    return "\n".join(lines)


def project_event_edition(
    draft: EventEditionDraft,
    markdown: str,
    *,
    story_deltas: tuple[StoryPublicationDelta, ...] = (),
) -> PublicEditionView:
    """Called only by the existing finalizer after terminal validation."""

    def receipts(refs: tuple[ContextRef, ...]) -> tuple[SealedStorySourceRef, ...]:
        return tuple(source_receipt(r, draft.documents) for r in dict.fromkeys(refs))

    events = []
    bindings = {b.identity.event_id: b for b in draft.bindings}
    plans = {p.event_id: p for p in draft.editorial_plan.events}
    vectors = {
        p.event_id: v for p, v in zip(draft.editorial_plan.events, draft.support, strict=True)
    }
    for article in draft.articles:
        vector, why_refs, reaction_claim = _reviewed_facets(
            article, draft, vectors[article.event_id]
        )
        observation = reaction_claim.observation if reaction_claim is not None else None
        binding = bindings[article.event_id]
        entities = {e.entity.entity_id: e.entity for e in binding.entities}
        source = plans[article.event_id].source_event
        doc = draft.documents[source.item_ids[0] - 1]
        points = {
            key: PublicTimeValue(
                value=getattr(doc.time, key).value,
                precision=getattr(doc.time, key).precision,
                source_refs=receipts(getattr(doc.time, key).source_refs),
            )
            for key in ("occurred_at", "announced_at", "published_at", "received_at")
        }
        facts = []
        for fact in binding.facts:
            if fact.fact_id not in article.fact_ids:
                continue
            fs = fact_source_map(binding, source, draft.documents)[fact.fact_id]
            label = (
                " ".join(resolve_context_ref(r, draft.documents) for r in fs.metric_refs)
                or fact.canonical.predicate
            )
            facts.append(
                PublicFactView(
                    fact_id=fact.fact_id,
                    subject_id=fact.canonical.subject_id,
                    object_id=fact.canonical.object_id,
                    metric_key_hash=fact.canonical.metric_key_hash,
                    reader_label=label,
                    value=fact.original_value,
                    unit=fact.canonical.unit,
                    period=fact.canonical.period,
                    status=fact.canonical.status,
                    source_refs=receipts(fact.source_refs),
                )
            )
        story = next(
            (
                f.story_id
                for f in draft.follow_ups
                if not isinstance(f, NumericFollowUpEntry) and f.event_id == article.event_id
            ),
            None,
        )
        events.append(
            PublicEventView(
                content_contract_version=article.content_contract_version,
                article_kind=(
                    "detailed"
                    if next(
                        r
                        for r in draft.article_readiness
                        if r.composition.event_id == article.event_id
                    ).state
                    == "detailed_ready"
                    else "brief"
                )
                if article.content_contract_version == 2
                else None,
                narrative=article.narrative,
                event_id=article.event_id,
                actor_labels=tuple(entities[e].display_label for e in binding.identity.actor_ids),
                object_labels=tuple(entities[e].display_label for e in binding.identity.object_ids),
                headline=article.headline,
                what_changed=article.what_changed,
                facts=tuple(facts),
                corrections=tuple(
                    PublicFactCorrection(
                        old_fact_id=c.old_fact_id,
                        new_fact_id=c.new_fact_id,
                        source_claim=" ".join(
                            resolve_context_ref(r, draft.documents) for r in c.source_refs
                        ),
                        source_refs=receipts(c.source_refs),
                    )
                    for c in binding.delta.correction_claims
                ),
                time=PublicEventTime(
                    **points,
                    reference_period=doc.time.reference_period.value,
                    reference_period_refs=receipts(doc.time.reference_period.source_refs),
                ),
                background=article.background,
                meaning=PublicMeaningView(
                    mode=vector.meaning,
                    text=article.meaning.text,
                    mechanism=article.meaning.mechanism,
                    assumptions=article.meaning.assumptions,
                    source_refs=receipts(why_refs),
                ),
                reaction=PublicReactionView(
                    status=vector.reaction,
                    attribution=observation.attribution
                    if observation
                    else "source_reported"
                    if reaction_claim
                    else article.reaction.attribution,
                    asset_id=observation.asset_id if observation else article.reaction.asset_id,
                    text=article.reaction.text,
                    window_start=observation.window_start
                    if observation
                    else article.reaction.window_start,
                    window_end=observation.window_end
                    if observation
                    else article.reaction.window_end,
                    observed_at=observation.observed_at
                    if observation
                    else article.reaction.observed_at,
                    source_refs=receipts(
                        reaction_claim.source_refs if reaction_claim else article.reaction.refs
                    ),
                ),
                support=vector,
                source_refs=receipts(article.source_refs),
                story_id=story,
            )
        )
    projection = PublishedEventEdition(
        content_contract_version=draft.content_contract_version,
        segment=draft.segment,
        target_date=draft.target_date,
        archive_relative_path=f"archive/{draft.segment}/{draft.target_date.year}/{draft.target_date.month:02d}/{draft.target_date.isoformat()}.md",
        markdown_sha256=sha256(markdown.encode("utf-8")).hexdigest(),
        projection_sha256="0" * 64,
        price_reference_date=draft.price_reference_date,
        price_time_basis=draft.price_time_basis,
        news_window=draft.news_window,
        availability=draft.availability,
        events=tuple(events),
        context_panels=tuple(
            PublicContextPanel(
                kind=p.kind, event_id=p.event_id, text=p.text, source_refs=receipts(p.source_refs)
            )
            for p in draft.context_panels
        ),
        reference_panels=tuple(
            PublicReferencePanel(
                event_id=r.event_id,
                facts=tuple(
                    PublicFactView(
                        fact_id=f.fact_id,
                        subject_id=f.canonical.subject_id,
                        object_id=f.canonical.object_id,
                        metric_key_hash=f.canonical.metric_key_hash,
                        reader_label=(
                            " ".join(
                                resolve_context_ref(ref, draft.documents)
                                for ref in fact_source_map(
                                    bindings[r.event_id],
                                    plans[r.event_id].source_event,
                                    draft.documents,
                                )[f.fact_id].metric_refs
                            )
                            or f.canonical.predicate
                        ),
                        value=f.original_value,
                        unit=f.canonical.unit,
                        period=f.canonical.period,
                        status=f.canonical.status,
                        source_refs=receipts(f.source_refs),
                    )
                    for f in bindings[r.event_id].facts
                ),
                source_refs=receipts(r.source_refs),
            )
            for r in draft.reference_panels
        ),
        digests=tuple(
            PublicDigestView(
                event_id=d.event_id,
                fact_ids=d.fact_ids,
                text=d.text,
                source_refs=receipts(d.source_refs),
            )
            for d in draft.digests
            if usable_digest(d.text)
        ),
        follow_ups=tuple(
            PublicNumericFollowUpView(
                event_id=f.event_id,
                fact_ids=f.fact_ids,
                source_refs=receipts(f.source_refs),
                numeric_values=f.numeric_values,
            )
            if isinstance(f, NumericFollowUpEntry)
            else PublicFollowUpView(
                kind=f.kind,
                event_id=f.event_id,
                story_id=f.story_id,
                reader_state=f.reader_state,
                basis=f.basis,
                last_evidence_at=f.last_evidence_at,
                verified_delta_text=f.verified_delta_text,
                question=f.question,
                next_check=f.next_check,
                source_refs=receipts(f.source_refs),
            )
            for f in draft.follow_ups
        ),
        asset_impacts=tuple(
            PublicAssetImpactView(
                event_id=a.event_id,
                asset_id=a.asset_id,
                relation=a.relation,
                mechanism=a.mechanism,
                condition=a.condition,
                fact_ids=a.fact_ids,
                source_refs=receipts(a.source_refs),
            )
            for a in draft.asset_impacts
        ),
        story_publication_deltas=story_deltas,
    )
    projection = projection.model_copy(
        update={"projection_sha256": projection.canonical_projection_hash}
    )
    return PublicEditionView(edition=projection, rendered_markdown=markdown)
