import streamlit as st
from supabase import create_client
import httpx
import csv
import io
import json
import time
import os
from datetime import date
from dotenv import load_dotenv

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

st.set_page_config(page_title="Search Intelligence Suite", page_icon="🔍", layout="wide")


def init_session_state():
    defaults = {
        "user": None, "workspace": None, "access_token": None,
        "error": None, "selected_project_id": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def db_request(method, table, access_token, params=None, body=None):
    """Direct REST call to Supabase PostgREST with authenticated JWT."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if method == "GET":
        r = httpx.get(url, headers=headers, params=params)
    elif method == "POST":
        r = httpx.post(url, headers=headers, json=body)
    elif method == "DELETE":
        r = httpx.delete(url, headers=headers, params=params)
    else:
        raise ValueError(f"Unsupported method: {method}")

    if r.status_code >= 400:
        raise Exception(f"DB {method} {table}: {r.status_code} {r.text}")
    if r.status_code == 204:
        return []
    return r.json()


def db_upsert(table, access_token, body, on_conflict):
    """UPSERT via PostgREST — insert or update on conflict."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }
    r = httpx.post(url, headers=headers, json=body,
        params={"on_conflict": on_conflict})
    if r.status_code >= 400:
        raise Exception(f"DB UPSERT {table}: {r.status_code} {r.text}")
    return r.json()


def rpc_request(fn_name, access_token, params):
    """Call a Supabase RPC function."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    r = httpx.post(url, headers=headers, json=params)
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
    for key in ["user", "workspace", "access_token", "error", "selected_project_id"]:
        st.session_state[key] = None
    st.rerun()


# --- Data functions ---

def get_projects(access_token, workspace_id):
    try:
        return db_request("GET", "projects", access_token,
            params={"select": "id,name,domain,country,language,created_at",
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
    """Insert queries, skipping duplicates. Returns (added_count, skipped_count)."""
    added = 0
    skipped = 0
    for q in query_list:
        text = q["query_text"].strip()
        cat = q["category"].strip()
        if not text:
            continue
        try:
            db_request("POST", "queries", access_token,
                body={"project_id": project_id, "query_text": text, "category": cat})
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

        if i < total - 1:
            time.sleep(1)

    progress_bar.empty()
    status_text.empty()

    msg = f"Done! {checked}/{total} queries checked."
    if failures:
        msg += f" {failures} failed."
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
    st.title("Search Intelligence Suite")
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
                        workspace = ensure_workspace(response.user, token)
                        if workspace:
                            st.session_state.workspace = workspace
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
        if st.button("Logout"):
            logout()

    # --- Show errors ---
    if st.session_state.error:
        st.error(f"Error: {st.session_state.error}")
        if st.button("Clear error"):
            st.session_state.error = None
            st.rerun()

    # --- Main area ---
    if not projects:
        st.title("Welcome to Search Intelligence Suite")
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
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            run_check = st.button("Run Citation Check")
        with col_info:
            if not PERPLEXITY_API_KEY:
                st.warning("Set PERPLEXITY_API_KEY to run checks.")

        if run_check and PERPLEXITY_API_KEY:
            active_queries = [q for q in queries if q.get("is_active", True)]
            run_citation_check(token, project["id"], project["domain"],
                active_queries, PERPLEXITY_API_KEY)
            st.rerun()

    # --- Results summary ---
    results = get_latest_results(token, project["id"])
    if results:
        # Get latest check date
        latest_date = results[0]["check_date"] if results else None
        # Filter to latest date only
        latest_results = [r for r in results if r["check_date"] == latest_date]

        # Build query_id → query_text lookup
        q_lookup = {q["id"]: q["query_text"] for q in queries}

        cited = sum(1 for r in latest_results if r["appears"])
        total = len(latest_results)
        rate = (cited / total * 100) if total > 0 else 0

        st.divider()
        st.subheader("Citation Results")
        st.markdown(f"**Last check:** {latest_date}")
        st.markdown(f"**{cited}/{total}** queries cite {project['domain']} (**{rate:.1f}%**)")

        # Results table
        table_data = []
        for r in latest_results:
            table_data.append({
                "Query": q_lookup.get(r["query_id"], "Unknown"),
                "Cited": "✓" if r["appears"] else "✗",
                "Position": r["position"] or "—",
                "Citation URL": r["citation_url"] or "",
            })
        st.dataframe(table_data, use_container_width=True, hide_index=True)

    # --- Add queries ---
    st.divider()
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
                content = uploaded.getvalue().decode("utf-8")
                reader = csv.DictReader(io.StringIO(content))
                if "query_text" not in reader.fieldnames or "category" not in reader.fieldnames:
                    st.error("CSV must have 'query_text' and 'category' columns.")
                else:
                    rows = [{"query_text": r["query_text"], "category": r["category"]}
                            for r in reader if r.get("query_text")]
                    if rows:
                        added, skipped = add_queries(token, project["id"], rows)
                        msg = f"Added {added} queries."
                        if skipped:
                            msg += f" {skipped} duplicates skipped."
                        st.success(msg)
                    else:
                        st.warning("CSV had no valid rows.")
            except Exception as e:
                st.error(f"CSV parsing error: {e}")

    # --- Query list ---
    if queries:
        st.divider()
        st.subheader("Queries")
        for q in queries:
            col1, col2, col3 = st.columns([4, 2, 1])
            col1.text(q["query_text"])
            col2.text(q["category"])
            if col3.button("Delete", key=f"del_{q['id']}"):
                if delete_query(token, q["id"]):
                    st.rerun()


# --- Main ---

def main():
    init_session_state()

    if st.session_state.user and st.session_state.workspace:
        show_dashboard()
    else:
        show_auth_page()


if __name__ == "__main__":
    main()
