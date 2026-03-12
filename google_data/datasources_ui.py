"""Streamlit UI for Google Data Sources — GSC + GA4 import with URL matching."""
from __future__ import annotations

import streamlit as st
from datetime import date, timedelta
from typing import Any

from google_data.oauth import (
    build_auth_url,
    exchange_code_for_tokens,
    get_credentials_from_refresh_token,
    load_connection,
    save_connection,
    update_selected_properties,
    verify_state,
)
from google_data.gsc_client import list_gsc_properties, fetch_gsc_data
from google_data.ga4_client import list_ga4_properties, fetch_ga4_data
from google_data.url_matcher import build_pages_lookup, match_url_to_page


def handle_oauth_callback_if_present() -> None:
    """Check for ?code= in URL and exchange for tokens. Call early in page lifecycle."""
    params = st.query_params
    code = params.get("code")
    state = params.get("state")

    if not code or not state:
        return

    # Verify CSRF state
    workspace_id = verify_state(state)
    if not workspace_id:
        st.error("Invalid OAuth state — possible CSRF. Please try connecting again.")
        st.query_params.clear()
        return

    # Exchange code for tokens
    tokens = exchange_code_for_tokens(code)
    if not tokens or not tokens.get("refresh_token"):
        st.error("Failed to get refresh token from Google. Please try again.")
        st.query_params.clear()
        return

    # Save to Supabase
    access_token = st.session_state.get("access_token")
    user = st.session_state.get("user")
    if access_token and user:
        save_connection(
            access_token=access_token,
            workspace_id=workspace_id,
            user_id=str(user.id),
            refresh_token=tokens["refresh_token"],
            token_expiry=tokens.get("token_expiry"),
        )
        st.session_state["google_connected"] = True

    # Clear query params to prevent re-processing
    st.query_params.clear()


