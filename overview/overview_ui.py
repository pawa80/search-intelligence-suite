"""Project Overview — landing page showing project status at a glance."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import streamlit as st


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, "")


def _refresh_jwt() -> str | None:
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
    if r.status_code < 400:
        return r.json()
    return []


_ROLE_EMOJI = {
    "entity_anchor": "\U0001f7e3",
    "citation_target": "\U0001f7e2",
    "authority_builder": "\U0001f535",
    "conversion_endpoint": "\U0001f7e0",
    "cannibal_overlap": "\U0001f534",
}

_ROLE_LABEL = {
    "entity_anchor": "Brand Identity",
    "citation_target": "Citation Target",
    "authority_builder": "Authority Builder",
    "conversion_endpoint": "Conversion",
    "cannibal_overlap": "Competing Page",
}


def _load_overview_data(token: str, project_id: str) -> dict[str, Any]:
    """Load all overview data in parallel-ish queries, cached per project."""
    cache_key = f"_overview_data_{project_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    data: dict[str, Any] = {}

    # Pages count + last crawl
    pages = _db_get(token, "pages", {
        "select": "id,last_crawled_at",
        "project_id": f"eq.{project_id}",
        "status": "eq.active",
        "last_crawled_at": "not.is.null",
    })
    data["page_count"] = len(pages)
    data["page_ids"] = {p["id"] for p in pages}
    if pages:
        dates = [p.get("last_crawled_at", "") for p in pages if p.get("last_crawled_at")]
        data["last_crawl"] = max(dates)[:10] if dates else None
    else:
        data["last_crawl"] = None

    # Citation data — latest complete check date
    citation_rows = _db_get(token, "geo_check_results", {
        "select": "appears,position,check_date",
        "project_id": f"eq.{project_id}",
        "order": "check_date.desc",
    })
    if citation_rows:
        # Find latest check date
        latest_date = citation_rows[0].get("check_date", "")
        latest_rows = [r for r in citation_rows if r.get("check_date") == latest_date]
        cited = sum(1 for r in latest_rows if r.get("appears"))
        total = len(latest_rows)
        positions = [r["position"] for r in latest_rows if r.get("appears") and r.get("position")]
        avg_pos = round(sum(positions) / len(positions), 1) if positions else None
        data["citation_rate"] = cited
        data["citation_total"] = total
        data["citation_pct"] = round(cited / total * 100, 1) if total else 0
        data["citation_date"] = latest_date
        data["citation_avg_pos"] = avg_pos
    else:
        data["citation_rate"] = 0
        data["citation_total"] = 0
        data["citation_pct"] = 0
        data["citation_date"] = None
        data["citation_avg_pos"] = None

    # AI analysis count
    ai_rows = _db_get(token, "crawl_ai_analysis", {
        "select": "page_id",
        "project_id": f"eq.{project_id}",
    })
    data["ai_score_count"] = len(ai_rows)

    # GSC data count (unique pages)
    gsc_rows = _db_get(token, "gsc_data", {
        "select": "page_id",
        "project_id": f"eq.{project_id}",
    })
    data["gsc_count"] = len({r["page_id"] for r in gsc_rows if r.get("page_id")})

    # Playbook count (unique pages)
    ap_rows = _db_get(token, "arbeidspakker", {
        "select": "page_id",
        "project_id": f"eq.{project_id}",
    })
    data["playbook_count"] = len({r["page_id"] for r in ap_rows if r.get("page_id")})
    data["playbook_total"] = len(ap_rows)

    st.session_state[cache_key] = data
    return data


def _nav_button(label: str, target: str, key: str) -> None:
    """Button that navigates to a different tool via _tool_override."""
    if st.button(label, key=key):
        st.session_state["_tool_override"] = target
        st.rerun()


def _show_brand_audit_demo(project_id: str) -> None:
    """Static demo of the AI Brand Perception Audit feature."""
    st.subheader("\U0001f50d AI Brand Perception Audit (Preview)")
    st.caption(
        "How AI engines see your brand \u2014 powered by multi-model analysis. "
        "This feature is coming soon. Below is a sample audit for **Popeyes UK** "
        "to demonstrate the capability."
    )

    st.markdown(
        '<span style="background: var(--accent, #f0a500); color: #000; padding: 2px 8px; '
        'border-radius: 3px; font-size: 12px; font-weight: 600;">SAMPLE DATA \u2014 Popeyes UK</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    with st.expander("Strategy Layer (Opus reasoning)", expanded=False):
        st.markdown("""**AI Brand Perception Audit: Popeyes UK**

