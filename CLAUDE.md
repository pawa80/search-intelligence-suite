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
- **JWT auto-refresh on 401**: All DB functions (`db_request`, `db_upsert`, `rpc_request`, plus module-local helpers in `aeo/aeo_ui.py`, `aeo/context_builder.py`, `crawler/ai_analyser.py`) catch 401 responses, call `supabase.auth.refresh_session()`, update `st.session_state.access_token`, and retry once. Prevents failures after long-running operations (AI generation, batch analysis) where the 1-hour JWT may expire mid-session.

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
- `pages` (id, project_id, url, canonical_url, status_code, title, h1, meta_description, word_count, depth, in_sitemap, last_crawled_at, created_at) — UPSERT on (project_id, url). Written by crawler after crawl completes.
- `google_connections` (id, workspace_id, user_id, google_refresh_token, google_token_expiry, gsc_property, ga4_property_id, ga4_property_name, connected_at) — UNIQUE on (workspace_id, user_id). RLS via `user_id = auth.uid()`.
- `gsc_data` (id, project_id, url, clicks, impressions, ctr, position, date_range_start, date_range_end, fetched_at, page_id FK→pages) — UPSERT on (project_id, url, date_range_start). RLS via `user_owns_project()`.
- `ga_data` (id, project_id, page_path, sessions, engaged_sessions, engagement_rate, avg_engagement_time, bounce_rate, date_range_start, date_range_end, fetched_at, page_id FK→pages) — UPSERT on (project_id, page_path, date_range_start). RLS via `user_owns_project()`.
- `crawl_ai_analysis` (id, page_id FK→pages, project_id FK→projects, seo_score 0-100, aeo_readiness_score 0-100, content_quality_score 0-100, issues JSONB, priority_action, action_plan, ai_model, analysed_at, created_at) — UNIQUE on (page_id). RLS via `user_owns_project()`.
- `arbeidspakker` (id, page_id FK→pages, project_id FK→projects, url, intent, arbeidspakke_markdown, context_snapshot JSONB, generated_at) — RLS via `user_owns_project()`.

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
- `pages` INSERT/SELECT/UPDATE/DELETE: `user_owns_project(project_id)` (SECURITY DEFINER)
- `google_connections` SELECT/INSERT/UPDATE/DELETE: `user_id = auth.uid()` (direct)
- `gsc_data` SELECT/INSERT/UPDATE/DELETE: `user_owns_project(project_id)` (SECURITY DEFINER)
- `ga_data` SELECT/INSERT/UPDATE/DELETE: `user_owns_project(project_id)` (SECURITY DEFINER)
- `crawl_ai_analysis` ALL: `user_owns_project(project_id)` (SECURITY DEFINER)
- `arbeidspakker` ALL: `user_owns_project(project_id)` (SECURITY DEFINER)

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
- **Section 5**: Dashboard visualisations — top metrics (citation rate, last check, avg position via `st.metric`), category breakdown table (sorted by rate), authority set analysis (top 15 source domains from raw_sources), uncited queries list, trend chart (`st.line_chart` when multiple check dates exist). Query management moved to expander. Zero new dependencies — uses stdlib Counter, urlparse, and built-in Streamlit charts.
- **Web Crawler**: SEMrush-style SEO crawler + sitemap checker. Standalone module (`crawler/`), accessible via sidebar tool selector. See Crawler section below.
- **Data Sources (M2)**: GSC + GA4 data import with URL matching. Module (`google_data/`), accessible via sidebar tool selector. See Data Sources section below.
- **AI Analysis (M3)**: Per-page AI assessment (SEO, AEO, content quality). Tab inside Web Crawler tool. See AI Analysis section below.
- **AEO Agent (M4)**: Integrated AEO audit with matrix context from suite data. Sidebar tool. See AEO Agent section below.

