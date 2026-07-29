import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import knowledge_gap as kg
import ollama_draft as od
import review_store as rs


def test_classify_coverage_thresholds():
    assert kg._classify_coverage(0.80) == "good"
    assert kg._classify_coverage(kg.GOOD_COVERAGE_THRESHOLD) == "good"
    assert kg._classify_coverage(0.40) == "weak"
    assert kg._classify_coverage(kg.WEAK_COVERAGE_THRESHOLD) == "weak"
    assert kg._classify_coverage(0.10) == "missing"


def test_bundled_ticket_ids_are_stable():
    tickets = kg.load_tickets()
    assert tickets
    assert all(t["id"].startswith("T-30") for t in tickets)


def test_evidence_ticket_url_points_at_local_viewer():
    url = kg.evidence_ticket_url("T-30001")
    assert url == "?mode=ticket&ticket=T-30001"


def test_bug_tickets_never_appear_in_analysis():
    themes = kg.analyze()
    bug_ids = {
        t["id"] for t in kg.load_tickets() if t["ticket_type"] not in kg.DOC_TICKET_TYPES
    }
    for theme in themes:
        evidence_ids = {t["id"] for t in theme["evidence_tickets"]}
        assert evidence_ids.isdisjoint(bug_ids)


def test_recurring_defect_topics_are_excluded_even_though_frequent():
    themes = kg.analyze()
    all_labels = " ".join(t["label"].lower() for t in themes)
    assert "crash" not in all_labels
    assert "chart" not in all_labels


def test_known_missing_topic_is_ranked_missing():
    themes = kg.analyze()
    tickets = {t["id"]: t["topic"] for t in kg.load_tickets()}
    by_topic = {}
    for theme in themes:
        for topic in {tickets[t["id"]] for t in theme["evidence_tickets"]}:
            by_topic.setdefault(topic, theme["coverage"])

    assert by_topic["billing_plan_migration"] == "missing"
    assert by_topic["bulk_user_import"] == "missing"


def test_known_good_coverage_topic_is_ranked_good():
    themes = kg.analyze()
    tickets = {t["id"]: t["topic"] for t in kg.load_tickets()}
    by_topic = {}
    for theme in themes:
        for topic in {tickets[t["id"]] for t in theme["evidence_tickets"]}:
            by_topic.setdefault(topic, theme["coverage"])

    assert by_topic["api_key_reset"] == "good"
    assert by_topic["timezone_settings"] == "good"


def test_low_evidence_topics_are_excluded():
    themes = kg.analyze()
    all_evidence_ids = {t["id"] for theme in themes for t in theme["evidence_tickets"]}
    noise_ids = {t["id"] for t in kg.load_tickets() if t["topic"] == "noise"}
    assert all_evidence_ids.isdisjoint(noise_ids)


def test_themes_ranked_missing_before_weak_before_good():
    themes = kg.analyze()
    ranks = [kg.COVERAGE_RANK[t["coverage"]] for t in themes]
    assert ranks == sorted(ranks)


def test_theme_labels_describe_the_whole_topic():
    themes = kg.analyze()
    labels = {theme["theme_id"]: theme["label"] for theme in themes}

    assert labels["bulk_user_import"] == "Bulk import users via CSV"
    assert labels["billing_plan_migration"] == "Migrate from a legacy billing plan"
    assert all(label in kg.THEME_LABELS.values() for label in labels.values())
    assert len(themes) == len(labels)
    assert all(
        {ticket["product_area"] for ticket in theme["evidence_tickets"]}
        == {theme["product_area"]}
        for theme in themes
    )


def test_outline_does_not_force_how_to_onto_every_subject():
    outline = kg._outline_from_tickets(
        [{"subject": "Bulk import limit on number of users"}]
    )

    assert outline == ["Bulk import limit on number of users"]


def test_draft_content_brief_for_missing_topic_recommends_new_article():
    themes = kg.analyze()
    missing_theme = next(t for t in themes if t["coverage"] == "missing")
    brief = kg.draft_content_brief(missing_theme)
    assert "new article" in brief.lower() or "new knowledge-base article" in brief.lower()
    assert "Proposed article outline" in brief
    assert "Evidence & customer questions" in brief
    assert missing_theme["label"] in brief


def test_draft_content_brief_for_weak_topic_recommends_expanding_article():
    themes = kg.analyze()
    weak_theme = next(t for t in themes if t["coverage"] == "weak")
    brief = kg.draft_content_brief(weak_theme)
    first_ticket = weak_theme["evidence_tickets"][0]
    assert weak_theme["best_match_article"]["title"] in brief
    assert "Proposed article outline" in brief
    assert "expand" in brief.lower()
    assert "mode=ticket" in brief
    assert first_ticket["id"] in brief
    assert first_ticket["subject"] in brief
    assert first_ticket["body"] in brief
    assert all(ticket["id"] in brief for ticket in weak_theme["evidence_tickets"])


def test_get_kb_article_returns_known_article():
    article = kg.get_kb_article("KB-004")
    assert article is not None
    assert article["title"] == "Data Export Overview"


