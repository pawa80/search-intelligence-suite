import streamlit as st
from supabase import create_client
import httpx
import csv
import io
import json
import time
import os
from collections import Counter
from datetime import date
from urllib.parse import urlparse
from dotenv import load_dotenv
from crawler.crawler_ui import show_crawler
from google_data.datasources_ui import show_datasources, handle_oauth_callback_if_present
from aeo.aeo_ui import show_aeo_agent
from matrise.matrise_ui import show_matrise
from arbeidspakker.arbeidspakker_ui import show_arbeidspakker_library

load_dotenv()


# Read from st.secrets (Streamlit Cloud) or .env (local)
def get_secret(key):
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key)


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_ANON_KEY = get_secret("SUPABASE_ANON_KEY")
PERPLEXITY_API_KEY = get_secret("PERPLEXITY_API_KEY")

# Unauthenticated client for auth operations only
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

st.set_page_config(page_title="Aevilab", page_icon="⬡", layout="wide")

# ---------------------------------------------------------------------------
# Aevilab design system — CSS variable-based dark/light theming
# ---------------------------------------------------------------------------

_AEVILAB_FONTS = """
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap');
"""

_DARK_VARS = """
:root {
    --bg: #0d0f14;
    --sidebar-bg: #111318;
    --surface: #1a1d24;
    --surface2: #21252e;
    --border: #2a2f3a;
    --border2: #343b48;
    --text-primary: #e8eaf0;
    --text-muted: #7a8099;
    --text-muted2: #4e5568;
    --accent: #f0a500;
    --accent-hover: #ffb820;
    --accent-dim: rgba(240,165,0,0.12);
    --accent-border: rgba(240,165,0,0.35);
    --green: #2dd4a0;
    --green-dim: rgba(45,212,160,0.1);
    --green-border: rgba(45,212,160,0.3);
    --red: #f06070;
    --red-dim: rgba(240,96,112,0.1);
    --red-border: rgba(240,96,112,0.3);
    --blue: #5b9cf6;
    --blue-dim: rgba(91,156,246,0.1);
    --blue-border: rgba(91,156,246,0.3);
    --purple: #a78bfa;
    --purple-dim: rgba(167,139,250,0.1);
    --btn-primary-text: #0d0f14;
    --scrollbar-thumb: #343b48;
    --scrollbar-hover: #4e5568;
}
"""

_LIGHT_VARS = """
:root {
    --bg: #f8f9fb;
    --sidebar-bg: #ffffff;
    --surface: #ffffff;
    --surface2: #f0f2f5;
    --border: #e2e5ea;
    --border2: #d0d4db;
    --text-primary: #1a1d24;
    --text-muted: #5a6070;
    --text-muted2: #8890a0;
    --accent: #d48f00;
    --accent-hover: #b87a00;
    --accent-dim: rgba(212,143,0,0.10);
    --accent-border: rgba(212,143,0,0.30);
    --green: #0fa67e;
    --green-dim: rgba(15,166,126,0.08);
    --green-border: rgba(15,166,126,0.25);
    --red: #d94452;
    --red-dim: rgba(217,68,82,0.08);
    --red-border: rgba(217,68,82,0.25);
    --blue: #3b7cdb;
    --blue-dim: rgba(59,124,219,0.08);
    --blue-border: rgba(59,124,219,0.25);
    --purple: #7c5fcf;
    --purple-dim: rgba(124,95,207,0.08);
    --btn-primary-text: #ffffff;
    --scrollbar-thumb: #d0d4db;
    --scrollbar-hover: #b0b8c4;
}
"""

