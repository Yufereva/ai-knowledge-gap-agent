"""Persist addressed themes and weekly coverage snapshots."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "data" / "runtime"
ADDRESSED_PATH = RUNTIME / "addressed_themes.json"
SNAPSHOTS_PATH = RUNTIME / "weekly_snapshots.json"
ARTICLE_DRAFTS_PATH = RUNTIME / "article_drafts.json"
PUBLISHED_PATH = RUNTIME / "published_articles.json"

# Seeded "last week" state so the Coverage changes section is meaningful on
# first open of the demo (without waiting a real calendar week). Values are
# intentional deltas vs the calibrated current analysis.
DEMO_PREVIOUS_WEEK = {
    "api_key_reset": {"coverage": "good", "ticket_count": 14, "label": "Reset and rotate API keys"},
    "sso_setup": {"coverage": "good", "ticket_count": 12, "label": "Configure single sign-on (SSO)"},
    "timezone_settings": {"coverage": "good", "ticket_count": 8, "label": "Configure workspace time zones"},
    "csv_export": {"coverage": "good", "ticket_count": 5, "label": "Export data to CSV"},
    "two_factor_auth": {"coverage": "missing", "ticket_count": 6, "label": "Set up and manage two-factor authentication"},
    "rate_limit_errors": {"coverage": "good", "ticket_count": 4, "label": "Understand and handle API rate limits"},
    "billing_plan_migration": {"coverage": "missing", "ticket_count": 9, "label": "Migrate from a legacy billing plan"},
    "webhook_retry_config": {"coverage": "good", "ticket_count": 7, "label": "Configure and troubleshoot webhook retries"},
    "bulk_user_import": {"coverage": "weak", "ticket_count": 10, "label": "Bulk import users via CSV"},
}


def _iso_week(day: date | None = None) -> str:
    day = day or date.today()
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _previous_iso_week(day: date | None = None) -> str:
    day = day or date.today()
    return _iso_week(day - timedelta(days=7))


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    """Write JSON safely on Windows/OneDrive where atomic replace often fails."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    try:
        temporary.replace(path)
    except PermissionError:
        # OneDrive / antivirus can lock the destination during os.replace.
        path.write_text(text, encoding="utf-8")
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def load_addressed() -> dict[str, dict]:
    payload = _read_json(ADDRESSED_PATH, {"themes": {}})
    return dict(payload.get("themes", {}))


def mark_addressed(theme_id: str, theme: dict) -> None:
    payload = _read_json(ADDRESSED_PATH, {"themes": {}})
    payload.setdefault("themes", {})
    payload["themes"][theme_id] = {
        "label": theme["label"],
        "coverage": theme["coverage"],
        "ticket_count": theme["ticket_count"],
        "product_area": theme["product_area"],
        "addressed_at": datetime.now(UTC).isoformat(),
    }
    _write_json(ADDRESSED_PATH, payload)


def unmark_addressed(theme_id: str) -> None:
    payload = _read_json(ADDRESSED_PATH, {"themes": {}})
    payload.setdefault("themes", {}).pop(theme_id, None)
    _write_json(ADDRESSED_PATH, payload)


def load_article_drafts() -> dict[str, dict]:
    payload = _read_json(ARTICLE_DRAFTS_PATH, {"drafts": {}})
    return dict(payload.get("drafts", {}))


def save_article_draft(theme_id: str, theme: dict, generated: dict) -> None:
    payload = _read_json(ARTICLE_DRAFTS_PATH, {"drafts": {}})
    payload.setdefault("drafts", {})
    payload["drafts"][theme_id] = {
        "label": theme["label"],
        "coverage": theme["coverage"],
        "content": generated["content"],
        "model": generated["model"],
        "generated_at": datetime.now(UTC).isoformat(),
    }
    _write_json(ARTICLE_DRAFTS_PATH, payload)


def load_published_articles() -> dict[str, dict]:
    payload = _read_json(PUBLISHED_PATH, {"articles": {}})
    return dict(payload.get("articles", {}))


def publish_article(theme_id: str, theme: dict, content: str) -> None:
    """Publish a reviewed draft into the demo knowledge base."""
    payload = _read_json(PUBLISHED_PATH, {"articles": {}})
    payload.setdefault("articles", {})
    payload["articles"][theme_id] = {
        "label": theme["label"],
        "product_area": theme["product_area"],
        "content": content,
        "published_at": datetime.now(UTC).isoformat(),
    }
    _write_json(PUBLISHED_PATH, payload)


def unpublish_article(theme_id: str) -> None:
    payload = _read_json(PUBLISHED_PATH, {"articles": {}})
    payload.setdefault("articles", {}).pop(theme_id, None)
    _write_json(PUBLISHED_PATH, payload)


