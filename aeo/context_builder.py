"""Assembles matrix context for a page from the suite's data tables."""
from __future__ import annotations

from typing import Any

import httpx
import streamlit as st


def _refresh_jwt(supabase_url: str, anon_key: str) -> str | None:
    """Refresh JWT via supabase client. Returns new token or None."""
    try:
        from supabase import create_client
        sb = create_client(supabase_url, anon_key)
        response = sb.auth.refresh_session()
        if response and response.session:
            new_token = response.session.access_token
            st.session_state.access_token = new_token
            return new_token
    except Exception:
        pass
    return None


def _get_with_retry(url: str, headers: dict, params: dict,
                    supabase_url: str, anon_key: str) -> list[dict]:
    """GET with 401 auto-refresh retry."""
    r = httpx.get(url, headers=headers, params=params, timeout=10.0)
    if r.status_code == 401:
        new_token = _refresh_jwt(supabase_url, anon_key)
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = httpx.get(url, headers=headers, params=params, timeout=10.0)
    if r.status_code < 400:
        return r.json()
    return []


def build_page_context(
    page_id: str,
    project_id: str,
    jwt: str,
    supabase_url: str,
    anon_key: str,
) -> dict[str, Any]:
    """Fetch all available suite data for a page.

    Returns a context dict with crawl_analysis, gsc, and ga data.
    Returns empty values gracefully if data not available.
    """
    context: dict[str, Any] = {
        "crawl_analysis": None,
        "gsc": None,
        "ga": None,
    }

    headers = {
        "Authorization": f"Bearer {jwt}",
        "apikey": anon_key,
        "Content-Type": "application/json",
    }

    # Fetch crawl AI analysis
    try:
        rows = _get_with_retry(
            f"{supabase_url}/rest/v1/crawl_ai_analysis",
            headers.copy(),
            {"select": "seo_score,aeo_readiness_score,content_quality_score,priority_action,issues",
             "page_id": f"eq.{page_id}"},
            supabase_url, anon_key,
        )
        if rows:
            context["crawl_analysis"] = rows[0]
    except Exception:
        pass

    # Fetch GSC data (most recent date range)
    try:
        rows = _get_with_retry(
            f"{supabase_url}/rest/v1/gsc_data",
            headers.copy(),
            {"select": "clicks,impressions,ctr,position",
             "page_id": f"eq.{page_id}",
             "order": "date_range_end.desc",
             "limit": "1"},
            supabase_url, anon_key,
        )
        if rows:
            context["gsc"] = rows[0]
    except Exception:
        pass

    # Fetch GA data (most recent date range)
    try:
        rows = _get_with_retry(
            f"{supabase_url}/rest/v1/ga_data",
            headers.copy(),
            {"select": "sessions,engagement_rate,avg_engagement_time",
             "page_id": f"eq.{page_id}",
             "order": "date_range_end.desc",
             "limit": "1"},
            supabase_url, anon_key,
        )
        if rows:
            context["ga"] = rows[0]
    except Exception:
        pass

    return context


def build_context_block(context: dict[str, Any]) -> str:
    """Format matrix context into a prompt-ready string to prepend to arbeidspakke prompt."""
    lines = ["## PAGE INTELLIGENCE (from suite data)\n"]

    if context.get("crawl_analysis"):
        c = context["crawl_analysis"]
        lines.append(
            f"**Crawl AI Scores:** SEO {c.get('seo_score')}/100 | "
            f"AEO Readiness {c.get('aeo_readiness_score')}/100 | "
            f"Content Quality {c.get('content_quality_score')}/100"
        )
        lines.append(f"**Top crawl issue:** {c.get('priority_action', 'none')}")

    if context.get("gsc"):
        g = context["gsc"]
        ctr_pct = (g.get("ctr") or 0) * 100
        lines.append(
            f"**Search Console (last period):** "
            f"{g.get('clicks')} clicks | {g.get('impressions')} impressions | "
            f"Position {g.get('position', 'N/A')} avg | CTR {ctr_pct:.1f}%"
        )

    if context.get("ga"):
        a = context["ga"]
        eng_pct = (a.get("engagement_rate") or 0) * 100
        lines.append(
            f"**Analytics (last period):** "
            f"{a.get('sessions')} sessions | "
            f"Engagement rate {eng_pct:.1f}% | "
            f"Avg engagement time {a.get('avg_engagement_time', 0):.0f}s"
        )

    if len(lines) == 1:
        lines.append("No suite data available for this page yet — running audit on page content only.")

    return "\n".join(lines) + "\n\n---\n\n"
