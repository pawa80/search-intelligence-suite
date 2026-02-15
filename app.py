import streamlit as st
from supabase import create_client
import httpx
import os
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

# Unauthenticated client for auth operations only
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

st.set_page_config(page_title="Search Intelligence Suite", page_icon="🔍", layout="wide")


def init_session_state():
    for key in ["user", "workspace", "access_token", "error"]:
        if key not in st.session_state:
            st.session_state[key] = None


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
    else:
        raise ValueError(f"Unsupported method: {method}")

    if r.status_code >= 400:
        raise Exception(f"DB {method} {table}: {r.status_code} {r.text}")
    return r.json()


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
        # Check existing workspace membership
        rows = db_request("GET", "workspace_members", access_token,
            params={"select": "workspace_id,workspaces(id,name)", "user_id": f"eq.{user_id}"})

        if rows and len(rows) > 0:
            ws = rows[0]["workspaces"]
            return {"id": ws["id"], "name": ws["name"]}

        # No workspace — create one
        ws_name = f"{email}'s Workspace"
        ws_rows = db_request("POST", "workspaces", access_token,
            body={"name": ws_name, "created_by": user_id})

        workspace_id = ws_rows[0]["id"]

        # Add user as owner
        db_request("POST", "workspace_members", access_token,
            body={"workspace_id": workspace_id, "user_id": user_id, "role": "owner"})

        return {"id": workspace_id, "name": ws_name}

    except Exception as e:
        # Decode JWT to show what auth.uid() resolves to
        import json, base64
        try:
            payload = access_token.split(".")[1]
            payload += "=" * (4 - len(payload) % 4)  # pad base64
            decoded = json.loads(base64.b64decode(payload))
            jwt_sub = decoded.get("sub", "MISSING")
        except Exception:
            jwt_sub = "DECODE_FAILED"
        st.session_state.error = (
            f"{e}\n\n"
            f"DEBUG — user_id we sent: {user_id}\n"
            f"DEBUG — JWT sub (auth.uid): {jwt_sub}\n"
            f"DEBUG — match: {user_id == jwt_sub}"
        )
        return None


def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.workspace = None
    st.session_state.access_token = None
    st.session_state.error = None
    st.rerun()


def show_auth_page():
    st.title("Search Intelligence Suite")
    st.markdown("AI-powered search optimisation tools")

    # Show persistent error if any
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


def show_dashboard():
    workspace = st.session_state.workspace
    user = st.session_state.user

    with st.sidebar:
        st.markdown(f"**{workspace['name']}**")
        st.caption(user.email)
        if st.button("Logout"):
            logout()

    st.title("Welcome to Search Intelligence Suite")
    st.markdown(f"**Workspace:** {workspace['name']}")
    st.info("No projects yet — create your first project to start tracking.")


def main():
    init_session_state()

    if st.session_state.user and st.session_state.workspace:
        show_dashboard()
    else:
        show_auth_page()


if __name__ == "__main__":
    main()