_AEVILAB_COMPONENTS = """
/* --- Global typography --- */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14px;
}
h1, h2, h3,
[data-testid="stHeading"] h1,
[data-testid="stHeading"] h2,
[data-testid="stHeading"] h3 {
    font-family: 'Syne', sans-serif !important;
    letter-spacing: -0.3px !important;
    color: var(--text-primary) !important;
}
code, pre, .stCode,
[data-testid="stCode"] {
    font-family: 'DM Mono', monospace !important;
}

/* --- Sidebar --- */
[data-testid="stSidebar"] {
    background-color: var(--sidebar-bg) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] label {
    color: var(--text-muted) !important;
    font-size: 13px !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: var(--text-primary) !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: var(--text-muted2) !important;
}

/* --- Main area --- */
[data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
}
.stApp {
    background-color: var(--bg) !important;
}
[data-testid="stHeader"] {
    background-color: var(--bg) !important;
}

/* --- Text colour --- */
.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span {
    color: var(--text-primary) !important;
}

/* --- Metric cards --- */
[data-testid="stMetric"] {
    background-color: var(--surface2) !important;
    border-radius: 8px !important;
    padding: 16px !important;
    border: 1px solid var(--border) !important;
}
[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
}

/* --- Buttons (primary = amber CTA) --- */
.stButton > button[kind="primary"],
.stButton > button {
    background-color: var(--accent) !important;
    color: var(--btn-primary-text) !important;
    border: none !important;
    font-weight: 500 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 13px !important;
    border-radius: 8px !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background-color: var(--accent-hover) !important;
    color: var(--btn-primary-text) !important;
}
.stButton > button[kind="secondary"] {
    background-color: var(--surface2) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border2) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: var(--text-muted2) !important;
}

/* --- Form inputs --- */
.stTextInput input,
.stTextArea textarea,
.stSelectbox > div > div {
    background-color: var(--surface2) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border2) !important;
    border-radius: 8px !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 13px !important;
}
.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: var(--text-muted2) !important;
}
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}

/* --- Expanders --- */
.streamlit-expanderHeader {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-muted) !important;
}

/* --- Tables and dataframes --- */
[data-testid="stDataFrame"] {
    background-color: var(--surface) !important;
    border-radius: 8px !important;
    border: 1px solid var(--border) !important;
}
.stDataFrame th {
    background-color: var(--surface) !important;
    color: var(--text-muted) !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    font-weight: 500 !important;
    border-bottom: 1px solid var(--border) !important;
}
.stDataFrame td {
    color: var(--text-primary) !important;
    border-bottom: 1px solid var(--border) !important;
    font-size: 12.5px !important;
}

/* --- Tabs --- */
.stTabs [data-baseweb="tab-list"] {
    gap: 0px;
    border-bottom: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    color: var(--text-muted2) !important;
    border-bottom: 2px solid transparent !important;
    font-size: 13px !important;
    font-weight: 400 !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    font-weight: 500 !important;
}

/* --- Download buttons --- */
.stDownloadButton > button {
    background-color: var(--surface) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border2) !important;
}
.stDownloadButton > button:hover {
    border-color: var(--text-muted2) !important;
}

/* --- Radio buttons (model toggle) --- */
.stRadio > div {
    background-color: var(--surface) !important;
    border-radius: 8px !important;
    padding: 8px !important;
    border: 1px solid var(--border) !important;
}
.stRadio label {
    color: var(--text-muted) !important;
}

/* --- Toggle / Switch --- */
[data-testid="stSidebar"] .stToggle label span {
    color: var(--text-muted) !important;
    font-size: 13px !important;
    text-transform: none !important;
    letter-spacing: normal !important;
}

/* --- Messages --- */
.stSuccess {
    background-color: var(--green-dim) !important;
    color: var(--green) !important;
    border: 1px solid var(--green-border) !important;
    border-radius: 8px !important;
}
.stWarning {
    background-color: var(--accent-dim) !important;
    color: var(--accent) !important;
    border: 1px solid var(--accent-border) !important;
    border-radius: 8px !important;
}
.stException, .stError {
    background-color: var(--red-dim) !important;
    color: var(--red) !important;
    border: 1px solid var(--red-border) !important;
    border-radius: 8px !important;
}
.stInfo {
    background-color: var(--blue-dim) !important;
    color: var(--blue) !important;
    border: 1px solid var(--blue-border) !important;
    border-radius: 8px !important;
}

/* --- Progress bar --- */
.stProgress > div > div > div {
    background-color: var(--accent) !important;
    border-radius: 3px !important;
}

/* --- Dividers --- */
hr {
    border-color: var(--border) !important;
}

/* --- Checkboxes --- */
.stCheckbox label {
    color: var(--text-muted) !important;
}

/* --- Caption/small text --- */
.stCaption, [data-testid="stCaption"] {
    color: var(--text-muted2) !important;
}

/* --- Links --- */
a {
    color: var(--blue) !important;
}

/* --- Scrollbar --- */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: transparent;
}
::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: var(--scrollbar-hover);
}
"""


def _inject_theme():
    """Inject Aevilab CSS with dark/light mode support."""
    is_dark = st.session_state.get("dark_mode", True)
    vars_css = _DARK_VARS if is_dark else _LIGHT_VARS
    st.markdown(
        f"<style>{_AEVILAB_FONTS}{vars_css}{_AEVILAB_COMPONENTS}</style>",
        unsafe_allow_html=True,
    )


_inject_theme()


