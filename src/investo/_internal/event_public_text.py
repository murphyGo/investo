"""Terminal content selection shared by reader surfaces; never a summarizer."""

from __future__ import annotations

from investo._internal.briefing_extract import extract_conclusion
from investo.models.event_document import (
    PublicEditionView,
    PublicNumericFollowUpView,
    PublishedEventEdition,
    ReadablePublicDocument,
)


def document_excerpt(document: ReadablePublicDocument | PublishedEventEdition) -> str:
    if isinstance(document, (PublicEditionView, PublishedEventEdition)):
        edition = document.edition if isinstance(document, PublicEditionView) else document
        if edition.digests:
            return edition.digests[0].text
        if edition.events:
            return edition.events[0].headline
        return (
            "출처 수집 제한"
            if edition.availability.status == "source_limited"
            else "새로운 주요 사건을 선정하지 못했습니다."
        )
    return extract_conclusion(document.rendered_markdown) or "결론 인용을 추출하지 못했습니다."


def edition_archive_excerpt(edition: PublishedEventEdition) -> str:
    """A retrospective retains the publication's state and evidence clock."""
    digests = {d.event_id: d.text for d in edition.digests}
    parts = [digests.get(event.event_id, event.headline) for event in edition.events]
    for follow_up in edition.follow_ups:
        if isinstance(follow_up, PublicNumericFollowUpView):
            continue
        text = f"당시 상태: {follow_up.reader_state}"
        if follow_up.verified_delta_text:
            text += " · " + follow_up.verified_delta_text
        if follow_up.last_evidence_at:
            text += f" (근거 확인: {follow_up.last_evidence_at.isoformat()})"
        parts.append(text)
    return (
        "; ".join(parts)
        if parts
        else document_excerpt(
            PublicEditionView(
                edition=edition,
                rendered_markdown="",
            )
        )
    )


def markdown_literal(value: object) -> str:
    """Native public source literals cannot become Markdown or HTML attributes."""
    from html import escape

    text = escape(str(value), quote=False).replace("\n", " ").replace("\r", " ")
    text = text.replace("{", "&#123;").replace("}", "&#125;")
    for token in ("\\", "`", "*", "_", "[", "]", "#", "|", "~"):
        text = text.replace(token, "\\" + token)
    return text
