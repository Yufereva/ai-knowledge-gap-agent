import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import knowledge_gap as kg  # noqa: E402
from validators import (  # noqa: E402
    completeness_validator,
    contradiction_validator,
    duplicate_validator,
    evidence_validator,
    gap_classifier,
    threshold_validator,
    validation_report,
)


def ticket(
    ticket_id,
    subject,
    body="",
    day=1,
    customer="ACCT-1001",
    ticket_type="question",
    version="4.1",
    searched=True,
    search_top_article=None,
):
    created_at = datetime(2026, 4, 1) + timedelta(days=day - 1)
    return {
        "id": ticket_id,
        "subject": subject,
        "body": body,
        "created_at": created_at.isoformat() + "Z",
        "product_area": "platform",
        "ticket_type": ticket_type,
        "customer_id": customer,
        "product_version": version,
        "searched": searched,
        "search_top_article": search_top_article,
    }


def theme(tickets, coverage="missing", score=0.2, article=None):
    return {
        "theme_id": "test_theme",
        "label": "Test theme",
        "ticket_count": len(tickets),
        "product_area": "platform",
        "coverage": coverage,
        "best_match_score": score,
        "best_match_article": article,
        "evidence_tickets": tickets,
    }


def bulk_import_tickets():
    return [
        ticket("T-1", "Bulk import users via CSV", "We need to add 200 users at once.", day=1),
        ticket("T-2", "Bulk import failing silently", "Nothing happens after upload.", day=20, customer="ACCT-1002"),
        ticket("T-3", "Required CSV format for user import", "What columns are required?", day=40, customer="ACCT-1003"),
        ticket("T-4", "Assigning roles during bulk import", "Can roles be set in the file?", day=60, customer="ACCT-1004"),
        ticket("T-5", "Bulk import limit on users", "Is there a maximum row count?", day=80, customer="ACCT-1002"),
    ]


def analyzed_themes():
    return {item["theme_id"]: item for item in kg.analyze()}


# Stage 1: evidence coverage


def test_section_without_supporting_tickets_is_held_for_sme_validation():
    result = evidence_validator.validate(
        theme(bulk_import_tickets()),
        ["Required CSV format for user import", "Configure quarterly invoice dunning rules"],
    )
    sections = {section["section"]: section for section in result.evidence["sections"]}

    assert sections["Required CSV format for user import"]["status"] == evidence_validator.SUPPORTED
    invented = sections["Configure quarterly invoice dunning rules"]
    assert invented["status"] == evidence_validator.NEEDS_SME_VALIDATION
    assert invented["supporting_tickets"] == 0
    assert result.status == "warn"


def test_fully_supported_outline_passes_with_ticket_ids():
    result = evidence_validator.validate(
        theme(bulk_import_tickets()), ["Bulk import users via CSV"]
    )
    section = result.evidence["sections"][0]

    assert result.passed
    # T-5 asks about the row limit for the same action, so it supports the section too.
    assert section["ticket_ids"] == ["T-1", "T-5"]
    assert section["confidence"] > 0


def test_outline_with_no_supported_section_fails():
    result = evidence_validator.validate(
        theme(bulk_import_tickets()), ["Rotate database encryption keys"]
    )

    assert result.status == "fail"
    assert result.metrics["supported_sections"] == 0


# Stage 2: minimum support threshold


def test_recurring_evidence_clears_thresholds():
    result = threshold_validator.validate(theme(bulk_import_tickets()))

    assert result.passed
    assert result.metrics["unique_customers"] == 4
    assert result.metrics["time_span_days"] == 79


def test_too_few_tickets_is_insufficient_evidence():
    result = threshold_validator.validate(theme(bulk_import_tickets()[:3]))

    assert result.status == "fail"
    assert "only 3 tickets" in result.summary


def test_volume_from_one_account_is_insufficient_evidence():
    tickets = [
        ticket(f"T-{i}", "Bulk import users via CSV", day=i * 10 + 1) for i in range(1, 7)
    ]
    result = threshold_validator.validate(theme(tickets))

    assert result.status == "fail"
    assert "unique customers" in result.summary


def test_short_lived_spike_needs_high_impact_to_pass():
    tickets = [
        ticket("T-1", "Bulk import users", day=1, customer="ACCT-1001"),
        ticket("T-2", "Bulk import users", day=2, customer="ACCT-1002"),
        ticket("T-3", "Bulk import users", day=3, customer="ACCT-1003"),
        ticket("T-4", "Bulk import users", day=4, customer="ACCT-1004"),
        ticket("T-5", "Bulk import users", day=5, customer="ACCT-1001"),
    ]

    assert threshold_validator.validate(theme(tickets)).status == "fail"
    assert threshold_validator.validate(theme(tickets), high_impact=True).passed


# Stage 3: gap classification


def test_defect_reports_are_not_a_documentation_gap():
    tickets = [
        ticket(f"T-{i}", "App crashes after login", ticket_type="bug", day=i)
        for i in range(1, 6)
    ]
    result = gap_classifier.validate(theme(tickets))

    assert result.metrics["gap_class"] == gap_classifier.PRODUCT_DEFECT
    assert result.status == "fail"
    assert result.metrics["documentation_gap"] is False