def init_session_state():
    defaults = {
        "user": None, "workspace": None, "access_token": None,
        "refresh_token": None, "error": None, "selected_project_id": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _refresh_jwt():
    """Refresh the Supabase JWT using the current session. Returns new token or None."""
    try:
        # Restore session from stored tokens so supabase client has context
        stored_access = st.session_state.get("access_token")
        stored_refresh = st.session_state.get("refresh_token")
        if stored_access and stored_refresh:
            try:
                supabase.auth.set_session(stored_access, stored_refresh)
            except Exception:
                pass
        response = supabase.auth.refresh_session()
        if response and response.session:
            st.session_state.access_token = response.session.access_token
            st.session_state.refresh_token = response.session.refresh_token
            return response.session.access_token
    except Exception:
        pass
    return None


def _make_rest_call(method, url, headers, params=None, body=None):
    """Execute a single REST call."""
    if method == "GET":
        return httpx.get(url, headers=headers, params=params, timeout=30.0)
    elif method == "POST":
        return httpx.post(url, headers=headers, json=body, params=params, timeout=30.0)
    elif method == "PATCH":
        return httpx.patch(url, headers=headers, json=body, params=params, timeout=30.0)
    elif method == "DELETE":
        return httpx.delete(url, headers=headers, params=params, timeout=30.0)
    else:
        raise ValueError(f"Unsupported method: {method}")


def db_request(method, table, access_token, params=None, body=None):
    """Direct REST call to Supabase PostgREST with authenticated JWT.
    Auto-refreshes token on 401 and retries once."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    r = _make_rest_call(method, url, headers, params=params, body=body)

    if r.status_code == 401:
        new_token = _refresh_jwt()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = _make_rest_call(method, url, headers, params=params, body=body)

    if r.status_code >= 400:
        raise Exception(f"DB {method} {table}: {r.status_code} {r.text}")
    if r.status_code == 204:
        return []
    return r.json()


def db_upsert(table, access_token, body, on_conflict):
    """UPSERT via PostgREST — insert or update on conflict.
    Auto-refreshes token on 401 and retries once."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }
    upsert_params = {"on_conflict": on_conflict}
    r = httpx.post(url, headers=headers, json=body, params=upsert_params, timeout=30.0)

    if r.status_code == 401:
        new_token = _refresh_jwt()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = httpx.post(url, headers=headers, json=body, params=upsert_params, timeout=30.0)

    if r.status_code >= 400:
        raise Exception(f"DB UPSERT {table}: {r.status_code} {r.text}")
    return r.json()


def rpc_request(fn_name, access_token, params):
    """Call a Supabase RPC function.
    Auto-refreshes token on 401 and retries once."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    r = httpx.post(url, headers=headers, json=params, timeout=30.0)

    if r.status_code == 401:
        new_token = _refresh_jwt()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = httpx.post(url, headers=headers, json=params, timeout=30.0)

    if r.status_code >= 400:
        raise Exception(f"RPC {fn_name}: {r.status_code} {r.text}")
    return r.json()


# --- Auth functions ---

def sign_up(email, password):
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user:
            return response
        return None
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            st.error("This email is already registered. Please log in instead.")
        else:
            st.error(f"Signup failed: {error_msg}")
        return None


def sign_in(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return response
    except Exception as e:
        error_msg = str(e)
        if "invalid" in error_msg.lower() or "wrong" in error_msg.lower():
            st.error("Invalid email or password.")
        elif "not found" in error_msg.lower():
            st.error("User not found. Please sign up first.")
        else:
            st.error(f"Login failed: {error_msg}")
        return None


def ensure_workspace(user, access_token):
    """Check if user has a workspace; create one if not."""
    user_id = str(user.id)
    email = user.email

    try:
        rows = db_request("GET", "workspace_members", access_token,
            params={"select": "workspace_id", "user_id": f"eq.{user_id}"})

        if rows and len(rows) > 0:
            ws_id = rows[0]["workspace_id"]
            ws_rows = db_request("GET", "workspaces", access_token,
                params={"select": "id,name", "id": f"eq.{ws_id}"})
            if ws_rows:
                return {"id": ws_rows[0]["id"], "name": ws_rows[0]["name"]}

        ws_name = f"{email}'s Workspace"
        workspace_id = rpc_request("create_workspace_for_user", access_token,
            {"ws_name": ws_name, "ws_user_id": user_id})

        return {"id": workspace_id, "name": ws_name}

    except Exception as e:
        st.session_state.error = str(e)
        return None


def logout():
    supabase.auth.sign_out()
    for key in ["user", "workspace", "access_token", "refresh_token", "error", "selected_project_id"]:
        st.session_state[key] = None
    st.rerun()


# --- Data functions ---

def get_projects(access_token, workspace_id):
    try:
        return db_request("GET", "projects", access_token,
            params={"select": "*",
                     "workspace_id": f"eq.{workspace_id}",
                     "order": "created_at.asc"})
    except Exception as e:
        st.session_state.error = str(e)
        return []


def create_project(access_token, workspace_id, name, domain, country, language):
    try:
        body = {"workspace_id": workspace_id, "name": name, "domain": domain}
        if country:
            body["country"] = country
        if language:
            body["language"] = language
        rows = db_request("POST", "projects", access_token, body=body)
        return rows[0] if rows else None
    except Exception as e:
        st.session_state.error = str(e)
        return None


def get_queries(access_token, project_id):
    try:
        return db_request("GET", "queries", access_token,
            params={"select": "id,query_text,category,is_active,created_at",
                     "project_id": f"eq.{project_id}",
                     "order": "created_at.asc"})
    except Exception as e:
        st.session_state.error = str(e)
        return []


def add_queries(access_token, project_id, query_list):
    """Insert queries, skipping duplicates. Returns (added_count, skipped_count).

    Uses batch INSERT via PostgREST (single request for all rows) to avoid
    JWT expiry on large uploads. Falls back to per-row insert if batch fails
    (e.g. duplicate key on some rows).
    """
    # Deduplicate and clean
    clean_rows = []
    for q in query_list:
        text = q["query_text"].strip()
        cat = q["category"].strip()
        if text:
            clean_rows.append({"project_id": project_id, "query_text": text, "category": cat})
    if not clean_rows:
        return 0, 0

    # Try batch insert first (single request — no JWT expiry risk)
    try:
        db_request("POST", "queries", access_token, body=clean_rows)
        return len(clean_rows), 0
    except Exception as batch_err:
        # Batch failed — likely some duplicates. Fall back to per-row.
        if "duplicate" not in str(batch_err).lower() and "23505" not in str(batch_err):
            raise

    # Per-row fallback for mixed new/duplicate rows
    added = 0
    skipped = 0
    for row in clean_rows:
        try:
            db_request("POST", "queries", access_token,
                body=row)
            added += 1
        except Exception as e:
            if "duplicate" in str(e).lower() or "23505" in str(e):
                skipped += 1
            else:
                raise
    return added, skipped


def delete_query(access_token, query_id):
    try:
        db_request("DELETE", "queries", access_token,
            params={"id": f"eq.{query_id}"})
        return True
    except Exception as e:
        st.session_state.error = str(e)
        return False


def delete_queries_bulk(access_token, query_ids):
    """Delete multiple queries by ID. Returns count deleted."""
    if not query_ids:
        return 0
    ids_csv = ",".join(query_ids)
    try:
        db_request("DELETE", "queries", access_token,
            params={"id": f"in.({ids_csv})"})
        return len(query_ids)
    except Exception as e:
        st.session_state.error = str(e)
        return 0


# --- Citation engine ---

def check_citation(query_text, domain, api_key):
    """Check if domain appears in Perplexity's sources for a query."""
    response = httpx.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "sonar",
            "messages": [{"role": "user", "content": query_text}],
        },
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()

    # Citations may be under "citations" or "sources"
    citations = data.get("citations", data.get("sources", []))
    if not isinstance(citations, list):
        citations = []

    appears = False
    position = None
    citation_url = None

    for i, url in enumerate(citations):
        if domain.lower() in url.lower():
            appears = True
            position = i + 1
            citation_url = url
            break

    return {
        "appears": appears,
        "position": position,
        "citation_url": citation_url,
        "raw_sources": citations,
    }


