"""Shared result type returned by every validation stage."""

from __future__ import annotations

from dataclasses import dataclass, field

PASS = "pass"
WARN = "warn"
FAIL = "fail"


@dataclass(frozen=True)
class ValidationResult:
    """One stage verdict.

    `status` is the machine-readable outcome, `summary` is the sentence a
    content owner reads, and `metrics` holds the numbers the verdict was
    derived from so the recommendation stays auditable.
    """

    stage: str
    status: str
    summary: str
    metrics: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == PASS

    def as_dict(self) -> dict:
        return {
            "stage": self.stage,
            "status": self.status,
            "summary": self.summary,
            "metrics": self.metrics,
            "evidence": self.evidence,
        }
