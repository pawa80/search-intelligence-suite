# Search Intelligence Suite (→ Aevily)

## Open Sessions
<!-- Each active Claude Code session adds a line here at start, removes/marks closed at end. Read this block BEFORE adding your own; if another session is open, flag the overlap to your user. -->
- 🟢 **Morten's Claude** — started 2026-04-14 — activity: establishing two-Claude coordination protocol (open-session banner + CLAUDE.md push-on-update).
- 🟢 **Pal's Claude** — 2026-04-14 — activity: assessing repo privacy switch + secret scan. *(Migrated from duplicate block below on 2026-04-14.)*

> **CLAUDE.md convention (added 2026-04-12):** This file now has three sections — **Shared**, **Pal**, and **Morten**. Both developers' Claude Code instances update it every turn to preserve state. Put rules/architecture/project direction under Shared; machine- or developer-specific context under the respective personal section. When editing, do not place personal context in the other developer's section. Existing content below is currently under **Pal** until jointly migrated.
>
> **Two-Claude protocol (added 2026-04-14):** (1) Maintain the **Open Sessions** block above — add a line at session start, flag overlap if another session is open, remove/close at session end. (2) **Push CLAUDE.md to GitHub `master` on every update** with a `docs:` commit prefix. Auto-deploy to Streamlit Cloud is an accepted side-effect.

---

## Shared

### Developers
- **Pal** — original author; works from his local machine, pushes to GitHub `master` (default branch).
- **Morten** — co-developer (joined 2026-04-12); works from `C:\mortenai\projects\search-intelligence-suite`; focuses on design/direction and now code.

### Rules of engagement
- Canonical repo: `github.com/pawa80/search-intelligence-suite` (default branch: `master`, not `main`).
- Each session: check local vs GitHub `master`, pull diffs before working.
- Update this CLAUDE.md every input→output cycle to retain state.
- Rename in progress: "Search Intelligence Suite" → **Aevily** (merges AEO citation tracker + page agent).

### Active branches (as of 2026-04-12)
- `master` — mainline
- `dev/2026-04-02`, `dev/2026-04-02-colour` — Pal's dev branches

---

## Morten

### Environment
- Local path: `C:\mortenai\projects\search-intelligence-suite`
- Platform: Windows 11, bash shell
- Cloned fresh from GitHub on 2026-04-12.

### Session log
- **2026-04-12** — First session. Cloned repo, established CLAUDE.md three-section convention. Not yet touched code.
- **2026-04-12** — Confirmed Streamlit deployment context is sufficient for now (auto-deploy from master, Py 3.9, secrets in Cloud dashboard). Intentionally not pursuing dashboard access or Pal's global CLAUDE.md deployment catalogue.
- **2026-04-13** — Produced a self-contained briefing of Domain Strategy Layer v4.0 for Morten to paste into Claude.ai (purpose, flow, storage, injection points, v5.0 hardening). No code changes.
- **2026-04-14** — Established two-Claude coordination protocol: Open Sessions banner at top of CLAUDE.md, per-turn push to GitHub `master` with `docs:` prefix. First push surfaced parallel work — Pal's Claude had independently added its own Open Sessions block (now merged). Active Pal session: repo privacy switch + secret scan — flagged to Morten, no direct overlap in work area.

---

## Pal

*(Existing CLAUDE.md content below — authored by Pal, kept intact. Shared rules will migrate up over time.)*

## ⚠️ MULTI-DEVELOPER PROJECT — ALWAYS PULL BEFORE STARTING
Pal and Morten both work on this repo from different machines. **Every session MUST start by checking for remote changes:**
```bash
git fetch origin && git status
```
If local is behind origin/master, pull before doing anything:
```bash
git pull origin master
```
This prevents merge conflicts and wasted work on stale code. **Do not skip this step.**

## Cross-Project Dependencies (maintained by COO, pal-ops)
- **SHARED SUPABASE**: This project uses Supabase project `dxduneaizaxnynsmsvbx`, which is ALSO used by GEO Tracker (gen-seo-tracker) and AEO Audit Agent. All three apps read/write to the same PostgreSQL instance. Do NOT make schema changes without checking with COO (pal-ops chat) first.
- **AEO Agent module**: The `aeo/` folder in this project is an adapted version of the standalone AEO Audit Agent (`C:\palai3\projects\aeo-audit-agent`). Changes to AEO logic should be coordinated. The standalone agent has its own deployment on Streamlit Cloud.
- **Deployment estate**: See global CLAUDE.md (`C:\Users\Pal\.claude\CLAUDE.md`) for full catalogue of all deployments.

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
- `projects` (id, workspace_id, name, domain, created_at, domain_context, domain_strategy JSONB, domain_strategy_generated_at TIMESTAMPTZ) — RLS via workspace membership. `domain_context` is universal brand info injected into all arbeidspakker. `domain_strategy` JSONB — holistic AEO strategy with page_roles, cannibalisation, gaps, strategic_rules. Generated by Sonnet analysis of all crawled pages. Injected into every playbook prompt to differentiate recommendations per page role.
- `queries` (id, project_id, query_text, created_at) — RLS via project→workspace chain
- `geo_check_results` (id, query_id, project_id, check_date, appears, position, citation_url, engine, raw_sources) — UPSERT on (query_id, engine, check_date)
- `pages` (id, project_id, url, canonical_url, status_code, title, h1, meta_description, word_count, depth, in_sitemap, last_crawled_at, created_at, page_type, intent, status, language, page_elements JSONB) — UPSERT on (project_id, url). Written by crawler after crawl completes. `page_type` and `intent` set by AEO Agent UI. `status` TEXT NOT NULL DEFAULT 'active' — values: active, redirected, dead, archived. Pages are NEVER deleted — status is set to 'archived' instead. `language` TEXT — ISO 639-1 content language code (e.g. 'nb', 'en', 'fr'). Set by crawler or user. `page_elements` JSONB DEFAULT '{}' — structured crawl data: `h2_structure` (string[]), `og_tags` (dict), `json_ld` (array of schema objects), `hero_image_alt`, `referrer`, `crawl_time_seconds`. Persisted on every crawl. NOTE: DELETE RLS policy has been removed.
- `google_connections` (id, workspace_id, user_id, google_refresh_token, google_token_expiry, gsc_property, ga4_property_id, ga4_property_name, connected_at) — UNIQUE on (workspace_id, user_id). RLS via `user_id = auth.uid()`.
- `gsc_data` (id, project_id, url, clicks, impressions, ctr, position, date_range_start, date_range_end, fetched_at, page_id FK→pages) — UPSERT on (project_id, url, date_range_start). RLS via `user_owns_project()`.
- `ga_data` (id, project_id, page_path, sessions, engaged_sessions, engagement_rate, avg_engagement_time, bounce_rate, date_range_start, date_range_end, fetched_at, page_id FK→pages) — UPSERT on (project_id, page_path, date_range_start). RLS via `user_owns_project()`.
- `crawl_ai_analysis` (id, page_id FK→pages, project_id FK→projects, seo_score 0-100, aeo_readiness_score 0-100, content_quality_score 0-100, issues JSONB, priority_action, action_plan, ai_model, analysed_at, created_at) — UNIQUE on (page_id). RLS via `user_owns_project()`.
- `arbeidspakker` (id, page_id FK→pages, project_id FK→projects, url, intent, arbeidspakke_markdown, context_snapshot JSONB, generated_at, language) — RLS via `user_owns_project()`. `language` TEXT — the language the playbook was generated in. Matches page language at generation time.
- `page_url_history` (id, page_id FK→pages, url, status, detected_at, transition_type, created_at) — URL identity graph. Append-only. Records URL transitions (301s, 404s, merges). RLS via `user_owns_project()` through page→project chain. No UPDATE or DELETE policies.

### RPC Functions
- `create_workspace_for_user(ws_name text, ws_user_id uuid)` — SECURITY DEFINER, creates workspace + membership atomically
- `user_in_workspace(ws_id uuid)` — SECURITY DEFINER, checks if auth.uid() is member of workspace

### RPC Functions (additional)
- `user_owns_project(p_id uuid)` — SECURITY DEFINER, checks project→workspace→member chain in one call. Used by `geo_check_results` RLS policies to avoid nested RLS subquery issues.

### Tables (continued)
- `usage_events` (id, user_id, project_id FK→projects, event_type, event_detail, api_provider, model, input_tokens, output_tokens, estimated_cost_usd, created_at) — RLS: INSERT `user_id = auth.uid()`, SELECT `user_id = auth.uid()`. Fire-and-forget tracking for all API calls and app analytics.

