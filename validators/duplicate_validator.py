"""Stage 4: prefer improving an existing article over publishing a near copy.

Overlap is the cosine similarity between the theme centroid and the closest
published article, the same score the coverage classifier uses. Thresholds are
calibrated for that scale, where a genuinely unrelated article lands near 0.2
and an article that already answers the theme lands above 0.75.
"""

from __future__ import annotations

from .result import PASS, WARN, ValidationResult

STAGE = "duplicate_detection"

CREATE_NEW = "Create New Article"
MERGE_WITH_EXISTING = "Merge With Existing"
UPDATE_EXISTING = "Update Existing"
REJECT_DUPLICATE = "Reject Duplicate"

REJECT_DUPLICATE_AT = 0.75
UPDATE_EXISTING_AT = 0.50
MERGE_WITH_EXISTING_AT = 0.35


def _action(overlap: float) -> str:
    if overlap >= REJECT_DUPLICATE_AT:
        return REJECT_DUPLICATE
    if overlap >= UPDATE_EXISTING_AT:
        return UPDATE_EXISTING
    if overlap >= MERGE_WITH_EXISTING_AT:
        return MERGE_WITH_EXISTING
    return CREATE_NEW


def validate(theme: dict) -> ValidationResult:
    article = theme.get("best_match_article")
    overlap = round(float(theme.get("best_match_score", 0.0)), 2)

    if not article:
        return ValidationResult(
            stage=STAGE,
            status=PASS,
            summary="No existing article overlaps this theme, so a new article is safe.",
            metrics={"overlap_score": 0.0, "recommended_action": CREATE_NEW},
            evidence={"existing_article": None},
        )

    action = _action(overlap)
    summaries = {
        CREATE_NEW: (
            f"Closest article \"{article['title']}\" overlaps only {overlap:.0%}. "
            "A new article will not duplicate it."
        ),
        MERGE_WITH_EXISTING: (
            f"\"{article['title']}\" overlaps {overlap:.0%}. Fold the new sections into "
            "it rather than publishing a competing page."
        ),
        UPDATE_EXISTING: (
            f"\"{article['title']}\" overlaps {overlap:.0%}. Update that article instead "
            "of creating a second one."
        ),
        REJECT_DUPLICATE: (
            f"\"{article['title']}\" already covers this theme ({overlap:.0%} overlap). "
            "Publishing another article would split the answer across two pages."
        ),
    }

    return ValidationResult(
        stage=STAGE,
        status=PASS if action in {CREATE_NEW, MERGE_WITH_EXISTING, UPDATE_EXISTING} else WARN,
        summary=summaries[action],
        metrics={"overlap_score": overlap, "recommended_action": action},
        evidence={"existing_article": article["id"], "existing_title": article["title"]},
    )
