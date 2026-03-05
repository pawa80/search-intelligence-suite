"""Arbeidspakker Library — central view of all work packages across a project."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import streamlit as st


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        import os
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
    """Direct GET to Supabase REST API with 401 auto-refresh."""
    url = f"{_get_secret('SUPABASE_URL')}/rest/v1/{table}"
    headers = {
        "apikey": _get_secret("SUPABASE_ANON_KEY"),
        "Authorization": f"Bearer {token}",
    }
    r = httpx.get(url, headers=headers, params=params, timeout=15.0)
    if r.status_code == 401:
        new_token = _refresh_jwt()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = httpx.get(url, headers=headers, params=params, timeout=15.0)
    if r.status_code >= 400:
        return []
    return r.json()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_arbeidspakker(project_id: str, token: str) -> list[dict]:
    """Fetch all arbeidspakker for a project, sorted newest-first."""
    return _db_get(token, "arbeidspakker", {
        "select": "id,page_id,url,intent,arbeidspakke_markdown,generated_at",
        "project_id": f"eq.{project_id}",
        "order": "generated_at.desc",
    })


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

def show_arbeidspakker_library(
    project_ctx: dict[str, Any] | None,
    token: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """Entry point for the Arbeidspakker Library UI."""
    st.title("Arbeidspakker")

    if not project_ctx:
        st.warning("Select a project first to view arbeidspakker.")
        return

    project_id = project_ctx["id"]
    domain = project_ctx.get("domain", "")

    st.info(f"Project: **{project_ctx['name']}** \u00b7 Domain: **{domain}**")

    with st.spinner("Loading arbeidspakker\u2026"):
        rows = _load_arbeidspakker(project_id, token)

    if not rows:
        st.info("No arbeidspakker found for this project. Generate one via the AEO Agent.")
        return

    # Summary metrics
    total = len(rows)
    unique_urls = len(set(r["url"] for r in rows if r.get("url")))
    latest_date = rows[0].get("generated_at", "")[:10] if rows else "\u2014"

    c1, c2, c3 = st.columns(3)
    c1.metric("Total arbeidspakker", total)
    c2.metric("Unique pages", unique_urls)
    c3.metric("Latest generated", latest_date)

    st.divider()

    # List of arbeidspakker
    for idx, r in enumerate(rows):
        url_display = r.get("url", "")
        for prefix in ("https://", "http://"):
            if url_display.startswith(prefix):
                url_display = url_display[len(prefix):]
                break

        intent = r.get("intent") or ""
        gen_date = r.get("generated_at", "")[:16].replace("T", " ")

        # Header row with URL, intent, date, and actions
        col_url, col_date, col_actions = st.columns([4, 1.5, 2])
        col_url.markdown(f"**{url_display}**")
        col_date.caption(gen_date)

        with col_actions:
            btn_cols = st.columns(2)
            # Download button
            md_content = r.get("arbeidspakke_markdown", "")
            safe_url = url_display.replace("/", "_").replace(".", "_")[:40]
            btn_cols[0].download_button(
                "Download .md",
                data=md_content,
                file_name=f"arbeidspakke-{safe_url}.md",
                mime="text/markdown",
                key=f"ap_dl_{idx}",
            )
            # Generate new button
            if btn_cols[1].button("Re-generate", key=f"ap_gen_{idx}"):
                st.session_state["matrise_generate_url"] = r.get("url", "")
                st.session_state["_tool_override"] = "AEO Agent"
                st.rerun()

        if intent:
            st.caption(f"Intent: {intent}")

        # Expandable full content
        with st.expander("View arbeidspakke", expanded=False):
            st.markdown(md_content)

        st.divider()