def test_kb_article_url_includes_theme_context():
    url = kg.kb_article_url("KB-005", theme_id="two_factor_auth")
    assert url == "?mode=kb&article=KB-005&theme=two_factor_auth"


def test_ollama_prompt_contains_article_outline_and_evidence():
    theme = next(t for t in kg.analyze() if t["coverage"] == "weak")
    brief = kg.draft_content_brief(theme)
    prompt = od.build_article_prompt(theme, brief)
    first_ticket = theme["evidence_tickets"][0]

    assert theme["label"] in prompt
    assert theme["best_match_article"]["content"] in prompt
    assert first_ticket["id"] in prompt
    assert first_ticket["body"] in prompt
    assert "Do not invent" in prompt
    assert "[VERIFY]" in prompt
    assert 'Never prefix a heading with "How to:"' in prompt
    assert "Consolidate related customer questions" in prompt


def test_generate_article_draft_calls_ollama(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return b'{"model":"llama3.2","response":"# Draft article\\n\\nUseful steps."}'

    monkeypatch.setattr(od, "urlopen", lambda request, timeout: FakeResponse())
    theme = next(t for t in kg.analyze() if t["coverage"] == "missing")

    generated = od.generate_article_draft(theme, kg.draft_content_brief(theme))

    assert generated == {
        "content": "# Draft article\n\nUseful steps.",
        "model": "llama3.2",
    }


def test_generated_article_draft_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "ARTICLE_DRAFTS_PATH", tmp_path / "article_drafts.json")
    theme = next(t for t in kg.analyze() if t["coverage"] == "missing")

    rs.save_article_draft(
        theme["theme_id"],
        theme,
        {"content": "# Draft article", "model": "llama3.2"},
    )

    saved = rs.load_article_drafts()[theme["theme_id"]]
    assert saved["content"] == "# Draft article"
    assert saved["model"] == "llama3.2"
    assert saved["generated_at"]


def test_publish_article_persists_for_knowledge_base_page(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "PUBLISHED_PATH", tmp_path / "published_articles.json")
    theme = next(t for t in kg.analyze() if t["coverage"] == "missing")

    rs.publish_article(theme["theme_id"], theme, "# Draft article")

    published = rs.load_published_articles()[theme["theme_id"]]
    assert published["content"] == "# Draft article"
    assert published["label"] == theme["label"]
    assert published["product_area"] == theme["product_area"]
    assert published["published_at"]

    rs.unpublish_article(theme["theme_id"])
    assert theme["theme_id"] not in rs.load_published_articles()


def test_mark_as_addressed_persists_and_can_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "ADDRESSED_PATH", tmp_path / "addressed_themes.json")
    theme = {
        "theme_id": "bulk_user_import",
        "label": "Bulk import users via CSV",
        "coverage": "missing",
        "ticket_count": 12,
        "product_area": "admin",
    }
    rs.mark_addressed(theme["theme_id"], theme)
    assert theme["theme_id"] in rs.load_addressed()
    rs.unmark_addressed(theme["theme_id"])
    assert theme["theme_id"] not in rs.load_addressed()


def test_coverage_changes_detect_degradation(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "SNAPSHOTS_PATH", tmp_path / "weekly_snapshots.json")
    themes = [
        {
            "theme_id": "csv_export",
            "label": "Export data to CSV",
            "coverage": "weak",
            "ticket_count": 7,
        },
        {
            "theme_id": "api_key_reset",
            "label": "Reset and rotate API keys",
            "coverage": "good",
            "ticket_count": 14,
        },
    ]
    rs.ensure_weekly_snapshot(themes)
    changes = rs.coverage_changes(themes)
    degraded = [c for c in changes if c["kind"] == "degraded"]
    assert any(c["theme_id"] == "csv_export" for c in degraded)
    csv_change = next(c for c in degraded if c["theme_id"] == "csv_export")
    assert csv_change["cta"] == "Improve article"
    assert "Expand the closest article" in csv_change["next_step"]
    assert "good → weak" in csv_change["summary"]


def test_improved_but_still_weak_offers_improve_article(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "SNAPSHOTS_PATH", tmp_path / "weekly_snapshots.json")
    previous = {
        "two_factor_auth": {
            "coverage": "missing",
            "ticket_count": 6,
            "label": "Set up and manage two-factor authentication",
        }
    }
    current = [
        {
            "theme_id": "two_factor_auth",
            "label": "Set up and manage two-factor authentication",
            "coverage": "weak",
            "ticket_count": 8,
        }
    ]
    payload = {
        "snapshots": {
            "2026-W29": {"themes": previous},
            "2026-W30": {"themes": rs._theme_snapshot(current)},
        }
    }
    rs._write_json(rs.SNAPSHOTS_PATH, payload)
    monkeypatch.setattr(rs, "_iso_week", lambda day=None: "2026-W30")
    monkeypatch.setattr(rs, "_previous_iso_week", lambda day=None: "2026-W29")

    change = rs.coverage_changes(current)[0]
    assert change["kind"] == "improved"
    assert change["to_coverage"] == "weak"
    assert change["cta"] == "Improve article"
    assert "still Weak" in change["next_step"]
