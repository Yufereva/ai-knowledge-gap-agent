"""Stage 1: map every outline section back to the tickets that justify it.

A section a customer never asked about is the most expensive kind of false
positive, because it sends a content owner to write documentation nobody needs.
Sections without supporting tickets are therefore marked for SME validation and
kept out of the outline the content owner sees.

Matching is deliberately lexical rather than embedding based: section headings
are short, the tickets are already narrowed to one theme by semantic
clustering, and a content owner can verify a word overlap by reading the ticket.
"""

from __future__ import annotations

import re

from .result import FAIL, PASS, WARN, ValidationResult

STAGE = "evidence_coverage"

# Share of a section's meaningful words that must appear in a ticket for that
# ticket to count as evidence for the section.
SUPPORT_OVERLAP = 0.5

STOPWORDS = frozenset(
    """
    a an and are as at be by can do does for from get has have how i in into is it
    my need not of on or our the there this to us we what when where which why
    with you your cannot
    """.split()
)

SUPPORTED = "supported"
NEEDS_SME_VALIDATION = "needs_sme_validation"


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if len(word) > 2 and word not in STOPWORDS}


def _overlap(section_tokens: set[str], ticket_tokens: set[str]) -> float:
    if not section_tokens:
        return 0.0
    return len(section_tokens & ticket_tokens) / len(section_tokens)


def validate(theme: dict, outline: list[str]) -> ValidationResult:
    tickets = theme["evidence_tickets"]
    ticket_tokens = {
        ticket["id"]: _tokens(f"{ticket['subject']} {ticket['body']}")
        for ticket in tickets
    }

    sections = []
    for heading in outline:
        section_tokens = _tokens(heading)
        scored = [
            (ticket_id, _overlap(section_tokens, tokens))
            for ticket_id, tokens in ticket_tokens.items()
        ]
        supporting = [
            (ticket_id, score) for ticket_id, score in scored if score >= SUPPORT_OVERLAP
        ]
        confidence = (
            round(sum(score for _, score in supporting) / len(supporting), 2)
            if supporting
            else 0.0
        )
        sections.append(
            {
                "section": heading,
                "status": SUPPORTED if supporting else NEEDS_SME_VALIDATION,
                "supporting_tickets": len(supporting),
                "ticket_ids": sorted(ticket_id for ticket_id, _ in supporting),
                "confidence": confidence,
            }
        )

    supported = [section for section in sections if section["status"] == SUPPORTED]
    unsupported = [section for section in sections if section["status"] != SUPPORTED]
    mean_confidence = (
        round(sum(section["confidence"] for section in supported) / len(supported), 2)
        if supported
        else 0.0
    )

    if not supported:
        status = FAIL
        summary = "No outline section is supported by ticket evidence."
    elif unsupported:
        status = WARN
        summary = (
            f"{len(supported)} of {len(sections)} sections are supported by tickets. "
            f"{len(unsupported)} need SME validation and are withheld from the outline."
        )
    else:
        status = PASS
        summary = (
            f"All {len(sections)} sections are supported by ticket evidence "
            f"(mean confidence {mean_confidence:.0%})."
        )

    return ValidationResult(
        stage=STAGE,
        status=status,
        summary=summary,
        metrics={
            "sections": len(sections),
            "supported_sections": len(supported),
            "unsupported_sections": len(unsupported),
            "mean_confidence": mean_confidence,
        },
        evidence={"sections": sections},
    )