## Next Up
- **Matrise**: Prioritisation view — ranks pages by score, shows where to focus effort
- **Morten test**: GSC + GA4 import with real data (Morten's Gmail needs adding as Google OAuth test user in Google Cloud Console)
- **AEO Agent E2E test**: Generate arbeidspakke on a real crawled page, verify it saves to `arbeidspakker` table and displays correctly
- **Section 6**: Data import (historical GEO Tracker data migration)
- **Section 7**: Mobile optimisation
- Investigate the 7 failed queries (likely Perplexity API timeouts on longer queries — consider retry logic)
- Remove "Test (3 queries)" button once stable (or keep as dev convenience)
- Set up custom SMTP (Resend) for email confirmation when approaching real users

## Notes for Product Director
- **M2-M4 all deployed** (commit 162e273). Streamlit Cloud auto-deploys from master.
- **GSC/GA4 untested with real data** — Pal has no active GSC properties. Morten needs to test. His Gmail must be added as a test user in Google Cloud Console OAuth consent screen first.
- **AEO Agent depends on OPENAI_API_KEY** — added to Streamlit Cloud secrets ✓
- **`aeo/` had embedded .git** from standalone repo — removed before commit. Standalone-only files (app.py, README, .streamlit, etc.) left unstaged intentionally.
- **sys.path poisoning risk**: `aeo/app.py` still exists on disk (unstaged). If anyone adds `aeo/` to sys.path without the temporary add/remove pattern, `from app import` breaks globally. Long-term fix: rename or delete `aeo/app.py` (the standalone entry point) since the suite uses `aeo/aeo_ui.py` instead.
- **`requests` package**: Used by `aeo/analyzer.py` but not in requirements.txt. Works because it's a transitive dep of streamlit. Could add explicitly if it ever breaks on Cloud.

## RLS Debugging Pattern (for future reference)
When adding new tables that reference `projects` or `workspaces`:
1. **Never** use inline subqueries in RLS policies that hit other RLS-protected tables
2. **Always** create a SECURITY DEFINER function that does the full ownership chain check internally
3. Pattern: `user_owns_project(project_id)` joins projects→workspace_members, bypasses RLS
4. The nested RLS problem: policy subquery on `projects` triggers `projects` RLS, which may trigger further RLS → silent failures or recursion

## Streamlit Cloud Gotchas

### Python Version
- Streamlit Cloud runs **Python 3.9** — does NOT support `int | None` or `dict | None` syntax
- **Always** add `from __future__ import annotations` at top of every new Python file
- Local dev uses Python 3.12 (uv-managed) so this won't surface locally

### Secrets
- Secrets must be valid TOML: `KEY = "value"` with quotes
- Pasting can introduce invisible characters or strip hyphens — always verify the key manually
- The Perplexity key has a hyphen: `pplx-` (was stripped during paste, caused 401)

## Web Crawler Module

### Architecture
- **Location**: `crawler/` package — `crawler_engine.py`, `sitemap_parser.py`, `crawler_ui.py`
- **Access**: Sidebar tool selector in `app.py` ("Rank Tracker" / "Web Crawler")
- **Supabase persistence**: Crawl results UPSERT to `pages` table via raw httpx + JWT (same pattern as `geo_check_results`). Requires project selected.
- **Dependencies added**: `beautifulsoup4`, `pandas`, `truststore` (OS cert store for Windows dev)

### Web Crawl Tab (SEMrush-style SEO crawler)
- **Modes**: "Crawl from URL" (BFS link discovery) or "Check URL list" (paste URLs)
- **Crawl behaviour**: Start from URL → discover links → follow them → repeat to max depth
- **Sitemap cross-reference**: Fetches `/sitemap.xml` in background before crawl, marks each discovered URL "In Sitemap: Yes/No". Sitemap does NOT guide what gets crawled.
- **15 columns per URL**: URL, Title, Status, Depth, Referrer, Time, Meta Desc, OG Desc, H1, H2, Hero Alt, Canonical, OG URL, In Sitemap, JSON-LD
- **Defaults**: max depth 10, max pages 20 (up to 2000), skip duplicates on
- **Delay**: 0.5s between requests, 10s timeout, custom User-Agent

### Sitemap Check Tab
- **Input**: Domain or URL (auto-appends `/sitemap.xml`)
- **Handles**: Sitemap index files (nested sitemaps)
- **Always checks HTTP status** for each URL (with progress)
- **Columns**: URL, Status, Last Modified, Change Freq, Priority

### Export
- CSV download with domain-name + date filename
- Copy to clipboard (TSV format)
- URL filter on results

### Original Reference
- `_reference/crawler-v5.06.html` — original Perplexity/Decodo HTML crawler
- Original uses Decodo scraper API as proxy — our version uses direct httpx
- Some sites with anti-bot protection may block direct requests

### Safety Tag
- `v1.0-pre-crawler` on commit `001680a` — state before crawler was added

## Data Sources Module (M2)

### Architecture
- **Location**: `google_data/` package — `oauth.py`, `gsc_client.py`, `ga4_client.py`, `url_matcher.py`, `datasources_ui.py`
- **Access**: Sidebar tool selector in `app.py` ("Rank Tracker" / "Web Crawler" / "Data Sources")
- **Google OAuth**: Raw httpx (no PKCE) — `google_auth_oauthlib.Flow` caused PKCE code_verifier issues with Streamlit's redirect lifecycle
- **Dependencies added**: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`, `google-analytics-data`

### OAuth Flow
1. User clicks "Connect Google Account" → raw Google consent URL (no PKCE)
2. Google redirects back with `?code=&state=` → `handle_oauth_callback_if_present()` exchanges code via raw httpx POST
3. Refresh token saved to `google_connections` table → used for all subsequent API calls
4. CSRF: HMAC-signed state param encoding workspace_id + nonce
5. `prompt=consent` guarantees refresh token on every connect

### GSC Client
- `list_gsc_properties()` — `searchconsole.sites.list()` via `google-api-python-client`
- `fetch_gsc_data()` — `searchanalytics.query`, dimensions=["page"], rowLimit=5000

### GA4 Client
- `list_ga4_properties()` — tries gRPC (`AnalyticsAdminServiceClient`), falls back to REST
- `fetch_ga4_data()` — tries gRPC (`BetaAnalyticsDataClient`), falls back to REST
- Fallback needed because gRPC can fail on Streamlit Cloud

### URL Matcher
- `normalise_url()` — same logic as `crawler_engine.normalise_url()` (https-force, strip trailing slash, lowercase netloc)
- `build_pages_lookup()` — dict of normalised URL → page_id from `pages` table
- `match_url_to_page()` — exact match after normalisation; GA4 paths prepend project domain
- On import, `page_id` is set on each row. "Re-run URL Matching" button available in Match Status tab.

### Google Cloud Setup
- Project in Google Cloud Console with Search Console API, Analytics Data API, Analytics Admin API enabled
- OAuth consent screen: External, Testing mode — test users must be manually added
- Secrets: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
- Redirect URIs: `http://localhost:8501` (local), Streamlit Cloud URL (prod)
- `.env` format: no quotes, no spaces around `=`, single `GOOGLE_REDIRECT_URI` (local vs prod)

### Migrations
- `migrations/001_google_connections.sql`, `002_gsc_data.sql`, `003_ga_data.sql`
- All run and verified in Supabase SQL editor

### Tested
- OAuth round-trip: consent → redirect → token exchange → saved to Supabase ✓
- GSC property listing ✓ (Pal's Norwegian site appeared)
- GA4 property listing ✓
- GSC/GA4 import: no data returned (Pal's sites have no traffic) — awaiting Morten test

### Gotchas
- `google_auth_oauthlib.Flow` adds PKCE automatically; code_verifier lost on Streamlit redirect → use raw httpx instead
- Google `expires_in` is seconds (e.g. 3599), not a timestamp — must convert before saving to TIMESTAMPTZ column
- `.env` quotes around values are included literally by `python-dotenv` — don't use quotes
- Duplicate `GOOGLE_REDIRECT_URI` in `.env`: last one wins but can cause confusion

## AI Analysis Module (M3)

### Architecture
- **Location**: `crawler/ai_analyser.py` (engine) + "AI Analysis" tab in `crawler/crawler_ui.py`
- **Access**: Web Crawler tool → AI Analysis tab
- **Model**: Perplexity API (`llama-3.1-sonar-small-128k-online`) via raw httpx
- **No new dependencies** — uses existing httpx + PERPLEXITY_API_KEY

### What It Does
- Reads crawled page data from `pages` table (title, H1, H2, meta desc, word count, status code, canonical, sitemap, JSON-LD, depth)
- Sends each page to Perplexity with structured prompt → returns JSON with 3 scores + issues + action plan
- Scores: `seo_score` (technical SEO), `aeo_readiness_score` (answer engine readiness), `content_quality_score` (content signals)
- Issues: JSONB array of `{type, severity (high/medium/low), description}`
- UPSERT to `crawl_ai_analysis` on `page_id` conflict

### UI
- Stats: total crawled pages, already analysed, not yet analysed
- Two buttons: "Run AI Analysis on Unanalysed Pages" (only missing) / "Re-analyse All Pages" (upserts all)
- Progress bar with per-page status during batch
- Summary metrics: avg SEO/AEO/content scores, pages needing attention (any score < 50)
- Results table: sorted worst-first, colour-coded badges (🔴 < 50, 🟡 50-74, 🟢 75+)
- Expandable per-page detail: scores, priority action, action plan, full issues list with severity icons

### Migration
- `migrations/004_crawl_ai_analysis.sql` — run in Supabase SQL editor

### What M3 Does NOT Do
- No Matrise (prioritisation view) — separate module
- No per-issue fix recommendations — that's M4
- No auto-trigger on crawl complete
- No competitor comparison

## AEO Agent Module (M4)

### Architecture
- **Location**: `aeo/` package — `analyzer.py`, `recommender.py`, `intelligence_feed.py`, `context_builder.py`, `aeo_ui.py`
- **Access**: Sidebar tool selector in `app.py` ("AEO Agent")
- **Models**: OpenAI GPT-4o-mini (recommendations), page content extraction via BeautifulSoup
- **Dependencies**: `openai`, `lxml` (with `html.parser` fallback)
- **Origin**: Adapted from standalone AEO Audit Agent (PRCS008) into suite context

### What It Does
- Selects a crawled page (dropdown from `pages` table) or manual URL
- Shows page intelligence panel: crawl AI scores (SEO/AEO/content), GSC data (clicks/impressions/position/CTR), GA4 data (sessions/engagement)
- User sets page intent (what the page should achieve)
- Generates "arbeidspakke" (work package) — AI audit report with:
  - Summary, critical issues, prioritised action plan with before/after text, quick wins
  - Intelligence evaluation checklist (trend alerts, counter-signals, citation patterns)
  - Each recommendation cites its intelligence source
- Saves arbeidspakke to `arbeidspakker` table in Supabase
- Previous arbeidspakker viewable in expandable history

### Matrix Context (`context_builder.py`)
- `build_page_context()` — fetches `crawl_ai_analysis`, `gsc_data`, `ga_data` for a page via raw httpx
- `build_context_block()` — formats into prompt-ready markdown injected before page content in GPT prompt
- Graceful degradation: works with partial data (no GSC = "No GSC data available")

### sys.path Poisoning Fix
- `aeo/` contains `app.py` (from standalone agent) — adding `aeo/` to sys.path causes ALL `from app import` to resolve to `aeo/app.py` instead of root `app.py`
- **Fix**: `aeo_ui.py` temporarily adds `aeo/` to sys.path for imports, then immediately removes it
- `aeo_ui.py` uses its own `_db_get()` / `_db_post()` helpers (raw httpx) to avoid `from app import` entirely

### Migration
- `migrations/005_aeo_scores_and_arbeidspakker.sql` — `arbeidspakker` table + RLS policies

### Tables
- `arbeidspakker` (id, page_id FK→pages, project_id FK→projects, url, intent, arbeidspakke_markdown, context_snapshot JSONB, generated_at) — RLS via `user_owns_project()`

## Rolling Handover
Last session: Mar 5 2026 (M2 + M3 + M4 build)

### Mar 5 2026 — M4: AEO Agent Integration
- Adapted standalone AEO Audit Agent into suite context
- New files: `aeo/context_builder.py` (matrix context assembly), `aeo/aeo_ui.py` (Streamlit UI)
- Modified: `aeo/recommender.py` (added `context_block` param), `aeo/analyzer.py` (lxml fallback to html.parser)
- `aeo_ui.py` uses own `_db_get()`/`_db_post()` helpers to avoid sys.path poisoning from `from app import`
- sys.path fix: temporarily add `aeo/` for imports, then remove (prevents `aeo/app.py` shadowing root `app.py`)
- Migration `005_aeo_scores_and_arbeidspakker.sql` created — needs running in Supabase SQL editor
- Added `openai`, `lxml` to requirements.txt
- Added "AEO Agent" to sidebar tool selector in `app.py`
- Dependencies: `OPENAI_API_KEY` must be in Streamlit Cloud secrets for production
- **Tested locally**: page selector, intelligence panel, intent input work. Arbeidspakke generation needs lxml fix verification.
- **Next**: Restart app to verify lxml fix, test full arbeidspakke generation end-to-end, commit + push

### Mar 5 2026 — M3: AI Analysis per Crawled URL
- Built `crawler/ai_analyser.py`: Perplexity API calls, JSON parsing, UPSERT to `crawl_ai_analysis`
- Added "AI Analysis" tab to `crawler/crawler_ui.py`: batch processing, progress bar, summary metrics, results table with score badges, expandable per-page detail
- Migration `004_crawl_ai_analysis.sql` created and run in Supabase
- Scores: seo_score, aeo_readiness_score, content_quality_score (all 0-100)
- Issues stored as JSONB with type/severity/description
- 1s delay between API calls for rate limiting
- **Tested locally**: Pal ran analysis on crawled pages, results saved to Supabase
- **Next**: M4 (fix recommendations), Matrise (prioritisation view)

### Mar 5 2026 — M2: GSC + GA4 Data Sources (1 session)
- Built full `google_data/` module: OAuth, GSC client, GA4 client, URL matcher, Streamlit UI
- 6 new files, 3 SQL migrations, 4 new dependencies
- OAuth flow: raw httpx (bypassed `Flow` PKCE issues), HMAC-signed CSRF state
- Fixed `expires_in` → TIMESTAMPTZ conversion bug (Google returns seconds, not timestamp)
- Tested locally: full OAuth round-trip working, property dropdowns populated
- GSC/GA4 import untested with real data — Pal's sites have no traffic, awaiting Morten
- Commit `5f63799`, pushed to master, auto-deployed
- Streamlit Cloud secrets added, Supabase migrations run
- **Pal's `pwaagbo@gmail.com` account**: password issue, can't log in. Used `ambiguous80@gmail.com` for testing. Needs password reset.
- **For Morten**: Add his Gmail as Google OAuth test user in Cloud Console before he can connect
- **Next**: Morten tests with real GSC/GA4 data, then URL matching verification

### Mar 4 2026 — Web Crawler module (1 session)
- Built full `crawler/` package from scratch based on original `crawler-v5.06.html` reference
- 3 files: `crawler_engine.py` (CrawlerEngine BFS + SEO extraction), `sitemap_parser.py` (XML parse + status check), `crawler_ui.py` (Streamlit UI)
- Modified `app.py`: sidebar tool selector, import + routing to crawler
- Added `beautifulsoup4`, `pandas`, `truststore` to requirements.txt
- **SSL fix**: uv-managed Python 3.12 on Windows lacks CA bundle — `truststore` injects OS cert store
- **v1 had 6 columns** — upgraded to **15 columns** matching original (meta desc, OG desc, H1, H2, hero alt, canonical, OG URL, JSON-LD, in-sitemap)
- Sitemap cross-reference: fetched before crawl, used as lookup only (not crawl guide)
- Default max depth changed from 2 → 10 (SEMrush-style)
- Sitemap tab: accepts domain, auto-finds /sitemap.xml, always checks HTTP status
- Safety tag `v1.0-pre-crawler` on commit `001680a`
- Commits: 3cf06ee, 909d23f, 5babb4c — all pushed to master, auto-deployed
- **Tested locally**: sitemaps.org crawl (SEO data + sitemap cross-ref working), sitemap parse (84 URLs)
- **Not tested on Streamlit Cloud yet** — Pal to verify after deploy
- **Known limitation**: Direct httpx (no proxy) — some anti-bot sites may block. Original used Decodo scraper API.
- **Next**: Test on Streamlit Cloud, consider Decodo API integration for blocked sites, Phase 2 Supabase persistence

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

### Feb 16 2026 — Section 5 Dashboard (session 3)
- Replaced basic results table with full dashboard: top metrics, category breakdown, authority set, uncited queries, trend chart
- Added `Counter` + `urlparse` imports (stdlib only, zero new deps)
- Query management (add/delete) moved into `st.expander("Manage Queries")`
- Trend chart uses `st.line_chart()` — only renders when multiple check dates exist
- Authority set parses `raw_sources` JSON, extracts netloc, shows top 15 domains
- **RLS BUG FIXED (session 4)**: Root cause was duplicate policies (old broken ones with inline subqueries never removed) + missing UPDATE policy for UPSERT conflict path. Fix: dropped all 4 duplicate policies via DO block, recreated 3 clean policies (`geo_results_insert`, `geo_results_select`, `geo_results_update`) all using `user_owns_project()` SECURITY DEFINER.
- **COMMITTED AND DEPLOYED** — commit 001680a, auto-deployed to Streamlit Cloud. Full 153-query citation check passed.
- **Next**: Section 6 (data import)