def _theme_snapshot(themes: list[dict]) -> dict[str, dict]:
    snapshot = {}
    for theme in themes:
        theme_id = theme.get("theme_id") or theme.get("label") or "unknown"
        snapshot[theme_id] = {
            "coverage": theme["coverage"],
            "ticket_count": theme["ticket_count"],
            "label": theme.get("label", theme_id),
        }
    return snapshot


def ensure_weekly_snapshot(themes: list[dict]) -> None:
    """Save this week's snapshot; seed a previous week on first run for demo."""
    payload = _read_json(SNAPSHOTS_PATH, {"snapshots": {}})
    snapshots = payload.setdefault("snapshots", {})
    this_week = _iso_week()
    prev_week = _previous_iso_week()

    if not snapshots:
        snapshots[prev_week] = {
            "captured_at": (datetime.now(UTC) - timedelta(days=7)).isoformat(),
            "themes": DEMO_PREVIOUS_WEEK,
            "seeded": True,
        }

    snapshots[this_week] = {
        "captured_at": datetime.now(UTC).isoformat(),
        "themes": _theme_snapshot(themes),
        "seeded": False,
    }
    _write_json(SNAPSHOTS_PATH, payload)


def _next_step_for_change(kind: str, coverage: str) -> str:
    # Color and CTA follow current coverage, not only the week-over-week delta.
    # missing → weak is an improvement, but Weak still needs work.
    if coverage == "missing":
        return "Write a new KB article for this gap."
    if coverage == "weak":
        if kind == "improved":
            return (
                "Coverage improved but still Weak. Expand the closest article "
                "with the missing steps customers ask about."
            )
        return "Expand the closest article with the missing steps customers ask about."
    if kind == "improved":
        return "Coverage improved. Skim the theme and confirm the article still holds."
    return "Review the theme and keep the article current."


def _cta_for_change(kind: str, coverage: str) -> str:
    if coverage == "missing":
        return "Create article"
    if coverage == "weak":
        return "Improve article"
    if kind == "improved":
        return "View theme"
    return "Review theme"


def coverage_changes(themes: list[dict]) -> list[dict]:
    """Compare current themes to the most recent earlier weekly snapshot."""
    payload = _read_json(SNAPSHOTS_PATH, {"snapshots": {}})
    snapshots = payload.get("snapshots", {})
    this_week = _iso_week()
    earlier_weeks = sorted(w for w in snapshots if w != this_week)
    if not earlier_weeks:
        return []

    previous = snapshots[earlier_weeks[-1]].get("themes", {})
    current = _theme_snapshot(themes)
    changes = []

    for theme_id, current_meta in current.items():
        prev_meta = previous.get(theme_id)
        if prev_meta is None:
            changes.append(
                {
                    "theme_id": theme_id,
                    "label": current_meta["label"],
                    "kind": "new",
                    "from_coverage": None,
                    "to_coverage": current_meta["coverage"],
                    "ticket_count": current_meta["ticket_count"],
                    "summary": (
                        f"New recurring theme · {current_meta['coverage']} coverage · "
                        f"{current_meta['ticket_count']} customers"
                    ),
                    "next_step": _next_step_for_change(
                        "new", current_meta["coverage"]
                    ),
                    "cta": _cta_for_change("new", current_meta["coverage"]),
                }
            )
            continue
        if prev_meta["coverage"] != current_meta["coverage"]:
            degraded = (
                {"good": 2, "weak": 1, "missing": 0}[current_meta["coverage"]]
                < {"good": 2, "weak": 1, "missing": 0}[prev_meta["coverage"]]
            )
            kind = "degraded" if degraded else "improved"
            changes.append(
                {
                    "theme_id": theme_id,
                    "label": current_meta["label"],
                    "kind": kind,
                    "from_coverage": prev_meta["coverage"],
                    "to_coverage": current_meta["coverage"],
                    "ticket_count": current_meta["ticket_count"],
                    "summary": (
                        f"{prev_meta['coverage']} → {current_meta['coverage']} · "
                        f"{current_meta['ticket_count']} customers"
                    ),
                    "next_step": _next_step_for_change(kind, current_meta["coverage"]),
                    "cta": _cta_for_change(kind, current_meta["coverage"]),
                }
            )

    order = {"degraded": 0, "new": 1, "improved": 2}
    severity = {"missing": 0, "weak": 1, "good": 2}
    changes.sort(
        key=lambda c: (
            severity.get(c["to_coverage"], 9),
            order.get(c["kind"], 9),
            -c["ticket_count"],
        )
    )
    return changes
