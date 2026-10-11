"""Deterministic native rendering and terminal public projection; no rewriting."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import quote

from investo._internal.disclaimer import DISCLAIMER_CRYPTO_V3, DISCLAIMER_V3
from investo._internal.event_context import resolve_context_ref
from investo._internal.event_identity import source_receipt
from investo._internal.event_public_text import markdown_literal as _plain
from investo._internal.event_v3_contract import fact_source_map, usable_digest
from investo.models.event_context import ContextRef
from investo.models.event_document import (
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
from investo.publisher.verifier import SHORT_DISCLAIMER_CRYPTO, SHORT_DISCLAIMER_EQUITY

_AVAILABILITY = {
    "normal": "검증된 사건을 중심으로 정리했습니다.",
    "quiet": "수집된 근거에서 새로운 주요 사건을 선정하지 못했습니다.",
    "source_limited": "출처 수집이 제한되어 중요 사건을 판단하기 어렵습니다.",
}
_STATUS = {"actual": "실제", "forecast": "예상", "scheduled": "예정", "quoted_opinion": "인용 발언"}


def _link(href: str) -> str:
    return quote(href, safe=":/?=&%+@;,$!~-_.")


@dataclass(frozen=True, slots=True)
class EventEditionRegions:
    event_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    follow_up_ids: tuple[str, ...]


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


def render_event_edition(draft: EventEditionDraft, *, retain_invalid_digests: bool = False) -> str:
    lines = [
        f"# {draft.target_date.isoformat()} {SEGMENT_LABELS[draft.segment]} 시황",
        "",
        SHORT_DISCLAIMER_CRYPTO if draft.segment == "crypto" else SHORT_DISCLAIMER_EQUITY,
        "",
        "<!-- investo:edition schema=3 -->",
        f"<!-- investo:availability {draft.availability.status} -->",
        "",
        _AVAILABILITY[draft.availability.status],
        "",
    ]
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
    if draft.articles:
        lines.extend(("## 한눈에 보기", ""))
        digests = {
            d.event_id: d for d in draft.digests if retain_invalid_digests or usable_digest(d.text)
        }
        for article in draft.articles[:3]:
            lines.append(
                "- "
                + _plain(
                    digests[article.event_id].text
                    if article.event_id in digests
                    else article.headline
                )
            )
        lines.append("")
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
        lines.extend(
            (
                f"<!-- investo:block event:{article.event_id} -->",
                f"## {_plain(article.headline)}",
                "",
                _plain(article.what_changed),
                "",
            )
        )
        for fact in binding.facts:
            if fact.fact_id not in article.fact_ids:
                continue
            fact_source = fact_source_map(binding, source, draft.documents)[fact.fact_id]
            label = (
                " ".join(resolve_context_ref(r, draft.documents) for r in fact_source.metric_refs)
                or fact.canonical.predicate
            )
            detail = " · ".join(
                v
                for v in (
                    label,
                    fact.original_value,
                    fact.canonical.unit,
                    fact.canonical.period,
                    _STATUS[fact.canonical.status],
                )
                if v
            )
            lines.extend((f"<!-- investo:fact {fact.fact_id} -->", f"- {_plain(detail)}"))
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
                f"사건 시점: {point.value.isoformat() if point.value else '확인 불가'} "
                f"({point.precision})",
                "",
            )
        )
        if article.background:
            lines.extend((f"배경: {_plain(article.background)}", ""))
        meaning = article.meaning.text or "시장에 미치는 의미는 확인하지 못했습니다."
        lines.extend((f"의미: {_plain(meaning)}", ""))
        if article.meaning.mode == "conditional":
            lines.extend(
                (
                    f"작동 경로: {_plain(article.meaning.mechanism)}",
                    "전제: " + "; ".join(_plain(a) for a in article.meaning.assumptions),
                    "",
                )
            )
        reaction = article.reaction.text or "시장 반응은 확인하지 못했습니다."
        if article.reaction.attribution == "coincidence_only":
            reaction += " 사건과의 인과관계는 확인되지 않았습니다."
        lines.extend((f"반응: {_plain(reaction)}", ""))
        limits = support_vector_reader_limits(
            support.model_copy(
                update={"meaning": article.meaning.mode, "reaction": article.reaction.status}
            )
        )
        if limits:
            lines.extend(("확인 한계: " + " · ".join(limits), ""))
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
            entities = {e.entity.entity_id: e.entity.display_label for e in binding.entities}
            for fact in binding.facts:
                label = " ".join(
                    resolve_context_ref(r, draft.documents)
                    for r in fact_sources[fact.fact_id].metric_refs
                )
                detail = " · ".join(
                    value
                    for value in (
                        entities[fact.canonical.subject_id],
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
    if draft.market_reference.anchors:
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
        lines.extend(("</details>", ""))
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
        vector = vectors[article.event_id]
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
                    mode=article.meaning.mode,
                    text=article.meaning.text,
                    mechanism=article.meaning.mechanism,
                    assumptions=article.meaning.assumptions,
                    source_refs=receipts(article.meaning.refs),
                ),
                reaction=PublicReactionView(
                    status=article.reaction.status,
                    attribution=article.reaction.attribution,
                    asset_id=article.reaction.asset_id,
                    text=article.reaction.text,
                    window_start=article.reaction.window_start,
                    window_end=article.reaction.window_end,
                    observed_at=article.reaction.observed_at,
                    source_refs=receipts(article.reaction.refs),
                ),
                support=vector.model_copy(
                    update={"meaning": article.meaning.mode, "reaction": article.reaction.status}
                ),
                source_refs=receipts(article.source_refs),
                story_id=story,
            )
        )
    projection = PublishedEventEdition(
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
