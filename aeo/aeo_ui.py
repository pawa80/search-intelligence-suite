"""Streamlit UI for AEO Agent — integrated into the suite with matrix context."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
from urllib.parse import urlparse
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
        "status": "eq.active",
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


def _clean_playbook_md(md: str) -> str:
    """Post-process playbook markdown: replace non-interactive checkboxes with bullets."""
    md = md.replace("☐ ", "• ")
    md = md.replace("□ ", "• ")
    md = md.replace("[ ] ", "• ")
    md = md.replace("[x] ", "✓ ")
    md = md.replace("[X] ", "✓ ")
    md = md.replace("- [ ] ", "- ")
    md = md.replace("- [x] ", "- ✓ ")
    md = md.replace("- [X] ", "- ✓ ")
    return md


def _format_arbeidspakke(recs: dict, context_block: str, url: str = "",
                         title: str = "", h1: str = "", intent: str = "") -> str:
    """Format recommendation JSON into readable markdown arbeidspakke."""
    lines = []
    lines.append("# Playbook — AEO Audit Report\n")

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
    st.title("AI Workspace")

    if not project_ctx:
        st.warning("Select a project first to use the AI Workspace.")
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
            if (key.startswith("aeo_page_") or key.startswith("aeo_arbeidspakke")
                    or key.startswith("aeo_intent_") or key.startswith("aeo_custom_")):
                del st.session_state[key]
        st.session_state["_aeo_project_id"] = project_id

    # Load domain strategy (cached per project in session state)
    _strategy_key = f"_domain_strategy_{project_id}"
    if _strategy_key not in st.session_state:
        _ds = project_ctx.get("domain_strategy") or {}
        if isinstance(_ds, str):
            try:
                _ds = json.loads(_ds)
            except (json.JSONDecodeError, TypeError):
                _ds = {}
        st.session_state[_strategy_key] = _ds
    _domain_strategy = st.session_state.get(_strategy_key, {})

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
        "Homepage",
        "Product/Service Page",
        "Blog Post",
        "Landing Page",
        "FAQ Page",
        "About Page",
        "Category Page",
        "Contact Page",
    ]

    # Pre-select from stored page_type if available
    stored_type = selected_page.get("page_type") or ""
    default_idx = _PAGE_TYPES.index(stored_type) if stored_type in _PAGE_TYPES else 0

    selected_page_type = st.selectbox(
        "Page type",
        _PAGE_TYPES,
        index=default_idx,
        format_func=lambda x: "Select page type..." if x == "" else x,
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

        # Check if Google is connected (cached per session)
        _gc_key = f"_google_connected_{workspace_id}"
        if _gc_key not in st.session_state:
            _gc_rows = _db_get(token, "google_connections", {
                "select": "gsc_property,ga4_property_id",
                "workspace_id": f"eq.{workspace_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            })
            st.session_state[_gc_key] = _gc_rows[0] if _gc_rows else None
        _gc = st.session_state.get(_gc_key)

        col_gsc, col_ga = st.columns(2)
        if context.get("gsc"):
            g = context["gsc"]
            col_gsc.markdown(
                f"**GSC:** {g.get('clicks')} clicks · {g.get('impressions')} impr · "
                f"Pos {g.get('position', '—')} · CTR {(g.get('ctr') or 0) * 100:.1f}%"
            )
        elif _gc and _gc.get("gsc_property"):
            col_gsc.caption("GSC connected — import data in **Data Sources** to see metrics here")
        else:
            col_gsc.caption("GSC not connected — connect in **Data Sources**")

        if context.get("ga"):
            a = context["ga"]
            col_ga.markdown(
                f"**GA4:** {a.get('sessions')} sessions · "
                f"{(a.get('engagement_rate') or 0) * 100:.1f}% engagement"
            )
        elif _gc and _gc.get("ga4_property_id"):
            col_ga.caption("GA4 connected — import data in **Data Sources** to see metrics here")
        else:
            col_ga.caption("GA4 not connected — connect in **Data Sources**")
    else:
        context = {"crawl_analysis": None, "gsc": None, "ga": None}
        st.caption("Manual URL — no suite data available. Audit will run on page content only.")

    # Domain Strategy banner
    _has_strategy = bool(_domain_strategy and _domain_strategy.get("page_roles") and not _domain_strategy.get("parse_error"))
    _ROLE_EMOJI = {
        "entity_anchor": "\U0001f7e3",
        "citation_target": "\U0001f7e2",
        "authority_builder": "\U0001f535",
        "conversion_endpoint": "\U0001f7e0",
        "cannibal_overlap": "\U0001f534",
    }
    st.divider()
    if _has_strategy and selected_page.get("id"):
        _page_role_info = None
        _lookup_id = str(selected_page["id"])
        _strategy_ids = [_pr.get("page_id") for _pr in _domain_strategy.get("page_roles", [])]
        for _pr in _domain_strategy.get("page_roles", []):
            if _pr.get("page_id") == _lookup_id:
                _page_role_info = _pr
                break
        if not _page_role_info:
            with st.expander("Debug: strategy page_id mismatch", expanded=False):
                st.code(f"Looking for: {repr(_lookup_id)}\nStrategy IDs: {_strategy_ids[:5]}", language="text")
        if _page_role_info:
            _role_raw = _page_role_info.get("role", "")
            _role_label = _role_raw.replace("_", " ").title()
            _role_emoji = _ROLE_EMOJI.get(_role_raw, "\U0001f3af")
            _banner_lines = [f"{_role_emoji} **Strategic role: {_role_label}**"]
            if _page_role_info.get("reasoning"):
                _banner_lines.append(_page_role_info["reasoning"])
            _pq = _page_role_info.get("priority_queries") or []
            if _pq:
                _banner_lines.append("**Priority queries:** " + ", ".join(f'"{q}"' for q in _pq[:5]))
            _dnr = _page_role_info.get("do_not_recommend") or []
            if _dnr:
                _banner_lines.append("\u26a0\ufe0f **Do not recommend:** " + "; ".join(_dnr))
            st.info("\n\n".join(_banner_lines))
        else:
            st.info("\U0001f3af No strategic role assigned for this page. Regenerate your domain strategy on the **Crawl** page to include recently added pages.")
    elif not _has_strategy:
        st.info("\U0001f3af No domain strategy generated yet. Generate one on the **Crawl** page to get differentiated playbooks for each page.")

    # --- Extract page content data from page_elements for reuse ---
    _pe = selected_page.get("page_elements") or {}
    if isinstance(_pe, str):
        try:
            _pe = json.loads(_pe)
        except (json.JSONDecodeError, TypeError):
            _pe = {}
    _h2_structure = _pe.get("h2_structure") or []
    _meta_desc = selected_page.get("meta_description") or ""
    _page_title = selected_page.get("title") or selected_page.get("url", "")
    _page_h1 = selected_page.get("h1") or ""
    _page_word_count = selected_page.get("word_count") or 0
    _first_500 = ""  # populated by live fetch fallback if needed
    _live_headings = []  # heading dicts from live fetch

    # Fallback: if page_elements has no H2 structure, fetch the page live and cache.
    # meta_description and h1 are direct columns on pages (always populated by crawl),
    # but H2s/content only exist in page_elements JSONB (added in v3.6). Pages crawled
    # before v3.6 have h1/meta but empty page_elements — we need the live fetch for those.
    _has_rich_content = bool(_h2_structure)
    _live_cache_key = f"aeo_live_analysis_{_page_key}"
    if not _has_rich_content and selected_page.get("url"):
        if _live_cache_key not in st.session_state:
            if not st.session_state.get("operation_in_progress", False):
                with st.spinner("Fetching page content for preview..."):
                    try:
                        _live = analyze_url(selected_page["url"])
                        if _live and _live.extraction_success:
                            st.session_state[_live_cache_key] = {
                                "title": _live.title,
                                "first_paragraph": _live.first_paragraph,
                                "first_500_words": _live.first_500_words,
                                "headings": _live.headings or [],
                                "word_count": _live.total_word_count,
                                "h1": "",
                            }
                            # Extract H1 from headings
                            for _hd in (_live.headings or []):
                                if _hd.get("level") == "h1" and _hd.get("text"):
                                    st.session_state[_live_cache_key]["h1"] = _hd["text"]
                                    break
                        else:
                            st.session_state[_live_cache_key] = None
                    except Exception as _fetch_err:
                        st.session_state[_live_cache_key] = None
                        st.caption(f"Could not fetch page: {_fetch_err}")

        _live_data = st.session_state.get(_live_cache_key)
        if _live_data:
            _page_title = _live_data["title"] or _page_title
            _page_h1 = _live_data["h1"] or _page_h1
            _page_word_count = _live_data["word_count"] or _page_word_count
            _first_500 = _live_data.get("first_500_words", "")
            _live_headings = _live_data.get("headings", [])
            # Build H2 list from live headings
            if not _h2_structure:
                _h2_structure = [h["text"] for h in _live_headings if h.get("level") == "h2" and h.get("text")]
            if not _meta_desc:
                _meta_desc = (_live_data.get("first_paragraph") or "")[:300]

    # Build a content summary from available data for intent generation + preview
    _content_parts = []
    if _page_h1:
        _content_parts.append(f"H1: {_page_h1}")
    if _meta_desc:
        _content_parts.append(f"Meta description: {_meta_desc}")
    if _h2_structure:
        _content_parts.append("H2 headings:\n" + "\n".join(f"- {h}" for h in _h2_structure[:20]))
    _og_desc = (_pe.get("og_tags") or {}).get("og:description", "")
    if _og_desc and _og_desc != _meta_desc:
        _content_parts.append(f"OG description: {_og_desc}")
    _json_ld = _pe.get("json_ld") or []
    if _json_ld:
        _ld_types = [s.get("@type", "Unknown") for s in _json_ld if isinstance(s, dict)]
        if _ld_types:
            _content_parts.append(f"Schema types: {', '.join(_ld_types)}")
    if _first_500:
        _content_parts.append(f"First 500 words:\n{_first_500[:2000]}")
    _content_summary = "\n".join(_content_parts)

    # Content preview (D)
    _content_source = "live fetch" if st.session_state.get(_live_cache_key) else "crawl data"
    st.divider()
    if _content_summary:
        with st.expander(f"Content Preview ({_page_word_count} words — {_content_source})", expanded=False):
            if _page_h1:
                st.markdown(f"**H1:** {_page_h1}")
            if _meta_desc:
                st.markdown(f"**Meta description:** {_meta_desc}")
            if _h2_structure:
                st.markdown("**H2 structure:**")
                for _h2 in _h2_structure[:20]:
                    st.markdown(f"- {_h2}")
                if len(_h2_structure) > 20:
                    st.caption(f"...and {len(_h2_structure) - 20} more")
            if _json_ld:
                _ld_types = [s.get("@type", "Unknown") for s in _json_ld if isinstance(s, dict)]
                if _ld_types:
                    st.markdown(f"**Schema markup:** {', '.join(_ld_types)}")
            if _pe.get("hero_image_alt"):
                st.markdown(f"**Hero image alt:** {_pe['hero_image_alt']}")
            if _first_500:
                st.markdown("**First 500 words:**")
                st.text(_first_500[:2000])
    else:
        st.caption("No content preview available — run a crawl to populate page data.")

    # Step 2: Validate user intents
    _raw_stored_intent = selected_page.get("intent") or ""
    # Parse stored intent — JSON (new) or comma-separated text (legacy)
    _stored_intents_set = set()
    _stored_manual = ""
    if _raw_stored_intent:
        try:
            _parsed = json.loads(_raw_stored_intent)
            if isinstance(_parsed, dict):
                _stored_intents_set = set(_parsed.get("selected", []))
                _stored_manual = _parsed.get("manual", "")
            else:
                # JSON but not a dict — treat as legacy
                _stored_intents_set = {s.strip() for s in _raw_stored_intent.split(",") if s.strip()}
        except (json.JSONDecodeError, TypeError):
            # Legacy plain text format
            _stored_intents_set = {s.strip() for s in _raw_stored_intent.split(",") if s.strip()}

    st.divider()
    st.subheader("Step 2: Validate user intents")
    st.caption(
        "These are the phrases we detected that your page could be optimised for. "
        "Select 3-6 intents that best match what you want this page to rank for. "
        "If none of these match, type your own below."
    )

    # --- AI intent suggestions ---
    from aeo.intent_helper import suggest_intents

    # Generate or retrieve cached suggestions for this page
    _suggestions_key = f"aeo_intent_suggestions_{_page_key}"
    if _suggestions_key not in st.session_state:
        # Build rich content context for Haiku (A: content-based intents)
        _intent_page_type = selected_page.get("page_type") or ""
        _intent_domain_ctx = st.session_state.get("domain_context", "")

        # Enrich with strategic role if available
        if _domain_strategy and _domain_strategy.get("page_roles") and selected_page.get("id"):
            for _pr in _domain_strategy.get("page_roles", []):
                if _pr.get("page_id") == str(selected_page["id"]):
                    _role_label = _pr.get("role", "").replace("_", " ")
                    _intent_domain_ctx += f"\nThis page's strategic role: {_role_label}. {_pr.get('reasoning', '')}"
                    break

        if not st.session_state.get("operation_in_progress", False):
            with st.spinner("Generating intent suggestions..."):
                suggestions = suggest_intents(
                    title=_page_title,
                    page_type=_intent_page_type,
                    domain=domain,
                    domain_context=_intent_domain_ctx,
                    first_paragraph=_meta_desc[:300],
                    h2_headings=_h2_structure,
                    content_summary=_content_summary,
                )
            if suggestions:
                st.session_state[_suggestions_key] = suggestions
            # Don't cache empty results — allows retry on next render
        else:
            pass  # Don't cache during operation lock — will retry after unlock

    suggestions = st.session_state.get(_suggestions_key, [])

    # Show checkboxes for each suggestion
    selected_intents_list = []
    if suggestions:
        for i, suggestion in enumerate(suggestions):
            _cb_key = f"aeo_intent_cb_{_page_key}_{i}"
            # Pre-check if this suggestion was in stored intents
            default_checked = suggestion in _stored_intents_set
            if _cb_key not in st.session_state and default_checked:
                st.session_state[_cb_key] = True
            checked = st.checkbox(suggestion, key=_cb_key)
            if checked:
                selected_intents_list.append(suggestion)
    else:
        st.info("No suggestions available — type your intents manually below.")

    # Custom intent text area — pre-fill from stored manual intents
    _custom_intent_key = f"aeo_custom_intent_{_page_key}"
    if _custom_intent_key not in st.session_state and _stored_manual:
        st.session_state[_custom_intent_key] = _stored_manual
    custom_intent = st.text_area(
        "Additional intents (one per line)",
        height=80,
        placeholder="Type any additional intents not listed above...",
        key=_custom_intent_key,
    )
    if custom_intent:
        for line in custom_intent.strip().split("\n"):
            line = line.strip()
            if line and line not in selected_intents_list:
                selected_intents_list.append(line)

    # Count, status, and relevance scoring (B)
    n_selected = len(selected_intents_list)
    if n_selected >= 3:
        st.success(f"Selected: {n_selected} intents — ready to audit!")
    elif n_selected > 0:
        st.caption(f"Selected: {n_selected} intents (recommend 3-6 for best results)")
    else:
        st.caption("No intents selected yet")

    # Intent Relevance Score (local heuristic, no AI call)
    if n_selected > 0:
        from aeo.intent_scorer import score_intent_relevance
        _score = score_intent_relevance(
            selected_intents=selected_intents_list,
            title=_page_title,
            h1=_page_h1,
            meta_description=_meta_desc,
            h2_headings=_h2_structure,
        )
        _total = _score["total_score"]

        # Colour-coded score display
        if _total >= 70:
            _score_color = "green"
            _score_label = "Strong match"
        elif _total >= 40:
            _score_color = "orange"
            _score_label = "Moderate match"
        else:
            _score_color = "red"
            _score_label = "Weak match"

        st.markdown(f"**Intent Relevance Score: :{_score_color}[{_total}/100]** — {_score_label}")

        with st.expander("Score breakdown", expanded=False):
            _col_k, _col_c, _col_s = st.columns(3)
            _col_k.metric("Keyword Overlap", f"{_score['keyword_overlap']}/40")
            _col_c.metric("H2 Coverage", f"{_score['coverage']}/35")
            _col_s.metric("Specificity", f"{_score['specificity']}/25")

            if _score.get("breakdown"):
                st.caption("Per-intent matching:")
                for _bd in _score["breakdown"]:
                    _elements = ", ".join(_bd["matched_elements"]) if _bd["matched_elements"] else "no match"
                    st.markdown(f"- **{_bd['intent']}** — {_elements}")

    # Combine into intent string for prompt injection
    intent = ", ".join(selected_intents_list)

    # Build JSON for saving (separates AI-selected from manual)
    _selected_from_checkboxes = [s for s in selected_intents_list if s in (suggestions or [])]
    _manual_text = (custom_intent or "").strip()
    _intent_json = json.dumps({"selected": _selected_from_checkboxes, "manual": _manual_text}, ensure_ascii=False)

    # Step 3: Generate
    st.divider()
    st.subheader("Step 3: Generate Playbook")

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

    _op_locked = st.session_state.get("operation_in_progress", False)
    if st.button("Generate Playbook", type="primary", key="btn_generate_arbeidspakke",
                  disabled=not selected_page.get("url") or _op_locked):
        url = selected_page["url"]

        if selected_page.get("id") and _intent_json != _raw_stored_intent:
            _db_patch(token, "pages",
                      params={"id": f"eq.{selected_page['id']}"},
                      body={"intent": _intent_json if selected_intents_list or _manual_text else None})
            try:
                from tracking.usage_tracker import log_usage_event
                log_usage_event("intent_saved", event_detail="page intent set", project_id=project_id)
            except Exception:
                pass

        st.session_state["operation_in_progress"] = True
        try:
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
            with st.spinner(f"Generating playbook with {_model_label}..."):
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
                    domain_strategy=_domain_strategy if _domain_strategy.get("page_roles") else None,
                    page_id=selected_page.get("id"),
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
                    st.success("Playbook saved to project.")
                else:
                    st.warning("Playbook generated but failed to save to database.")
            else:
                st.info("Manual URL — playbook not saved (no page_id).")
        finally:
            st.session_state["operation_in_progress"] = False

    # Display output
    if st.session_state.get("aeo_arbeidspakke"):
        st.divider()
        st.markdown(_clean_playbook_md(st.session_state["aeo_arbeidspakke"]))

        # Download — filename includes domain + page path slug
        _dl_url = selected_page.get("url", "")
        _dl_parsed = urlparse(_dl_url) if _dl_url else None
        _dl_domain = (_dl_parsed.netloc.lower().replace("www.", "").replace(".", "-") if _dl_parsed else "site")[:30]
        _dl_path_raw = (_dl_parsed.path.strip("/") if _dl_parsed else "").replace("/", "-").replace(".", "-")
        _dl_path_slug = _dl_path_raw[:40] if _dl_path_raw else "homepage"
        st.download_button(
            "Download as .md",
            data=st.session_state["aeo_arbeidspakke"],
            file_name=f"playbook-{_dl_domain}-{_dl_path_slug}-{datetime.now().strftime('%Y-%m-%d')}.md",
            mime="text/markdown",
            key="btn_download_arbeidspakke",
        )

    # Previous arbeidspakker
    if selected_page.get("id"):
        previous = _load_arbeidspakker(token, project_id, selected_page["id"])
        if previous:
            st.divider()
            with st.expander(f"Previous playbooks for this page ({len(previous)})"):
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
                        st.markdown(_clean_playbook_md(ap.get("arbeidspakke_markdown", "")))
                    st.caption("---")
