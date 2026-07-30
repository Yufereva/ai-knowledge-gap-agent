"""Stage 2: refuse to justify documentation work with isolated questions.

Volume alone is misleading. Twelve tickets from one account is an account
problem, and twelve tickets in a single day is usually an incident. A real
documentation gap keeps returning, across accounts, over time.
"""

from __future__ import annotations

from datetime import datetime

from .result import FAIL, PASS, ValidationResult

STAGE = "minimum_support"

MIN_TICKETS = 5
MIN_UNIQUE_CUSTOMERS = 3
MIN_TIME_SPAN_DAYS = 14


def _parsed_dates(tickets: list[dict]) -> list[datetime]:
    dates = []
    for ticket in tickets:
        raw = ticket.get("created_at")
        if raw:
            dates.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    return dates


def validate(theme: dict, high_impact: bool = False) -> ValidationResult:
    tickets = theme["evidence_tickets"]
    customers = {ticket.get("customer_id") for ticket in tickets if ticket.get("customer_id")}
    dates = _parsed_dates(tickets)
    span_days = (max(dates) - min(dates)).days if len(dates) > 1 else 0

    failures = []
    if len(tickets) < MIN_TICKETS:
        failures.append(f"only {len(tickets)} tickets (minimum {MIN_TICKETS})")
    if len(customers) < MIN_UNIQUE_CUSTOMERS:
        failures.append(
            f"only {len(customers)} unique customers (minimum {MIN_UNIQUE_CUSTOMERS})"
        )
    if span_days < MIN_TIME_SPAN_DAYS and not high_impact:
        failures.append(
            f"evidence spans {span_days} days (minimum {MIN_TIME_SPAN_DAYS}) "
            "and impact is not flagged as high"
        )

    if failures:
        status = FAIL
        summary = "Insufficient evidence: " + ", ".join(failures) + "."
    else:
        status = PASS
        summary = (
            f"{len(tickets)} tickets from {len(customers)} customers over "
            f"{span_days} days clear the support thresholds."
        )

    return ValidationResult(
        stage=STAGE,
        status=status,
        summary=summary,
        metrics={
            "tickets": len(tickets),
            "unique_customers": len(customers),
            "time_span_days": span_days,
            "high_impact": high_impact,
        },
        evidence={"customer_ids": sorted(customers), "failed_rules": failures},
    )
