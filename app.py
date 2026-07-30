"""Knowledge Gap Agent Streamlit dashboard and local evidence viewers."""

from __future__ import annotations

import html
import importlib

import markdown as md
import streamlit as st
import streamlit.components.v1 as components

import knowledge_gap as _kg
import ollama_draft as _od
import review_store as _store
import validators.validation_report as _vr

# Streamlit often keeps a stale knowledge_gap module in memory on Windows/OneDrive.
# Force a reload so new helpers are always visible after code changes.
_kg = importlib.reload(_kg)
_od = importlib.reload(_od)
_store = importlib.reload(_store)
_vr = importlib.reload(_vr)
analyze = _kg.analyze
build_report = _vr.build_report
proposed_outline = _kg.proposed_outline
draft_content_brief = _kg.draft_content_brief
get_ticket = _kg.get_ticket
load_kb_articles = _kg.load_kb_articles
generate_article_draft = _od.generate_article_draft
OllamaDraftError = _od.OllamaDraftError
coverage_changes = _store.coverage_changes
ensure_weekly_snapshot = _store.ensure_weekly_snapshot
load_addressed = _store.load_addressed
load_article_drafts = _store.load_article_drafts
load_published_articles = _store.load_published_articles
mark_addressed = _store.mark_addressed
publish_article = _store.publish_article
save_article_draft = _store.save_article_draft
unmark_addressed = _store.unmark_addressed
unpublish_article = _store.unpublish_article

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


def published_article_url(theme_id: str) -> str:
    return f"?mode=published&theme={theme_id}"


def evidence_ticket_url(ticket_id: str) -> str:
    return f"?mode=ticket&ticket={ticket_id}"


st.set_page_config(
    page_title="Knowledge Gap Agent", page_icon="\U0001F4DA", layout="centered"
)

COVERAGE_LABEL = {"missing": "Missing", "weak": "Weak", "good": "Good"}