def test_missing_coverage_is_a_content_gap():
    result = gap_classifier.validate(theme(bulk_import_tickets()))

    assert result.metrics["gap_class"] == gap_classifier.MISSING_CONTENT
    assert result.passed


def test_article_that_search_never_returns_is_a_findability_problem():
    tickets = [
        ticket(f"T-{i}", "Reset our API key", day=i * 10, search_top_article=None)
        for i in range(1, 6)
    ]
    result = gap_classifier.validate(
        theme(tickets, coverage="good", score=0.85, article={"id": "KB-001", "title": "API Keys"})
    )

    assert result.metrics["gap_class"] == gap_classifier.POOR_FINDABILITY
    assert result.status == "fail"


def test_search_returning_the_wrong_article_is_a_retrieval_failure():
    tickets = [
        ticket(f"T-{i}", "Change workspace timezone", day=i * 10, search_top_article="KB-015")
        for i in range(1, 6)
    ]
    result = gap_classifier.validate(
        theme(tickets, coverage="good", score=0.85, article={"id": "KB-003", "title": "Timezone"})
    )

    assert result.metrics["gap_class"] == gap_classifier.AGENT_RETRIEVAL_FAILURE
    assert result.status == "fail"


def test_article_customers_do_reach_is_partial_coverage():
    tickets = [
        ticket(f"T-{i}", "Configure SSO with Okta", day=i * 10, search_top_article="KB-002")
        for i in range(1, 6)
    ]
    result = gap_classifier.validate(
        theme(tickets, coverage="good", score=0.79, article={"id": "KB-002", "title": "SSO"})
    )

    assert result.metrics["gap_class"] == gap_classifier.PARTIAL_COVERAGE
    assert result.passed


def test_contradiction_makes_the_gap_outdated_documentation():
    result = gap_classifier.validate(
        theme(bulk_import_tickets(), coverage="weak", score=0.47), contradiction_found=True
    )

    assert result.metrics["gap_class"] == gap_classifier.OUTDATED_DOCUMENTATION
    assert result.status == "fail"


# Stage 4: duplicate detection


def test_duplicate_actions_follow_overlap_score():
    article = {"id": "KB-004", "title": "Data Export Overview"}
    actions = {
        0.20: duplicate_validator.CREATE_NEW,
        0.40: duplicate_validator.MERGE_WITH_EXISTING,
        0.60: duplicate_validator.UPDATE_EXISTING,
        0.90: duplicate_validator.REJECT_DUPLICATE,
    }
    for score, expected in actions.items():
        result = duplicate_validator.validate(
            theme(bulk_import_tickets(), score=score, article=article)
        )
        assert result.metrics["recommended_action"] == expected


def test_no_close_article_means_a_new_article_is_safe():
    result = duplicate_validator.validate(theme(bulk_import_tickets()))

    assert result.metrics["recommended_action"] == duplicate_validator.CREATE_NEW
    assert result.evidence["existing_article"] is None


# Stage 5: completeness


def test_missing_critical_concept_marks_the_outline_for_revision():
    tickets = [
        ticket(
            f"T-{i}",
            "How do I bulk import users?",
            "What are the steps to configure the import and who approves it?",
            day=i * 10,
        )
        for i in range(1, 6)
    ]
    result = completeness_validator.validate(theme(tickets), ["Bulk import overview"])

    assert result.status == "fail"
    assert "resolution_steps" in result.metrics["missing_concepts"]
    assert result.evidence["coverage_report"]["resolution_steps"] == completeness_validator.MISSING


def test_outline_covering_raised_concepts_passes():
    tickets = [
        ticket(f"T-{i}", "How do I set up bulk import?", "What steps are required?", day=i * 10)
        for i in range(1, 6)
    ]
    result = completeness_validator.validate(
        theme(tickets),
        ["How to set up bulk import", "Steps and required permissions", "Before you start"],
    )

    assert result.passed
    assert result.metrics["missing_concepts"] == []
    assert result.metrics["completeness"] >= 0.8


# Stage 6: contradiction detection


def test_article_written_for_an_older_version_is_flagged():
    tickets = [
        ticket(
            f"T-{i}",
            "Retries no longer automatic",
            "We must re-enable retries manually since the upgrade.",
            day=i * 10,
            version="4.2",
        )
        for i in range(1, 4)
    ]
    article = {
        "id": "KB-012",
        "title": "Integrations Overview",
        "content": "Delivery is handled automatically and no configuration is required.",
        "applies_to_version": "4.1",
    }
    result = contradiction_validator.validate(
        theme(tickets, coverage="weak", score=0.47, article=article)
    )

    assert result.status == "fail"
    assert result.metrics["contradictions_found"] is True
    assert result.metrics["reason"] == "Conflicting product behavior"
    assert result.evidence["evidence_versions"] == ["4.2"]


