"""Generate reviewable knowledge-base article drafts with local Ollama."""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


class OllamaDraftError(RuntimeError):
    """Raised when the local Ollama service cannot generate a draft."""


def build_article_prompt(theme: dict, content_brief: str) -> str:
    article = theme.get("best_match_article")
    existing_article = (
        f"Existing article to improve:\nTitle: {article['title']}\n"
        f"Content: {article['content']}"
        if article and theme["coverage"] == "weak"
        else "No adequate article exists. Write a new article."
    )
    evidence = "\n".join(
        f"- {ticket['id']} | {ticket['subject']} | {ticket['body']}"
        for ticket in theme["evidence_tickets"]
    )

    return f"""You are a senior knowledge-base writer for a B2B SaaS product.

Write a complete customer-facing knowledge-base article in Markdown.

Rules:
- Use only the supplied article and support evidence.
- Do not invent UI labels, product behavior, limits, URLs, or policy.
- Mark any detail that requires product confirmation as [VERIFY].
- Do not mention AI, clustering, similarity scores, internal analysis, or ticket IDs.
- Use a clear title, short introduction, prerequisites if relevant, numbered steps,
  troubleshooting, and an FAQ.
- Use concise, natural section headings. Never prefix a heading with "How to:".
  Use an imperative heading for a task ("Import users from a CSV file"),
  "Troubleshoot..." for a failure, and a noun phrase for reference information.
- Consolidate related customer questions instead of turning every ticket subject
  into a separate section.
- Make the draft practical enough for a content owner to edit and publish.
- Return only the article draft in Markdown.

Theme: {theme['label']}
Product area: {theme['product_area']}
Coverage status: {theme['coverage']}

{existing_article}

Content brief:
{content_brief}

Support evidence:
{evidence}
"""


def generate_article_draft(theme: dict, content_brief: str, timeout: int = 180) -> dict:
    prompt = build_article_prompt(theme, content_brief)
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
    ).encode("utf-8")
    request = Request(
        OLLAMA_GENERATE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise OllamaDraftError(
            "Local Ollama is unavailable. Start Ollama and confirm llama3.2 is installed."
        ) from exc

    content = str(result.get("response", "")).strip()
    if not content:
        raise OllamaDraftError("Ollama returned an empty article draft.")

    return {"content": content, "model": result.get("model", OLLAMA_MODEL)}