KB_CSS = """
<style>
.change-missing,
.change-weak,
.change-good,
.change-degraded,
.change-improved,
.change-new {
  border: 1px solid #e9e9e7;
  border-radius: 6px;
  padding: 10px 12px;
  margin: 8px 0;
  background: #fff;
}
.change-missing, .change-degraded { border-left: 4px solid #e35b5b; }
.change-weak, .change-new { border-left: 4px solid #f59f00; }
.change-good, .change-improved { border-left: 4px solid #2f9e44; }
.change-title {
  font-size: 13px;
  font-weight: 600;
  color: #37352f;
  margin: 0 0 2px;
}
.change-summary {
  font-size: 12px;
  color: #787774;
  margin: 0 0 4px;
}
.change-next {
  font-size: 12px;
  color: #37352f;
  margin: 0;
}

/* Keep long button labels inside the theme card instead of overflowing it. */
div[data-testid="stButton"] > button {
  white-space: normal;
  line-height: 1.2;
  min-height: 38px;
  padding: 6px 10px;
  font-size: 13px;
}
.st-key-published_toolbar,
.st-key-published_editor {
  max-width: 640px;
}
.st-key-published_toolbar {
  margin-top: 18px;
}

/* Compact theme card header with a Notion-style status pill */
.theme-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 2px;
}
.theme-title {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.3;
  color: #37352f;
}
.pill {
  flex: 0 0 auto;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 3px;
  white-space: nowrap;
}
.pill-missing { background: #ffe2dd; color: #9f2b12; }
.pill-weak { background: #fdecc8; color: #8a5300; }
.pill-good { background: #dbeddb; color: #1d6b32; }

/* Validation verdict shown on every theme card before any draft is offered */
.verdict {
  border: 1px solid #e9e9e7;
  border-left: 4px solid #9b9a97;
  border-radius: 6px;
  background: #fbfbfa;
  padding: 8px 12px;
  margin: 8px 0 2px;
}
.verdict-ok { border-left-color: #2f9e44; }
.verdict-review { border-left-color: #f59f00; }
.verdict-blocked { border-left-color: #e35b5b; }
.verdict-action {
  font-size: 12px;
  font-weight: 600;
  color: #37352f;
  margin: 0 0 2px;
}
.verdict-reason {
  font-size: 12px;
  color: #787774;
  margin: 0;
}
.verdict-metrics {
  font-size: 11px;
  color: #9b9a97;
  margin: 4px 0 0;
}
.focus-note {
  display: inline-block;
  background: #e7f3f8;
  color: #0b6e99;
  border-radius: 3px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 6px;
}

/* Notion / help-center style article shell */
.kb-shell, .doc-shell, .hc-shell {
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  max-width: 640px;
  color: #37352f;
}
.kb-top {
  background: #f7f6f3;
  color: #787774;
  padding: 8px 14px;
  border: 1px solid #e9e9e7;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 12px;
}
.kb-badge {
  background: #2383e2;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 3px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.kb-body {
  border: 1px solid #e9e9e7;
  border-top: none;
  border-radius: 0 0 6px 6px;
  padding: 28px 36px 36px;
  background: #fff;
}
.doc-shell {
  border: 1px solid #e9e9e7;
  border-radius: 6px;
  padding: 18px 24px 24px;
  background: #fff;
  margin: 4px 0 8px;
}
.kb-body h1, .doc-body h1, .hc-body h1 {
  margin: 0 0 4px;
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -0.01em;
  color: #37352f;
}
.kb-meta {
  color: #787774;
  font-size: 12px;
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid #e9e9e7;
}
.kb-content {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: #37352f;
}
.doc-body, .hc-body {
  font-size: 13px;
  line-height: 1.55;
  color: #37352f;
}
.doc-body h1, .hc-body h1 { margin-top: 0; }
.doc-body h2, .hc-body h2 {
  margin: 1.2em 0 0.3em;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.3;
  color: #37352f;
}
.doc-body h3, .hc-body h3 {
  margin: 1em 0 0.25em;
  font-size: 0.85rem;
  font-weight: 600;
  color: #37352f;
}
.doc-body p, .hc-body p { margin: 0.35em 0; }
.doc-body ul, .doc-body ol, .hc-body ul, .hc-body ol {
  margin: 0.3em 0 0.5em;
  padding-left: 1.25em;
}
.doc-body li, .hc-body li { margin: 0.15em 0; }
.doc-body li > ul, .doc-body li > ol { margin: 0.1em 0; }
.doc-body a, .hc-body a {
  color: #2383e2;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.doc-body code, .hc-body code {
  font-size: 0.85em;
  background: #f1f1ef;
  padding: 1px 4px;
  border-radius: 3px;
}
.doc-body table, .hc-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.6em 0;
  font-size: 12px;
}
.doc-body th, .doc-body td, .hc-body th, .hc-body td {
  border: 1px solid #e9e9e7;
  padding: 5px 8px;
  text-align: left;
  vertical-align: top;
}
.doc-body th, .hc-body th { background: #f7f6f3; font-weight: 600; }
.doc-body hr, .hc-body hr {
  border: none;
  border-top: 1px solid #e9e9e7;
  margin: 1em 0;
}
.kb-flag, .doc-callout {
  background: #fbf3db;
  border: none;
  border-radius: 4px;
  padding: 8px 10px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #5d4a14;
  line-height: 1.4;
}

/* Stub help center page for published articles */
.hc-top {
  background: #6b53f5;
  border-radius: 6px 6px 0 0;
  padding: 14px 18px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}
.hc-search {
  margin-top: 10px;
  background: rgba(255, 255, 255, 0.16);
  border-radius: 6px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.85);
}
.hc-body {
  border: 1px solid #e9e9e7;
  border-top: none;
  border-radius: 0 0 6px 6px;
  padding: 20px 24px 28px;
  background: #fff;
}
.hc-crumbs {
  color: #787774;
  font-size: 11px;
  margin-bottom: 14px;
}
.hc-meta {
  color: #787774;
  font-size: 11px;
  margin-bottom: 12px;
}
.hc-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0 0 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e9e9e7;
}
.hc-tool {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid #e9e9e7;
  background: #fff;
  color: #37352f;
  border-radius: 4px;
  padding: 4px 9px;
  font-size: 12px;
  line-height: 1.2;
  white-space: nowrap;
}
.hc-tool-primary {
  border-color: #2383e2;
  color: #2383e2;
  font-weight: 600;
}
.hc-footer {
  margin-top: 22px;
  padding-top: 10px;
  border-top: 1px solid #e9e9e7;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  color: #787774;
  font-size: 11px;
  align-items: center;
}
.hc-footer span {
  white-space: nowrap;
}
</style>
"""


