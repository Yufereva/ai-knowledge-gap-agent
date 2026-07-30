"""Stage 5: check the outline answers everything the tickets actually raised.

An outline built from recurring ticket subjects tends to cover the question and
the happy path while quietly dropping prerequisites, known mistakes, and when to
contact support. Those omissions are what send the customer back to the queue.

Concepts are detected with explicit phrase lists so a content owner can see why
a concept was counted as raised or as covered.
"""

from __future__ import annotations

from .result import FAIL, PASS, WARN, ValidationResult

STAGE = "outline_completeness"

CONCEPT_PATTERNS = {
    "user_goal": ("how do i", "how to", "how can", "want to", "need to", "is it possible"),
    "symptoms": ("not working", "stuck", "fails", "failing", "broken", "not visible", "no longer"),
    "error_messages": ("error", "429", "exception", "failed to", "rejected"),
    "prerequisites": ("plan", "permission", "admin", "role", "requires", "required", "before you"),
    "resolution_steps": ("steps", "configure", "set up", "setup", "enable", "instructions", "process"),
    "common_mistakes": ("silently", "duplicate", "partial", "incorrect", "wrong", "by mistake"),
    "escalation_criteria": ("contact support", "support said", "escalate", "approves", "reach out"),
}

# An outline that never states the goal or the resolution is not reviewable.
CRITICAL_CONCEPTS = frozenset({"user_goal", "resolution_steps"})

COVERED = "covered"
PARTIAL = "partial"
MISSING = "missing"
NOT_RAISED = "not_raised"


def _hits(texts: list[str], patterns: tuple[str, ...]) -> int:
    return sum(1 for text in texts if any(pattern in text for pattern in patterns))


def validate(theme: dict, outline: list[str]) -> ValidationResult:
    ticket_texts = [
        f"{ticket['subject']} {ticket['body']}".lower()
        for ticket in theme["evidence_tickets"]
    ]
    outline_texts = [heading.lower() for heading in outline]

    report = {}
    for concept, patterns in CONCEPT_PATTERNS.items():
        raised = _hits(ticket_texts, patterns)
        covered = _hits(outline_texts, patterns)
        if raised == 0:
            report[concept] = NOT_RAISED
        elif covered == 0:
            report[concept] = MISSING
        elif covered == 1 and raised >= 3:
            report[concept] = PARTIAL
        else:
            report[concept] = COVERED

    required = [concept for concept, state in report.items() if state != NOT_RAISED]
    covered_count = sum(1 for concept in required if report[concept] == COVERED)
    partial_count = sum(1 for concept in required if report[concept] == PARTIAL)
    completeness = (
        round((covered_count + 0.5 * partial_count) / len(required), 2) if required else 0.0
    )

    missing = [concept for concept in required if report[concept] == MISSING]
    missing_critical = sorted(set(missing) & CRITICAL_CONCEPTS)

    if missing_critical:
        status = FAIL
        summary = (
            "Needs revision: the outline does not cover "
            + ", ".join(concept.replace("_", " ") for concept in missing_critical)
            + ", which customers raised."
        )
    elif missing:
        status = WARN
        summary = (
            f"Outline completeness {completeness:.0%}. Add the sections customers raised "
            "but the outline omits: "
            + ", ".join(concept.replace("_", " ") for concept in missing)
            + "."
        )
    else:
        status = PASS
        summary = (
            f"Outline completeness {completeness:.0%}. Every concept raised in the "
            "tickets appears in the outline."
        )

    return ValidationResult(
        stage=STAGE,
        status=status,
        summary=summary,
        metrics={"completeness": completeness, "missing_concepts": missing},
        evidence={"coverage_report": report},
    )
