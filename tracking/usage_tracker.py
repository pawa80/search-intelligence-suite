from __future__ import annotations

"""Fire-and-forget usage event tracking. Never raises — failures log to console only."""

import os
import httpx
import streamlit as st


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, "")


def _refresh_jwt() -> str | None:
    """Refresh Supabase JWT. Returns new token or None."""
    try:
        from supabase import create_client
        url = _get_secret("SUPABASE_URL")
        anon = _get_secret("SUPABASE_ANON_KEY")
        sb = create_client(url, anon)
        stored_access = st.session_state.get("access_token")
        stored_refresh = st.session_state.get("refresh_token")
        if stored_access and stored_refresh:
            try:
                sb.auth.set_session(stored_access, stored_refresh)
            except Exception:
                pass
        resp = sb.auth.refresh_session()
        if resp and resp.session:
            st.session_state["access_token"] = resp.session.access_token
            st.session_state["refresh_token"] = resp.session.refresh_token
            return resp.session.access_token
    except Exception:
        pass
    return None


def log_usage_event(
    event_type: str,
    api_provider: str | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    event_detail: str | None = None,
    project_id: str | None = None,
) -> None:
    """Log a usage event to Supabase. Fire-and-forget — never raises."""
    try:
        user = st.session_state.get("user")
        if not user:
            return
        user_id = str(user.id)

        token = st.session_state.get("access_token")
        if not token:
            return

        supabase_url = _get_secret("SUPABASE_URL")
        anon_key = _get_secret("SUPABASE_ANON_KEY")
        if not supabase_url or not anon_key:
            return

        # If no project_id passed, try to get from session state
        if not project_id:
            project_id = st.session_state.get("selected_project_id") or st.session_state.get("crawler_project_id")

        body = {
            "user_id": user_id,
            "event_type": event_type,
        }
        if project_id:
            body["project_id"] = project_id
        if api_provider:
            body["api_provider"] = api_provider
        if model:
            body["model"] = model
        if input_tokens is not None:
            body["input_tokens"] = input_tokens
        if output_tokens is not None:
            body["output_tokens"] = output_tokens
        if estimated_cost_usd is not None:
            body["estimated_cost_usd"] = float(estimated_cost_usd)
        if event_detail:
            body["event_detail"] = event_detail

        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

        r = httpx.post(
            f"{supabase_url}/rest/v1/usage_events",
            headers=headers,
            json=body,
            timeout=10.0,
        )

        if r.status_code == 401:
            new_token = _refresh_jwt()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                r = httpx.post(
                    f"{supabase_url}/rest/v1/usage_events",
                    headers=headers,
                    json=body,
                    timeout=10.0,
                )

        if r.status_code >= 400:
            print(f"[usage_tracker] Failed to log {event_type}: {r.status_code} {r.text}")

    except Exception as e:
        print(f"[usage_tracker] Error logging {event_type}: {e}")
