"""Closed source-assertion frames for native nonnumeric facts.

These frames prove an explicit assertion; absence of a modal or negation is
never sufficient. Unhandled grammar stays unsupported rather than acquiring
an inferred actual status. No source names or generated prose are inputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextFactFrame:
    predicate: str
    status: str
    subject: str
    action: str
    value: str
    assertion: str


_ACTIONS = {
    "launch": (
        "launched",
        "launches",
        "introduced",
        "introduces",
        "unveiled",
        "unveils",
        "released",
        "releases",
        "출시했다",
        "출시했습니다",
        "공개했다",
        "공개했습니다",
        "선보였다",
        "선보였습니다",
    ),
    "agreement": (
        "signed",
        "signs",
        "agreed",
        "reached",
        "finalized",
        "entered into",
        "체결했다",
        "체결했습니다",
        "합의했다",
        "합의했습니다",
    ),
    "decision": (
        "approved",
        "approves",
        "adopted",
        "adopts",
        "decided",
        "decides",
        "승인했다",
        "승인했습니다",
        "의결했다",
        "의결했습니다",
        "결정했다",
        "결정했습니다",
    ),
    "statement": (
        "announced",
        "announces",
        "reported",
        "reports",
        "stated",
        "states",
        "said",
        "says",
        "confirmed",
        "confirms",
        "published",
        "publishes",
        "issued",
        "issues",
        "발표했다",
        "발표했습니다",
        "밝혔다",
        "밝혔습니다",
        "공표했다",
        "공표했습니다",
    ),
    "status_change": (
        "completed",
        "completes",
        "cancelled",
        "canceled",
        "terminated",
        "terminates",
        "resumed",
        "resumes",
        "완료했다",
        "완료했습니다",
        "취소했다",
        "취소했습니다",
        "재개했다",
        "재개했습니다",
    ),
    "result": (
        "reported",
        "reports",
        "rose",
        "fell",
        "increased",
        "decreased",
        "기록했다",
        "기록했습니다",
        "증가했다",
        "증가했습니다",
        "감소했다",
        "감소했습니다",
    ),
}
_BASE_ACTIONS = {
    "launch": ("launch", "introduce", "unveil", "release"),
    "agreement": ("sign", "agree", "finalize"),
    "decision": ("approve", "adopt", "decide"),
    "statement": ("announce", "report", "state", "publish", "issue"),
    "status_change": ("complete", "cancel", "terminate", "resume"),
    "result": ("report", "rise", "fall", "increase", "decrease"),
}
_ACTION_EQUIVALENTS = (
    ("launched", "launches", "출시했다", "출시했습니다"),
    ("introduced", "introduces", "선보였다", "선보였습니다"),
    ("unveiled", "unveils", "공개했다", "공개했습니다"),
    ("released", "releases"),
    ("signed", "signs", "entered into", "체결했다", "체결했습니다"),
    ("agreed", "합의했다", "합의했습니다"),
    ("approved", "approves", "승인했다", "승인했습니다"),
    ("adopted", "adopts", "의결했다", "의결했습니다"),
    ("decided", "decides", "결정했다", "결정했습니다"),
    ("announced", "announces", "발표했다", "발표했습니다"),
    ("reported", "reports"),
    ("stated", "states", "said", "says", "밝혔다", "밝혔습니다"),
    ("published", "publishes", "공표했다", "공표했습니다"),
    ("confirmed", "confirms"),
    ("issued", "issues"),
    ("completed", "completes", "완료했다", "완료했습니다"),
    ("cancelled", "canceled", "취소했다", "취소했습니다"),
    ("terminated", "terminates"),
    ("resumed", "resumes", "재개했다", "재개했습니다"),
    ("rose", "increased", "증가했다", "증가했습니다"),
    ("fell", "decreased", "감소했다", "감소했습니다"),
    ("기록했다", "기록했습니다"),
)
_MARKERS = {
    "actual": ("actual", "reported", "실제", "실적", "발표치", "확정"),
    "forecast": ("forecast", "estimate", "estimated", "예상", "전망"),
    "scheduled": ("scheduled", "schedule", "예정"),
    "quoted_opinion": ("quoted_opinion", "opinion", "의견"),
}
_NEGATIVE = re.compile(
    r"\b(?:not|never|no|without|cannot|can't|isn't|hasn't|didn't|won't)\b"
    r"|않|못했|못하|아니|미완료|미취소|취소하지|완료하지",
    re.I,
)
_FUTURE = re.compile(
    r"\b(?:if|may|might|could|would|will|unless|conditional|pending|expected|expects|"
    r"forecast|estimated|plans?|planned|intends?|proposed|proposal)\b"
    r"|예정|계획|추진|조건|경우|전망|예상|검토|가능성",
    re.I,
)
_NESTED = re.compile(
    r"[\"'\u201c\u201d\u2018\u2019]|\b(?:that|according|reportedly|although|while|because|and|but)\b",
    re.I,
)


def action_equivalents(action: str) -> tuple[str, ...]:
    return next((group for group in _ACTION_EQUIVALENTS if action.casefold() in group), (action,))


def canonical_text_action(value: str) -> str:
    encoded = re.fullmatch(r"text-action:([^:]+):[0-9a-f]{64}", value)
    return (
        encoded.group(1)
        if encoded and encoded.group(1) in {group[0] for group in _ACTION_EQUIVALENTS}
        else action_equivalents(value.casefold())[0]
    )


def performed_actions(text: str) -> tuple[str, ...]:
    """Finite completed/performed verbs, excluding future/conditional clauses."""
    actions = {
        action for group in (*_ACTIONS.values(), *_BASE_ACTIONS.values()) for action in group
    }
    found: list[str] = []
    for clause in re.split(r"[;!?。\n]|(?<!\d)\.(?!\d)", text):
        for action in sorted(actions):
            pattern = re.escape(action)
            if action.isascii():
                pattern = r"(?<![A-Za-z])" + pattern + r"(?![A-Za-z])"
            for _match in re.finditer(pattern, clause, re.I):
                found.append(action)
    return tuple(found)


def prove_text_assertion(
    *,
    predicate: str,
    status: str,
    subject: str,
    action: str,
    object_label: str,
    value: str,
    assertion: str,
    status_proofs: tuple[str, ...],
) -> TextFactFrame | None:
    """Accept only complete, literal source frames with their own status proof."""
    if not subject or not value or not assertion or len(assertion) > 240:
        return None
    if re.search(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?", value):
        return None  # Numeric values require their metric/unit/period proof.
    # A subject cannot absorb a reporting clause to impersonate its actor.
    name = r"(?:[A-Z][A-Za-z0-9_.&-]*|[a-z][A-Z][A-Za-z0-9_.&-]*|[가-힣][가-힣0-9·]*)"
    if not re.fullmatch(rf"{name}(?:\s+(?:and|of|the|for|{name}))*", subject):
        return None
    verbs = {
        word.casefold()
        for actions in (*_ACTIONS.values(), *_BASE_ACTIONS.values())
        for word in actions
    }
    if any(word.casefold() in verbs for word in subject.split()):
        return None
    if _NEGATIVE.search(assertion) or _NESTED.search(assertion.replace(subject, "", 1)):
        return None
    if status == "actual" and _FUTURE.search(assertion):
        return None
    subject_re, value_re = re.escape(subject), re.escape(value)
    marker = "|".join(map(re.escape, _MARKERS[status]))
    # Explicit source rows remain supported, including the existing status
    # fixtures. Repeating `reported` elsewhere never matches this declaration.
    labels = [subject_re]
    if object_label and object_label not in value:
        labels.append(re.escape(object_label))
    if action and action.casefold() not in _ACTIONS.get(predicate, ()):
        labels.append(re.escape(action))
    declaration = r"\s+".join(labels) + rf"\s+(?:{marker})\s+(?:status\s+)?{value_re}[.!。]?"
    if (
        predicate == "status_change"
        and status == "actual"
        and value.casefold() in _ACTIONS["status_change"]
        and action.casefold() in {"", "status"}
        and re.fullmatch(declaration, assertion, re.I)
        and all(
            proof.casefold() in _MARKERS[status] or proof.strip() == assertion
            for proof in status_proofs
        )
    ):
        return TextFactFrame(predicate, status, subject, value, value, assertion)
    if not action:
        return None
    if status == "actual":
        allowed = _ACTIONS.get(predicate, ())
        modal = r"(?:(?:has|have)\s+)?"
    elif status == "forecast":
        allowed = _BASE_ACTIONS.get(predicate, ())
        modal = r"(?:will|plans\s+to|expects\s+to)\s+"
    else:
        return None  # Other states need their explicit source declaration.
    if action.casefold() not in allowed:
        return None
    complement = value
    if value.casefold() == action.casefold():
        complement = object_label
    tails = [re.escape(complement)]
    if object_label and object_label not in complement:
        tails = [rf"{re.escape(complement)}\s+with\s+{re.escape(object_label)}"]
    for tail in tails:
        ending = (r"\s+" + tail) if tail else ""
        english = rf"(?:The\s+)?{subject_re}\s+{modal}{re.escape(action)}{ending}[.!。]?"
        korean = rf"{subject_re}(?:이|가|은|는)\s+{tail}(?:을|를|에)?\s+{re.escape(action)}[.!。]?"
        if not (re.fullmatch(english, assertion, re.I) or re.fullmatch(korean, assertion)):
            continue
        valid_proofs = (
            {assertion, assertion.rstrip(".!。"), action}
            if status == "actual"
            else {
                assertion,
                "will",
                "plans to",
                "expects to",
            }
        )
        if not status_proofs or not all(proof in valid_proofs for proof in status_proofs):
            return None
        return TextFactFrame(predicate, status, subject, action, value, assertion)
    return None


def display_matches_frame(text: str, frame: TextFactFrame) -> bool:
    """Display assertions retain source actors, values, action and modality.

    Translation of the closed predicate is allowed; free paraphrases of the
    actor/value cannot manufacture a differently attributed assertion.
    """
    if text.rstrip(".!。") == frame.assertion.rstrip(".!。"):
        return True
    equivalents = action_equivalents(frame.action)
    for action in equivalents:
        if frame.status != "actual":
            continue
        if prove_text_assertion(
            predicate=frame.predicate,
            status=frame.status,
            subject=frame.subject,
            action=action,
            object_label="",
            value=frame.value,
            assertion=text,
            status_proofs=(text,),
        ):
            return True
    return False