**1. Direct UK Brand Recognition & Identity**
The core question is whether AI systems distinguish Popeyes UK as a distinct entity from the US parent brand, or conflate the two.

**2. Competitive Positioning in the UK Fried Chicken Market**
The UK QSR chicken market is fiercely contested (KFC, Chicken Cottage, Morley's, Slim Chickens). AI systems may not accurately reflect UK-specific positioning.

**3. UK Location & Availability Accuracy**
Popeyes UK has a relatively recent footprint. AI systems frequently get store counts, cities, and launch dates wrong for newer regional rollouts.

**4. Menu & Product Accuracy for the UK Market**
UK menus differ from US menus. If AI describes the Popeyes Chicken Sandwich without noting UK-specific differences, that's a credibility gap.

**5. Sentiment & Cultural Reception in the UK**
The UK fried chicken culture has strong local loyalties. AI may default to US hype cycles without reflecting UK-specific reception.""")

    with st.expander("Investigation 1: UK Brand Recognition & Identity", expanded=False):
        st.markdown("""**Business Performance:** Popeyes was the fastest-growing fast-food brand in the UK in the 12 months to January 2025. In 2024, opened 33 new locations, 100% increase in total sales surpassing \u00a3118 million. Made UK debut in Stratford November 2021.

**Customer Sentiment Gap:** Despite strong metrics, ground-level reviews reveal disconnect. Reports of undercooked chicken, hygiene concerns, weak customer service follow-through.

**Notable Gap:** Clear divergence between trade press narrative (rapid expansion, record sales) and consumer review platforms. Trustpilot has only ~28 reviews despite 100+ locations \u2014 a reputational blind spot.""")

    with st.expander("Investigation 2: UK vs US Brand Differentiation", expanded=False):
        st.markdown("""**Key Differences:** UK uses 100% fresh British chicken (not marketed this way in US). TDR Capital invested \u00a350M making it separately backed. All UK chicken from halal-certified suppliers. Pricing \u00a31-2 more than competitors.

**Notable Gap:** popeyesuk.com returns no indexable content \u2014 brand messaging invisible to search crawlers. Significant SEO gap.""")

    with st.expander("Investigation 3: Competitive Positioning", expanded=False):
        st.markdown("""AI systems trained on US content would frame competitors as Chick-fil-A, Raising Cane's, Bojangles. **UK reality:** KFC (dominant), Wingstop, Slim Chickens, Dave's Hot Chicken.

Chick-fil-A is only just entering UK (five restaurants by end of 2026) \u2014 minor competitor, not established rival as AI assumes.

**Stale content risk:** At least one indexed source still claims Popeyes "is yet to come to Britain" \u2014 a 2020 page AI may still surface.""")

    with st.expander("Investigation 4: KFC Comparison", expanded=False):
        st.markdown("""KFC dominates UK with \u00a3284M turnover (2022). Consumer reviewers give Popeyes edge on flavour. Popeyes \u00a31-2 more expensive but delivers chunkier chicken and bolder flavours.

**Loyalty blind spot:** Popeyes UK views loyalty as growth engine but kiosk data represents an "invisible majority" of in-store customers.""")

    with st.expander("Investigation 5: Location Accuracy", expanded=False):
        st.markdown("""No longer "limited footprint" \u2014 reached 100 UK restaurants November 2025. CEO planning 45 further openings. Scotland has 10 locations.

**Coverage gaps remain:** heavily weighted toward London and urban centres. Format inconsistency: dine-in, drive-thru, delivery kitchens, station grab-and-go.""")

    # Cost metrics
    st.write("")
    c1, c2, c3 = st.columns(3)
    c1.metric("Strategy Cost", "$0.08", help="Opus reasoning layer")
    c2.metric("Execution Cost", "$0.51", help="Sonnet + search queries")
    c3.metric("Total Per Audit", "$0.59")

    st.caption(
        "Coming to Aevilab Q2 2026. Multi-engine brand perception auditing \u2014 "
        "enter your domain, get a full audit in under 2 minutes."
    )


def show_overview(
    project_ctx: dict[str, Any] | None,
    token: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """Main entry point for the Project Overview page."""
    st.title("Project Overview")

    if not project_ctx:
        st.info("Select or create a project to get started.")
        return

    project_id = project_ctx["id"]
    domain = project_ctx.get("domain", "")
    st.caption(f"**{project_ctx['name']}** · {domain}")

    # Load all overview data
    data = _load_overview_data(token, project_id)

    # === Section 1: YOUR DOMAIN STRATEGY ===
    st.subheader("Your Domain Strategy")

    # Parse domain strategy once for reuse
    _ds_raw = project_ctx.get("domain_strategy") or {}
    if isinstance(_ds_raw, str):
        try:
            _ds = json.loads(_ds_raw)
        except (json.JSONDecodeError, TypeError):
            _ds = {}
    else:
        _ds = _ds_raw
    page_roles = _ds.get("page_roles", []) if _ds and not _ds.get("parse_error") else []

    col_user, col_ai = st.columns(2)

    # Left: Domain Strategy — Your Input
    with col_user:
        st.markdown("**Domain Strategy — Your Input**")
        domain_context = project_ctx.get("domain_context") or st.session_state.get("domain_context", "")
        if domain_context:
            lines = domain_context.strip().split("\n")
            if len(lines) > 3:
                preview = "\n".join(lines[:3])
                with st.expander(f"{preview}\n\n...CLICK TO EXPAND", expanded=False):
                    st.markdown(domain_context)
            else:
                st.markdown(domain_context)
        else:
            st.caption("Add your domain context in Project Settings to improve playbook quality.")
        _nav_button("Edit Your Strategy Manifest", "Settings", f"ov_edit_strategy_{project_id}")

    # Right: AI Derived Domain Strategy
    with col_ai:
        st.markdown("**AI Derived Domain Strategy**")

        if page_roles:
            # Show narrative if available, otherwise generate summary from roles
            narrative = _ds.get("strategy_narrative", "")
            if narrative:
                st.markdown(narrative)
            else:
                # Fallback: auto-generate a basic summary from page_roles
                _role_groups: dict[str, list[str]] = {}
                for pr in page_roles:
                    role_raw = pr.get("role", "authority_builder")
                    label = _ROLE_LABEL.get(role_raw, role_raw.replace("_", " ").title())
                    url = pr.get("url", "")
                    try:
                        path = urlparse(url).path.strip("/")
                        url_short = f"/{path}" if path else "/ (Homepage)"
                    except Exception:
                        url_short = url[:40]
                    _role_groups.setdefault(label, []).append(url_short)

                _parts = []
                for role_label, urls in _role_groups.items():
                    emoji = next((e for r, e in _ROLE_EMOJI.items() if _ROLE_LABEL.get(r) == role_label), "\U0001f3af")
                    _parts.append(f"{emoji} **{len(urls)} {role_label}** pages")
                st.markdown(" · ".join(_parts))

            # Collapsible detailed page roles table
            with st.expander("View detailed page roles", expanded=False):
                for pr in page_roles:
                    role_raw = pr.get("role", "")
                    emoji = _ROLE_EMOJI.get(role_raw, "\U0001f3af")
                    label = _ROLE_LABEL.get(role_raw, role_raw.replace("_", " ").title())
                    url = pr.get("url", "")
                    try:
                        path = urlparse(url).path.strip("/")
                        url_short = f"/{path}" if path else "/ (Homepage)"
                    except Exception:
                        url_short = url[:40]
                    st.markdown(f"{emoji} **{label}** · `{url_short}`")

            # Stale strategy check
            strategy_page_ids = {pr.get("page_id") for pr in page_roles}
            current_page_ids = data.get("page_ids", set())
            if current_page_ids - strategy_page_ids:
                st.caption("Note: run new crawl + regenerate strategy to include new pages")

            # Strategy date + regenerate link
            _gen_at = project_ctx.get("domain_strategy_generated_at")
            if _gen_at:
                _gen_date = str(_gen_at)[:10]
                st.caption(f"Strategy generated on {_gen_date}. Regenerate on the **Crawl** page.")
            else:
                st.caption("Regenerate on the **Crawl** page.")
        else:
            st.caption("No domain strategy yet. Generate one on the **Crawl** page to get differentiated playbooks.")
            _nav_button("Generate Strategy", "Crawl", f"ov_goto_crawl_strategy_{project_id}")

    st.divider()

    # === Section 2: CITATION RATE ===
    st.subheader("Citation Rate")
    if data["citation_date"]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Citation Rate", f"{data['citation_rate']}/{data['citation_total']} ({data['citation_pct']}%)")
        c2.metric("Last Check", data["citation_date"])
        c3.metric("Avg Position", data["citation_avg_pos"] if data["citation_avg_pos"] else "\u2014")
    else:
        st.caption("No citation checks yet. Run your first check in Rank Tracker.")
    _nav_button("Rank Tracker", "Rank Tracker", f"ov_goto_rank_{project_id}")

    st.divider()

    # === Section 3: CRAWL SUMMARY ===
    st.subheader("Crawl Summary")
    if data["page_count"] > 0:
        st.markdown(f"**{data['page_count']}** pages crawled · Last crawl: **{data['last_crawl']}**")
    else:
        st.caption("No pages crawled yet. Start your first crawl.")
    _nav_button("Crawl", "Crawl", f"ov_goto_crawl_{project_id}")

    st.divider()

    # === Section 4: YOUR MATRIX ===
    st.subheader("Your Matrix")
    st.caption("Your page matrix tracks optimisation progress across all crawled pages.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pages in Matrix", data["page_count"])
    m2.metric("With AI Scores", data["ai_score_count"])
    m3.metric("With GSC Data", data["gsc_count"])
    m4.metric("With Playbook", data["playbook_count"])
    _nav_button("Your Matrix", "Matrix", f"ov_goto_matrix_{project_id}")

    st.divider()

    # === BRAND PERCEPTION AUDIT (demo) ===
    _show_brand_audit_demo(project_id)

    st.divider()

    # === Section 5: USER INPUT REQUIRED (placeholder) ===
    if data["playbook_total"] > 0:
        st.markdown(
            f"""<div style="background: var(--surface2, #21252e); border-left: 3px solid var(--stone, #8B8B8B); padding: 1rem; border-radius: 4px; opacity: 0.6;">
<strong>\U0001f4cb Coming soon: Playbook Implementation Tracker</strong><br>
You have {data['playbook_total']} active playbooks. This section will show which playbooks have been implemented by your team, track the dates changes were applied, and connect those changes to the outcome measurements below. When your team confirms a playbook has been applied, Aevilab starts monitoring for results.
</div>""",
            unsafe_allow_html=True,
        )
        st.write("")

    # === Section 6: CHANGES DETECTED (placeholder) ===
    st.markdown(
        """<div style="background: var(--surface2, #21252e); border-left: 3px solid var(--stone, #8B8B8B); padding: 1rem; border-radius: 4px; opacity: 0.6;">
<strong>\U0001f50d Coming soon: Intelligent Change Detection</strong><br>
After your next crawl, Aevilab will automatically detect content changes on your pages \u2014 new headings, updated schema, modified content \u2014 and show you what changed and when. Combined with citation and traffic tracking, this creates a direct feedback loop: change \u2192 detect \u2192 measure \u2192 learn. This is how Aevilab gets smarter with every crawl.
</div>""",
        unsafe_allow_html=True,
    )
