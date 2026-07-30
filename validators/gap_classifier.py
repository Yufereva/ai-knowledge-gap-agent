"""Stage 3: decide what kind of gap this is before writing anything.

"Customers keep asking" is not the same finding as "documentation is missing".
The same ticket volume can mean the article does not exist, exists but is never
returned by search, is returned but describes older behavior, or that the
product is simply broken. Only the first two justify content work.
"""

from __future__ import annotations

from .result import FAIL, PASS, ValidationResult

STAGE = "gap_classification"

MISSING_CONTENT = "Missing Content"
PARTIAL_COVERAGE = "Partial Coverage"
POOR_FINDABILITY = "Poor Findability"
OUTDATED_DOCUMENTATION = "Outdated Documentation"
AGENT_RETRIEVAL_FAILURE = "Agent Retrieval Failure"
PRODUCT_DEFECT = "Product Defect"

# Only these two classes may continue to documentation generation.
DOCUMENTATION_CLASSES = frozenset({MISSING_CONTENT, PARTIAL_COVERAGE})

SUMMARIES = {
    MISSING_CONTENT: "No article covers this theme, so new content is justified.",
    PARTIAL_COVERAGE: (
        "A related article exists and customers do reach it, but it does not answer "
        "what they keep asking."
    ),
    POOR_FINDABILITY: (
        "A complete article exists, but self-service search returns nothing for how "
        "customers phrase this. Fix findability instead of writing a second article."
    ),
    AGENT_RETRIEVAL_FAILURE: (
        "A complete article exists, but retrieval keeps returning a different article. "
        "Fix the retrieval or the article metadata, not the content."
    ),
    OUTDATED_DOCUMENTATION: (
        "The closest article contradicts what customers report on their product "
        "version, so it needs an SME before it is rewritten."
    ),
    PRODUCT_DEFECT: (
        "This theme is dominated by defect reports. It belongs with Engineering, "
        "not with documentation."
    ),
}


def _defect_share(tickets: list[dict]) -> float:
    if not tickets:
        return 0.0
    defects = [ticket for ticket in tickets if ticket.get("ticket_type") == "bug"]
    return len(defects) / len(tickets)


def validate(theme: dict, contradiction_found: bool = False) -> ValidationResult:
    tickets = theme["evidence_tickets"]
    article = theme.get("best_match_article")
    article_id = article["id"] if article else None
    defect_share = _defect_share(tickets)

    searched = [ticket for ticket in tickets if ticket.get("searched")]
    retrieved_correct = [
        ticket for ticket in searched if ticket.get("search_top_article") == article_id
    ]
    retrieved_nothing = [
        ticket for ticket in searched if ticket.get("search_top_article") is None
    ]
    search_hit_share = len(retrieved_correct) / len(searched) if searched else None

    if defect_share > 0.5:
        gap_class = PRODUCT_DEFECT
    elif contradiction_found:
        gap_class = OUTDATED_DOCUMENTATION
    elif theme["coverage"] == "missing":
        gap_class = MISSING_CONTENT
    elif theme["coverage"] == "good" and searched and search_hit_share < 0.5:
        # The article answers the question, so the failure is in reaching it.
        gap_class = (
            POOR_FINDABILITY
            if len(retrieved_nothing) >= len(searched) - len(retrieved_nothing)
            else AGENT_RETRIEVAL_FAILURE
        )
    else:
        gap_class = PARTIAL_COVERAGE

    documentation_gap = gap_class in DOCUMENTATION_CLASSES
    return ValidationResult(
        stage=STAGE,
        status=PASS if documentation_gap else FAIL,
        summary=SUMMARIES[gap_class],
        metrics={
            "gap_class": gap_class,
            "documentation_gap": documentation_gap,
            "coverage": theme["coverage"],
            "defect_share": round(defect_share, 2),
            "search_hit_share": (
                round(search_hit_share, 2) if search_hit_share is not None else None
            ),
        },
        evidence={
            "closest_article": article_id,
            "tickets_that_searched": len(searched),
            "searches_returning_nothing": len(retrieved_nothing),
        },
    )
