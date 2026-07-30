"""Stage 6: catch published behavior that customer evidence disagrees with.

If the article says a step is automatic and customers on a newer product version
report doing it by hand, the safe outcome is an SME review, not a rewrite driven
by ticket text. Rewriting first would publish a guess about product behavior.

Detection is a narrow deterministic rule set, not general purpose entailment:
each rule pairs a claim phrased in the article with the opposite behavior
described in tickets, and only fires when the conflicting tickets run on a
product version newer than the one the article was written for.
"""

from __future__ import annotations

from .result import FAIL, PASS, ValidationResult

STAGE = "contradiction_detection"

MIN_CONFLICTING_TICKETS = 2

CONTRADICTION_RULES = (
    {
        "id": "automatic_vs_manual",
        "article_claims": ("automatic", "automatically", "no configuration is required"),
        "ticket_evidence": ("manually", "manual step", "re-enable", "must turn"),
        "reason": "Conflicting product behavior",
        "detail": (
            "The article documents the behavior as automatic while customers on a newer "
            "version report having to do it manually."
        ),
    },
)


def _version(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts = []
    for chunk in str(value).split("."):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    return tuple(parts)


def validate(theme: dict) -> ValidationResult:
    article = theme.get("best_match_article")
    if not article:
        return ValidationResult(
            stage=STAGE,
            status=PASS,
            summary="No published article to contradict.",
            metrics={"contradictions_found": False},
        )

    content = article.get("content", "").lower()
    article_version = _version(article.get("applies_to_version"))

    for rule in CONTRADICTION_RULES:
        if not any(claim in content for claim in rule["article_claims"]):
            continue
        conflicting = [
            ticket
            for ticket in theme["evidence_tickets"]
            if any(
                phrase in f"{ticket['subject']} {ticket['body']}".lower()
                for phrase in rule["ticket_evidence"]
            )
            and _version(ticket.get("product_version")) > article_version
        ]
        if len(conflicting) < MIN_CONFLICTING_TICKETS:
            continue

        versions = sorted({ticket.get("product_version") for ticket in conflicting})
        return ValidationResult(
            stage=STAGE,
            status=FAIL,
            summary=(
                f"SME review required: {rule['detail']} "
                f"\"{article['title']}\" is written for "
                f"{article.get('applies_to_version', 'an unstated version')}, "
                f"evidence comes from {', '.join(versions)}."
            ),
            metrics={
                "contradictions_found": True,
                "rule": rule["id"],
                "reason": rule["reason"],
            },
            evidence={
                "article": article["id"],
                "article_version": article.get("applies_to_version"),
                "evidence_versions": versions,
                "ticket_ids": sorted(ticket["id"] for ticket in conflicting),
            },
        )

    return ValidationResult(
        stage=STAGE,
        status=PASS,
        summary="No contradiction between the closest article and the ticket evidence.",
        metrics={"contradictions_found": False},
        evidence={"article": article["id"]},
    )
