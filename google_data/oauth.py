"""Google OAuth flow — token exchange, refresh, credential building."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import streamlit as st
from google.oauth2.credentials import Credentials


# Scopes needed for GSC + GA4 read access
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]

AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _get_secret(key: str) -> str:
    """Read from st.secrets first, fall back to env."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, "")


def _hmac_key() -> bytes:
    """Derive HMAC key from client secret."""
    secret = _get_secret("GOOGLE_CLIENT_SECRET")
    return secret.encode("utf-8")


def build_auth_url(workspace_id: str) -> str:
    """Build Google OAuth consent URL with CSRF-protected state. No PKCE."""
    # CSRF state: HMAC-signed workspace_id + timestamp
    nonce = str(int(time.time()))
    payload = f"{workspace_id}:{nonce}"
    sig = hmac.new(_hmac_key(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    state = f"{payload}:{sig}"

    params = {
        "client_id": _get_secret("GOOGLE_CLIENT_ID"),
        "redirect_uri": _get_secret("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URI}?{urlencode(params)}"


def verify_state(state: str) -> str | None:
    """Verify CSRF state and return workspace_id if valid."""
    parts = state.split(":")
    if len(parts) != 3:
        return None
    workspace_id, nonce, sig = parts
    payload = f"{workspace_id}:{nonce}"
    expected = hmac.new(_hmac_key(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return None
    return workspace_id


def exchange_code_for_tokens(code: str) -> dict[str, Any] | None:
    """Exchange authorization code for tokens via raw HTTP POST. No PKCE."""
    body = {
        "code": code,
        "client_id": _get_secret("GOOGLE_CLIENT_ID"),
        "client_secret": _get_secret("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": _get_secret("GOOGLE_REDIRECT_URI"),
        "grant_type": "authorization_code",
    }
    try:
        r = httpx.post(TOKEN_URI, data=body, timeout=30.0)
        if r.status_code >= 400:
            st.error(f"Token exchange failed: {r.status_code} {r.text}")
            return None
        data = r.json()
        # expires_in is seconds — convert to ISO timestamp
        from datetime import datetime, timedelta, timezone
        expiry = None
        if data.get("expires_in"):
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])).isoformat()
        return {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "token_expiry": expiry,
        }
    except Exception as e:
        st.error(f"Token exchange failed: {e}")
        return None


def get_credentials_from_refresh_token(refresh_token: str) -> Credentials | None:
    """Build Credentials object from stored refresh token (auto-refreshes)."""
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=_get_secret("GOOGLE_CLIENT_ID"),
        client_secret=_get_secret("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    try:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        return creds
    except Exception as e:
        st.error(f"Failed to refresh Google token: {e}")
        return None


# --- Supabase persistence for google_connections ---

def _supabase_url() -> str:
    return _get_secret("SUPABASE_URL")


def _supabase_anon_key() -> str:
    return _get_secret("SUPABASE_ANON_KEY")


def save_connection(
    access_token: str,
    workspace_id: str,
    user_id: str,
    refresh_token: str,
    token_expiry: str | None = None,
    gsc_property: str | None = None,
    ga4_property_id: str | None = None,
    ga4_property_name: str | None = None,
) -> bool:
    """Save or update Google connection in Supabase."""
    url = f"{_supabase_url()}/rest/v1/google_connections"
    headers = {
        "apikey": _supabase_anon_key(),
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }
    body = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "google_refresh_token": refresh_token,
    }
    if token_expiry:
        body["google_token_expiry"] = token_expiry
    if gsc_property is not None:
        body["gsc_property"] = gsc_property
    if ga4_property_id is not None:
        body["ga4_property_id"] = ga4_property_id
    if ga4_property_name is not None:
        body["ga4_property_name"] = ga4_property_name

    r = httpx.post(url, headers=headers, json=body,
                   params={"on_conflict": "workspace_id,user_id"})
    if r.status_code >= 400:
        st.error(f"Failed to save Google connection: {r.status_code} {r.text}")
        return False
    return True


def load_connection(access_token: str, workspace_id: str, user_id: str) -> dict[str, Any] | None:
    """Load existing Google connection from Supabase."""
    url = f"{_supabase_url()}/rest/v1/google_connections"
    headers = {
        "apikey": _supabase_anon_key(),
        "Authorization": f"Bearer {access_token}",
    }
    params = {
        "select": "google_refresh_token,google_token_expiry,gsc_property,ga4_property_id,ga4_property_name,connected_at",
        "workspace_id": f"eq.{workspace_id}",
        "user_id": f"eq.{user_id}",
    }
    r = httpx.get(url, headers=headers, params=params)
    if r.status_code >= 400:
        return None
    rows = r.json()
    return rows[0] if rows else None


def update_selected_properties(
    access_token: str,
    workspace_id: str,
    user_id: str,
    gsc_property: str | None = None,
    ga4_property_id: str | None = None,
    ga4_property_name: str | None = None,
) -> bool:
    """Update just the selected property fields on an existing connection."""
    url = f"{_supabase_url()}/rest/v1/google_connections"
    headers = {
        "apikey": _supabase_anon_key(),
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    body: dict[str, Any] = {}
    if gsc_property is not None:
        body["gsc_property"] = gsc_property
    if ga4_property_id is not None:
        body["ga4_property_id"] = ga4_property_id
    if ga4_property_name is not None:
        body["ga4_property_name"] = ga4_property_name

    if not body:
        return True

    params = {
        "workspace_id": f"eq.{workspace_id}",
        "user_id": f"eq.{user_id}",
    }
    r = httpx.patch(url, headers=headers, json=body, params=params)
    return r.status_code < 400