def run_citation_check(access_token, project_id, domain, queries, api_key):
    """Run citation check for all queries. Shows progress in Streamlit."""
    total = len(queries)
    checked = 0
    failures = 0
    today = str(date.today())

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, q in enumerate(queries):
        status_text.text(f"Checking {i + 1}/{total}: {q['query_text'][:60]}...")
        progress_bar.progress((i + 1) / total)

        try:
            result = check_citation(q["query_text"], domain, api_key)
            db_upsert("geo_check_results", access_token, {
                "query_id": q["id"],
                "project_id": project_id,
                "check_date": today,
                "appears": result["appears"],
                "position": result["position"],
                "citation_url": result["citation_url"],
                "engine": "perplexity",
                "raw_sources": json.dumps(result["raw_sources"]),
            }, on_conflict="query_id,engine,check_date")
            checked += 1
        except Exception as e:
            failures += 1
            last_error = str(e)

        if i < total - 1:
            time.sleep(1)

    progress_bar.empty()
    status_text.empty()

    # Track usage
    try:
        from tracking.usage_tracker import log_usage_event
        log_usage_event(
            event_type="citation_check",
            api_provider="perplexity",
            event_detail=f"{checked} queries checked",
            project_id=project_id,
        )
    except Exception:
        pass

    msg = f"Done! {checked}/{total} queries checked."
    if failures:
        msg += f" {failures} failed."
        st.warning(msg)
        st.error(f"Last error: {last_error}")
    else:
        st.success(msg)


def get_latest_results(access_token, project_id):
    """Get the most recent citation check results for a project."""
    try:
        return db_request("GET", "geo_check_results", access_token,
            params={
                "select": "query_id,check_date,appears,position,citation_url,raw_sources",
                "project_id": f"eq.{project_id}",
                "order": "check_date.desc,created_at.desc",
            })
    except Exception as e:
        st.session_state.error = str(e)
        return []


# --- UI: Auth page ---

