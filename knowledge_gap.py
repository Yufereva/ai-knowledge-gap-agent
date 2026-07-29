"""Embedding-based knowledge gap detection over bundled synthetic data.

Pipeline:
  1. Load tickets and KB articles.
  2. Keep only documentation-relevant ticket types (exclude bugs/complaints).
  3. Embed ticket text and greedily cluster into recurring themes.
  4. Drop themes with too few tickets.
  5. Classify each theme's KB coverage as good / weak / missing.
  6. Rank missing, then weak, then good, followed by ticket count.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_PATH = DATA_DIR / "embeddings_cache.npz"

MODEL_NAME = "all-MiniLM-L6-v2"

DOC_TICKET_TYPES = {"question", "how-to"}

CLUSTER_THRESHOLD = 0.50
MIN_CLUSTER_SIZE = 5

GOOD_COVERAGE_THRESHOLD = 0.50
WEAK_COVERAGE_THRESHOLD = 0.35

COVERAGE_RANK = {"missing": 0, "weak": 1, "good": 2}

# Stable article-level names for the known support themes. Ticket subjects are
# evidence, not titles: a narrow subject such as "Bulk import audit trail"
# should not name a cluster that also covers CSV format, roles, and failures.
THEME_LABELS = {
    "api_key_reset": "Reset and rotate API keys",
    "sso_setup": "Configure single sign-on (SSO)",
    "timezone_settings": "Configure workspace time zones",
    "csv_export": "Export data to CSV",
    "two_factor_auth": "Set up and manage two-factor authentication",
    "rate_limit_errors": "Understand and handle API rate limits",
    "billing_plan_migration": "Migrate from a legacy billing plan",
    "webhook_retry_config": "Configure and troubleshoot webhook retries",
    "bulk_user_import": "Bulk import users via CSV",
}

def load_tickets() -> list[dict]:
    return json.loads((DATA_DIR / "tickets.json").read_text(encoding="utf-8"))


def load_kb_articles() -> list[dict]:
    return json.loads((DATA_DIR / "kb_articles.json").read_text(encoding="utf-8"))


def evidence_ticket_url(ticket_id: str) -> str:
    return f"?mode=ticket&ticket={ticket_id}"


def _ticket_text(ticket: dict) -> str:
    return f"{ticket['subject']} {ticket['body']}"


def _article_text(article: dict) -> str:
    return f"{article['title']} {article['content']}"


def _embed(texts: list[str]):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    return model.encode(texts, show_progress_bar=False, normalize_embeddings=True)


def compute_embeddings(
    tickets: list[dict] | None = None,
    articles: list[dict] | None = None,
    force_recompute: bool = False,
) -> dict:
    tickets = tickets if tickets is not None else load_tickets()
    articles = articles if articles is not None else load_kb_articles()
    ticket_ids = [t["id"] for t in tickets]
    article_ids = [a["id"] for a in articles]

    if not force_recompute and CACHE_PATH.exists():
        data = np.load(CACHE_PATH, allow_pickle=True)
        if (
            data["ticket_ids"].tolist() == ticket_ids
            and data["article_ids"].tolist() == article_ids
        ):
            return {
                "ticket_ids": ticket_ids,
                "ticket_embeddings": data["ticket_embeddings"],
                "article_ids": article_ids,
                "article_embeddings": data["article_embeddings"],
            }

    ticket_embeddings = _embed([_ticket_text(t) for t in tickets])
    article_embeddings = _embed([_article_text(a) for a in articles])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(
        CACHE_PATH,
        ticket_ids=np.array(ticket_ids),
        ticket_embeddings=ticket_embeddings,
        article_ids=np.array(article_ids),
        article_embeddings=article_embeddings,
    )
    return {
        "ticket_ids": ticket_ids,
        "ticket_embeddings": ticket_embeddings,
        "article_ids": article_ids,
        "article_embeddings": article_embeddings,
    }


def cluster_tickets(
    tickets: list[dict],
    embeddings: np.ndarray,
    threshold: float = CLUSTER_THRESHOLD,
) -> list[list[int]]:
    """Greedy leader-follower clustering over normalized embeddings."""
    clusters: list[dict] = []

    for idx in range(len(tickets)):
        vec = embeddings[idx]
        best_cluster = None
        best_score = -1.0
        for cluster in clusters:
            if cluster["product_area"] != tickets[idx]["product_area"]:
                continue
            score = float(np.dot(cluster["centroid"], vec))
            if score > best_score:
                best_score = score
                best_cluster = cluster
        if best_cluster is not None and best_score >= threshold:
            best_cluster["members"].append(idx)
            member_vecs = embeddings[best_cluster["members"]]
            centroid = member_vecs.mean(axis=0)
            norm = np.linalg.norm(centroid)
            best_cluster["centroid"] = centroid / norm if norm > 0 else centroid
        else:
            clusters.append(
                {
                    "members": [idx],
                    "centroid": vec.copy(),
                    "product_area": tickets[idx]["product_area"],
                }
            )

    return [c["members"] for c in clusters]


def _classify_coverage(best_score: float) -> str:
    if best_score >= GOOD_COVERAGE_THRESHOLD:
        return "good"
    if best_score >= WEAK_COVERAGE_THRESHOLD:
        return "weak"
    return "missing"


def _theme_label(theme_tickets: list[dict]) -> str:
    theme_id = _theme_id(theme_tickets)
    if theme_id in THEME_LABELS:
        return THEME_LABELS[theme_id]
    return theme_id.replace("_", " ").capitalize()


def _theme_id(theme_tickets: list[dict]) -> str:
    topics = [t.get("topic") for t in theme_tickets if t.get("topic")]
    if topics:
        return Counter(topics).most_common(1)[0][0]
    return sorted(t["id"] for t in theme_tickets)[0]


def get_ticket(ticket_id: str) -> dict | None:
    for ticket in load_tickets():
        if ticket["id"] == ticket_id:
            return ticket
    return None


def analyze() -> list[dict]:
    """Run the full pipeline and return ranked knowledge-gap themes."""
    tickets = load_tickets()
    articles = load_kb_articles()
    cache = compute_embeddings(tickets, articles)

    doc_indices = [
        i for i, t in enumerate(tickets) if t["ticket_type"] in DOC_TICKET_TYPES
    ]
    doc_tickets = [tickets[i] for i in doc_indices]
    doc_embeddings = cache["ticket_embeddings"][doc_indices]

    raw_clusters = cluster_tickets(doc_tickets, doc_embeddings)
    # A broad theme can split into multiple embedding clusters (for example,
    # SSO setup by provider versus general SSO configuration). Merge clusters
    # that resolve to the same stable theme so the UI recommends one article.
    merged_clusters: dict[str, list[int]] = {}
    for cluster_index, positions in enumerate(raw_clusters):
        theme_id = _theme_id([doc_tickets[i] for i in positions])
        merge_key = (
            theme_id
            if theme_id in THEME_LABELS
            else f"{theme_id}:{cluster_index}"
        )
        merged_clusters.setdefault(merge_key, []).extend(positions)
    clusters = list(merged_clusters.values())
    article_embeddings = cache["article_embeddings"]

    themes = []
    for member_positions in clusters:
        if len(member_positions) < MIN_CLUSTER_SIZE:
            continue
        theme_tickets = [doc_tickets[i] for i in member_positions]
        theme_embeddings = doc_embeddings[member_positions]
        centroid = theme_embeddings.mean(axis=0)
        norm = np.linalg.norm(centroid)
        centroid = centroid / norm if norm > 0 else centroid

        article_scores = article_embeddings @ centroid
        best_idx = int(np.argmax(article_scores))
        best_score = float(article_scores[best_idx])
        coverage = _classify_coverage(best_score)

        themes.append(
            {
                "theme_id": _theme_id(theme_tickets),
                "label": _theme_label(theme_tickets),
                "ticket_count": len(theme_tickets),
                "product_area": theme_tickets[0]["product_area"],
                "coverage": coverage,
                "best_match_score": best_score,
                "best_match_article": articles[best_idx] if best_score > 0 else None,
                "evidence_tickets": sorted(theme_tickets, key=lambda t: t["id"]),
            }
        )

    themes.sort(key=lambda t: (COVERAGE_RANK[t["coverage"]], -t["ticket_count"]))
    return themes


def get_kb_article(article_id: str) -> dict | None:
    for article in load_kb_articles():
        if article["id"] == article_id:
            return article
    return None


def kb_article_url(article_id: str, theme_id: str | None = None) -> str:
    url = f"?mode=kb&article={article_id}"
    if theme_id:
        url += f"&theme={theme_id}"
    return url


def _outline_from_tickets(tickets: list[dict], limit: int = 8) -> list[str]:
    """Turn recurring ticket subjects into proposed article section headings."""
    seen: set[str] = set()
    outline = []
    for ticket in tickets:
        subject = ticket["subject"].strip()
        # Normalize light punctuation so near-duplicates collapse.
        key = subject.lower().rstrip("?.!")
        if key in seen:
            continue
        seen.add(key)
        heading = subject.rstrip("?.!")
        outline.append(heading)
        if len(outline) >= limit:
            break
    return outline


def _customer_questions(tickets: list[dict]) -> list[str]:
    questions = []
    for ticket in tickets:
        subject = " ".join(ticket["subject"].split())
        body = " ".join(ticket["body"].split())
        if len(body) > 140:
            body = body[:137] + "..."
        link = f"[`{ticket['id']}`]({evidence_ticket_url(ticket['id'])})"
        questions.append(f"{link} **{subject}**: “{body}”")
    return questions


def draft_content_brief(theme: dict) -> str:
    coverage = theme["coverage"]
    tickets = theme["evidence_tickets"]
    outline = _outline_from_tickets(tickets)
    questions = _customer_questions(tickets)
    outline_md = "\n".join(f"{i}. {heading}" for i, heading in enumerate(outline, start=1))
    questions_md = "\n".join(f"- {q}" for q in questions)

    if coverage == "missing":
        goal = (
            f"Publish a new knowledge-base article that answers the recurring "
            f"\"{theme['label']}\" questions without requiring a support ticket."
        )
        existing = (
            "No close match exists in the knowledge base today. "
            "Do not bolt this onto an unrelated article. Create a dedicated page."
        )
        recommendation = (
            "Create a new article with the outline below, then link it from "
            "Settings / related product surfaces where customers currently get stuck."
        )
        article_block = ""
    else:
        article = theme["best_match_article"]
        goal = (
            f"Update \"{article['title']}\" so customers stop opening tickets about "
            f"\"{theme['label']}\"."
        )
        existing = (
            f"**Closest article today:** [{article['id']}] {article['title']} "
            f"(similarity {theme['best_match_score']:.0%})\n\n"
            f"> {article['content']}\n\n"
            "The article is related, but it does not walk through the specific "
            "steps customers keep asking about."
        )
        recommendation = (
            f"Expand \"{article['title']}\" with the missing sections below. "
            "Keep the existing overview; add concrete steps, limits, and failure cases."
        )
        article_block = (
            f"\n**Open article to improve:** `{article['id']}` "
            f"(use the link on the theme card)\n"
        )

    return (
        f"# Content brief: {theme['label']}\n\n"
        f"**Product area:** {theme['product_area']}\n"
        f"**Recurring customers:** {theme['ticket_count']}\n"
        f"**Current coverage:** {coverage}\n\n"
        f"## Goal\n{goal}\n\n"
        f"## What exists today\n{existing}\n"
        f"{article_block}\n"
        f"## Proposed article outline\n{outline_md}\n\n"
        f"## Evidence & customer questions "
        f"({theme['ticket_count']} tickets, click an ID to open the local evidence view)\n"
        f"{questions_md}\n\n"
        f"## Suggested next step\n{recommendation}\n\n"
        f"_Draft recommendation for a content owner. Publishing is an explicit "
        f"human action and only writes to this app's local demo knowledge base._\n"
    )
