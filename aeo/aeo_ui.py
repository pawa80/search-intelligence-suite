"""Streamlit UI for AEO Agent — integrated into the suite with matrix context."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
import streamlit as st

from aeo.context_builder import build_page_context, build_context_block

# Temporarily add aeo/ to sys.path for imports that need it (recommender -> intelligence_feed),
# then remove it so it doesn't poison other `from app import` calls
_aeo_dir = os.path.dirname(os.path.abspath(__file__))
_added = False
if _aeo_dir not in sys.path:
    sys.path.insert(0, _aeo_dir)
    _added = True
from aeo.analyzer import analyze_url
from aeo.recommender import generate_recommendations
if _added:
    sys.path.remove(_aeo_dir)


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, "")


def _refresh_jwt() -> str | None:
    """Refresh JWT via supabase client. Returns new token or None."""
    try:
        from supabase import create_client
        sb = create_client(_get_secret("SUPABASE_URL"), _get_secret("SUPABASE_ANON_KEY"))
        response = sb.auth.refresh_session()
        if response and response.session:
            new_token = response.session.access_token
            st.session_state.access_token = new_token
            return new_token
    except Exception:
        pass
    return None


def _db_get(token: str, table: str, params: dict) -> list[dict]:
    """Direct GET to Supabase REST API. Auto-refreshes token on 401."""
    url = f"{_get_secret('SUPABASE_URL')}/rest/v1/{table}"
    headers = {
        "apikey": _get_secret("SUPABASE_ANON_KEY"),
        "Authorization": f"Bearer {token}",
    }
    r = httpx.get(url, headers=headers, params=params, timeout=10.0)
    if r.status_code == 401:
        new_token = _refresh_jwt()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = httpx.get(url, headers=headers, params=params, timeout=10.0)
    if r.status_code >= 400:
        return []
    return r.json()


def _db_post(token: str, table: str, body: dict) -> bool:
    """Direct POST to Supabase REST API. Auto-refreshes token on 401."""
    url = f"{_get_secret('SUPABASE_URL')}/rest/v1/{table}"
    headers = {
        "apikey": _get_secret("SUPABASE_ANON_KEY"),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    r = httpx.post(url, headers=headers, json=body, timeout=10.0)
    if r.status_code == 401:
        new_token = _refresh_jwt()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = httpx.post(url, headers=headers, json=body, timeout=10.0)
    return r.status_code < 400


def _db_patch(token: str, table: str, params: dict, body: dict) -> bool:
    """Direct PATCH to Supabase REST API. Auto-refreshes token on 401."""
    url = f"{_get_secret('SUPABASE_URL')}/rest/v1/{table}"
    headers = {
        "apikey": _get_secret("SUPABASE_ANON_KEY"),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    r = httpx.patch(url, headers=headers, params=params, json=body, timeout=10.0)
    if r.status_code == 401:
        new_token = _refresh_jwt()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = httpx.patch(url, headers=headers, params=params, json=body, timeout=10.0)
    return r.status_code < 400


def _load_crawled_pages(token: str, project_id: str) -> list[dict]:
    """Load all crawled pages for this project."""
    return _db_get(token, "pages", {
        "select": "*",
        "project_id": f"eq.{project_id}",
        "last_crawled_at": "not.is.null",
        "order": "url.asc",
    })


def _load_arbeidspakker(token: str, project_id: str, page_id: str) -> list[dict]:
    """Load previous arbeidspakker for a page."""
    return _db_get(token, "arbeidspakker", {
        "select": "id,url,intent,arbeidspakke_markdown,generated_at",
        "project_id": f"eq.{project_id}",
        "page_id": f"eq.{page_id}",
        "order": "generated_at.desc",
    })


def _save_arbeidspakke(
    token: str,
    project_id: str,
    page_id: str,
    url: str,
    intent: str,
    markdown: str,
    context: dict,
) -> bool:
    """Save generated arbeidspakke to Supabase."""
    return _db_post(token, "arbeidspakker", {
        "page_id": page_id,
        "project_id": project_id,
        "url": url,
        "intent": intent,
        "arbeidspakke_markdown": markdown,
        "context_snapshot": json.dumps(context),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


def _format_arbeidspakke(recs: dict, context_block: str, url: str = "",
                         title: str = "", h1: str = "", intent: str = "") -> str:
    """Format recommendation JSON into readable markdown arbeidspakke."""
    lines = []
    lines.append("# Arbeidspakke — AEO Audit Report\n")

    # Page identity block
    if url:
        lines.append(f"**URL:** {url}")
    if title:
        lines.append(f"**Title tag:** {title}")
    if h1 and h1 != title:
        lines.append(f"**H1:** {h1}")
    if intent:
        lines.append(f"**Intent:** {intent}")
    if url or title or intent:
        lines.append("")

    lines.append(context_block)

    # Arbeidspakke content (full markdown from GPT)
    lines.append(f"{recs.get('summary', '—')}\n")

    # Critical Issues
    issues = recs.get("critical_issues", [])
    if issues:
        lines.append("## Critical Issues\n")
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")

    # Action Plan
    actions = recs.get("action_plan", [])
    if actions:
        lines.append("## Action Plan\n")
        for a in actions:
            lines.append(f"### Priority {a.get('priority', '?')}: {a.get('action', '')}\n")
            lines.append(f"**Why:** {a.get('reason', '')}")
            lines.append(f"**Intelligence source:** {a.get('intelligence_source', '—')}")
            if a.get("current_text"):
                lines.append(f"\n**Current text:**\n> {a['current_text']}")
            if a.get("suggested_text"):
                lines.append(f"\n**Suggested text:**\n> {a['suggested_text']}")
            lines.append("")

    # Quick Wins
    wins = recs.get("quick_wins", [])
    if wins:
        lines.append("## Quick Wins\n")
        for w in wins:
            lines.append(f"- {w}")
        lines.append("")

    # Intelligence Applied
    intel = recs.get("intelligence_applied", [])
    if intel:
        applied = [i for i in intel if i.get("verdict") == "APPLIES"]
        respected = [i for i in intel if i.get("verdict") == "RESPECTED"]

        if applied:
            lines.append("## Intelligence Applied\n")
            for i in applied:
                lines.append(f"- **{i.get('item', '')}** ({i.get('type', '')}): {i.get('impact', '')}")
            lines.append("")

        if respected:
            lines.append("## Counter-Signals Respected\n")
            for i in respected:
                lines.append(f"- **{i.get('item', '')}**: {i.get('impact', '')}")
            lines.append("")

    return "\n".join(lines)


def _score_badge(score: int | None) -> str:
    if score is None:
        return "—"
    if score >= 75:
        return f"🟢 {score}/100"
    if score >= 50:
        return f"🟡 {score}/100"
    return f"🔴 {score}/100"


def show_aeo_agent(
    project_ctx: dict[str, Any] | None,
    token: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """Main entry point for the AEO Agent UI."""
    st.title("AEO Agent")

    if not project_ctx:
        st.warning("Select a project first to use the AEO Agent.")
        return

    openai_key = _get_secret("OPENAI_API_KEY")
    if not openai_key:
        st.error("OPENAI_API_KEY not configured. Add it to .env or Streamlit Cloud secrets.")
        return

    project_id = project_ctx["id"]
    domain = project_ctx.get("domain", "")
    supabase_url = _get_secret("SUPABASE_URL")
    anon_key = _get_secret("SUPABASE_ANON_KEY")

    # Detect project switch — clear stale page-specific state
    prev_aeo_project = st.session_state.get("_aeo_project_id")
    if prev_aeo_project != project_id:
        for key in list(st.session_state.keys()):
            if key.startswith("aeo_page_") or key.startswith("aeo_arbeidspakke") or key.startswith("aeo_intent_"):
                del st.session_state[key]
        st.session_state["_aeo_project_id"] = project_id

    st.info(f"Project: **{project_ctx['name']}** · Domain: **{domain}**")

    # Step 1: Select page
    st.subheader("Step 1: Select page to optimise")
    pages = _load_crawled_pages(token, project_id)

    selected_page = None
    use_manual = st.checkbox("Paste URL manually instead", key=f"aeo_manual_url_{project_id}")

    if use_manual:
        manual_url = st.text_input("URL to analyse", placeholder="https://example.com/page",
                                    key=f"aeo_manual_url_input_{project_id}")
        if manual_url:
            selected_page = {"id": None, "url": manual_url.strip(), "title": "", "status_code": None}
    else:
        if not pages:
            st.info("No crawled pages found for this project. Run a crawl first, then return here.")
            return

        page_options = [f"{p['url']} — {(p.get('title') or '')[:50]}" for p in pages]
        # Pre-select page if coming from Matrise Generate button
        _page_select_key = f"aeo_page_select_{project_id}"
        matrise_url = st.session_state.pop("matrise_generate_url", None)
        if matrise_url:
            for i, p in enumerate(pages):
                if p["url"] == matrise_url:
                    st.session_state[_page_select_key] = i
                    break
        selected_idx = st.selectbox("Select a crawled page", range(len(page_options)),
                                     format_func=lambda i: page_options[i],
                                     key=_page_select_key)
        selected_page = pages[selected_idx]

    if not selected_page:
        return

    _page_key = selected_page.get("id") or "manual"

    # Step 1b: Page type selector
    _PAGE_TYPES = [
        "",
        "Forside",
        "Produktside",
        "Blogginnlegg",
        "Landingsside",
        "FAQ-side",
        "Om oss",
        "Kategoriside",
        "Kontaktside",
    ]

    # Pre-select from stored page_type if available
    stored_type = selected_page.get("page_type") or ""
    default_idx = _PAGE_TYPES.index(stored_type) if stored_type in _PAGE_TYPES else 0

    selected_page_type = st.selectbox(
        "Sidetype",
        _PAGE_TYPES,
        index=default_idx,
        format_func=lambda x: "Velg sidetype..." if x == "" else x,
        key=f"aeo_page_type_select_{_page_key}",
    )

    # Persist page type to DB when changed
    if selected_page.get("id") and selected_page_type != stored_type:
        _db_patch(token, "pages",
                  params={"id": f"eq.{selected_page['id']}"},
                  body={"page_type": selected_page_type if selected_page_type else None})
        # Track usage
        try:
            from tracking.usage_tracker import log_usage_event
            log_usage_event("page_type_set", event_detail=selected_page_type, project_id=project_id)
        except Exception:
            pass

    # Intelligence panel
    st.divider()
    if selected_page.get("id"):
        context = build_page_context(
            selected_page["id"], project_id, token, supabase_url, anon_key
        )

        st.subheader("Page Intelligence")
        col1, col2, col3 = st.columns(3)

        if context.get("crawl_analysis"):
            c = context["crawl_analysis"]
            col1.markdown(f"**SEO:** {_score_badge(c.get('seo_score'))}")
            col2.markdown(f"**AEO Readiness:** {_score_badge(c.get('aeo_readiness_score'))}")
            col3.markdown(f"**Content Quality:** {_score_badge(c.get('content_quality_score'))}")

        col_gsc, col_ga = st.columns(2)
        if context.get("gsc"):
            g = context["gsc"]
            col_gsc.markdown(
                f"**GSC:** {g.get('clicks')} clicks · {g.get('impressions')} impr · "
                f"Pos {g.get('position', '—')} · CTR {(g.get('ctr') or 0) * 100:.1f}%"
            )
        else:
            col_gsc.caption("No GSC data available")

        if context.get("ga"):
            a = context["ga"]
            col_ga.markdown(
                f"**GA4:** {a.get('sessions')} sessions · "
                f"{(a.get('engagement_rate') or 0) * 100:.1f}% engagement"
            )
        else:
            col_ga.caption("No GA4 data available")
    else:
        context = {"crawl_analysis": None, "gsc": None, "ga": None}
        st.caption("Manual URL — no suite data available. Audit will run on page content only.")

    # Step 2: Intent
    stored_intent = selected_page.get("intent") or ""
    st.divider()
    st.subheader("Step 2: Set page intent")
    intent = st.text_input(
        "What is this page meant to achieve?",
        value=stored_intent,
        placeholder='e.g. "Rank for \'best running shoes Norway\' and be cited by AI for product comparisons"',
        key=f"aeo_intent_input_{_page_key}",
    )

    # Step 3: Generate
    st.divider()
    st.subheader("Step 3: Generate Arbeidspakke")

    # Model selection toggle
    model_tier = st.radio(
        "AI Model",
        options=["cheap", "expensive"],
        format_func=lambda x: {
            "cheap": "💰 Reasonable — Structural Audit",
            "expensive": "🚀 Premium — Full Rewrite"
        }[x],
        index=1,
        horizontal=True,
        help="Reasonable: structural audit with actionable recommendations (~$0.02/generation). Premium: full page rewrites, complete FAQ content, and paste-ready text (~$0.11/generation).",
        key="aeo_model_tier",
    )

    if st.button("Generate Arbeidspakke", type="primary", key="btn_generate_arbeidspakke",
                  disabled=not selected_page.get("url")):
        url = selected_page["url"]

        if selected_page.get("id") and intent != stored_intent:
            _db_patch(token, "pages",
                      params={"id": f"eq.{selected_page['id']}"},
                      body={"intent": intent if intent else None})
            try:
                from tracking.usage_tracker import log_usage_event
                log_usage_event("intent_saved", event_detail="page intent set", project_id=project_id)
            except Exception:
                pass

        with st.spinner("Fetching and analysing page content..."):
            analysis = analyze_url(url, openai_key)

        if not analysis or not analysis.extraction_success:
            st.error(f"Failed to fetch page content: {analysis.error_message if analysis else 'Unknown error'}")
            return

        # Build context block for prompt
        context_block = build_context_block(context)

        # Use intent as selected_intents
        selected_intents = [intent] if intent else []

        _model_label = "o4-mini" if model_tier == "cheap" else "Claude Sonnet"
        with st.spinner(f"Generating arbeidspakke with {_model_label}..."):
            recs = generate_recommendations(
                title=analysis.title,
                full_content=analysis.full_content,
                first_paragraph=analysis.first_paragraph,
                direct_answer_score=analysis.direct_answer_score,
                citation_results=[],
                selected_intents=selected_intents,
                api_key=openai_key,
                context_block=context_block,
                page_type=selected_page_type,
                domain_context=st.session_state.get("domain_context"),
                model_tier=model_tier,
            )

        # Format as markdown
        arbeidspakke_md = _format_arbeidspakke(
            recs, context_block,
            url=url,
            title=analysis.title or selected_page.get("title") or "",
            h1=selected_page.get("h1") or "",
            intent=intent,
        )

        # Add model footer to markdown
        _model_display = "🚀 Expensive (Sonnet)" if model_tier == "expensive" else "💰 Reasonable (o4-mini)"
        arbeidspakke_md += f"\n\n---\n*Generated with: {_model_display} | {datetime.now().strftime('%Y-%m-%d %H:%M')}*"

        # Store model info in context for history display
        context["model_tier"] = model_tier
        context["model_name"] = "gpt-4.1-mini-2025-04-14" if model_tier == "cheap" else "claude-sonnet-4-20250514"

        # Save to session state for display
        st.session_state["aeo_arbeidspakke"] = arbeidspakke_md
        st.session_state["aeo_arbeidspakke_recs"] = recs
        st.session_state["aeo_arbeidspakke_context"] = context

        # Save to Supabase
        if selected_page.get("id"):
            saved = _save_arbeidspakke(
                token, project_id, selected_page["id"],
                url, intent or "", arbeidspakke_md, context,
            )
            if saved:
                st.success("Arbeidspakke saved to project.")
            else:
                st.warning("Arbeidspakke generated but failed to save to database.")
        else:
            st.info("Manual URL — arbeidspakke not saved (no page_id).")

    # Display output
    if st.session_state.get("aeo_arbeidspakke"):
        st.divider()
        st.markdown(st.session_state["aeo_arbeidspakke"])

        # Download
        st.download_button(
            "Download as .md",
            data=st.session_state["aeo_arbeidspakke"],
            file_name=f"arbeidspakke-{datetime.now().strftime('%Y%m%d-%H%M')}.md",
            mime="text/markdown",
            key="btn_download_arbeidspakke",
        )

    # Previous arbeidspakker
    if selected_page.get("id"):
        previous = _load_arbeidspakker(token, project_id, selected_page["id"])
        if previous:
            st.divider()
            with st.expander(f"Previous arbeidspakker for this page ({len(previous)})"):
                for ap in previous:
                    _snap = ap.get("context_snapshot") or {}
                    if isinstance(_snap, str):
                        try:
                            _snap = json.loads(_snap)
                        except Exception:
                            _snap = {}
                    _mtier = _snap.get("model_tier")
                    _mlabel = " — 🚀 Sonnet" if _mtier == "expensive" else " — 💰 o4-mini" if _mtier == "cheap" else ""
                    st.markdown(f"**{ap.get('generated_at', '')[:16]}**{_mlabel} — Intent: {ap.get('intent', '—')}")
                    with st.expander("View", expanded=False):
                        st.markdown(ap.get("arbeidspakke_markdown", ""))
                    st.caption("---")