def show_datasources(
    project_ctx: dict[str, Any] | None,
    token: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """Main entry point for the Data Sources UI."""
    st.title("Data Sources")

    if not project_ctx:
        st.warning("Select a project first to import data.")
        return

    st.info(f"Project: **{project_ctx['name']}** · Domain: **{project_ctx.get('domain', '—')}**")

    # Load existing connection
    conn = load_connection(token, workspace_id, user_id)

    # Section 1: Connection status
    _show_connection_section(conn, token, workspace_id, user_id)

    if not conn or not conn.get("google_refresh_token"):
        return

    # Get credentials
    creds = get_credentials_from_refresh_token(conn["google_refresh_token"])
    if not creds:
        st.error("Could not refresh Google credentials. Try reconnecting.")
        return

    # Property selection
    _show_property_selection(creds, conn, token, workspace_id, user_id)

    st.divider()

    # Import tabs
    tab_gsc, tab_ga4, tab_match = st.tabs(["GSC Import", "GA4 Import", "Match Status"])

    with tab_gsc:
        _show_gsc_import(creds, conn, project_ctx, token)

    with tab_ga4:
        _show_ga4_import(creds, conn, project_ctx, token)

    with tab_match:
        _show_match_status(project_ctx, token)


def _show_connection_section(
    conn: dict | None,
    token: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """Show connection status and connect/disconnect button."""
    if conn and conn.get("google_refresh_token"):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success(f"Google account connected (since {conn.get('connected_at', '—')[:10]})")
        with col2:
            if st.button("Reconnect", key="btn_reconnect_google"):
                auth_url = build_auth_url(workspace_id)
                st.markdown(f"[Click to reconnect Google account]({auth_url})")
    else:
        st.warning("No Google account connected.")
        auth_url = build_auth_url(workspace_id)
        st.link_button("Connect Google Account", auth_url)


def _show_property_selection(
    creds: Any,
    conn: dict,
    token: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """Show dropdowns for selecting GSC and GA4 properties."""
    col_gsc, col_ga4 = st.columns(2)

    with col_gsc:
        st.subheader("GSC Property")
        try:
            gsc_sites = list_gsc_properties(creds)
        except Exception as e:
            st.error(f"Failed to list GSC properties: {e}")
            gsc_sites = []

        if gsc_sites:
            options = [s["url"] for s in gsc_sites]
            current = conn.get("gsc_property", "")
            idx = options.index(current) if current in options else 0
            selected = st.selectbox("Select GSC site", options, index=idx, key="gsc_property_select")
            if selected != conn.get("gsc_property"):
                update_selected_properties(token, workspace_id, user_id, gsc_property=selected)
                conn["gsc_property"] = selected
        else:
            st.caption("No GSC properties found.")

    with col_ga4:
        st.subheader("GA4 Property")
        try:
            ga4_props = list_ga4_properties(creds)
        except Exception as e:
            st.error(f"Failed to list GA4 properties: {e}")
            ga4_props = []

        if ga4_props:
            options = [f"{p['display_name']} ({p['property_id']})" for p in ga4_props]
            ids = [p["property_id"] for p in ga4_props]
            current_id = conn.get("ga4_property_id", "")
            idx = ids.index(current_id) if current_id in ids else 0
            selected_idx = st.selectbox("Select GA4 property", range(len(options)),
                                         format_func=lambda i: options[i],
                                         index=idx, key="ga4_property_select")
            selected_prop = ga4_props[selected_idx]
            if selected_prop["property_id"] != conn.get("ga4_property_id"):
                update_selected_properties(
                    token, workspace_id, user_id,
                    ga4_property_id=selected_prop["property_id"],
                    ga4_property_name=selected_prop["display_name"],
                )
                conn["ga4_property_id"] = selected_prop["property_id"]
                conn["ga4_property_name"] = selected_prop["display_name"]
        else:
            st.caption("No GA4 properties found.")


def _show_gsc_import(
    creds: Any,
    conn: dict,
    project_ctx: dict[str, Any],
    token: str,
) -> None:
    """GSC data import section."""
    gsc_property = conn.get("gsc_property")
    if not gsc_property:
        st.info("Select a GSC property above to import data.")
        return

    st.markdown(f"**Property:** {gsc_property}")

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start date", value=date.today() - timedelta(days=28),
                               key="gsc_start_date")
    with col2:
        end = st.date_input("End date", value=date.today() - timedelta(days=1),
                             key="gsc_end_date")

    if st.button("Import GSC Data", type="primary", key="btn_import_gsc"):
        with st.spinner("Fetching GSC data..."):
            try:
                rows = fetch_gsc_data(creds, gsc_property, str(start), str(end))
            except Exception as e:
                st.error(f"GSC API error: {e}")
                return

        if not rows:
            st.warning("No GSC data returned for this date range.")
            return

        st.info(f"Fetched {len(rows)} page rows. Saving...")

        # Build pages lookup for URL matching
        pages = _load_pages(token, project_ctx["id"])
        lookup = build_pages_lookup(pages)

        # UPSERT to gsc_data
        from app import db_upsert
        saved = 0
        matched = 0
        for row in rows:
            page_id = match_url_to_page(row["url"], lookup, project_ctx.get("domain", ""))
            body = {
                "project_id": project_ctx["id"],
                "url": row["url"],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": row["ctr"],
                "position": row["position"],
                "date_range_start": str(start),
                "date_range_end": str(end),
                "page_id": page_id,
            }
            try:
                db_upsert("gsc_data", token, body,
                          on_conflict="project_id,url,date_range_start")
                saved += 1
                if page_id:
                    matched += 1
            except Exception as e:
                st.error(f"Failed to save row: {e}")
                break

        st.success(f"Saved {saved} GSC rows. {matched}/{saved} matched to crawled pages.")

        # Track usage
        try:
            from tracking.usage_tracker import log_usage_event
            log_usage_event(
                event_type="gsc_import",
                event_detail=f"{saved} rows",
                project_id=project_ctx["id"],
            )
        except Exception:
            pass

    # Show existing data
    _show_existing_gsc_data(token, project_ctx["id"])


def _show_ga4_import(
    creds: Any,
    conn: dict,
    project_ctx: dict[str, Any],
    token: str,
) -> None:
    """GA4 data import section."""
    ga4_property_id = conn.get("ga4_property_id")
    if not ga4_property_id:
        st.info("Select a GA4 property above to import data.")
        return

    st.markdown(f"**Property:** {conn.get('ga4_property_name', ga4_property_id)}")

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start date", value=date.today() - timedelta(days=28),
                               key="ga4_start_date")
    with col2:
        end = st.date_input("End date", value=date.today() - timedelta(days=1),
                             key="ga4_end_date")

    if st.button("Import GA4 Data", type="primary", key="btn_import_ga4"):
        with st.spinner("Fetching GA4 data..."):
            try:
                rows = fetch_ga4_data(creds, ga4_property_id, str(start), str(end))
            except Exception as e:
                st.error(f"GA4 API error: {e}")
                return

        if not rows:
            st.warning("No GA4 data returned for this date range.")
            return

        st.info(f"Fetched {len(rows)} page rows. Saving...")

        # Build pages lookup for URL matching
        pages = _load_pages(token, project_ctx["id"])
        lookup = build_pages_lookup(pages)
        domain = project_ctx.get("domain", "")

        # UPSERT to ga_data
        from app import db_upsert
        saved = 0
        matched = 0
        for row in rows:
            page_id = match_url_to_page(row["page_path"], lookup, domain)
            body = {
                "project_id": project_ctx["id"],
                "page_path": row["page_path"],
                "sessions": row["sessions"],
                "engaged_sessions": row["engaged_sessions"],
                "engagement_rate": row["engagement_rate"],
                "avg_engagement_time": row["avg_engagement_time"],
                "bounce_rate": row["bounce_rate"],
                "date_range_start": str(start),
                "date_range_end": str(end),
                "page_id": page_id,
            }
            try:
                db_upsert("ga_data", token, body,
                          on_conflict="project_id,page_path,date_range_start")
                saved += 1
                if page_id:
                    matched += 1
            except Exception as e:
                st.error(f"Failed to save row: {e}")
                break

        st.success(f"Saved {saved} GA4 rows. {matched}/{saved} matched to crawled pages.")

        # Track usage
        try:
            from tracking.usage_tracker import log_usage_event
            log_usage_event(
                event_type="ga_import",
                event_detail=f"{saved} rows",
                project_id=project_ctx["id"],
            )
        except Exception:
            pass

    # Show existing data
    _show_existing_ga4_data(token, project_ctx["id"])


def _show_match_status(project_ctx: dict[str, Any], token: str) -> None:
    """Show URL match percentages and re-run matching."""
    project_id = project_ctx["id"]
    domain = project_ctx.get("domain", "")

    # Load current counts
    from app import db_request

    gsc_rows = db_request("GET", "gsc_data", token,
                          params={"select": "id,url,page_id",
                                  "project_id": f"eq.{project_id}"})
    ga_rows = db_request("GET", "ga_data", token,
                         params={"select": "id,page_path,page_id",
                                 "project_id": f"eq.{project_id}"})

    col1, col2 = st.columns(2)
    with col1:
        gsc_total = len(gsc_rows)
        gsc_matched = sum(1 for r in gsc_rows if r.get("page_id"))
        pct = (gsc_matched / gsc_total * 100) if gsc_total else 0
        st.metric("GSC URL Match", f"{gsc_matched}/{gsc_total} ({pct:.0f}%)")
    with col2:
        ga_total = len(ga_rows)
        ga_matched = sum(1 for r in ga_rows if r.get("page_id"))
        pct = (ga_matched / ga_total * 100) if ga_total else 0
        st.metric("GA4 URL Match", f"{ga_matched}/{ga_total} ({pct:.0f}%)")

    if st.button("Re-run URL Matching", type="primary", key="btn_rematch"):
        pages = _load_pages(token, project_id)
        if not pages:
            st.warning("No crawled pages found. Run the crawler first.")
            return

        lookup = build_pages_lookup(pages)
        gsc_updated = 0
        ga_updated = 0
        ga_newly_matched = 0
        gsc_newly_matched = 0

        status = st.empty()
        status.info("Re-matching GSC URLs...")

        # Re-match GSC
        for row in gsc_rows:
            page_id = match_url_to_page(row["url"], lookup, domain)
            if page_id != row.get("page_id"):
                _update_page_id("gsc_data", token, row["id"], page_id)
                gsc_updated += 1
                if page_id:
                    gsc_newly_matched += 1

        status.info("Re-matching GA4 page paths...")

        # Re-match GA4
        for row in ga_rows:
            page_id = match_url_to_page(row["page_path"], lookup, domain)
            if page_id != row.get("page_id"):
                _update_page_id("ga_data", token, row["id"], page_id)
                ga_updated += 1
                if page_id:
                    ga_newly_matched += 1

        status.empty()

        # Show results without rerun so user can see them
        st.success(
            f"Re-matching complete. "
            f"GSC: {gsc_newly_matched} newly matched ({gsc_updated} changed). "
            f"GA4: {ga_newly_matched} newly matched ({ga_updated} changed). "
            f"Domain used: `{domain}`"
        )

        # Debug: show sample paths that didn't match
        unmatched_ga = [r["page_path"] for r in ga_rows
                        if not match_url_to_page(r["page_path"], lookup, domain)][:5]
        if unmatched_ga:
            sample_pages = list(lookup.keys())[:3]
            st.info(
                f"Sample unmatched GA4 paths: {unmatched_ga}\n\n"
                f"Sample crawled URLs in lookup: {sample_pages}"
            )


def _load_pages(token: str, project_id: str) -> list[dict]:
    """Load pages for a project from Supabase."""
    from app import db_request
    try:
        return db_request("GET", "pages", token,
                          params={"select": "id,url",
                                  "project_id": f"eq.{project_id}"})
    except Exception:
        return []


def _update_page_id(table: str, token: str, row_id: str, page_id: str | None) -> None:
    """Update page_id on a single row via PATCH."""
    import httpx
    import os

    supabase_url = ""
    supabase_anon_key = ""
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_anon_key = st.secrets["SUPABASE_ANON_KEY"]
    except (KeyError, FileNotFoundError):
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", "")

    url = f"{supabase_url}/rest/v1/{table}"
    headers = {
        "apikey": supabase_anon_key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    httpx.patch(url, headers=headers, json={"page_id": page_id},
                params={"id": f"eq.{row_id}"})


def _show_existing_gsc_data(token: str, project_id: str) -> None:
    """Show summary of existing GSC data for this project."""
    from app import db_request
    try:
        rows = db_request("GET", "gsc_data", token,
                          params={"select": "url,clicks,impressions,ctr,position,date_range_start,page_id",
                                  "project_id": f"eq.{project_id}",
                                  "order": "clicks.desc",
                                  "limit": "20"})
    except Exception:
        rows = []

    if rows:
        st.divider()
        st.subheader("Top GSC Pages (by clicks)")
        display = []
        for r in rows:
            display.append({
                "URL": r["url"],
                "Clicks": r["clicks"],
                "Impressions": r["impressions"],
                "CTR": f"{r['ctr'] * 100:.1f}%" if r["ctr"] else "0%",
                "Position": r["position"],
                "Matched": "Yes" if r.get("page_id") else "No",
            })
        st.dataframe(display, use_container_width=True, hide_index=True)


def _show_existing_ga4_data(token: str, project_id: str) -> None:
    """Show summary of existing GA4 data for this project."""
    from app import db_request
    try:
        rows = db_request("GET", "ga_data", token,
                          params={"select": "page_path,sessions,engaged_sessions,engagement_rate,bounce_rate,page_id",
                                  "project_id": f"eq.{project_id}",
                                  "order": "sessions.desc",
                                  "limit": "20"})
    except Exception:
        rows = []

    if rows:
        st.divider()
        st.subheader("Top GA4 Pages (by sessions)")
        display = []
        for r in rows:
            display.append({
                "Page Path": r["page_path"],
                "Sessions": r["sessions"],
                "Engaged": r["engaged_sessions"],
                "Engagement Rate": f"{r['engagement_rate'] * 100:.1f}%" if r["engagement_rate"] else "0%",
                "Bounce Rate": f"{r['bounce_rate'] * 100:.1f}%" if r["bounce_rate"] else "0%",
                "Matched": "Yes" if r.get("page_id") else "No",
            })
        st.dataframe(display, use_container_width=True, hide_index=True)
