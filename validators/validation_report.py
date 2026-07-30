"""Combine the stage verdicts into one explainable recommendation.

The report answers a narrow question: is documentation work justified here, and
if not, what should happen instead. Every recommendation carries the reasons and
the numbers behind it, and an outline is only released to a content owner when
its sections are backed by tickets.

Stage order note: contradiction detection runs before gap classification because
an article that disagrees with the evidence changes the class of the gap. The
report still lists the stages in pipeline order.
"""

from __future__ import annotations

from . import (
    completeness_validator,
    contradiction_validator,
    duplicate_validator,
    evidence_validator,
    gap_classifier,
    threshold_validator,
)
from .result import FAIL, PASS, WARN

PRESENT_TO_CONTENT_OWNER = "Present to Content Owner"
UPDATE_EXISTING_ARTICLE = "Update Existing Article"
NEEDS_SME_REVIEW = "Needs SME Review"
IMPROVE_SEARCH_METADATA = "Improve Search Metadata"
INSUFFICIENT_EVIDENCE = "Insufficient Evidence"
REJECT = "Reject"

# Actions that let a content owner see the proposed outline.
OUTLINE_ACTIONS = frozenset({PRESENT_TO_CONTENT_OWNER, UPDATE_EXISTING_ARTICLE})

HIGH_EVIDENCE_TICKETS = 10
HIGH_EVIDENCE_CUSTOMERS = 4


def _evidence_strength(threshold_result) -> str:
    metrics = threshold_result.metrics
    if not threshold_result.passed:
        return "Low"
    if (
        metrics["tickets"] >= HIGH_EVIDENCE_TICKETS
        and metrics["unique_customers"] >= HIGH_EVIDENCE_CUSTOMERS
    ):
        return "High"
    return "Medium"


def _content_gap_confidence(evidence_result, threshold_result, duplicate_result) -> float:
    """Blend the three independent signals that a real gap exists.

    Weights are fixed and reported so a reviewer can disagree with the number
    without having to guess how it was produced: how little existing content
    overlaps (0.5), how much of the outline is backed by tickets (0.3), and how
    much recurring volume stands behind it (0.2).
    """
    sections = evidence_result.metrics["sections"]
    evidence_share = (
        evidence_result.metrics["supported_sections"] / sections if sections else 0.0
    )
    volume = min(
        1.0, threshold_result.metrics["tickets"] / (2 * threshold_validator.MIN_TICKETS)
    )
    novelty = 1.0 - duplicate_result.metrics["overlap_score"]
    return round(0.5 * novelty + 0.3 * evidence_share + 0.2 * volume, 2)


def _recommend(evidence, threshold, classification, duplicate, completeness, contradiction):
    """Return (action, reasons) using a fixed precedence over the stage verdicts.

    Only evidence, support volume, gap class, contradictions, and duplication can
    withhold an outline. Outline completeness never blocks: concept detection is
    lexical, and an outline written as customer questions legitimately lacks
    procedural wording, so a hard block there would reject real gaps. Incomplete
    outlines are released with the missing sections named instead.
    """
    if evidence.status == FAIL:
        return INSUFFICIENT_EVIDENCE, [evidence.summary]
    if not threshold.passed:
        return INSUFFICIENT_EVIDENCE, [threshold.summary]

    gap_class = classification.metrics["gap_class"]
    if gap_class == gap_classifier.PRODUCT_DEFECT:
        return REJECT, [classification.summary]
    if gap_class in {gap_classifier.POOR_FINDABILITY, gap_classifier.AGENT_RETRIEVAL_FAILURE}:
        return IMPROVE_SEARCH_METADATA, [classification.summary]
    if contradiction.metrics["contradictions_found"]:
        return NEEDS_SME_REVIEW, [contradiction.summary]
    if duplicate.metrics["recommended_action"] == duplicate_validator.REJECT_DUPLICATE:
        return REJECT, [duplicate.summary]

    reasons = []
    if evidence.status == WARN:
        reasons.append(evidence.summary)
    if completeness.status != PASS:
        reasons.append(completeness.summary)

    if duplicate.metrics["recommended_action"] in {
        duplicate_validator.UPDATE_EXISTING,
        duplicate_validator.MERGE_WITH_EXISTING,
    }:
        return UPDATE_EXISTING_ARTICLE, [duplicate.summary, *reasons]

    return PRESENT_TO_CONTENT_OWNER, [threshold.summary, *reasons]


def build_report(theme: dict, outline: list[str], high_impact: bool = False) -> dict:
    evidence = evidence_validator.validate(theme, outline)
    threshold = threshold_validator.validate(theme, high_impact=high_impact)
    contradiction = contradiction_validator.validate(theme)
    classification = gap_classifier.validate(
        theme, contradiction_found=contradiction.metrics["contradictions_found"]
    )
    duplicate = duplicate_validator.validate(theme)
    completeness = completeness_validator.validate(theme, outline)

    action, reasons = _recommend(
        evidence, threshold, classification, duplicate, completeness, contradiction
    )
    sections = evidence.evidence["sections"]
    supported = [
        section["section"]
        for section in sections
        if section["status"] == evidence_validator.SUPPORTED
    ]
    withheld = [
        section["section"]
        for section in sections
        if section["status"] != evidence_validator.SUPPORTED
    ]

    return {
        "theme_id": theme["theme_id"],
        "label": theme["label"],
        "content_gap_confidence": _content_gap_confidence(evidence, threshold, duplicate),
        "evidence_strength": _evidence_strength(threshold),
        "duplicate_score": duplicate.metrics["overlap_score"],
        "outline_completeness": completeness.metrics["completeness"],
        "contradictions_found": contradiction.metrics["contradictions_found"],
        "gap_class": classification.metrics["gap_class"],
        "recommended_action": action,
        "reasons": reasons,
        "outline_needs_revision": completeness.status == FAIL,
        "missing_concepts": completeness.metrics["missing_concepts"],
        "may_present_outline": action in OUTLINE_ACTIONS and bool(supported),
        "validated_outline": supported,
        "withheld_sections": withheld,
        "stages": [
            evidence.as_dict(),
            threshold.as_dict(),
            classification.as_dict(),
            duplicate.as_dict(),
            completeness.as_dict(),
            contradiction.as_dict(),
        ],
    }
