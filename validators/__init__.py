"""Validation pipeline that runs between outline generation and human review.

Each stage lives in its own module, exposes `validate()`, returns a
`ValidationResult`, and can be tested on its own. `validation_report.build_report`
runs them in order and turns the verdicts into a single recommendation.
"""

from .result import FAIL, PASS, WARN, ValidationResult
from .validation_report import build_report

__all__ = ["ValidationResult", "PASS", "WARN", "FAIL", "build_report"]