### RLS Policies
- `workspaces` INSERT: `created_by = auth.uid()`
- `workspaces` SELECT: `created_by = auth.uid()`
- `workspaces` UPDATE: `user_in_workspace(id)` (SECURITY DEFINER, safe)
- `projects` UPDATE: `user_in_workspace(workspace_id)` (SECURITY DEFINER) — migration 010
- `workspace_members` INSERT: `user_id = auth.uid()`
- `workspace_members` SELECT: `user_id = auth.uid()`
- `geo_check_results` INSERT: `user_owns_project(project_id)` (SECURITY DEFINER)
- `geo_check_results` SELECT: `user_owns_project(project_id)` (SECURITY DEFINER)
- `pages` INSERT/SELECT/UPDATE: `user_owns_project(project_id)` (SECURITY DEFINER). DELETE: **REMOVED** — pages are never deleted, only archived
- `page_url_history` SELECT: `user_owns_project()` via page→project chain
- `page_url_history` INSERT: `user_owns_project()` via page→project chain
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
- **Matrise**: Prioritisation view — computed from all modules, ranks pages by priority score. Sidebar tool. See Matrise section below.
- **Arbeidspakker Library**: Central view of all work packages across a project. Sidebar tool. See Arbeidspakker section below.
- **AI Analysis CSV exports**: Summary table + per-issue detail downloadable as CSV from AI Analysis tab.
- **Stabilise Session 1 (Apr 7)**: Project settings scoping fix (#35), English page types (#31), Rank Tracker per-category batching (#19), light mode WCAG AA contrast (#25), crawler data persistence via `page_elements` JSONB.
- **Domain Strategy Layer (Apr 7-8)**: Holistic AEO domain intelligence. Per-project strategy (page roles, cannibalisation, gaps, rules) generated by Sonnet, injected into every playbook prompt to differentiate recommendations. UI lock during operations (#26). AI intent suggestion helper (R:C).
- **Session 2 (Apr 9)**: #9a Sonnet prompt — 8 research-backed AEO rules (declarative H2s, no FAQ on product pages, front-loading, schema completeness, Org/Person schema, AI crawler audit, entity checklist, platform tags). #9b intent helper backend — content preview (D), content-based intent suggestions with H2s/content (A), local relevance scoring (B). Live fetch fallback when page_elements empty.
- **Session 3 (Apr 9-10)**: Strategy banner in AI Workspace (colour-coded roles + priority queries + do-not-recommend). Strategy overwrite protection (validates before save, backs up to domain_strategy_previous). Domain strategy all-page coverage fix. page_elements double-encoding fix. GSC/GA contextual status messages. Intent JSON save format. Playbook download filename with domain+path slug.
- **v5.0 Project Overview (Apr 10)**: New default landing page. 7-item nav (Project Overview first). 6 sections: domain strategy (user input + AI narrative), citation rate, crawl summary, matrix stats, coming soon placeholders. Strategy narrative field added to domain_strategy JSONB. v5.0.1: UX polish (labels, narrative display, homepage URL clarity, richer placeholders, matrix context).
- **v5.1 Session (Apr 10-11)**: Crawler max_pages 20→200 (root cause of incomplete strategies). Strategy timeout fix: tag/category auto-assignment + 180s timeout. Strategy overwrite protection (validates + backs up to domain_strategy_previous). 404→dead status + status badges in crawl overview (✅/🔴/↩️). content_text extraction (first 500 words) in page_elements. Domain context editor moved to Settings page. Brand Context Auditor demo (wagamama sample audit with colour-coded investigations). HTTP 529 handling across all Anthropic calls.

## Next Up
- **Migration 013**: Run `migrations/013_domain_strategy_previous.sql` in Supabase SQL editor for strategy backup column.
- **Re-crawl projects**: With max_pages=200 default, re-crawl to populate content_text and get full page coverage for domain strategies.
- **Regenerate strategies**: After re-crawl, regenerate to get strategy_narrative + full page coverage.
- **Session 4 backlog**: #27 language fix + #33 matrix headers + #34 download button + R:A authority guide
- **Morten test**: GSC + GA4 import with real data (Morten's Gmail needs adding as Google OAuth test user in Google Cloud Console)
- **AEO Guide research**: Pal commissioning AEO research to improve `aeo/intelligence/aeo_guide.md`. Potential gaps: multi-modal content signals, freshness/recency weighting, updated stats.
- **Superadmin AEO Guide editor** (parked): Superadmin role on workspace_members, admin panel to edit AEO guide in-app, store guide in Supabase instead of flat file.
- **Domain context + intent persistence**: Re-enabled Mar 24. Run migration 010 (projects UPDATE RLS) + PostgREST schema reload, then test.
- **OpenAI → Haiku consolidation** (parked, 9 Apr): Swap gpt-4.1-mini (Reasonable tier) + GPT-4o-mini (content analysis) to Haiku 4.5. Reduces API keys from 3 to 2. Investigated: both OpenAI models retired from ChatGPT (Feb 2026) but API still live — no sunset date announced. Strategic consolidation, not urgent. Product Director decision: park until post-South America.
- **AI Visibility Auditor** (feature idea, 9 Apr): Cross-engine brand visibility check. Perplexity serves as the default citation tracker (cheap, frequent), but AI search engines are diverging like cable channels — ChatGPT, Claude, Gemini, Google AI Overviews each surface different sources and have different brand visibility. Need a way to occasionally (premium, user-triggered) query multiple AI engines for a brand/domain and compare responses. **Build as:** simple Python module (`ai_visibility/visibility_auditor.py`), NOT an agent SDK setup. Takes domain + brand name + domain context + 3-5 test queries. Calls Claude API + OpenAI API + (optionally Gemini) in parallel with httpx. Sonnet synthesises a structured report: how each AI describes the brand, what it gets right/wrong, what's missing. Store as JSONB on projects table (like domain_strategy). Button in Crawl page or dedicated section. ~$0.10-0.20 per audit. **Insight source:** Pal's weekly newsletter analysis (Apr 2026) showing engine divergence — Perplexity as average, but specific engines have unique blind spots and preferences. **Explored via Anthropic managed agents console** — confirmed API approach works (no blocking), but agent SDK is overkill for what is 3 parallel API calls + synthesis. **Dependencies:** ANTHROPIC_API_KEY (already have), OPENAI_API_KEY (already have), optionally Google AI Studio key for Gemini.
- **Mobile optimisation** (parked): Not blocking beta.
- Set up custom SMTP (Resend) for email confirmation when approaching real users

## Notes for Product Director
- **All modules deployed**. Streamlit Cloud auto-deploys from master.
- **Sidebar nav (7)**: Project Overview (default), Rank Tracker, Crawl, Matrix, AI Workspace, Data Sources, Settings. Full English UI. Radio buttons (all visible). Project Overview is the landing page since v5.0.
- **GSC/GA4 untested with real data** — Pal has no active GSC properties. Morten needs to test. His Gmail must be added as a test user in Google Cloud Console OAuth consent screen first.
- **AI Workspace depends on ANTHROPIC_API_KEY** (Claude Sonnet 4) + **OPENAI_API_KEY** (content analysis + gpt-4.1-mini playbook) — both in Streamlit Cloud secrets ✓
- **Playbook v4.1** (Apr 9): Sonnet prompt now includes 8 AEO research-backed rules. Reasonable tier = structural audit (gpt-4.1-mini ~$0.02), Premium tier = full rewrite (Sonnet ~$0.11). Safety tags: `v4.1-sonnet-prompt-research-upgrade`, `v4.2-intent-helper-backend`.
- **AI Workspace intent flow** (Apr 9): Content preview (H1/H2/meta from crawl or live fetch), Haiku intent suggestions enriched with H2s + content summary, local relevance scoring (Keyword Overlap /40, H2 Coverage /35, Specificity /25). Zero-cost scorer replaces standalone's GPT API call.
- **Crawler** (Apr 11): Default max_pages bumped 20→200. Extracts content_text (first 500 words of body). Sets status from HTTP code (404→dead, 3xx→redirected). Status badges in overview (✅/🔴/↩️). Tag/category pages auto-assigned authority_builder in strategy generation.
- **Domain Strategy** (Apr 10-11): Overwrite protection (validates page_roles before save, backs up to domain_strategy_previous). All-page coverage enforced. Strategy narrative field. Tag/category filtering reduces timeouts. Timeout 120→180s.
- **Brand Context Auditor** (Apr 11): Static demo on Project Overview — wagamama sample audit. Colour-coded investigations (purple strategy, green/blue/orange/red investigations). Styled callout boxes for gaps/verdicts. Inference Economics metrics. Preview of upcoming multi-engine brand perception feature.
- **Settings page** (Apr 11): Domain context editor moved from sidebar expander to Settings nav item. Overview "Edit Your Strategy Manifest" navigates to Settings.
- **AEO Guide**: Lives at `aeo/intelligence/aeo_guide.md` (321 lines). Synced from Notion via `sync_aeo_guide.py`. Injected into Sonnet prompt in `recommender.py`. Future: store in Supabase, editable by superadmins in-app.
- **`aeo/` had embedded .git** from standalone repo — removed before commit. Standalone-only files (app.py, README, .streamlit, etc.) left unstaged intentionally.
- **sys.path poisoning risk**: `aeo/app.py` still exists on disk (unstaged). If anyone adds `aeo/` to sys.path without the temporary add/remove pattern, `from app import` breaks globally. Long-term fix: rename or delete `aeo/app.py` (the standalone entry point) since the suite uses `aeo/aeo_ui.py` instead.
- **`requests` package**: Used by `aeo/analyzer.py` but not in requirements.txt. Works because it's a transitive dep of streamlit. Could add explicitly if it ever breaks on Cloud.
- **Matrise→AEO Agent wiring**: Generate button sets `matrise_generate_url` in session state and switches to AEO Agent. AEO Agent pre-selects the page from that value.

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

### Known Bug: Select All checkbox visual state
- **Rank Tracker "Select all" button** functionally works (bulk delete removes the correct keywords) but checkboxes don't visually fill after clicking "Select all". Likely a Streamlit rendering quirk — `st.checkbox(value=True)` on rerun doesn't always update the visual state despite the widget key being cleared. Low priority — cosmetic only, no data impact.

### JWT / Session Expiry
- JWT expires after ~1 hour. Auto-refresh logic in `db_request()` handles this transparently (catches 401, calls `_refresh_jwt()`, retries once).
- **Refresh token** expires after ~1 week of inactivity (Supabase default). When this happens, auto-refresh silently fails and the user sees `JWT expired` errors on every DB call. **Fix: log out and log back in.** This is normal, not a bug.
- Long-running operations (AI generation, batch crawls) can also hit the 1-hour JWT window mid-operation — the per-module `_db_get`/`_db_post` helpers in `aeo/aeo_ui.py`, `aeo/context_builder.py`, `crawler/ai_analyser.py` all have their own 401 retry logic for this.

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
- **Data persistence**: All 15 columns now persisted to Supabase. Individual columns (H1, meta_description, canonical_url, etc.) saved directly on `pages` table. Transient data (H2, OG tags, JSON-LD, hero alt, referrer, crawl time) stored in `page_elements` JSONB column (migration 011). Persistent overview matches active crawl columns.
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
- **Models**: Anthropic Claude Sonnet 4 (`claude-sonnet-4-20250514`, expensive) or OpenAI gpt-4.1-mini (`gpt-4.1-mini-2025-04-14`, reasonable/cheap) for arbeidspakke generation — user-selectable toggle. OpenAI GPT-4o-mini for content analysis/intent extraction
- **Model deprecation watch**: gpt-4.1-mini retired from ChatGPT Feb 2026 but API still active. Monitor for API deprecation announcements. GPT-5 Mini ($0.25/$2.00) is the future migration path if needed.
- **Dependencies**: `anthropic`, `openai`, `lxml` (with `html.parser` fallback)
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

## Matrise Module

### Architecture
- **Location**: `matrise/` package — `matrise_ui.py`
- **Access**: Sidebar tool selector in `app.py` ("Matrise")
- **No database table** — computed view assembled at runtime from existing tables
- **No new dependencies**

### What It Does
- Fetches all crawled pages + crawl_ai_analysis + gsc_data + ga_data + arbeidspakker for a project
- Joins on page_id, deduplicates GSC/GA to most recent date range per page
- Calculates a priority_score (0-100) per page using weighted formula:
  - AEO gap 40% (low readiness = high opportunity)
  - SEO gap 20% (low score = technical debt)
  - Traffic signal 25% (impressions/clicks from GSC)
  - Engagement signal 15% (sessions from GA4)
- Sorted by priority_score descending — highest opportunity pages first

### UI
- Summary metrics: total pages, with AI scores, with GSC data, with arbeidspakke
- CSV export button (filename: `matrise-{domain}-{date}.csv`)
- Header row + data rows using `st.columns` with colour-coded badges
- Priority: red 70+, yellow 40-69, green <40
- Scores: red <50, yellow 50-74, green 75+
- Missing data shown as em dash (\u2014)
- Generate button per row → switches to AEO Agent tool (stub — sets session state)
- Expandable detail per row: priority action, GSC/GA date ranges, last crawled

### Generate Button Wiring
- Sets `st.session_state["matrise_generate_url"]` and `_tool_override` to "AEO Agent", then reruns
- `_tool_override` is consumed before selectbox renders — sets `active_tool` programmatically
- AEO Agent pre-selects the page from `matrise_generate_url`

## Arbeidspakker Library Module

### Architecture
- **Location**: `arbeidspakker/` package — `arbeidspakker_ui.py`
- **Access**: Sidebar tool selector in `app.py` ("Arbeidspakker")
- **No database table** — reads existing `arbeidspakker` table
- **No new dependencies**
- **Self-contained**: Own `_get_secret`, `_refresh_jwt`, `_db_get` helpers (same pattern as matrise)

### What It Does
- Fetches all arbeidspakker for a project, sorted newest-first
- Summary metrics: total count, unique pages, latest generated date
- Each item shows: URL, intent, generated date
- Expandable full markdown content per arbeidspakke
- Download `.md` button per item
- "Re-generate" button → switches to AEO Agent via `_tool_override` + `matrise_generate_url`

## Rolling Handover
Last session: Apr 11 2026

### Apr 11 2026 — v5.1 Crawler fixes + Brand Audit demo + Settings

**Crawler fixes:**
- CRITICAL: `max_pages` default 20→200 (root cause of incomplete domain strategies — only 4% of sites were being persisted).
- `content_text` extraction: first 500 words of visible body text saved in `page_elements` JSONB. Both BFS crawl and URL list check modes.
- HTTP status → page status: 404→dead, 301/302/307/308→redirected, else active.
- Crawl overview shows ALL pages (except archived) with status badges: ✅ 200, 🔴 404, ↩️ 3xx.
- Strategy generator filters to active-only pages inline (not at query level).

**Domain strategy hardening:**
- Strategy generation timeout fix: tag/category pages (`/tag/`, `/category/`) auto-assigned `authority_builder` without Sonnet call. Timeout 120→180s.
- HTTP 529 handling across all 3 Anthropic call sites (strategy, playbook, intent). `st.warning` not `st.error`.
- UI lock: `st.rerun()` moved after `finally` block. `_strategy_saved` flag prevents NameError. Explicit `except` surfaces errors.
- Stale cache clearing on strategy save (`_domain_strategy_`, `_overview_data_`).

**Project Overview v5.0.1:**
- Domain context editor moved from sidebar to Settings page. Overview button navigates to Settings.
- Tab CSS: gap 0→8px + padding, fixes "Web CrawlSitemap Check" run-together labels.

**Brand Context Auditor demo:**
- Static wagamama audit on Project Overview. 5 expandable sections (strategy + 4 investigations).
- Colour-coded: 🟣 strategy, 🟢/🔵/🟠/🔴 investigations. Styled callout boxes for gaps (red), identity (blue), positioning (amber), verdict (green).
- Inference Economics: 4,988 strategy tokens + 143,055 execution tokens = $0.50 per audit.
- "Coming to Aevilab Q2 2026" tagline.

**Content-based fallback update:**
- Live-fetch fallback now triggers on missing `content_text` (not just missing H2s).
- After re-crawl with v5.1, `content_text` is populated and live-fetch is no longer needed.

**Safety tags:** `v5.0-project-overview`, `v5.0.1-overview-ux-polish`, `v5.1-working-before-brand-audit-embed`, `v5.1-brand-audit-embed`, `v4.3-session2-complete`, `v4.4-gsc-ga-connection-fix`.

### Apr 10 2026 — v5.0 Project Overview + Session 3 bugfixes

**v5.0 Project Overview** (commits `6b47a01`, `v5.0.1`):
- New default landing page. 7-item nav (Project Overview first).
- 6 sections: domain strategy (user input + AI narrative), citation rate, crawl summary, matrix stats, 2 coming-soon placeholders.
- Domain strategy section: left column = user's domain_context (expandable), right column = AI narrative from `strategy_narrative` field, collapsible detailed roles table.
- `strategy_narrative` added to Sonnet prompt output — 150-300 word strategic brief in plain English.
- Fallback: if no narrative in JSONB (pre-v5.0 strategies), auto-generates role count summary from page_roles.
- Nav buttons use `_tool_override` pattern. Overview cache cleared on project switch.
- v5.0.1: Labels ("Domain Strategy — Your Input" / "AI Derived Domain Strategy"), homepage shows "/ (Homepage)", matrix context line, richer coming-soon text, strategy date + regenerate link replaces bare Crawl button.

**Session 3 bugfixes** (Apr 9-10):
- **page_elements double-encoding**: `json.dumps()` removed from crawler UPSERT — was double-encoding JSONB.
- **Strategy overwrite protection**: `save_domain_strategy()` validates non-empty page_roles before saving. Backs up to `domain_strategy_previous` column. Migration 013.
- **Strategy all-page coverage**: Sonnet prompt now requires one role per page. max_tokens 4096→8192. Post-generation validation warns on missing pages.
- **Strategy banner**: Colour-coded role with emoji, reasoning, priority queries, do-not-recommend in AI Workspace. Three states: role found, no role, no strategy.
- **GSC/GA status messages**: Three-state ("not connected" / "connected, import needed" / data shown).
- **Intent JSON save**: `{"selected": [...], "manual": "..."}` format with legacy fallback.
- **Playbook download filename**: `playbook-{domain}-{path-slug}-{date}.md`.
- **Live fetch fallback**: Fixed guard to check H2s not meta/h1.
- **Intent JSON parse**: Strip markdown fences from Haiku response.

### Apr 9 2026 — #9b Intent Helper Backend (D, A, B)
**Safety tag:** `v4.2-intent-helper-backend`

**3 features ported from standalone AEO Agent into AI Workspace intent step:**

**D — Content Preview** (`aeo/aeo_ui.py`):
- Expandable "Content Preview (N words crawled)" section between Page Intelligence and Step 2.
- Shows H1, meta description, H2 structure (up to 20), schema types, hero image alt.
- Data sourced from `page_elements` JSONB + direct `pages` columns — no new crawl needed.

**A — Content-Based Intent Suggestions** (`aeo/intent_helper.py`, `aeo/aeo_ui.py`):
- `suggest_intents()` now accepts `h2_headings` (list[str]) and `content_summary` (str) params.
- Haiku system prompt updated to weight H2 headings + content structure, not just title/meta.
- `aeo_ui.py` builds `_content_summary` from page_elements (H1, meta, H2s, OG tags, schema types) and passes it to Haiku.
- Previously only sent `meta_description[:300]` — now sends full structural context.

**B — Intent Relevance Score** (`aeo/intent_scorer.py`, `aeo/aeo_ui.py`):
- Replaced standalone's GPT-4o-mini scorer with pure Python heuristic (zero API cost).
- Three sub-scores: Keyword Overlap (0-40), H2 Coverage (0-35), Specificity (0-25).
- Keyword overlap: tokenizes intents + page metadata (title, H1, meta, H2s), measures intersection.
- H2 coverage: % of H2 sections that have at least one matching intent.
- Specificity: longer intent phrases score higher (5+ words = 25, 1 word = 3).
- Displayed as "Intent Relevance Score: X/100 — Strong/Moderate/Weak match" with expandable breakdown showing per-intent element matching.
- Norwegian + English stopwords stripped from tokenization.

**E — Domain strategy role injection**: Already shipped in v4.0 (lines 454-459 of aeo_ui.py). Confirmed, skipped.

**C — Query generation**: Deferred to separate prompt.

**Files changed:** `aeo/aeo_ui.py` (content preview + richer intent params + scoring UI), `aeo/intent_helper.py` (new params + enriched prompt), `aeo/intent_scorer.py` (rewritten: GPT scorer → local Python heuristic).
**No migrations, no schema changes, no new secrets, no new dependencies.**

**Live fetch fallback** (commit `562d8f4`): When `page_elements` is empty (pages crawled before v3.6), `analyze_url()` fetches the page live via HTTP + BeautifulSoup. Result cached in `st.session_state[aeo_live_analysis_{page_id}]` — no re-fetch on interaction. Extracts H1, H2s, first 500 words, first paragraph, word count. Content preview shows "(live fetch)" vs "(crawl data)" label.

### Apr 9 2026 — #9a Sonnet Prompt Research Upgrade
**Safety tag:** `v4.1-sonnet-prompt-research-upgrade`

**What:** Injected 8 empirical AEO research findings into the Sonnet system prompt (`aeo/recommender.py`). New `## AEO RESEARCH-BACKED RULES` section placed after the 6-section output structure and before OUTPUT QUALITY RULES.

**The 8 rules:**
1. **Declarative H2s** > question H2s (26% more citations). Applied to Blog/FAQ/Landing pages, not Homepage/Product.
2. **No FAQ schema on product pages** — FAQ REDUCES product page citations (-0.3 score). Belt-and-suspenders with domain strategy's `do_not_recommend`.
3. **Front-load answers** — 44% of citations from first 30% of content. Section 2 rewrites must lead with citation-worthy info.
4. **Schema completeness or omit** — 18-point penalty for incomplete schema vs none. No placeholders allowed; incomplete schemas go to checklist as manual tasks.
5. **Organisation/Person schema** — mandatory sameAs array for entity_anchor/homepage/about pages. sameAs is single most impactful field for AI entity recognition.
6. **AI crawler access audit** — mandatory Section 4 item: check robots.txt for GPTBot, ClaudeBot, PerplexityBot, Google-Extended.
7. **Entity presence checklist** — Section 5 item for entity pages: Wikidata > LinkedIn > Google Business > directories.
8. **Platform-specific impact tags** — inline tags on recommendations noting Google AI Overviews (traditional SEO) vs ChatGPT/Perplexity/Claude (entity/authority) impact.

**Files changed:** `aeo/recommender.py` (Sonnet system prompt only). No other files touched.
**No migrations, no schema changes, no new secrets, no new dependencies.**
**Reasonable tier (gpt-4.1-mini) prompt NOT changed** — it produces structural audits, not full rewrites.

**Verification needed:** Generate playbooks for blog post, product page, and homepage to confirm rules are applied correctly. See prompt spec verification checklist.

### Apr 7 2026 — Stabilise Session 1 (5 backlog items, 5 commits)
**All pushed to master, auto-deployed to Streamlit Cloud.**

**#35 (P0) Project settings leak fix** (commit `cbb97a4`):
- Central project change detector in `app.py` (~line 977). When `selected_project_id` changes, clears all project-scoped session state: `domain_context`, `selected_query_ids`, `_confirm_bulk_delete`, `crawl_results`, `url_list_results`, `sitemap_results`, `matrise_generate_url`, `_tool_override`, plus all `aeo_page_*`/`aeo_arbeidspakke*`/`aeo_intent_*`/`cb_*`/`_citation_batch_status_*` prefixed keys.
- AEO module's own detector (aeo_ui.py:268-273) kept as belt-and-braces.
- Safety tag: `v3.4-pre-settings-scoping-fix`.

**#31 Norwegian page types → English** (commit `0980255`):
- `aeo/aeo_ui.py` dropdown: Forside→Homepage, Produktside→Product/Service Page, etc. (8 labels).
- `aeo/recommender.py` Sonnet prompt: matching English labels in page type guidance.
- Existing DB records with Norwegian values degrade gracefully (dropdown shows unselected, user re-picks).
- Safety tag: `v3.2-english-page-types`.

**#19 Rank Tracker reliability** (commits `b0d729e` then `cd39152`):
- v1 (b0d729e): Per-category batching with JWT refresh. Had per-category "Check" buttons.
- v2 (cd39152): **Reverted per-category UI** — partial checks corrupted the trend chart (nosedive effect). Single "Run Citation Check (N keywords)" button. Backend still batches by category with JWT refresh between batches. Results accumulated in memory during run, **bulk-written to Supabase only after ALL keywords complete** — prevents partial data in time series. Trend chart filters out incomplete check dates (< 80% of current query count). 0.2s delay between API calls, 1s between category batches.
- Safety tags: `v3.3-rank-tracker-batching`, `v3.7-rank-tracker-single-check`.

**#25 Light mode contrast fix** (commits `226f795` + `cbb06b5`):
- **v1** (226f795): Darkened light mode CSS variables for WCAG AA — text-muted #5a6070→#3d4450, text-muted2 #8890a0→#5c6370, sidebar-bg #ffffff→#f3f4f6, borders darkened, all 5 semantic colours darkened.
- **v2** (cbb06b5): Comprehensive component pass — BaseWeb selectbox/dropdown overrides (menu bg, option text, hover/focus states), expander headers + content area, checkbox labels, caption colours, tab hover states, button active/focus states, form submit buttons, widget labels, tooltips, multiselect tags, number input spinners, metric card font-size bump (fixes #32 truncation). All sidebar labels bumped to text-primary.
- Dark mode completely untouched in both commits.
- Safety tag: `v3.4-light-mode-contrast`.

**#30 Missing keywords for palerikwaagbo.no** — investigated via Supabase SQL. No `.no` project exists. Only `.com` projects (315 queries + 0-query duplicate "Pal Brand"). False alarm.

**Crawler column alignment** (commit `cd0cf95`):
- Persistent page overview SELECT expanded to include h1, meta_description, canonical_url, in_sitemap, depth (all stored in Supabase but previously not shown on revisit).

**Crawler data persistence — page_elements JSONB** (commit `982de6c`):
- Migration 011: `page_elements JSONB DEFAULT '{}'` on `pages` table. Run on Supabase, schema reloaded.
- `_build_page_elements()` builds dict from CrawlResult: h2_structure (string[]), og_tags (dict), json_ld (parsed schema objects), hero_image_alt, referrer, crawl_time_seconds.
- `_save_crawl_results()` now includes `page_elements` in every UPSERT.
- Persistent view reads page_elements and displays all 15 crawl columns + 4 operational (Page Type, Intent, Last Crawled, Last Playbook). Column order matches active crawl view.
- Existing pages show `—` for new columns until re-crawled.
- Safety tag: `v3.6-persist-crawl-data`.

**#19 v2 — Rank Tracker single-button revision** (commit `cd39152`):
- Reverted per-category UI buttons (partial checks corrupted trend chart). Single "Run Citation Check (N keywords)" button.
- Backend still batches by category with JWT refresh. Results accumulated in memory, **bulk-written only after ALL keywords complete**.
- Trend chart filters out incomplete check dates (< 80% of current query count).
- Safety tag: `v3.7-rank-tracker-single-check`.

**#26 UI lock during long-running operations** (commit `b0c4256`):
- `operation_in_progress` flag in session state disables sidebar nav, project selector, dark/light toggle, and logout during any long operation.
- Applied to: citation check (`app.py`), crawl + URL check + AI analysis (`crawler/crawler_ui.py`), playbook generation (`aeo/aeo_ui.py`).
- All wrapped in `try/finally` — guaranteed unlock on error. Warning banner shown when locked.
- Safety tag: `v3.8-ui-lock-during-operations`.

**R:C AI intent suggestion helper** (commit `8069de4`):
- New `aeo/intent_helper.py`: calls Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) to generate 8-12 intent phrases from page title, type, domain context, and meta description. ~$0.005/call, <3s response.
- AI Workspace Step 2 rewritten: blank text input → selectable checkboxes (auto-generated on page select) + custom text area. Status shows "Selected: N intents — ready to audit!" (green at 3+).
- Selected intents combined as comma-separated string for prompt injection and `pages.intent` persistence. Previously saved intents pre-check matching boxes on revisit.
- Suggestion cache: `aeo_intent_suggestions_{page_key}` in session state, cleared on project/page switch. Respects UI lock.
- Safety tag: `v3.9-intent-suggestion-helper`.

**Domain Strategy Layer v4.0** (commit `85266a1`):
- New `domain_strategy/strategy_generator.py`: Sonnet analyses all crawled pages holistically, assigns each page a strategic role (entity_anchor, citation_target, authority_builder, conversion_endpoint, cannibal_overlap), identifies cannibalisation and content gaps, defines strategic rules. ~$0.20-0.50 per generation. Runs once per project.
- Crawl page: "Generate Domain Strategy" button + full strategy display (role table with colour-coded icons, cannibalisation warnings, gap analysis, strategic rules). Expandable view.
- `generate_recommendations()`: new `domain_strategy` + `page_id` params. Strategy context injected between domain_context and AEO methodology in Sonnet prompt. Per-page: role, priority queries, do-not-recommend list, strategic rules.
- Intent helper: page's strategic role enriches Haiku context for role-appropriate suggestions.
- `_build_project_ctx()` helper in app.py — DRY project context builder includes domain_strategy.
- `_domain_strategy_{project_id}` cached in session state, cleared on project switch.
- Migration 012: `domain_strategy JSONB` + `domain_strategy_generated_at TIMESTAMPTZ` on `projects`. Already run.
- Safety tag: `v4.0-domain-strategy-layer`.

**Backlog progress**: Session 1 plan + #26, #19v2, R:C, crawler persistence, Domain Strategy v4.0 all shipped. Next: #9 (Sonnet prompt improvements from AEO research). Session 3 = #27+#28/#15+#32+#33+#34+R:A.

### Apr 3 2026 — Sidebar nav: selectbox → radio (v3.4)
- Replaced `st.selectbox` with `st.radio` + `label_visibility="collapsed"` for sidebar tool selector
- All 6 nav items now visible at once — no dropdown click needed (demo readiness)
- Safety tag: `v3.3-pre-radio-nav`. Commit `be43e4d`, pushed, auto-deploying.
- One-line change in `app.py` line 884. All `_tool_override` wiring unchanged.

### Apr 2 2026 — Playbook Formatting Fixes
- Sonnet prompt: added scannability rule (blank line before every bold item) + checklist format rule (bullets not checkboxes)
- Section 6 instruction changed from `- [ ]` checkbox syntax to bullet points
- Checkbox characters (☐, □, [ ], [x]) replaced with bullets/checkmarks in display code (`_clean_playbook_md`)
- Download filename now includes page slug: `playbook-{slug}-{date}.md` (e.g. `playbook-for-skoler-2026-04-02.md`)
- Prompt instructions: "arbeidspakke" / "work package" → "playbook" / "AEO playbook" (output language logic unchanged)
- Safety tag: `v3.3-playbook-formatting`
- Files changed: `aeo/recommender.py`, `aeo/aeo_ui.py`

### Apr 2 2026 — Aevilab Colour System + Dark/Light Mode
- Replaced hardcoded dark-only CSS with CSS custom property system (two complete palettes)
- Dark mode: Morten's approved prototype palette (bg #0d0f14, amber #f0a500, green #2dd4a0, red #f06070, blue #5b9cf6, purple #a78bfa)
- Light mode: high-contrast inverse (bg #f8f9fb, darker accent variants for readability)
- Dark/light toggle in sidebar (`st.toggle("Dark mode")`, default dark, persists in session state)
- 5-colour semantic system: amber (CTA/active), green (success), red (error/critical), blue (info/links), purple (tags/metadata)
- Google Fonts: Syne (headings), DM Sans (body), DM Mono (code) — carried forward from v3.0
- All Streamlit component overrides use `var(--name)` instead of hardcoded hex — theme-aware
- Added `[data-testid="stHeader"]` background override, link colour (`a { color: var(--blue) }`)
- Safety tag: `v3.2-colour-system`
- Files changed: `app.py`, `.streamlit/config.toml`

### Apr 2 2026 — Navigation Restructure + English UI
- Sidebar restructured: 6 nav items (Rank Tracker, Crawl, Matrix, AI Workspace, Data Sources, Settings)
- Rank Tracker set as default landing page
- Full English UI: Matrise→Matrix, Arbeidspakke→Playbook, AEO Agent→AI Workspace, Web Crawler→Crawl
- Norwegian UI labels retired (Prosjektinnstillinger, Domenekontekst, Lagre, Sidetype, Crawlede sider, etc.)
- DB table names unchanged (still `arbeidspakker`, `matrise` module folder, etc.)
- `_tool_override` references updated: Matrix and Playbooks Generate buttons now route to "AI Workspace"
- Settings page: minimal placeholder (st.header + st.info)
- Standalone Arbeidspakker Library removed from nav (playbooks still accessible via AI Workspace history + Matrix Generate buttons)
- Safety tag: `v3.1-nav-english`
- Files changed: `app.py`, `crawler/crawler_ui.py`, `aeo/aeo_ui.py`, `matrise/matrise_ui.py`, `arbeidspakker/arbeidspakker_ui.py`

### Apr 2 2026 — Priority 0 Schema Corrections + Archive-Not-Delete
- Migration: Added `status` column to pages (active/redirected/dead/archived), removed DELETE policy — pages are never deleted, only archived
- Migration: Created `page_url_history` table for URL identity resolution (append-only, tracks 301s/404s/merges)
- Migration: Added `language` to pages (ISO 639-1, set by crawler or user) and arbeidspakker (language at generation time)
- Safety tags: `v3.0-priority0-schema-corrections` (pre-schema), `v3.0-priority0-python-archive` (pre-Python)
- PostgREST schema cache reloaded
- Python: Added `status=eq.active` filter to all 4 user-facing page queries (no DELETE operations existed to replace)
- Intentionally unfiltered: `google_data/datasources_ui.py` `_load_pages()` (internal URL matching lookup), crawler UPSERT, AEO PATCH operations
- Files changed: `crawler/crawler_ui.py`, `aeo/aeo_ui.py`, `matrise/matrise_ui.py`

### Mar 25 2026 — Aevilab design system (matched to prototype)

**Safety tag**: `v3.0-pre-visual-overhaul` (pre-change state — reverts ALL visual changes)

**Visual-only change. No logic, no database, no functionality changes.**

**Replaces the earlier "Midnight Observatory" theme with the Aevilab prototype's exact design system.**

**What changed:**
1. `.streamlit/config.toml`: Aevilab palette (bg #0d0f14, surface #1a1d24, accent #f0a500, text #e8eaf0)
2. `app.py`: CSS injection block rewritten — ~250 lines matching `aevilab-prototype.html`. Google Fonts import (Syne headings, DM Sans body, DM Mono code). All component colours updated.
3. Names: "Avily" → "Aevilab". Page title → "Aevilab". Icon → ⬡.

**Naming:**
- **Aevily** = umbrella brand (domain, top-level)
- **Aevilab** = the Search Intelligence Suite app

**Design system — Aevilab prototype:**
- Background: #0d0f14, Sidebar: #111318, Surface: #1a1d24, Surface2: #21252e
- Amber #f0a500: CTA buttons, progress bars, active tabs, focus borders
- Green #2dd4a0: success messages
- Red #f06070: errors, low scores
- Blue #5b9cf6: info messages
- Text: #e8eaf0 (primary), #7a8099 (muted), #4e5568 (muted2)
- Borders: #2a2f3a (primary), #343b48 (secondary)
- Fonts: Syne (headings), DM Sans (body), DM Mono (inputs/code)

**Prototype reference**: `C:\Users\Pal\Downloads\aevilab-prototype.html` (Morten + his Claude built this)

**Reversal**: `git checkout v3.0-pre-visual-overhaul -- .streamlit/config.toml app.py`

**Files changed**: `.streamlit/config.toml`, `app.py` (CSS + titles only)

**Next (separate session)**: Navigation restructure — sidebar tools → object-oriented nav (Pages, Opportunities, AI Workspace, Settings). See Aevilab UX Vision memory for full spec.

### Mar 25 2026 — Intent persistence fix + cross-screen visibility

**Safety tag**: `v2.9-intent-persistence-fix` (pre-change state)

**4 fixes:**

1. **Auto-save intent button** (`aeo/aeo_ui.py`): "Save intent" button appears below text input when intent differs from stored value. PATCHes `pages` table immediately. Save-on-Generate also kept (belt and braces).

2. **Intent pre-fill fix** (`aeo/aeo_ui.py`): Used `st.session_state[key]` pre-seeding pattern instead of `value=` parameter. Streamlit ignores `value=` after first render — pre-seeding the session state before the widget renders ensures the stored intent appears even when revisiting a page.

3. **Intent in Crawler overview** (`crawler/crawler_ui.py`): Added "Intent" column to "Crawlede sider" dataframe table. Shows first 60 chars or em dash if empty. Read-only.

4. **Intent in Matrise** (`matrise/matrise_ui.py`): Added "Intent" column to priority table (header, data rows, CSV export). Shows first 40 chars or em dash. Column widths adjusted (URL narrowed from 3 to 2.5, Intent gets 2). CSV export includes Intent after URL.

**Files changed**: `aeo/aeo_ui.py`, `crawler/crawler_ui.py`, `matrise/matrise_ui.py`, `CLAUDE.md`

**No migrations, no schema changes, no new secrets, no new dependencies.**

### Mar 24 2026 — Re-enabled domain context + intent persistence

**Safety tag**: `v2.7-re-enable-context-intent` (pre-change state)

**What was re-enabled:**
1. **Domain context** (`app.py`): "Prosjektinnstillinger" sidebar expander uncommented. Textarea loads/saves `domain_context` per project. Widget key includes `project_id` (`domain_context_input_{_pid}`). Save button PATCHes `projects` table.
2. **Intent persistence** (`aeo/aeo_ui.py`): Intent pre-fills from stored `intent` column on `pages` table when a page is selected. On Generate, if intent changed, PATCHes `intent` on the selected page. Widget key already included `_page_key` (page_id).

**Why it was originally disabled (Mar 12)**: Values followed user across projects/pages because Streamlit widget keys didn't include entity IDs. The fix pattern (include `project_id`/`page_id` in widget key) was already applied in the page selector fix (v2.3) and was already present in the commented-out code — it just needed uncommenting.

**No code changes beyond uncommenting** — the widget key scoping was already correct in the disabled code.

**Manual step required**: Reload PostgREST schema in Supabase Dashboard (Settings > API > Reload Schema) to ensure `domain_context` and `intent` columns are PATCHable. The columns exist (migration 008 was run Mar 12) but PostgREST may have a stale schema cache.

**Security review**: Both PATCH operations are RLS-protected (projects via `user_in_workspace`, pages via `user_owns_project`). Values passed as JSON body, no injection risk.

**Test plan**:
- Switch between two projects → verify domain context is different per project
- Select a page, set intent, switch to different page, come back → intent should persist
- Generate arbeidspakke with domain context set → verify context appears in output

**Migration required**: `migrations/010_projects_update_policy.sql` — adds UPDATE RLS policy on `projects` table using `user_in_workspace(workspace_id)`. Without this, the domain context PATCH is silently blocked by RLS (returns 200 but affects 0 rows). Run in Supabase SQL editor.

**No schema changes, no new secrets, no new dependencies.**

### Mar 18 2026 — Arbeidspakke output formatting fixes (Premium Sonnet prompt)

**Session focus: UX quality of arbeidspakke markdown output, triggered by Morten feedback.**

**Safety tag**: `v2.8-pre-h2-format-fix` (pre-change state)

**2 commits, both pushed to master, auto-deployed:**

1. **H2 heading rendering fix** (commit `fe589c2`): Sonnet prompt Section 2 instructed AI to output `[H1]`, `[H2]`, `[H3]` bracket labels. These rendered as flat text in `st.markdown()`. Changed to standard markdown heading syntax (`#`, `##`, `###`). Explicit "Do NOT use bracketed labels" rule added.

2. **FAQ + priority formatting overhaul** (commit `6466036`): Section 1 priorities and Section 3 FAQs had current/new text running together on one line with no visual separation. Fixed:
   - **Section 1**: Each priority now gets `####` subheading, current/suggested text in blockquotes (`>`)
   - **Section 3**: Each FAQ gets `####` question heading, current answer in blockquote, new answer as body text, `---` dividers between FAQs. Mandatory formatting instructions added to prompt.

**Only file changed**: `aeo/recommender.py` (Sonnet system prompt only — Reasonable tier prompt NOT changed, it doesn't output page rewrites).

**No migrations, no schema changes, no new secrets.**

**Note for Product Director**: These are prompt-only changes affecting output formatting. The Reasonable tier prompt was left untouched since it produces structural audits (no full rewrites = no heading formatting issue). If Morten reports similar formatting issues in Section 1 priorities on the Reasonable tier, the same blockquote pattern can be applied to `O4_MINI_SYSTEM_PROMPT`. The `[link: /url-path]` syntax in Section 2 is still bracket-based but intentional — it's a placeholder notation for the implementer, not a rendered heading.

### Mar 15 2026 — Reasonable tier restructure + model swap + Rank Tracker UX + CSV fixes

**Big session: 7 safety tags, 6 commits, all deployed to Streamlit Cloud.**

**AEO Agent changes (prompts 1-6):**

1. **o4-mini prompt quality fixes** (`v2.2-pre-o4mini-fix`): Added anti-hallucination rule, strict language rule, markdown-only output, key findings opening to `O4_MINI_SYSTEM_PROMPT`. Sonnet prompt UNCHANGED.

2. **Page selector project scoping** (`v2.3-pre-page-selector-fix`): Fixed AEO Agent page dropdown showing wrong project's pages after project switch. Widget keys now include `project_id`. Project change detector clears stale `aeo_page_*` / `aeo_arbeidspakke*` / `aeo_intent_*` state.

3. **Label rename + model indicator** (`v2.4-pre-label-fix`): "Cheap" → "Reasonable". Model footer in arbeidspakke markdown. `model_tier` + `model_name` in `context_snapshot` JSONB. History shows model label per arbeidspakke.

4. **Model swap o4-mini → gpt-4.1-mini** (`v2.5-pre-model-swap`): o4-mini hallucinated stats in 100% of tests despite anti-hallucination rules (reasoning model "reasons" fabricated metrics into existence). Switched to gpt-4.1-mini: `system` role (not `developer`), `max_tokens` (not `max_completion_tokens`), cheaper ($0.40/$1.60 vs $1.10/$4.40 per M tokens).

5. **Reasonable tier → structural audit** (`v2.6-pre-reasonable-restructure`): gpt-4.1-mini also hallucinated (root cause: prompt asked for full rewrites encouraging fabrication). Restructured as diagnostic audit: Sections 2+3 show 🔒 premium upsell + structural blueprint/questions instead of full rewrites. Labels: "💰 Reasonable — Structural Audit" / "🚀 Premium — Full Rewrite". Genuine product differentiation instead of a worse version of the same thing.

**Rank Tracker changes (prompts 7-8):**

6. **Keyword management UX** (`v2.7-pre-keyword-mgmt`): Multiselect checkboxes on keyword list, Select all/Deselect all (scoped by category filter), bulk delete with confirmation dialog, category filter dropdown, natural language query input hint. **Known bug**: Select all functionally works but checkboxes don't visually fill (Streamlit rendering quirk, cosmetic only).

7. **CSV upload fixes** (`v2.8-pre-csv-fixes`): UTF-8 BOM handling (`utf-8-sig` decode), `latin-1` fallback, semicolon delimiter auto-detection, column name whitespace stripping, better error messages showing actual columns found. Batch INSERT (single POST) instead of per-row loop to prevent JWT expiry on large uploads. Falls back to per-row only for duplicate handling.

**Commits**: `709c0ae` → `a2a0db0` → `0a1d278` → `52f22b7` → `77e18ff`, all pushed to master.

**Files changed**: `aeo/recommender.py`, `aeo/aeo_ui.py`, `app.py`, `CLAUDE.md`

**No migrations, no schema changes, no new secrets needed.**

**Stale items cleaned up**: Migrations 006+007 (already run), Section 6 (discarded), label rename TODO (done).

### Mar 14 2026 (session 2) — o4-mini prompt fixes + page selector scoping + label rename
**Superseded by Mar 15 session above — kept for reference.**

**3 prompts shipped this session. All in `aeo/` only. No DB/migration/secrets changes.**

**Prompt 1: o4-mini prompt quality fixes** (`aeo/recommender.py`)
- **Safety tag**: `v2.2-pre-o4mini-fix`
- 4 rules added to `O4_MINI_SYSTEM_PROMPT` (Sonnet prompt UNCHANGED):
  1. **No fabricated data** — critical rule at top banning invented statistics/percentages
  2. **Strict language rule** — 5-point rule with explicit heading translations (EN/NO)
  3. **Markdown-only output** — no raw HTML tags except JSON-LD in Section 4
  4. **Key findings opening** — required 3-5 sentence diagnostic paragraph before Section 1
- Section headings changed from hardcoded Norwegian to English defaults (language rule handles translation)

**Prompt 2: Page selector project scoping fix** (`aeo/aeo_ui.py`)
- **Safety tag**: `v2.3-pre-page-selector-fix`
- **Bug**: Switching projects kept old project's pages in AEO Agent dropdown
- **Fix**: Same pattern as Mar 12 widget scoping fix — include entity ID in widget keys
  - Page selector key: `aeo_page_select` → `aeo_page_select_{project_id}`
  - Manual URL widgets: scoped by project_id
  - Matrise pre-select: writes to project-scoped key
  - Project change detector: clears `aeo_page_*`, `aeo_arbeidspakke*`, `aeo_intent_*` on switch

**Prompt 3: Label rename + model indicator** (`aeo/aeo_ui.py`)
- **Safety tag**: `v2.4-pre-label-fix`
- "Cheap" → "Reasonable" in toggle label + help text (internal value stays `"cheap"`)
- Model footer appended to arbeidspakke markdown: `Generated with: 💰 Reasonable (o4-mini) | 2026-03-14 22:30`
- `model_tier` + `model_name` stored in `context_snapshot` JSONB on save
- History list shows model label per arbeidspakke (graceful fallback for pre-change items)

**Stale items cleaned up:**
- Migrations 006 (usage_events) + 007 (page_type): Already run — removed from blockers
- Section 6 (GEO data import): Discarded — removed from Next Up
- Rename label TODO: Done

### Mar 14 2026 (session 1) — Model toggle + data source auto-match
Two features shipped. Both deployed to Streamlit Cloud via master auto-deploy.

**Feature 1: Model toggle (reasonable/expensive) for arbeidspakke generation**
- **Safety tag**: `v2.1-pre-model-toggle` on commit `99463eb`
- **Commit**: `7bbcf05`
- **What**: Radio toggle in AEO Agent Step 3 — "💰 Reasonable (o4-mini)" / "🚀 Expensive (Sonnet)". Defaults to Expensive (Sonnet). Both produce same 6-section arbeidspakke format.
- **Why**: o4-mini is ~$0.03/gen vs Sonnet ~$0.11/gen. Gives users a fast/cheap option for iterating, expensive option for final client-ready output.
- **Files changed**: `aeo/aeo_ui.py` (toggle UI), `aeo/recommender.py` (model routing + o4-mini prompt)
- **Technical**: o4-mini uses `role: "developer"` (not `system`), `max_completion_tokens` (not `max_tokens`). Separate `O4_MINI_SYSTEM_PROMPT` — shorter, more directive, same output structure. Sonnet prompt UNCHANGED.
- **Usage tracking**: Both paths log `arbeidspakke_generation` with model name + `event_detail="model_tier=cheap|expensive"`
- **Migration 009** (optional): Adds `model_tier`/`model_name` columns to `usage_events`. Not required — tier info already in `event_detail`.
- **OPENAI_API_KEY**: Already in Streamlit Cloud secrets ✓

**Feature 2: Data Sources property auto-match by project domain**
- **Safety tag**: `v2.2-pre-datasource-fix` on commit `a676d3b`
- **Bug**: GSC/GA4 property selection was tied to workspace (one connection per user per workspace), not project. Switching projects showed the same GSC/GA4 property — e.g. palerikwaagbo.com data showing when palerikwaagbo.no project was selected.
- **Fix**: Property dropdowns now auto-select the option matching the current project's domain. Widget keys include project domain so Streamlit resets selection on project switch.
- **File changed**: `google_data/datasources_ui.py` — new `_best_match_index()` helper, `project_domain` param threaded through.
- **Scope**: UI-only fix. No schema changes, no RLS changes, no data model changes. Data import was already correctly scoped to `project_id`.
- **Longer-term**: Could move property selection to per-project (columns on `projects` table) if multi-domain workspaces become common.

### Mar 14 2026 — Model toggle: cheap (o4-mini) / expensive (Sonnet)
- **Safety tag**: `v2.1-pre-model-toggle` on commit `99463eb`
- **Commit**: `7bbcf05`, pushed to master, auto-deploying to Streamlit Cloud
- **What changed**:
  - `aeo/aeo_ui.py`: Horizontal radio toggle ("💰 Cheap (o4-mini)" / "🚀 Expensive (Sonnet)") above Generate button, defaults to Expensive. Spinner shows which model is generating.
  - `aeo/recommender.py`: New `model_tier` param (default `"expensive"`). `O4_MINI_SYSTEM_PROMPT` constant — shorter, more directive prompt with same 6-section output structure. o4-mini uses `role: "developer"` (not `system`), `max_completion_tokens=16000`. Page type, domain context, and intelligence section injected into o4-mini prompt dynamically. Sonnet path UNCHANGED.
  - `migrations/009_usage_events_model_columns.sql`: Optional — adds `model_tier` and `model_name` columns to `usage_events`. NOT required — tier info already tracked via `event_detail` field.
- **Usage tracking**: Both paths log `arbeidspakke_generation` events with model name and `event_detail="model_tier=cheap|expensive"`
- **o4-mini pricing**: ~$0.03/gen ($1.10/M input, $4.40/M output). Sonnet: ~$0.11/gen ($3/M input, $15/M output)
- **OPENAI_API_KEY**: Already in Streamlit Cloud secrets from previous GPT-4o-mini usage ✓
- **Next**: Test both models on same page, compare output quality. Optionally run migration 009 + reload PostgREST schema for dedicated tracking columns.

### Mar 12 2026 — DISABLED: domain context + intent persistence (temporary) — ✅ RE-ENABLED Mar 24
- **Reason for disabling**: Domain context caused project scoping instability (values followed user across projects). Intent persistence had same widget key scoping issue.
- **Re-enabled**: Mar 24 2026. Widget key scoping was already correct in the disabled code — just needed uncommenting.

### Mar 12 2026 — Widget scoping fix (domain context, intent, page type)
- **Bug**: Domain context persisted across project switches. Intent and page type persisted across page switches.
- **Root cause**: Streamlit widgets with fixed `key` params persist their values across reruns. When switching projects/pages, `st.text_area`/`st.selectbox` kept the old entity's value even though `value=` was updated.
- **Fix** (commit 1ea588b): Key all per-entity widgets by parent ID:
  - `domain_context_input_{project_id}` + `btn_save_domain_context_{project_id}`
  - `aeo_intent_input_{page_id}`
  - `aeo_page_type_select_{page_id}`
- **Lesson**: In Streamlit, `value=` only applies on first render. After that, the widget's internal state (keyed by `key`) takes over. To reset on entity switch, include the entity ID in the key.

### Mar 12 2026 — PostgREST schema cache fix (intent + domain context not loading)
- **Bug**: "Prosjektinnstillinger" sidebar missing, intent not pre-filling from DB
- **Root cause**: PostgREST caches DB schema. Migrations 007/008 added columns (`page_type`, `intent`, `domain_context`) but PostgREST didn't know about them yet. SELECTing unknown columns returns 400 → `get_projects()` caught error, returned `[]` → entire sidebar broke. Same for `_load_crawled_pages()`.
- **Fix** (commit bff58f8): Changed both queries to `SELECT *` instead of named columns. PostgREST returns whatever exists, `.get()` defaults handle missing fields.
- **Lesson**: After running ALTER TABLE migrations, either reload PostgREST schema cache (Supabase Dashboard > Settings > API) or use `SELECT *` for queries that include newly-added columns.

### Mar 12 2026 — Language detection bugfix
- **Bug**: English pages produced Norwegian arbeidspakker. Root cause: system prompt saturated with Norwegian template text biasing Sonnet.
- **Fix** (commit 41e7d37):
  - Language instruction moved to very top of system prompt (first thing model reads)
  - Hardcoded Norwegian removed from template: "Hovedfunn" → "Key findings", "Vanlige spørsmål om" → "Frequently asked questions about", "arbeidspakke" → "work package"
  - Language reminder added in user message right before page content
  - Rule #6 added to OUTPUT QUALITY RULES reinforcing language matching
- **Test expectation**: English page → English output, Norwegian page → Norwegian output
- **Only file changed**: `aeo/recommender.py`

### Mar 12 2026 — Arbeidspakke gold standard + Claude Sonnet 4 + date column
- **Safety tag**: `v2.0-working-2026-03-12` on pre-change state
- **3 commits pushed** (1dd3635, 2137644, f23ff12), auto-deploying to Streamlit Cloud

**Prompt rewrite** (commit 1dd3635):
- Rewrote system prompt in `aeo/recommender.py` to match Morten's gold standard (Fyresign example)
- 6-section structure: AEO priorities → Full page rewrite → FAQ rewrites → Technical (JSON-LD) → SEO → Checklist
- Language detection (Norwegian page = Norwegian output), full rewrites only, paste-ready for CMS
- Removed redundant `## Summary` heading from `aeo_ui.py` — arbeidspakke has its own structure
- Output format: markdown in `summary` field, empty arrays for legacy fields

**Model swap** (commit 2137644):
- GPT-4o-mini → Claude Sonnet 4 (`claude-sonnet-4-20250514`) via Anthropic SDK
- Split prompt into system/user messages for better prompt following
- Reads `ANTHROPIC_API_KEY` from st.secrets/env (added to Streamlit Cloud secrets)
- Added `anthropic>=0.40.0` to requirements.txt. OpenAI kept (used by analyzer.py)
- max_tokens: 16000, content window: 12000 chars
- ~$0.20/generation — quality > cost for the product's core deliverable

**Date column** (commit f23ff12):
- Added "Siste arbeidspakke" column to AI Analysis results table in `crawler/crawler_ui.py`
- Shows dd.mm.yyyy or "Aldri" — single DB query to `arbeidspakker`, deduplicated in Python

**Product Director decisions (Mar 12)**:
- Q1 Model: Claude Sonnet 4 — prompt gap was closing, but Sonnet's Norwegian + structured output is superior. $0.20/gen is irrelevant at current scale.
- Q2 Summary heading: Fixed — removed.
- Q3 Intelligence panel: Parked. Gold standard arbeidspakke is the deliverable. Verdicts were noise for target user (marketer executing work package).
- Q4 Language: Auto-detection sufficient. Norwegian agencies on Norwegian sites = primary use case.

### Mar 12 2026 — Usage event tracking
- **New module**: `tracking/usage_tracker.py` — fire-and-forget `log_usage_event()` helper
- **Migration**: `migrations/006_usage_events.sql` — NOT yet run. Pal must run manually in Supabase SQL editor.
- **Instrumented 7 call sites**:
  - `aeo/recommender.py`: `arbeidspakke_generation` — tokens + cost from Anthropic response
  - `crawler/ai_analyser.py`: `ai_analysis` — tokens from Perplexity response
  - `app.py`: `citation_check` (per batch), `login`, `tool_switch`
  - `crawler/crawler_ui.py`: `page_crawl` (per crawl run)
  - `google_data/datasources_ui.py`: `gsc_import`, `ga_import`
- All tracking is fire-and-forget (try/except, never raises). App works normally even if table doesn't exist.
- Cost formula for Sonnet: `(input_tokens * 3 + output_tokens * 15) / 1_000_000`
- **Blocker**: Run `migrations/006_usage_events.sql` in Supabase SQL editor before tracking works

### Mar 12 2026 — Page type system for AEO Agent
- **Migration**: `migrations/007_page_type.sql` — adds `page_type TEXT` column to `pages`. NOT yet run.
- **AEO Agent UI** (`aeo/aeo_ui.py`):
  - "Sidetype" dropdown between page selector and intent input
  - 8 page types: Forside, Produktside, Blogginnlegg, Landingsside, FAQ-side, Om oss, Kategoriside, Kontaktside
  - Pre-selects from stored `page_type` on `pages` table
  - Persists selection via PATCH to `pages` table (new `_db_patch` helper)
  - `page_type` added to `_load_crawled_pages` SELECT
  - Tracks `page_type_set` usage event
- **Recommender** (`aeo/recommender.py`):
  - New `page_type` param on `generate_recommendations()`
  - Page type context injected into system prompt between language rule and AEO methodology
  - Full guidance per type (e.g. homepage = no FAQ, blog = question-based H2s)
  - If no type set, AI infers from content and states inference in opening paragraph

### Mar 12 2026 — Persistent crawler page overview
- Added page overview section to Web Crawler (`crawler/crawler_ui.py`)
- Appears above crawl tabs when project is selected, loads from `pages` + `arbeidspakker` tables
- Collapsible expander: "Crawlede sider ({count})" with summary line "{X} sider crawlet | Sist crawl: {date}"
- Columns: URL, Tittel, Status, Sidetype, Sist crawlet, Siste arbeidspakke
- "Ingen sider crawlet ennå" message when empty
- Tracks `page_overview_loaded` usage event

### Mar 12 2026 — Intent persistence + domain-level universal context
- **Migration**: `migrations/008_intent_and_domain_context.sql` — adds `intent TEXT` to `pages`, `domain_context TEXT` to `projects`. RUN ✓
- **AEO Agent UI** (`aeo/aeo_ui.py`):
  - Intent pre-fills from stored `intent` column on `pages` table
  - Intent saved via PATCH to `pages` on Generate click (only if changed)
  - `domain_context` passed from `st.session_state["domain_context"]` to `generate_recommendations()`
  - `intent` added to `_load_crawled_pages` SELECT
- **App sidebar** (`app.py`):
  - "Prosjektinnstillinger" expander with domain context `text_area` + "Lagre" button
  - PATCH support added to `_make_rest_call()`
  - `domain_context` loaded with project data and stored in `st.session_state["domain_context"]`
- **Recommender** (`aeo/recommender.py`):
  - New `domain_context` param on `generate_recommendations()`
  - Domain context section injected into system prompt between page type and AEO methodology
  - Only injected if `domain_context` is non-empty
  - Instructs AI to ground all rewrites in the brand's identity, services, and positioning
- **Commit**: 75aa716, pushed, auto-deploying

**Next**:
- Run migrations 006 + 007 in Supabase SQL editor (008 done ✓)
- Test: page types, persistent crawler overview, language detection (English page → English output)
- Re-enable domain context + intent persistence after fixing Streamlit widget scoping (search `DISABLED:` in app.py + aeo/aeo_ui.py)
- Morten tests with real GSC/GA4 data (his Gmail needs adding as Google OAuth test user first)

### Mar 5 2026 — Arbeidspakker Library + AI Analysis CSV + Bugfix

### Mar 5 2026 — Arbeidspakker Library + AI Analysis CSV + Bugfix
- New module `arbeidspakker/arbeidspakker_ui.py` — central library of all work packages per project
- Added "Arbeidspakker" to sidebar tool selector (6 tools total)
- AI Analysis: added CSV export buttons (summary table + issues detail)
- Fixed `any()` TypeError in AI Analysis summary — was passing 3 args instead of a tuple
- Commits: 424deaa (library), ec01a6e (bugfix), 399f865 (CSV exports) — all pushed, auto-deployed
- **Morten was testing live** during session — bugfix was urgent
- **AEO Guide review**: Guide at `aeo/intelligence/aeo_guide.md` is solid for AI consumption. Identified gaps: multi-modal content signals, freshness/recency weighting, updated 2026 stats. Pal commissioning research.
- **Superadmin concept** (parked): Future — store AEO guide in Supabase, superadmin role on workspace_members, in-app editor panel

### Mar 5 2026 — Matrise: Prioritisation View
- New module `matrise/matrise_ui.py` — computed view, no new Supabase table
- Joins pages + crawl_ai_analysis + gsc_data + ga_data + arbeidspakker at runtime
- Priority score formula: AEO gap (40%) + SEO gap (20%) + traffic (25%) + engagement (15%)
- Colour-coded table with header row, expandable detail per page
- CSV export, Generate button (stub — switches tool to AEO Agent)
- Added "Matrise" to sidebar tool selector in `app.py`
- Unit tested: priority_score formula produces correct rankings
- **No migration needed** — reads existing tables only

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
