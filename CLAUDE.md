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
- `projects` (id, workspace_id, name, domain, created_at) — RLS via workspace membership
- `queries` (id, project_id, query_text, created_at) — RLS via project→workspace chain
- `geo_check_results` (id, query_id, project_id, check_date, appears, position, citation_url, engine, raw_sources) — UPSERT on (query_id, engine, check_date)

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
- **Section 3**: Project + query management — CRUD for projects, single/bulk/CSV query add, delete queries
- **Section 4**: Citation engine — Perplexity API integration, batch check with progress bar, PostgREST UPSERT, results display with citation rate

## Next Up
- **Section 4 testing**: Add PERPLEXITY_API_KEY to Streamlit Cloud secrets, then test citation check on WTA queries
- **Section 5**: Dashboard visualisations (trend charts, citation rate over time)
- **Section 6**: Data import (historical GEO Tracker data migration)
- **Section 7**: Mobile optimisation
- Restore original `user_in_workspace` RLS policies once we confirm they work with SECURITY DEFINER
- Set up custom SMTP (Resend) for email confirmation when approaching real users

## Rolling Handover
Last session: Feb 16 2026

### Feb 16 2026 — Sections 2-4
- **Section 2** (Auth): Built Streamlit app with Supabase Auth. Fought RLS extensively — solved with raw httpx + SECURITY DEFINER RPC. 13 commits.
- **Section 3** (Projects/Queries): CRUD for projects and queries. Single/bulk/CSV add, delete. Pre-verified against live DB. 1 commit.
- **Section 4** (Citation Engine): Perplexity API `sonar` model, `check_citation()` with domain matching, batch `run_citation_check()` with progress bar, `db_upsert()` for PostgREST UPSERT, results display with citation rate summary + dataframe. 1 commit (1e55ee2).
- **Pending**: PERPLEXITY_API_KEY needs adding to Streamlit Cloud secrets before testing Section 4.
- Test user: pwaagbo@gmail.com (workspace created, login/logout verified)