def show_auth_page():
    st.title("Aevilab")
    st.markdown("AI-powered search optimisation tools")

    if st.session_state.error:
        st.error(f"Error: {st.session_state.error}")
        if st.button("Clear error"):
            st.session_state.error = None
            st.rerun()

    st.divider()

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log In")
            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    response = sign_in(email, password)
                    if response and response.user:
                        token = response.session.access_token
                        st.session_state.user = response.user
                        st.session_state.access_token = token
                        st.session_state.refresh_token = response.session.refresh_token
                        workspace = ensure_workspace(response.user, token)
                        if workspace:
                            st.session_state.workspace = workspace

                        # Track login
                        try:
                            from tracking.usage_tracker import log_usage_event
                            log_usage_event(event_type="login")
                        except Exception:
                            pass

                        st.rerun()

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")
            submitted = st.form_submit_button("Sign Up")
            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                else:
                    response = sign_up(email, password)
                    if response and response.user:
                        if response.session:
                            token = response.session.access_token
                            st.session_state.user = response.user
                            st.session_state.access_token = token
                            st.session_state.refresh_token = response.session.refresh_token
                            workspace = ensure_workspace(response.user, token)
                            if workspace:
                                st.session_state.workspace = workspace
                            st.rerun()
                        else:
                            st.success("Account created! Check your email to confirm, then log in.")


# --- UI: Dashboard ---

