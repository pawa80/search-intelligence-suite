# Search Intelligence Suite

## Project Overview
Suite of AI search optimisation tools. Starting with GEO Tracker migration into shared workspace model.
Pal + Morten collaboration.

## Stack
- **App**: Python + Streamlit
- **Auth**: Supabase Auth (email/password)
- **Database**: Supabase PostgreSQL (project: `dxduneaizaxnynsmsvbx`)
- **Hosting**: Streamlit Cloud (auto-deploys from GitHub `master`)
- **Repo**: github.com/pawa80/search-intelligence-suite (private)
- **Live**: https://search-intelligence-suite-a3uaskapg7vwmh9ipxcgp4.streamlit.app/

## Architecture Decisions

### Auth & DB Access Pattern
- **Supabase client** (`create_client`) used ONLY for auth operations (sign_up, sign_in)
- **Raw httpx** used for ALL table operations — sends JWT directly in Authorization header
- **SECURITY DEFINER RPC** for workspace creation (`create_workspace_for_user`) — bypasses RLS
- **Reason**: supabase-py's PostgREST client doesn't reliably propagate the JWT after auth. Raw REST calls are deterministic.

### RLS Lessons (Critical)
- `user_in_workspace()` function was SECURITY INVOKER → caused infinite recursion when called from RLS policies on tables it queries
- **Fixed**: Made `user_in_workspace()` SECURITY DEFINER so it bypasses RLS internally
- `workspace_members` SELECT policy changed to `user_id = auth.uid()` (direct, no function call)
- `workspaces` SELECT policy changed to `created_by = auth.uid()` (direct, no function call)
- **Rule**: Never use SECURITY INVOKER functions in RLS policies that query the same table the policy protects

### Secrets
- Streamlit Cloud: secrets in dashboard (Settings > Secrets)
- Local: `.env` file (gitignored)
- App reads from `st.secrets` first, falls back to `os.getenv()`

## Database

### Tables (all RLS enabled)
- `workspaces` (id, name, created_by, created_at)
- `workspace_members` (workspace_id, user_id, role, joined_at)
- `projects` (exists, not yet used)
- `queries` (exists, not yet used)
- `geo_check_results` (exists, not yet used)

### RPC Functions
- `create_workspace_for_user(ws_name text, ws_user_id uuid)` — SECURITY DEFINER, creates workspace + membership atomically
- `user_in_workspace(ws_id uuid)` — SECURITY DEFINER, checks if auth.uid() is member of workspace

### RLS Policies
- `workspaces` INSERT: `created_by = auth.uid()`
- `workspaces` SELECT: `created_by = auth.uid()`
- `workspaces` UPDATE: `user_in_workspace(id)` (SECURITY DEFINER, safe)
- `workspace_members` INSERT: `user_id = auth.uid()`
- `workspace_members` SELECT: `user_id = auth.uid()`

## Python Environment
- **uv** for package management (installed via `python -m pip install uv`)
- `.venv` with Python 3.12 (uv-managed, since system Python 3.14 is too new for supabase package)
- `supabase` pinned to `<2.10.0` (newer versions pull in pyiceberg which fails to build)
- Run locally: `.venv\Scripts\streamlit run app.py`

## Email Confirmation
- Currently **disabled** in Supabase (Authentication > Providers > Email)
- Built-in Supabase email has hard rate limit (2/hour) regardless of plan
- To re-enable: need custom SMTP provider (e.g. Resend.com — free tier 3k/month)
- App code handles both flows (auto-login if no confirmation, success message if confirmation required)

## Completed
- **Section 2**: Auth flow — signup, login, auto-workspace creation, logout, re-login finds existing workspace

## Next Up
- **Section 3**: Project creation + query management within workspaces
- Restore original `user_in_workspace` RLS policies once we confirm they work with SECURITY DEFINER
- Set up custom SMTP (Resend) for email confirmation when approaching real users
- Investigate why direct table INSERT via REST API fails RLS despite valid JWT (the `WITH CHECK (true)` test still failed — may be a Supabase/PostgREST config issue worth a support ticket)

## Rolling Handover
Last session: Feb 16 2026

### Feb 16 2026 — Section 2 Auth
- Built Streamlit app with Supabase Auth
- Fought RLS issues extensively — supabase-py doesn't propagate JWT to PostgREST client
- Solved with raw httpx for table ops + SECURITY DEFINER RPC for workspace creation
- Fixed recursive RLS (`user_in_workspace` made SECURITY DEFINER, direct policies on workspace_members)
- 13 commits, all deployed via Streamlit Cloud
- Test user: pwaagbo@gmail.com (workspace created, login/logout verified)
