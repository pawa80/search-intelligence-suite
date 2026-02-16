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

### RPC Functions (additional)
- `user_owns_project(p_id uuid)` — SECURITY DEFINER, checks project→workspace→member chain in one call. Used by `geo_check_results` RLS policies to avoid nested RLS subquery issues.

### RLS Policies
- `workspaces` INSERT: `created_by = auth.uid()`
- `workspaces` SELECT: `created_by = auth.uid()`
- `workspaces` UPDATE: `user_in_workspace(id)` (SECURITY DEFINER, safe)
- `workspace_members` INSERT: `user_id = auth.uid()`
- `workspace_members` SELECT: `user_id = auth.uid()`
- `geo_check_results` INSERT: `user_owns_project(project_id)` (SECURITY DEFINER)
- `geo_check_results` SELECT: `user_owns_project(project_id)` (SECURITY DEFINER)

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
- **Section 4**: Citation engine — Perplexity API integration, batch check with progress bar, PostgREST UPSERT, results display with citation rate. **TESTED AND WORKING** — 142/149 queries checked (7 failed, likely API timeouts). Results persist and display correctly.

## Next Up
- **Section 5**: Dashboard visualisations (trend charts, citation rate over time)
- **Section 6**: Data import (historical GEO Tracker data migration)
- **Section 7**: Mobile optimisation
- Investigate the 7 failed queries (likely Perplexity API timeouts on longer queries — consider retry logic)
- Remove "Test (3 queries)" button once stable (or keep as dev convenience)
- Set up custom SMTP (Resend) for email confirmation when approaching real users

## RLS Debugging Pattern (for future reference)
When adding new tables that reference `projects` or `workspaces`:
1. **Never** use inline subqueries in RLS policies that hit other RLS-protected tables
2. **Always** create a SECURITY DEFINER function that does the full ownership chain check internally
3. Pattern: `user_owns_project(project_id)` joins projects→workspace_members, bypasses RLS
4. The nested RLS problem: policy subquery on `projects` triggers `projects` RLS, which may trigger further RLS → silent failures or recursion

## Streamlit Cloud Secrets Gotcha
- Secrets must be valid TOML: `KEY = "value"` with quotes
- Pasting can introduce invisible characters or strip hyphens — always verify the key manually
- The Perplexity key has a hyphen: `pplx-` (was stripped during paste, caused 401)

## Rolling Handover
Last session: Feb 16 2026

### Feb 16 2026 — Sections 2-4 (2 sessions)
**Session 1** (earlier):
- Built Sections 2-4 from scratch: auth, project/query CRUD, citation engine
- Fought RLS extensively — solved with raw httpx + SECURITY DEFINER RPC
- ~15 commits total

**Session 2** (this session — continuation after context ran out):
- Committed + pushed Section 4 citation engine code (commit 1e55ee2)
- Fixed `geo_check_results` RLS — policies had nested subquery on `projects` table (RLS-protected), causing silent INSERT failures
- Created `user_owns_project()` SECURITY DEFINER function — checks project→workspace→member chain in one call
- Replaced both INSERT and SELECT policies on `geo_check_results` to use `user_owns_project(project_id)`
- Fixed Perplexity API 401 — key was missing hyphen in Streamlit Cloud secrets (paste issue)
- Added "Test (3 queries)" button + visible error messages for debugging
- Removed `st.rerun()` after citation check so errors stay visible
- **Final result**: 142/149 queries checked successfully, 7 failed (likely API timeouts). Results persist and display.
- Commits: 1e55ee2, 0e71a54, 704abdf, d7b2bae
- Test user: pwaagbo@gmail.com (workspace created, login/logout verified)