def show_dashboard():
    workspace = st.session_state.workspace
    user = st.session_state.user
    token = st.session_state.access_token

    # Load projects
    projects = get_projects(token, workspace["id"])

    # --- Sidebar ---
    with st.sidebar:
        st.markdown(f"**{workspace['name']}**")
        st.caption(user.email)

        # Tool selector — _tool_override can set the value BEFORE the widget renders
        _tools = ["Rank Tracker", "Crawl", "Matrix", "AI Workspace", "Data Sources", "Settings"]
        if "_tool_override" in st.session_state:
            st.session_state["active_tool"] = st.session_state.pop("_tool_override")
        _prev_tool = st.session_state.get("active_tool")
        tool = st.radio("Tool", _tools, key="active_tool", label_visibility="collapsed")
        if tool != _prev_tool:
            try:
                from tracking.usage_tracker import log_usage_event
                log_usage_event(event_type="tool_switch", event_detail=tool)
            except Exception:
                pass
        st.divider()

        if projects:
            project_names = [p["name"] for p in projects]
            current_idx = 0
            if st.session_state.selected_project_id:
                for i, p in enumerate(projects):
                    if p["id"] == st.session_state.selected_project_id:
                        current_idx = i
                        break
            selected_name = st.selectbox("Project", project_names, index=current_idx)
            selected_project = next(p for p in projects if p["name"] == selected_name)
            st.session_state.selected_project_id = selected_project["id"]

            st.session_state["domain_context"] = selected_project.get("domain_context") or ""

        if projects and st.session_state.selected_project_id:
            _pid = st.session_state.selected_project_id
            with st.expander("Project Settings"):
                _dc_val = st.session_state.get("domain_context", "")
                _new_dc = st.text_area(
                    "Domain context",
                    value=_dc_val,
                    height=120,
                    help="Describe the brand, target audience, tone and positioning. This context is used in all playbooks for this project.",
                    key=f"domain_context_input_{_pid}",
                )
                if st.button("Save", key=f"btn_save_domain_context_{_pid}"):
                    try:
                        db_request("PATCH", "projects", token,
                                   params={"id": f"eq.{st.session_state.selected_project_id}"},
                                   body={"domain_context": _new_dc if _new_dc else None})
                        st.session_state["domain_context"] = _new_dc
                        st.success("Domain context saved.")
                        try:
                            from tracking.usage_tracker import log_usage_event
                            log_usage_event("domain_context_set",
                                            event_detail=f"{len(_new_dc)} chars",
                                            project_id=st.session_state.selected_project_id)
                        except Exception:
                            pass
                    except Exception as e:
                        st.error(f"Failed to save: {e}")

        with st.expander("Create New Project"):
            with st.form("create_project_form"):
                p_name = st.text_input("Project name", key="new_project_name")
                p_domain = st.text_input("Domain", key="new_project_domain",
                    placeholder="e.g. wtatennis.com")
                p_country = st.text_input("Country (optional)", key="new_project_country",
                    placeholder="e.g. US")
                p_language = st.text_input("Language (optional)", key="new_project_language",
                    placeholder="e.g. en")
                if st.form_submit_button("Create Project"):
                    if not p_name or not p_domain:
                        st.error("Name and domain are required.")
                    else:
                        result = create_project(token, workspace["id"],
                            p_name, p_domain, p_country, p_language)
                        if result:
                            st.session_state.selected_project_id = result["id"]
                            st.rerun()

        st.divider()
        st.toggle("Dark mode", value=True, key="dark_mode")
        if st.button("Logout"):
            logout()

    # --- Handle OAuth callback (must run before UI renders) ---
    handle_oauth_callback_if_present()

    # --- Show errors ---
    if st.session_state.error:
        st.error(f"Error: {st.session_state.error}")
        if st.button("Clear error"):
            st.session_state.error = None
            st.rerun()

    # --- Route to selected tool ---
    if st.session_state.get("active_tool") == "Crawl":
        # Pass project context to crawler (if a project is selected)
        project_ctx = None
        if st.session_state.selected_project_id and projects:
            p = next((p for p in projects if p["id"] == st.session_state.selected_project_id), None)
            if p:
                project_ctx = {"id": p["id"], "name": p["name"], "domain": p.get("domain", "")}
        show_crawler(project_ctx=project_ctx)
        return

    if st.session_state.get("active_tool") == "Matrix":
        project_ctx = None
        if st.session_state.selected_project_id and projects:
            p = next((p for p in projects if p["id"] == st.session_state.selected_project_id), None)
            if p:
                project_ctx = {"id": p["id"], "name": p["name"], "domain": p.get("domain", "")}
        show_matrise(
            project_ctx=project_ctx,
            token=token,
            workspace_id=workspace["id"],
            user_id=str(user.id),
        )
        return

    if st.session_state.get("active_tool") == "AI Workspace":
        project_ctx = None
        if st.session_state.selected_project_id and projects:
            p = next((p for p in projects if p["id"] == st.session_state.selected_project_id), None)
            if p:
                project_ctx = {"id": p["id"], "name": p["name"], "domain": p.get("domain", "")}
        show_aeo_agent(
            project_ctx=project_ctx,
            token=token,
            workspace_id=workspace["id"],
            user_id=str(user.id),
        )
        return

    if st.session_state.get("active_tool") == "Data Sources":
        project_ctx = None
        if st.session_state.selected_project_id and projects:
            p = next((p for p in projects if p["id"] == st.session_state.selected_project_id), None)
            if p:
                project_ctx = {"id": p["id"], "name": p["name"], "domain": p.get("domain", "")}
        show_datasources(
            project_ctx=project_ctx,
            token=token,
            workspace_id=workspace["id"],
            user_id=str(user.id),
        )
        return

    if st.session_state.get("active_tool") == "Settings":
        st.header("Settings")
        st.info("Settings page coming soon.")
        return

    # --- Rank Tracker main area ---
    if not projects:
        st.title("Welcome to Aevilab")
        st.info("Create your first project to start tracking.")
        return

    if not st.session_state.selected_project_id:
        st.session_state.selected_project_id = projects[0]["id"]

    project = next((p for p in projects if p["id"] == st.session_state.selected_project_id), projects[0])

    # Project header
    st.title(project["name"])
    st.caption(f"Domain: {project['domain']}"
        + (f" · Country: {project['country']}" if project.get("country") else "")
        + (f" · Language: {project['language']}" if project.get("language") else ""))

    # Load queries
    queries = get_queries(token, project["id"])

    # Query summary
    if queries:
        categories = set(q["category"] for q in queries)
        st.markdown(f"**{len(queries)} queries** across **{len(categories)} categories**")
    else:
        st.info("Add queries to start monitoring AI search citations.")

    # --- Citation check ---
    if queries:
        st.divider()
        col_btn, col_test, col_info = st.columns([1, 1, 2])
        with col_btn:
            run_check = st.button("Run Citation Check")
        with col_test:
            run_test = st.button("Test (3 queries)")
        with col_info:
            if not PERPLEXITY_API_KEY:
                st.warning("Set PERPLEXITY_API_KEY to run checks.")

        if (run_check or run_test) and PERPLEXITY_API_KEY:
            active_queries = [q for q in queries if q.get("is_active", True)]
            if run_test:
                active_queries = active_queries[:3]
            run_citation_check(token, project["id"], project["domain"],
                active_queries, PERPLEXITY_API_KEY)

    # --- Dashboard ---
    results = get_latest_results(token, project["id"])
    q_lookup = {q["id"]: q for q in queries}

    if results:
        # Split results by check date
        latest_date = results[0]["check_date"]
        latest_results = [r for r in results if r["check_date"] == latest_date]
        all_dates = sorted(set(r["check_date"] for r in results))

        cited = sum(1 for r in latest_results if r["appears"])
        total = len(latest_results)
        rate = (cited / total * 100) if total > 0 else 0
        positions = [r["position"] for r in latest_results if r["appears"] and r["position"]]
        avg_pos = sum(positions) / len(positions) if positions else 0

        # Top metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Citation Rate", f"{cited}/{total} ({rate:.1f}%)")
        m2.metric("Last Check", latest_date)
        m3.metric("Avg Position", f"{avg_pos:.1f}" if positions else "—")

        # Trend chart (only if multiple dates)
        if len(all_dates) > 1:
            st.divider()
            st.subheader("Citation Rate Over Time")
            trend_data = {}
            for d in all_dates:
                day_results = [r for r in results if r["check_date"] == d]
                day_cited = sum(1 for r in day_results if r["appears"])
                day_total = len(day_results)
                trend_data[d] = (day_cited / day_total * 100) if day_total > 0 else 0
            st.line_chart({"Citation Rate %": trend_data})
        elif len(all_dates) == 1:
            st.caption("Run citation checks on different days to see trends.")

        # Category breakdown
        st.divider()
        st.subheader("Category Breakdown")
        cat_stats = {}
        for r in latest_results:
            q_info = q_lookup.get(r["query_id"])
            cat = q_info["category"] if q_info else "Unknown"
            if cat not in cat_stats:
                cat_stats[cat] = {"queries": 0, "cited": 0, "positions": []}
            cat_stats[cat]["queries"] += 1
            if r["appears"]:
                cat_stats[cat]["cited"] += 1
                if r["position"]:
                    cat_stats[cat]["positions"].append(r["position"])

        cat_table = []
        for cat, s in cat_stats.items():
            cat_rate = (s["cited"] / s["queries"] * 100) if s["queries"] > 0 else 0
            cat_avg = sum(s["positions"]) / len(s["positions"]) if s["positions"] else None
            cat_table.append({
                "Category": cat,
                "Queries": s["queries"],
                "Cited": s["cited"],
                "Rate": f"{cat_rate:.0f}%",
                "Avg Position": f"{cat_avg:.1f}" if cat_avg else "—",
            })
        cat_table.sort(key=lambda x: float(x["Rate"].rstrip("%")), reverse=True)
        st.dataframe(cat_table, use_container_width=True, hide_index=True)

        # Authority set analysis
        st.divider()
        st.subheader("Authority Set — Top Sources")
        domain_counter = Counter()
        for r in latest_results:
            sources = r.get("raw_sources")
            if isinstance(sources, str):
                try:
                    sources = json.loads(sources)
                except (json.JSONDecodeError, TypeError):
                    sources = []
            if isinstance(sources, list):
                for url in sources:
                    try:
                        netloc = urlparse(url).netloc
                        if netloc:
                            domain_counter[netloc] += 1
                    except Exception:
                        pass

        if domain_counter:
            source_table = []
            for domain, count in domain_counter.most_common(15):
                pct = (count / total * 100) if total > 0 else 0
                source_table.append({
                    "Source Domain": domain,
                    "Appearances": count,
                    "% of Queries": f"{pct:.0f}%",
                })
            st.dataframe(source_table, use_container_width=True, hide_index=True)
        else:
            st.info("No source data available.")

        # Uncited queries
        uncited = [r for r in latest_results if not r["appears"]]
        if uncited:
            st.divider()
            st.subheader(f"Uncited Queries ({len(uncited)})")
            uncited_table = []
            for r in uncited:
                q_info = q_lookup.get(r["query_id"])
                uncited_table.append({
                    "Query": q_info["query_text"] if q_info else "Unknown",
                    "Category": q_info["category"] if q_info else "Unknown",
                })
            uncited_table.sort(key=lambda x: x["Category"])
            st.dataframe(uncited_table, use_container_width=True, hide_index=True)

    else:
        st.info("No citation data yet. Click 'Run Citation Check' to start.")

    # --- Manage Queries (in expander) ---
    st.divider()
    with st.expander("Manage Queries"):
        st.subheader("Add Queries")
        tab_single, tab_bulk, tab_csv = st.tabs(["Single", "Bulk Text", "CSV Upload"])

        with tab_single:
            with st.form("add_single_query"):
                q_text = st.text_input("Query", key="single_query_text")
                q_cat = st.text_input("Category", key="single_query_category")
                if st.form_submit_button("Add"):
                    if not q_text or not q_cat:
                        st.error("Query and category are required.")
                    else:
                        added, skipped = add_queries(token, project["id"],
                            [{"query_text": q_text, "category": q_cat}])
                        if added:
                            st.success(f"Added 1 query.")
                            st.rerun()
                        elif skipped:
                            st.warning("Query already exists — skipped.")

        with tab_bulk:
            with st.form("add_bulk_queries"):
                bulk_text = st.text_area("Queries (one per line)", key="bulk_query_text",
                    height=150)
                bulk_cat = st.text_input("Category for all", key="bulk_query_category")
                if st.form_submit_button("Add All"):
                    if not bulk_text or not bulk_cat:
                        st.error("Queries and category are required.")
                    else:
                        lines = [l.strip() for l in bulk_text.strip().split("\n") if l.strip()]
                        query_list = [{"query_text": l, "category": bulk_cat} for l in lines]
                        added, skipped = add_queries(token, project["id"], query_list)
                        msg = f"Added {added} queries."
                        if skipped:
                            msg += f" {skipped} duplicates skipped."
                        st.success(msg)
                        st.rerun()

        with tab_csv:
            uploaded = st.file_uploader("Upload CSV (columns: query_text, category)",
                type=["csv"], key="csv_upload")
            if uploaded:
                try:
                    raw_bytes = uploaded.getvalue()
                    # Decode: utf-8-sig strips BOM if present (Excel default), fallback chain
                    try:
                        text = raw_bytes.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        try:
                            text = raw_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            text = raw_bytes.decode("latin-1")

                    reader = csv.DictReader(io.StringIO(text))
                    fieldnames = [f.strip() for f in (reader.fieldnames or [])]

                    # Try semicolon delimiter if comma didn't produce expected columns
                    if "query_text" not in fieldnames or "category" not in fieldnames:
                        reader = csv.DictReader(io.StringIO(text), delimiter=";")
                        fieldnames = [f.strip() for f in (reader.fieldnames or [])]

                    if "query_text" not in fieldnames or "category" not in fieldnames:
                        st.error(
                            f"CSV must have 'query_text' and 'category' columns. "
                            f"Found columns: {fieldnames}. "
                            f"Tip: In Excel, save as 'CSV UTF-8 (Comma delimited)'."
                        )
                    else:
                        rows = [{"query_text": r.get("query_text", "").strip(),
                                 "category": r.get("category", "").strip()}
                                for r in reader if r.get("query_text", "").strip()]
                        if rows:
                            with st.spinner(f"Uploading {len(rows)} queries..."):
                                added, skipped = add_queries(token, project["id"], rows)
                            msg = f"Added {added} queries."
                            if skipped:
                                msg += f" {skipped} duplicates skipped."
                            st.success(msg)
                            st.rerun()
                        else:
                            st.warning("CSV had no valid rows.")
                except Exception as e:
                    st.error(f"CSV upload failed: {e}")

        st.caption("💡 Write queries as natural language — the way someone would type them into ChatGPT or Perplexity. For example: \"who are the leading CDP experts in the UK\" rather than \"CDP expert + UK\". Personal name queries like \"who is Pal Erik Waagbo\" work as-is. Queries are sent to the AI engine exactly as written — no preprocessing is applied.")

        # Query list with multiselect and bulk delete
        if queries:
            st.divider()
            st.subheader("Queries")

            # Category filter
            all_categories = sorted(set(q["category"] for q in queries))
            cat_options = ["All categories"] + all_categories
            selected_cat = st.selectbox("Filter by category", cat_options, key="query_cat_filter")

            visible_queries = queries if selected_cat == "All categories" else [
                q for q in queries if q["category"] == selected_cat
            ]

            # Initialise selection set
            if "selected_query_ids" not in st.session_state:
                st.session_state["selected_query_ids"] = set()

            # Select all / Deselect all
            visible_ids = {q["id"] for q in visible_queries}
            currently_selected = st.session_state["selected_query_ids"] & visible_ids
            all_selected = len(currently_selected) == len(visible_ids) and len(visible_ids) > 0

            col_sel, col_count = st.columns([1, 3])
            with col_sel:
                if all_selected:
                    if st.button("Deselect all", key="btn_deselect_all"):
                        st.session_state["selected_query_ids"] -= visible_ids
                        for qid in visible_ids:
                            st.session_state.pop(f"cb_{qid}", None)
                        st.rerun()
                else:
                    if st.button("Select all", key="btn_select_all"):
                        st.session_state["selected_query_ids"] |= visible_ids
                        for qid in visible_ids:
                            st.session_state.pop(f"cb_{qid}", None)
                        st.rerun()
            with col_count:
                n_selected = len(currently_selected)
                if n_selected > 0:
                    st.caption(f"{n_selected} selected")

            # Bulk delete button + confirmation
            if n_selected > 0:
                if st.session_state.get("_confirm_bulk_delete"):
                    st.warning(f"Delete {n_selected} keywords? This cannot be undone.")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("Yes, delete", key="btn_confirm_delete", type="primary"):
                            deleted = delete_queries_bulk(token, list(currently_selected))
                            st.session_state["selected_query_ids"] -= currently_selected
                            st.session_state["_confirm_bulk_delete"] = False
                            if deleted:
                                st.success(f"Deleted {deleted} keywords.")
                            st.rerun()
                    with col_no:
                        if st.button("Cancel", key="btn_cancel_delete"):
                            st.session_state["_confirm_bulk_delete"] = False
                            st.rerun()
                else:
                    if st.button(f"Delete selected ({n_selected})", key="btn_bulk_delete"):
                        st.session_state["_confirm_bulk_delete"] = True
                        st.rerun()

            # Query rows with checkboxes
            for q in visible_queries:
                col_cb, col_text, col_cat, col_del = st.columns([0.5, 4, 2, 1])
                is_checked = q["id"] in st.session_state["selected_query_ids"]
                with col_cb:
                    new_val = st.checkbox("", value=is_checked, key=f"cb_{q['id']}", label_visibility="collapsed")
                    if new_val and not is_checked:
                        st.session_state["selected_query_ids"].add(q["id"])
                    elif not new_val and is_checked:
                        st.session_state["selected_query_ids"].discard(q["id"])
                col_text.text(q["query_text"])
                col_cat.text(q["category"])
                if col_del.button("Delete", key=f"del_{q['id']}"):
                    if delete_query(token, q["id"]):
                        st.session_state["selected_query_ids"].discard(q["id"])
                        st.rerun()


# --- Main ---

def main():
    init_session_state()

    if st.session_state.user and st.session_state.workspace:
        try:
            show_dashboard()
        except Exception as e:
            if "401" in str(e) and ("JWT" in str(e) or "expired" in str(e)):
                st.warning("Session expired. Please log in again.")
                logout()
            else:
                raise
    else:
        show_auth_page()


if __name__ == "__main__":
    main()
