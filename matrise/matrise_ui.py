"""Matrise — prioritisation view for crawled pages."""
from __future__ import annotations

import csv
import io
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
# Priority score
# ---------------------------------------------------------------------------

def calculate_priority_score(page: dict) -> float:
    """
    Higher score = higher priority for optimisation.
    Logic: pages with traffic potential but low AEO readiness are highest value.
    """
    score = 0.0

    # AEO gap (40% weight) — low aeo_readiness = high opportunity
    aeo = page.get("aeo_readiness_score")
    if aeo is not None:
        score += (1 - aeo / 100) * 40

    # SEO gap (20% weight) — low seo_score = technical debt
    seo = page.get("seo_score")
    if seo is not None:
        score += (1 - seo / 100) * 20

    # Traffic signal (25% weight) — pages with real traffic are worth fixing
    clicks = page.get("clicks") or 0
    impressions = page.get("impressions") or 0
    if impressions > 0:
        traffic_weight = min(impressions / 1000, 1.0) * 25
        score += traffic_weight
    elif clicks > 0:
        score += min(clicks / 100, 1.0) * 25

    # Engagement signal (15% weight) — GA sessions show real user value
    sessions = page.get("sessions") or 0
    if sessions > 0:
        score += min(sessions / 500, 1.0) * 15

    return round(score, 1)


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------

def build_matrise(project_id: str, token: str) -> list[dict]:
    """Fetch and join all data sources for a project, sorted by priority_score desc."""

    # 1. Crawled pages
    pages = _db_get(token, "pages", {
        "select": "id,url,title,status_code,last_crawled_at",
        "project_id": f"eq.{project_id}",
        "last_crawled_at": "not.is.null",
        "order": "url.asc",
    })
    if not pages:
        return []

    # 2. Crawl AI analysis
    analyses = _db_get(token, "crawl_ai_analysis", {
        "select": "page_id,seo_score,aeo_readiness_score,content_quality_score,priority_action",
        "project_id": f"eq.{project_id}",
    })
    analysis_map: dict[str, dict] = {a["page_id"]: a for a in analyses}

    # 3. GSC data (most recent per page_id)
    gsc_rows = _db_get(token, "gsc_data", {
        "select": "page_id,clicks,impressions,ctr,position,date_range_start,date_range_end",
        "project_id": f"eq.{project_id}",
        "order": "date_range_end.desc",
    })
    gsc_map: dict[str, dict] = {}
    for g in gsc_rows:
        pid = g.get("page_id")
        if pid and pid not in gsc_map:
            gsc_map[pid] = g

    # 4. GA data (most recent per page_id)
    ga_rows = _db_get(token, "ga_data", {
        "select": "page_id,sessions,engagement_rate,date_range_start,date_range_end",
        "project_id": f"eq.{project_id}",
        "order": "date_range_end.desc",
    })
    ga_map: dict[str, dict] = {}
    for g in ga_rows:
        pid = g.get("page_id")
        if pid and pid not in ga_map:
            ga_map[pid] = g

    # 5. Arbeidspakker — most recent per page
    ap_rows = _db_get(token, "arbeidspakker", {
        "select": "page_id,generated_at",
        "project_id": f"eq.{project_id}",
        "order": "generated_at.desc",
    })
    ap_map: dict[str, str] = {}
    for a in ap_rows:
        pid = a.get("page_id")
        if pid and pid not in ap_map:
            ap_map[pid] = a.get("generated_at", "")

    # 6. Join everything
    result = []
    for p in pages:
        pid = p["id"]
        ai = analysis_map.get(pid, {})
        gsc = gsc_map.get(pid, {})
        ga = ga_map.get(pid, {})

        row = {
            "page_id": pid,
            "url": p.get("url", ""),
            "title": p.get("title") or "",
            "intent": p.get("intent") or "",
            "status_code": p.get("status_code"),
            "last_crawled_at": p.get("last_crawled_at", ""),
            # AI scores
            "seo_score": ai.get("seo_score"),
            "aeo_readiness_score": ai.get("aeo_readiness_score"),
            "content_quality_score": ai.get("content_quality_score"),
            "priority_action": ai.get("priority_action") or "",
            # GSC
            "clicks": gsc.get("clicks"),
            "impressions": gsc.get("impressions"),
            "position": gsc.get("position"),
            "ctr": gsc.get("ctr"),
            "gsc_date_start": gsc.get("date_range_start", ""),
            "gsc_date_end": gsc.get("date_range_end", ""),
            # GA
            "sessions": ga.get("sessions"),
            "engagement_rate": ga.get("engagement_rate"),
            "ga_date_start": ga.get("date_range_start", ""),
            "ga_date_end": ga.get("date_range_end", ""),
            # Arbeidspakke
            "arbeidspakke_at": ap_map.get(pid, ""),
        }
        row["priority_score"] = calculate_priority_score(row)
        result.append(row)

    result.sort(key=lambda r: r["priority_score"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _score_badge(score: int | None) -> str:
    if score is None:
        return "\u2014"
    if score >= 75:
        return f"\U0001f7e2 {score}"
    if score >= 50:
        return f"\U0001f7e1 {score}"
    return f"\U0001f534 {score}"


def _priority_badge(score: float) -> str:
    if score >= 70:
        return f"\U0001f534 {score}"
    if score >= 40:
        return f"\U0001f7e1 {score}"
    return f"\U0001f7e2 {score}"


def _fmt(val: Any, fmt: str = "") -> str:
    """Format a value for display. None → em dash."""
    if val is None:
        return "\u2014"
    if fmt == "int":
        return f"{int(val):,}"
    if fmt == "pos":
        return f"{float(val):.1f}"
    return str(val)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def _build_csv(rows: list[dict], domain: str) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "URL", "Intent", "Priority Score", "AEO Score", "SEO Score", "Content Score",
        "Impressions", "Clicks", "Position", "CTR",
        "Sessions", "Engagement Rate",
        "Arbeidspakke", "Priority Action",
    ])
    for r in rows:
        writer.writerow([
            r["url"],
            r.get("intent", ""),
            r["priority_score"],
            r.get("aeo_readiness_score", ""),
            r.get("seo_score", ""),
            r.get("content_quality_score", ""),
            r.get("impressions", ""),
            r.get("clicks", ""),
            r.get("position", ""),
            r.get("ctr", ""),
            r.get("sessions", ""),
            r.get("engagement_rate", ""),
            r.get("arbeidspakke_at", "")[:10] if r.get("arbeidspakke_at") else "",
            r.get("priority_action", ""),
        ])
    return output.getvalue()


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