def strip_leading_title(markdown_text: str) -> str:
    """Drop the article's own H1 when the page already renders a title."""
    lines = markdown_text.lstrip().split("\n")
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).lstrip()
    return markdown_text


def markdown_to_html(text: str) -> str:
    return md.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    )


def render_article_draft(content: str) -> None:
    """Render an AI draft like a compact Notion / help-center article."""
    st.markdown(
        f"""
        <div class="doc-shell">
          <div class="doc-callout">
            Review required. This AI draft may contain incorrect or
            incomplete product details.
          </div>
          <div class="doc-body">{markdown_to_html(content)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_content_brief(brief: str) -> None:
    """Render the content brief with the same compact document typography."""
    st.markdown(
        f'<div class="doc-shell"><div class="doc-body">'
        f"{markdown_to_html(brief)}</div></div>",
        unsafe_allow_html=True,
    )


VERDICT_STYLE = {
    "Present to Content Owner": "verdict-ok",
    "Update Existing Article": "verdict-ok",
    "Needs SME Review": "verdict-review",
    "Improve Search Metadata": "verdict-review",
    "Insufficient Evidence": "verdict-blocked",
    "Reject": "verdict-blocked",
}


def render_validation(report: dict) -> None:
    """Show the verdict that decides whether a draft is offered at all."""
    support = next(
        stage for stage in report["stages"] if stage["stage"] == "minimum_support"
    )
    metrics = (
        f"Gap class: {report['gap_class']}. "
        f"Evidence: {report['evidence_strength']} "
        f"({support['metrics']['tickets']} tickets, "
        f"{support['metrics']['unique_customers']} customers, "
        f"{support['metrics']['time_span_days']} days). "
        f"Gap confidence {report['content_gap_confidence']:.0%}. "
        f"Overlap with closest article {report['duplicate_score']:.0%}. "
        f"Outline completeness {report['outline_completeness']:.0%}."
    )
    st.markdown(
        f'<div class="verdict {VERDICT_STYLE[report["recommended_action"]]}">'
        f'<p class="verdict-action">Validation: {html.escape(report["recommended_action"])}</p>'
        f'<p class="verdict-reason">{html.escape(" ".join(report["reasons"]))}</p>'
        f'<p class="verdict-metrics">{html.escape(metrics)}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Validation report", expanded=False):
        for stage in report["stages"]:
            name = stage["stage"].replace("_", " ").capitalize()
            st.markdown(f"**{name}** ({stage['status']}): {stage['summary']}")
        if report["withheld_sections"]:
            st.caption(
                "Withheld from the outline until an SME confirms them: "
                + "; ".join(report["withheld_sections"])
            )


def render_published_article() -> None:
    """Stub help center page showing an article after it was published."""
    st.markdown(KB_CSS, unsafe_allow_html=True)
    theme_id = st.query_params.get("theme", "")
    published = load_published_articles().get(theme_id)
    edit_key = f"edit_published_{theme_id}"

    if st.button("← Back to dashboard"):
        st.session_state.pop(edit_key, None)
        st.query_params.clear()
        st.rerun()

    if published is None:
        st.error("This article has not been published to the knowledge base yet.")
        return

    editing = bool(st.session_state.get(edit_key))
    product_area = html.escape(published["product_area"].title())
    published_on = html.escape(published["published_at"][:10])

    st.markdown(
        f"""
        <div class="hc-shell">
          <div class="hc-top">
            Northstar Help Center
            <div class="hc-search">Search for articles...</div>
          </div>
          <div class="hc-body">
            <div class="hc-crumbs">
              All collections › {product_area} › Articles
            </div>
            <h1>{html.escape(published["label"])}</h1>
            <div class="hc-meta">Published {published_on}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="published_toolbar"):
        edit_col, publish_col, copy_col, history_col, unpub_col = st.columns(
            [1, 1, 1.1, 1.1, 1.2]
        )
        with edit_col:
            if st.button(
                "Done" if editing else "Edit",
                key=f"edit_btn_{theme_id}",
                use_container_width=True,
                type="primary" if editing else "secondary",
            ):
                st.session_state[edit_key] = not editing
                st.rerun()
        with publish_col:
            if st.button(
                "Publish",
                key=f"publish_page_btn_{theme_id}",
                use_container_width=True,
            ):
                publish_article(
                    theme_id,
                    {
                        "label": published["label"],
                        "product_area": published["product_area"],
                    },
                    published["content"],
                )
                st.toast("Published to the Help Center.")
                st.rerun()
        with copy_col:
            if st.button(
                "Copy page", key=f"copy_btn_{theme_id}", use_container_width=True
            ):
                st.toast("Page Markdown copied (demo).", icon="📋")
        with history_col:
            if st.button(
                "History", key=f"history_btn_{theme_id}", use_container_width=True
            ):
                st.toast("Version history is a demo stub.", icon="🕘")
        with unpub_col:
            if st.button(
                "Unpublish",
                key=f"unpub_btn_{theme_id}",
                use_container_width=True,
            ):
                unpublish_article(theme_id)
                st.session_state.pop(edit_key, None)
                st.query_params.clear()
                st.rerun()

    if editing:
        with st.container(key="published_editor"):
            edited = st.text_area(
                "Article Markdown",
                value=published["content"],
                height=420,
                key=f"editor_{theme_id}",
                label_visibility="collapsed",
            )
            save_col, cancel_col, _ = st.columns([1, 1, 3])
            with save_col:
                if st.button(
                    "Save changes",
                    key=f"save_btn_{theme_id}",
                    use_container_width=True,
                    type="primary",
                ):
                    publish_article(
                        theme_id,
                        {
                            "label": published["label"],
                            "product_area": published["product_area"],
                        },
                        edited,
                    )
                    st.session_state[edit_key] = False
                    st.rerun()
            with cancel_col:
                if st.button(
                    "Cancel",
                    key=f"cancel_btn_{theme_id}",
                    use_container_width=True,
                ):
                    st.session_state[edit_key] = False
                    st.rerun()
    else:
        st.markdown(
            f"""
            <div class="hc-shell">
              <div class="hc-body" style="border-top:1px solid #e9e9e7;border-radius:6px;">
                <div class="hc-content">
                  {markdown_to_html(strip_leading_title(published["content"]))}
                </div>
                <div class="hc-footer">
                  <span>Northstar Help Center</span>
                  <span>Edited {published_on}</span>
                  <span>Comments</span>
                  <span>Favorites</span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_kb_article() -> None:
    st.markdown(KB_CSS, unsafe_allow_html=True)
    article_id = st.query_params.get("article", "")
    theme_id = st.query_params.get("theme")
    article = get_kb_article(article_id)

    if st.button("← Back to dashboard"):
        st.query_params.clear()
        st.rerun()

    if article is None:
        st.error(f"Knowledge base article {article_id!r} was not found.")
        return

    flag_html = ""
    if theme_id:
        flag_html = (
            f'<div class="kb-flag"><strong>Flagged for improvement.</strong> '
            f"This article is the closest match for theme "
            f"<code>{html.escape(theme_id)}</code>, but coverage is weak. "
            f"Use the content brief on the dashboard for the missing sections."
            f"</div>"
        )

    st.markdown(
        f"""
        <div class="kb-shell">
          <div class="kb-top">
            <span class="kb-badge">Knowledge base</span>
            <span>{html.escape(article["id"])}</span>
          </div>
          <div class="kb-body">
            {flag_html}
            <h1>{html.escape(article["title"])}</h1>
            <div class="kb-meta">Synthetic demo article · Northstar Help Center</div>
            <div class="kb-content">{html.escape(article["content"])}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_evidence_ticket() -> None:
    st.markdown(KB_CSS, unsafe_allow_html=True)
    ticket_id = st.query_params.get("ticket", "")
    ticket = get_ticket(ticket_id)

    if st.button("← Back to dashboard"):
        st.query_params.clear()
        st.rerun()

    if ticket is None:
        st.error(f"Evidence ticket {ticket_id!r} was not found.")
        return

    st.markdown(
        f"""
        <div class="doc-shell">
          <div class="doc-body">
            <div class="kb-meta">
              Synthetic evidence ticket · {html.escape(ticket["id"])} ·
              {html.escape(ticket["product_area"].title())}
            </div>
            <h1>{html.escape(ticket["subject"])}</h1>
            <p>{html.escape(ticket["body"])}</p>
            <div class="kb-meta">
              Created {html.escape(ticket["created_at"][:10])} ·
              Type: {html.escape(ticket["ticket_type"])}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard() -> None:
    st.markdown(KB_CSS, unsafe_allow_html=True)
    st.title("Knowledge Gap Agent")
    st.caption(
        "Identifies recurring support questions that documentation does not "
        "adequately answer. Evidence tickets and weak-coverage "
        "articles open in the local knowledge base viewer."
    )

    with st.spinner("Analyzing tickets against the knowledge base..."):
        themes = analyze()
        for theme in themes:
            theme.setdefault(
                "theme_id",
                theme.get("label", "unknown").lower().replace(" ", "_")[:64],
            )
        ensure_weekly_snapshot(themes)
        changes = coverage_changes(themes)
        addressed = load_addressed()
        article_drafts = load_article_drafts()
        published = load_published_articles()

    active = [t for t in themes if t["theme_id"] not in addressed]
    addressed_themes = [t for t in themes if t["theme_id"] in addressed]

    missing = [t for t in active if t["coverage"] == "missing"]
    weak = [t for t in active if t["coverage"] == "weak"]
    good = [t for t in active if t["coverage"] == "good"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Missing documentation", len(missing))
    col2.metric("Weak coverage", len(weak))
    col3.metric("Well covered", len(good))
    col4.metric("Addressed this cycle", len(addressed_themes))

    if changes:
        st.subheader("Needs attention this week")
        st.caption(
            "Coverage shifts since last week. Each row has a recommended next step. "
            "Open the theme and act on it."
        )
        for change in changes:
            css = f"change-{change['to_coverage']}"
            action_col, cta_col = st.columns([4.2, 1.3])
            with action_col:
                st.markdown(
                    f'<div class="{css}">'
                    f'<div class="change-title">{html.escape(change["label"])}</div>'
                    f'<div class="change-summary">{html.escape(change["summary"])}</div>'
                    f'<div class="change-next">'
                    f"<strong>Next:</strong> {html.escape(change['next_step'])}"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
            with cta_col:
                st.write("")
                if st.button(
                    change["cta"],
                    key=f"change_cta_{change['theme_id']}_{change['kind']}",
                    use_container_width=True,
                    type=(
                        "primary"
                        if change["to_coverage"] in {"missing", "weak"}
                        else "secondary"
                    ),
                ):
                    target = (change.get("to_coverage") or "missing").capitalize()
                    st.session_state["coverage_filter"] = target
                    st.session_state["focus_theme_id"] = change["theme_id"]
                    st.session_state["scroll_to_focus"] = True
                    st.rerun()
        st.divider()

    if "coverage_filter" not in st.session_state:
        st.session_state["coverage_filter"] = "Missing"

    status_filter = st.radio(
        "Filter by coverage",
        options=["Missing", "Weak", "Good", "All", "Addressed"],
        horizontal=True,
        key="coverage_filter",
    )

    if status_filter == "Addressed":
        visible = addressed_themes
    elif status_filter == "All":
        visible = active
    else:
        visible = [t for t in active if t["coverage"] == status_filter.lower()]

    focus_theme_id = st.session_state.get("focus_theme_id")
    if focus_theme_id:
        visible = sorted(
            visible,
            key=lambda theme: 0 if theme["theme_id"] == focus_theme_id else 1,
        )

    if not visible:
        st.info("No themes match this filter.")

    for index, theme in enumerate(visible):
        article = theme["best_match_article"]
        is_addressed = theme["theme_id"] in addressed
        action_key = f"{theme['theme_id']}_{index}"
        is_focused = theme["theme_id"] == focus_theme_id

        if article and theme["coverage"] in {"weak", "good"}:
            article_href = kb_article_url(article["id"], theme["theme_id"])
            article_line = (
                f"Closest article: [{article['title']}]({article_href}) "
                f"(similarity {theme['best_match_score']:.0%})"
            )
        elif article:
            article_line = (
                f"Closest article: **{article['title']}** "
                f"(similarity {theme['best_match_score']:.0%}), "
                f"still too weak to count as coverage"
            )
        else:
            article_line = "No matching article found."

        with st.container(border=True):
            if is_focused:
                st.markdown(
                    '<div id="focused-theme" class="focus-note">'
                    "Opened from Needs attention</div>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<div class="theme-head">'
                f'<span class="theme-title">{html.escape(theme["label"])}</span>'
                f'<span class="pill pill-{theme["coverage"]}">'
                f'{COVERAGE_LABEL[theme["coverage"]]}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

            customers = {
                ticket.get("customer_id")
                for ticket in theme["evidence_tickets"]
                if ticket.get("customer_id")
            }
            st.caption(
                f"**{len(customers)} customers** across "
                f"**{theme['ticket_count']} tickets** "
                f"(product area: {theme['product_area']}). {article_line}"
            )

            if theme["coverage"] == "weak" and article:
                st.markdown(
                    f"[Open article to improve →]({kb_article_url(article['id'], theme['theme_id'])})"
                )

            report = build_report(theme, proposed_outline(theme))
            render_validation(report)

            review_col = None
            if report["may_present_outline"]:
                content_brief = draft_content_brief(theme, report["validated_outline"])
                with st.expander("Draft content brief", expanded=False):
                    render_content_brief(content_brief)

                generated = article_drafts.get(theme["theme_id"])
                if generated:
                    with st.expander(
                        "AI-generated article draft",
                        expanded=is_focused or focus_theme_id is None,
                    ):
                        render_article_draft(generated["content"])

                is_published = theme["theme_id"] in published
                if is_published:
                    st.markdown(
                        f"Published to the knowledge base: "
                        f"[open article →]({published_article_url(theme['theme_id'])})"
                    )

                generate_label = "Regenerate draft" if generated else "Generate draft"
                publish_label = (
                    "Update published article"
                    if is_published
                    else "Publish to knowledge base"
                )
                generate_col, publish_col, review_col = st.columns([1.15, 1.5, 1.35])
                with generate_col:
                    if st.button(
                        generate_label,
                        key=f"generate_{action_key}",
                        use_container_width=True,
                    ):
                        with st.spinner("Generating..."):
                            try:
                                result = generate_article_draft(theme, content_brief)
                            except OllamaDraftError as exc:
                                st.error(str(exc))
                            else:
                                save_article_draft(theme["theme_id"], theme, result)
                                st.rerun()

                with publish_col:
                    if st.button(
                        publish_label,
                        key=f"publish_{action_key}",
                        use_container_width=True,
                        disabled=generated is None,
                        help=(
                            None
                            if generated
                            else "Generate a draft before publishing."
                        ),
                    ):
                        publish_article(
                            theme["theme_id"], theme, generated["content"]
                        )
                        st.query_params["mode"] = "published"
                        st.query_params["theme"] = theme["theme_id"]
                        st.rerun()
            else:
                review_col, _ = st.columns([1, 3])

            with review_col:
                if is_addressed:
                    if st.button(
                        "Reopen",
                        key=f"reopen_{action_key}",
                        use_container_width=True,
                    ):
                        unmark_addressed(theme["theme_id"])
                        st.rerun()
                else:
                    if st.button(
                        "Mark as addressed",
                        key=f"addr_{action_key}",
                        use_container_width=True,
                        type="primary",
                    ):
                        mark_addressed(theme["theme_id"], theme)
                        st.rerun()
    if st.session_state.pop("scroll_to_focus", False):
        components.html(
            """
            <script>
              const target = parent.document.getElementById("focused-theme");
              if (target) {
                target.scrollIntoView({behavior: "smooth", block: "center"});
              }
            </script>
            """,
            height=0,
        )


mode = st.query_params.get("mode")
if mode == "kb":
    render_kb_article()
elif mode == "published":
    render_published_article()
elif mode == "ticket":
    render_evidence_ticket()
else:
    render_dashboard()