def test_same_version_evidence_is_not_treated_as_a_contradiction():
    tickets = [
        ticket(f"T-{i}", "Retries", "We re-enable retries manually.", day=i * 10, version="4.1")
        for i in range(1, 4)
    ]
    article = {
        "id": "KB-012",
        "title": "Integrations Overview",
        "content": "Delivery is handled automatically and no configuration is required.",
        "applies_to_version": "4.1",
    }
    result = contradiction_validator.validate(
        theme(tickets, coverage="weak", score=0.47, article=article)
    )

    assert result.passed
    assert result.metrics["contradictions_found"] is False


def test_theme_without_a_close_article_has_nothing_to_contradict():
    result = contradiction_validator.validate(theme(bulk_import_tickets()))

    assert result.passed
    assert result.metrics["contradictions_found"] is False


# Final report


def test_report_lists_every_stage_and_stays_explainable():
    themes = analyzed_themes()
    subject = themes["bulk_user_import"]
    report = validation_report.build_report(subject, kg.proposed_outline(subject))

    assert [stage["stage"] for stage in report["stages"]] == [
        "evidence_coverage",
        "minimum_support",
        "gap_classification",
        "duplicate_detection",
        "outline_completeness",
        "contradiction_detection",
    ]
    assert report["reasons"]
    assert 0.0 <= report["content_gap_confidence"] <= 1.0
    assert report["evidence_strength"] == "High"


def test_documented_gap_reaches_the_content_owner():
    themes = analyzed_themes()
    subject = themes["billing_plan_migration"]
    report = validation_report.build_report(subject, kg.proposed_outline(subject))

    assert report["gap_class"] == gap_classifier.MISSING_CONTENT
    assert report["recommended_action"] == validation_report.PRESENT_TO_CONTENT_OWNER
    assert report["may_present_outline"] is True


def test_contradicting_article_is_sent_to_an_sme_instead_of_a_draft():
    themes = analyzed_themes()
    subject = themes["webhook_retry_config"]
    report = validation_report.build_report(subject, kg.proposed_outline(subject))

    assert report["contradictions_found"] is True
    assert report["gap_class"] == gap_classifier.OUTDATED_DOCUMENTATION
    assert report["recommended_action"] == validation_report.NEEDS_SME_REVIEW
    assert report["may_present_outline"] is False


def test_findable_content_problem_recommends_metadata_not_an_article():
    themes = analyzed_themes()
    for theme_id in ("api_key_reset", "timezone_settings"):
        report = validation_report.build_report(
            themes[theme_id], kg.proposed_outline(themes[theme_id])
        )
        assert report["recommended_action"] == validation_report.IMPROVE_SEARCH_METADATA
        assert report["may_present_outline"] is False


def test_existing_article_is_updated_instead_of_duplicated():
    themes = analyzed_themes()
    subject = themes["two_factor_auth"]
    report = validation_report.build_report(subject, kg.proposed_outline(subject))

    assert report["recommended_action"] == validation_report.UPDATE_EXISTING_ARTICLE
    assert report["may_present_outline"] is True


def test_theme_already_covered_end_to_end_is_rejected():
    themes = analyzed_themes()
    subject = themes["sso_setup"]
    report = validation_report.build_report(subject, kg.proposed_outline(subject))

    assert report["recommended_action"] == validation_report.REJECT
    assert report["may_present_outline"] is False


def test_thin_evidence_never_reaches_the_content_owner():
    subject = theme(bulk_import_tickets()[:2])
    report = validation_report.build_report(subject, ["Bulk import users via CSV"])

    assert report["recommended_action"] == validation_report.INSUFFICIENT_EVIDENCE
    assert report["may_present_outline"] is False


def test_defect_theme_is_rejected_for_documentation():
    tickets = [
        ticket(
            f"T-{i}",
            "App crashes after login",
            day=i * 10,
            customer=f"ACCT-100{i}",
            ticket_type="bug",
        )
        for i in range(1, 7)
    ]
    report = validation_report.build_report(theme(tickets), ["App crashes after login"])

    assert report["gap_class"] == gap_classifier.PRODUCT_DEFECT
    assert report["recommended_action"] == validation_report.REJECT


def test_presented_outline_only_contains_evidence_backed_sections():
    themes = analyzed_themes()
    subject = themes["bulk_user_import"]
    outline = [*kg.proposed_outline(subject), "Configure quarterly invoice dunning rules"]
    report = validation_report.build_report(subject, outline)

    assert "Configure quarterly invoice dunning rules" in report["withheld_sections"]
    assert "Configure quarterly invoice dunning rules" not in report["validated_outline"]
    assert report["validated_outline"]


def test_every_analyzed_theme_gets_a_recommendation_with_reasons():
    for subject in kg.analyze():
        report = validation_report.build_report(subject, kg.proposed_outline(subject))
        assert report["recommended_action"] in {
            validation_report.PRESENT_TO_CONTENT_OWNER,
            validation_report.UPDATE_EXISTING_ARTICLE,
            validation_report.NEEDS_SME_REVIEW,
            validation_report.IMPROVE_SEARCH_METADATA,
            validation_report.INSUFFICIENT_EVIDENCE,
            validation_report.REJECT,
        }
        assert report["reasons"]
        if report["may_present_outline"]:
            assert report["validated_outline"]