def show_matrise(
    project_ctx: dict[str, Any] | None,
    token: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """Entry point for the Matrise UI."""
    st.title("Matrise")

    if not project_ctx:
        st.warning("Select a project first to view the Matrise.")
        return

    project_id = project_ctx["id"]
    domain = project_ctx.get("domain", "")

    st.info(f"Project: **{project_ctx['name']}** \u00b7 Domain: **{domain}**")

    with st.spinner("Building matrise\u2026"):
        rows = build_matrise(project_id, token)

    if not rows:
        st.info("No crawled pages found for this project. Run a crawl first, then return here.")
        return

    # Summary metrics
    total = len(rows)
    with_ai = sum(1 for r in rows if r.get("aeo_readiness_score") is not None)
    with_gsc = sum(1 for r in rows if r.get("impressions") is not None)
    with_ap = sum(1 for r in rows if r.get("arbeidspakke_at"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pages in matrix", total)
    c2.metric("With AI scores", with_ai)
    c3.metric("With GSC data", with_gsc)
    c4.metric("With arbeidspakke", with_ap)

    # CSV export
    csv_data = _build_csv(rows, domain)
    date_str = datetime.now().strftime("%Y-%m-%d")
    clean_domain = domain.replace("https://", "").replace("http://", "").rstrip("/").replace("/", "_")
    st.download_button(
        "Export CSV",
        data=csv_data,
        file_name=f"matrise-{clean_domain}-{date_str}.csv",
        mime="text/csv",
        key="btn_matrise_csv",
    )

    st.divider()

    # Column widths for the table
    _COL_WIDTHS = [0.5, 2.5, 2, 1, 1, 1, 1, 1.2, 0.8, 0.8, 0.8, 1.2, 1]

    # Header row
    hdr = st.columns(_COL_WIDTHS)
    hdr[0].markdown("**#**")
    hdr[1].markdown("**URL**")
    hdr[2].markdown("**Intent**")
    hdr[3].markdown("**Priority**")
    hdr[4].markdown("**AEO**")
    hdr[5].markdown("**SEO**")
    hdr[6].markdown("**Content**")
    hdr[7].markdown("**Impressions**")
    hdr[8].markdown("**Clicks**")
    hdr[9].markdown("**Pos**")
    hdr[10].markdown("**Sessions**")
    hdr[11].markdown("**Arbeidspakke**")
    hdr[12].markdown("**Action**")

    # Data rows
    for idx, r in enumerate(rows):
        url_short = r["url"]
        for prefix in ("https://", "http://"):
            if url_short.startswith(prefix):
                url_short = url_short[len(prefix):]
                break

        cols = st.columns(_COL_WIDTHS)
        cols[0].markdown(f"{idx + 1}")
        cols[1].markdown(f"**{url_short}**")
        cols[2].markdown(r.get("intent", "")[:40] or "\u2014")
        cols[3].markdown(_priority_badge(r["priority_score"]))
        cols[4].markdown(_score_badge(r.get("aeo_readiness_score")))
        cols[5].markdown(_score_badge(r.get("seo_score")))
        cols[6].markdown(_score_badge(r.get("content_quality_score")))
        cols[7].markdown(_fmt(r.get("impressions"), "int"))
        cols[8].markdown(_fmt(r.get("clicks"), "int"))
        cols[9].markdown(_fmt(r.get("position"), "pos"))
        cols[10].markdown(_fmt(r.get("sessions"), "int"))
        if r.get("arbeidspakke_at"):
            cols[11].markdown(f"\u2705 {r['arbeidspakke_at'][:10]}")
        else:
            cols[11].markdown("\u2014")
        if cols[12].button("Generate", key=f"matrise_gen_{idx}"):
            st.session_state["matrise_generate_url"] = r["url"]
            st.session_state["_tool_override"] = "AEO Agent"
            st.rerun()

        # Expandable detail
        with st.expander(f"Details: {url_short}", expanded=False):
            if r.get("priority_action"):
                st.markdown(f"**Priority action:** {r['priority_action']}")
            if r.get("gsc_date_start"):
                st.caption(f"GSC date range: {r['gsc_date_start']} to {r['gsc_date_end']}")
            if r.get("ga_date_start"):
                st.caption(f"GA date range: {r['ga_date_start']} to {r['ga_date_end']}")
            if r.get("last_crawled_at"):
                st.caption(f"Last crawled: {r['last_crawled_at'][:16]}")
