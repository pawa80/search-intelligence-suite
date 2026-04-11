"""Streamlit UI for the web crawler and sitemap checker."""

from __future__ import annotations

import streamlit as st
import pandas as pd
import io
import csv
from urllib.parse import urlparse

import json
from datetime import datetime, timezone, date
from crawler.crawler_engine import CrawlerEngine, check_url_list, CrawlResult
from crawler.sitemap_parser import fetch_sitemap_from_domain, check_sitemap_urls, SitemapEntry
from crawler.ai_analyser import analyse_page, save_analysis, MODEL


def _build_page_elements(r: CrawlResult) -> dict:
    """Build page_elements JSONB from crawl result."""
    # Parse H2 into list
    h2_list = []
    if r.seo.h2 and r.seo.h2 not in ("Missing", ""):
        h2_list = [h.strip() for h in r.seo.h2.split(" | ") if h.strip()]

    # Build OG tags dict
    og_tags = {}
    if r.seo.og_desc:
        og_tags["og:description"] = r.seo.og_desc
    if r.seo.og_url:
        og_tags["og:url"] = r.seo.og_url

    # Parse JSON-LD string into structured data
    json_ld = []
    if r.seo.jsonld:
        try:
            parsed = json.loads(r.seo.jsonld)
            if isinstance(parsed, list):
                json_ld = parsed
            elif isinstance(parsed, dict):
                json_ld = [parsed]
        except (json.JSONDecodeError, TypeError):
            json_ld = [{"raw": r.seo.jsonld[:500]}]

    return {
        "h2_structure": h2_list,
        "og_tags": og_tags,
        "json_ld": json_ld,
        "hero_image_alt": r.seo.hero_alt if r.seo.hero_alt not in ("Missing", "") else None,
        "referrer": r.referrer or None,
        "crawl_time_seconds": round(r.response_time, 2) if r.response_time else None,
        "content_text": r.content_text[:3000] if r.content_text else None,
    }


def _save_crawl_results(results: list[CrawlResult]) -> tuple[int, int]:
    """Save crawl results to pages table via UPSERT. Returns (saved, failed)."""
    from app import db_upsert

    project_id = st.session_state.get("crawler_project_id")
    token = st.session_state.get("access_token")
    if not project_id or not token:
        return 0, 0

    now = datetime.now(timezone.utc).isoformat()
    saved = 0
    failed = 0

    for r in results:
        try:
            # Set status based on HTTP response
            _page_status = "active"
            if r.status_code == 404:
                _page_status = "dead"
            elif r.status_code and r.status_code in (301, 302, 307, 308):
                _page_status = "redirected"

            db_upsert("pages", token, {
                "project_id": project_id,
                "url": r.url,
                "canonical_url": r.seo.canonical or None,
                "status_code": r.status_code,
                "status": _page_status,
                "title": r.title or None,
                "h1": r.seo.h1 if r.seo.h1 != "Missing" else None,
                "meta_description": r.seo.meta_desc or None,
                "depth": r.depth,
                "in_sitemap": r.in_sitemap == "Yes",
                "last_crawled_at": now,
                "page_elements": _build_page_elements(r),
            }, on_conflict="project_id,url")
            saved += 1
        except Exception:
            failed += 1

    return saved, failed


def _status_badge(code: int | None, error: str = "") -> str:
    if error:
        return f"ERR: {error}"
    if code is None:
        return "—"
    return str(code)


def _results_to_df(results: list[CrawlResult]) -> pd.DataFrame:
    """Convert crawl results to a DataFrame with all 15 columns."""
    rows = []
    for r in results:
        rows.append({
            "URL": r.url,
            "Title": r.title,
            "Status": _status_badge(r.status_code, r.error),
            "Depth": r.depth,
            "Referrer": r.referrer,
            "Time (s)": r.response_time,
            "Meta Desc": r.seo.meta_desc,
            "OG Desc": r.seo.og_desc,
            "H1": r.seo.h1,
            "H2": r.seo.h2,
            "Hero Alt": r.seo.hero_alt,
            "Canonical": r.seo.canonical,
            "OG URL": r.seo.og_url,
            "In Sitemap": r.in_sitemap,
            "JSON-LD": r.seo.jsonld[:150] if r.seo.jsonld else "",
        })
    return pd.DataFrame(rows)


def _df_to_csv(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.to_csv(buf, index=False, quoting=csv.QUOTE_ALL)
    return buf.getvalue()


def _ensure_scheme(url: str) -> str:
    if url and not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _get_domain_from_url(url: str) -> str:
    try:
        return urlparse(url).hostname or "unknown"
    except Exception:
        return "unknown"


def _load_page_overview(token: str, project_id: str) -> list[dict]:
    """Load all crawled pages for the persistent overview table."""
    from app import db_request
    try:
        return db_request("GET", "pages", token,
                          params={"select": "id,url,title,status_code,page_type,intent,h1,meta_description,canonical_url,in_sitemap,depth,last_crawled_at,page_elements",
                                  "project_id": f"eq.{project_id}",
                                  "status": "eq.active",
                                  "last_crawled_at": "not.is.null",
                                  "order": "url.asc"})
    except Exception:
        return []


def _show_page_overview(project_ctx: dict) -> None:
    """Show persistent page overview above the crawl tabs."""
    token = st.session_state.get("access_token")
    if not token:
        return

    project_id = project_ctx["id"]
    pages = _load_page_overview(token, project_id)

    if not pages:
        st.caption("No pages crawled yet. Start a crawl below.")
        return

    # Track usage
    try:
        from tracking.usage_tracker import log_usage_event
        log_usage_event("page_overview_loaded", event_detail=f"{len(pages)} pages", project_id=project_id)
    except Exception:
        pass

    # Load arbeidspakke dates
    ap_dates = _load_arbeidspakke_dates(token, project_id)

    # Find most recent crawl date
    last_crawl = ""
    for p in pages:
        raw = p.get("last_crawled_at", "")
        if raw and raw > last_crawl:
            last_crawl = raw
    try:
        last_crawl_fmt = datetime.fromisoformat(last_crawl.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except (ValueError, AttributeError):
        last_crawl_fmt = last_crawl[:10] if last_crawl else "—"

    with st.expander(f"Crawled pages ({len(pages)})", expanded=True):
        st.caption(f"{len(pages)} pages crawled | Last crawl: {last_crawl_fmt}")

        table_rows = []
        for p in pages:
            # Format last_crawled_at
            raw_crawl = p.get("last_crawled_at", "")
            try:
                crawl_fmt = datetime.fromisoformat(raw_crawl.replace("Z", "+00:00")).strftime("%d.%m.%Y")
            except (ValueError, AttributeError):
                crawl_fmt = raw_crawl[:10] if raw_crawl else "—"

            url = p.get("url", "")

            # Extract page_elements (JSONB — may be dict or JSON string)
            pe = p.get("page_elements") or {}
            if isinstance(pe, str):
                try:
                    pe = json.loads(pe)
                except (json.JSONDecodeError, TypeError):
                    pe = {}

            h2_list = pe.get("h2_structure") or []
            h2_display = " | ".join(h2_list[:3])
            if len(h2_list) > 3:
                h2_display += f" (+{len(h2_list) - 3})"

            og_tags = pe.get("og_tags") or {}
            og_desc = og_tags.get("og:description") or "\u2014"
            og_url = og_tags.get("og:url") or "\u2014"

            json_ld_list = pe.get("json_ld") or []
            json_ld_types = []
            for item in json_ld_list:
                if isinstance(item, dict) and "@type" in item:
                    json_ld_types.append(item["@type"])
            json_ld_display = ", ".join(json_ld_types) if json_ld_types else "\u2014"

            hero_alt = pe.get("hero_image_alt") or "\u2014"
            referrer = pe.get("referrer") or "\u2014"
            crawl_time = pe.get("crawl_time_seconds")
            time_display = f"{crawl_time:.1f}" if crawl_time is not None else "\u2014"

            table_rows.append({
                "URL": url[:60] + ("..." if len(url) > 60 else ""),
                "Title": (p.get("title") or "\u2014")[:50],
                "Status": p.get("status_code", "\u2014"),
                "Depth": p.get("depth") if p.get("depth") is not None else "\u2014",
                "Referrer": referrer[:40] if referrer != "\u2014" else "\u2014",
                "Time (s)": time_display,
                "Meta Desc": (p.get("meta_description") or "\u2014")[:40],
                "OG Desc": og_desc[:40] if og_desc != "\u2014" else "\u2014",
                "H1": (p.get("h1") or "\u2014")[:40],
                "H2": h2_display[:50] if h2_display else "\u2014",
                "Hero Alt": hero_alt[:40] if hero_alt != "\u2014" else "\u2014",
                "Canonical": (p.get("canonical_url") or "\u2014")[:40],
                "OG URL": og_url[:40] if og_url != "\u2014" else "\u2014",
                "In Sitemap": "Yes" if p.get("in_sitemap") else "No" if p.get("in_sitemap") is False else "\u2014",
                "JSON-LD": json_ld_display[:40],
                "Page Type": p.get("page_type") or "\u2014",
                "Intent": (p.get("intent") or "\u2014")[:40],
                "Last Crawled": crawl_fmt,
                "Last Playbook": ap_dates.get(p.get("id"), "Never"),
            })

        st.dataframe(table_rows, use_container_width=True, hide_index=True)


_ROLE_COLOURS = {
    "entity_anchor": "🟣",
    "citation_target": "🟢",
    "authority_builder": "🔵",
    "conversion_endpoint": "🟠",
    "cannibal_overlap": "🔴",
}


def _show_domain_strategy(project_ctx: dict) -> None:
    """Show domain strategy section — generate or display."""
    try:
        from app import db_request
        from domain_strategy.strategy_generator import (
            generate_domain_strategy, save_domain_strategy,
        )
    except Exception as e:
        st.divider()
        st.error(f"Domain Strategy module failed to load: {e}")
        return

    token = st.session_state.get("access_token")
    if not token:
        return

    project_id = project_ctx["id"]

    # Fetch current strategy from project
    try:
        projects = db_request("GET", "projects", token,
                              params={"select": "domain_strategy,domain_strategy_generated_at",
                                      "id": f"eq.{project_id}"})
        proj_data = projects[0] if projects else {}
    except Exception as e:
        st.divider()
        st.error(f"Failed to load project strategy: {e}")
        proj_data = {}

    strategy = proj_data.get("domain_strategy") or {}
    if isinstance(strategy, str):
        try:
            strategy = json.loads(strategy)
        except (json.JSONDecodeError, TypeError):
            strategy = {}
    generated_at = proj_data.get("domain_strategy_generated_at")

    st.divider()

    has_strategy = bool(strategy and strategy.get("page_roles") and not strategy.get("parse_error"))
    _op_locked = st.session_state.get("operation_in_progress", False)

    if has_strategy:
        # Format date
        try:
            gen_date = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).strftime("%d %b %Y %H:%M")
        except (ValueError, AttributeError, TypeError):
            gen_date = str(generated_at)[:16] if generated_at else "unknown"

        summary = strategy.get("domain_summary", {})
        n_roles = len(strategy.get("page_roles", []))
        n_cannibal = len(strategy.get("cannibalisation", []))
        n_gaps = len(strategy.get("gaps", []))

        st.markdown(f"**Domain Strategy** (generated {gen_date})")
        st.caption(summary.get("business_description", ""))
        st.caption(
            f"Page roles assigned: {n_roles} · "
            f"Cannibalisation warnings: {n_cannibal} · "
            f"Content gaps identified: {n_gaps}"
        )

        with st.expander("View full strategy"):
            # Page roles table
            st.markdown("**Page Roles**")
            role_rows = []
            for pr in strategy.get("page_roles", []):
                icon = _ROLE_COLOURS.get(pr.get("role"), "⬜")
                role_rows.append({
                    "URL": (pr.get("url") or "")[:50],
                    "Role": f"{icon} {pr.get('role', '').replace('_', ' ')}",
                    "Reasoning": (pr.get("reasoning") or "")[:80],
                })
            if role_rows:
                st.dataframe(role_rows, use_container_width=True, hide_index=True)

            # Cannibalisation warnings
            cannibals = strategy.get("cannibalisation", [])
            if cannibals:
                st.markdown("**Cannibalisation Warnings**")
                for c in cannibals:
                    urls = ", ".join(c.get("urls", []))
                    st.warning(f"**{urls}**\nShared queries: {', '.join(c.get('shared_queries', []))}\n{c.get('recommendation', '')}")

            # Content gaps
            gaps = strategy.get("gaps", [])
            if gaps:
                st.markdown("**Content Gaps**")
                for g in gaps:
                    prio = g.get("priority", "medium")
                    icon = "🔴" if prio == "high" else "🟡" if prio == "medium" else "🟢"
                    st.info(f"{icon} **{g.get('missing_topic', '')}** ({prio})\n{g.get('reasoning', '')}")

            # Strategic rules
            rules = strategy.get("strategic_rules", [])
            if rules:
                st.markdown("**Strategic Rules** (applied to all playbooks)")
                for rule in rules:
                    st.markdown(f"- {rule}")

        if st.button("Regenerate Strategy", key=f"btn_regen_strategy_{project_id}",
                      disabled=_op_locked):
            _run_strategy_generation(project_ctx, token)

    elif strategy.get("parse_error"):
        st.markdown("**Domain Strategy** (parse error)")
        st.warning("Strategy was generated but could not be parsed automatically.")
        with st.expander("View raw strategy"):
            st.code(strategy.get("raw_text", ""), language=None)
        if st.button("Regenerate Strategy", key=f"btn_regen_strategy_{project_id}",
                      disabled=_op_locked):
            _run_strategy_generation(project_ctx, token)

    else:
        # No strategy yet
        pages = _load_page_overview(token, project_id)
        n_pages = len(pages)
        if n_pages > 0:
            st.markdown("**Domain Strategy**")
            st.caption(
                f"No domain strategy generated yet. Generate a holistic AEO strategy based on your "
                f"{n_pages} crawled pages. This will assign each page a strategic role and ensure "
                f"your playbooks are differentiated — not generic."
            )
            if st.button("Generate Domain Strategy", type="primary",
                          key=f"btn_gen_strategy_{project_id}", disabled=_op_locked):
                _run_strategy_generation(project_ctx, token)


def _run_strategy_generation(project_ctx: dict, token: str) -> None:
    """Execute domain strategy generation with UI lock."""
    from app import db_request
    from domain_strategy.strategy_generator import (
        generate_domain_strategy, save_domain_strategy,
    )

    project_id = project_ctx["id"]

    st.session_state["operation_in_progress"] = True
    _strategy_saved = False
    try:
        # Load all data needed for strategy
        pages = _load_page_overview(token, project_id)
        if not pages:
            st.warning("No crawled pages. Run a crawl first.")
            return

        # Load AI analyses
        analyses = _load_existing_analyses(token, project_id)

        # Load playbook counts per page
        try:
            ap_rows = db_request("GET", "arbeidspakker", token,
                                 params={"select": "page_id",
                                         "project_id": f"eq.{project_id}"})
            playbook_counts: dict[str, int] = {}
            for row in ap_rows:
                pid = row.get("page_id")
                if pid:
                    playbook_counts[pid] = playbook_counts.get(pid, 0) + 1
        except Exception:
            playbook_counts = {}

        with st.spinner(f"Analysing {len(pages)} pages holistically..."):
            strategy = generate_domain_strategy(project_ctx, pages, analyses, playbook_counts)

        if strategy:
            saved = save_domain_strategy(token, project_id, strategy)
            if saved:
                st.success("Domain strategy generated and saved.")
                # Clear stale caches so overview + banner pick up new strategy
                st.session_state.pop(f"_domain_strategy_{project_id}", None)
                st.session_state.pop(f"_overview_data_{project_id}", None)
                _strategy_saved = True
            else:
                st.warning("Strategy generated but failed to save.")
        else:
            st.error("Strategy generation failed.")
    except Exception as _strat_err:
        st.error(f"Strategy generation error: {_strat_err}")
    finally:
        st.session_state["operation_in_progress"] = False
    # Rerun AFTER finally has released the lock
    if _strategy_saved:
        st.rerun()


def show_crawler(project_ctx: dict | None = None):
    """Main entry point for the crawler UI."""
    st.title("Crawl")

    # Project context banner
    if project_ctx:
        st.info(f"Crawling as part of: **{project_ctx['name']}**")
        st.session_state["crawler_project_id"] = project_ctx["id"]
        st.session_state["crawler_project_domain"] = project_ctx.get("domain", "")
    else:
        st.warning("No project selected. Results won't be saved.")
        st.session_state["crawler_project_id"] = None
        st.session_state["crawler_project_domain"] = ""

    # Persistent page overview (loads from Supabase)
    if project_ctx:
        _show_page_overview(project_ctx)
        _show_domain_strategy(project_ctx)

    tab_crawl, tab_sitemap, tab_ai = st.tabs(["Web Crawl", "Sitemap Check", "AI Analysis"])

    with tab_crawl:
        _show_web_crawl()

    with tab_sitemap:
        _show_sitemap_check()

    with tab_ai:
        _show_ai_analysis(project_ctx)


def _show_web_crawl():
    mode = st.radio("Mode", ["Crawl from URL", "Check URL list"], horizontal=True,
                    key="crawl_mode")

    if mode == "Crawl from URL":
        _show_crawl_from_url()
    else:
        _show_check_url_list()


def _show_crawl_from_url():
    default_domain = st.session_state.get("crawler_project_domain", "")
    if default_domain.startswith(("http://", "https://")):
        default_url = default_domain
    else:
        default_url = f"https://{default_domain}" if default_domain else ""

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        start_url = st.text_input("Starting URL", value=default_url,
                                  placeholder="https://example.com",
                                  key="crawl_start_url")
    with col2:
        max_depth = st.number_input("Max depth", min_value=1, max_value=20, value=10,
                                    key="crawl_max_depth")
    with col3:
        max_pages = st.number_input("Max pages", min_value=1, max_value=2000, value=200,
                                    key="crawl_max_pages")

    skip_dupes = st.checkbox("Skip duplicates", value=True, key="crawl_skip_dupes")

    if max_pages > 100:
        st.caption("Large crawls can take a while. Refresh the page to stop at any time — partial results are saved.")

    col_start, col_clear = st.columns([1, 5])
    with col_start:
        run = st.button("Start Crawl", type="primary", key="btn_start_crawl")
    with col_clear:
        if st.button("Clear Results", key="btn_clear_crawl"):
            st.session_state.pop("crawl_results", None)
            st.rerun()

    if run and start_url:
        url = _ensure_scheme(start_url.strip())
        engine = CrawlerEngine(url, max_depth=max_depth, max_pages=max_pages,
                               skip_duplicates=skip_dupes)

        st.session_state["operation_in_progress"] = True
        try:
            # Background: fetch sitemap for cross-reference lookup (does NOT guide the crawl)
            sitemap_status = st.empty()
            sitemap_status.info("Loading sitemap.xml for cross-reference...")

            stats_container = st.empty()
            current_url = st.empty()
            progress_bar = st.progress(0)
            results_container = st.empty()

            results: list[CrawlResult] = []
            for result in engine.crawl():
                # Clear sitemap status after first result
                if len(results) == 0:
                    sitemap_count = len(engine.sitemap_urls)
                    if sitemap_count > 0:
                        sitemap_status.success(f"Sitemap loaded: {sitemap_count} URLs found")
                    else:
                        sitemap_status.warning("No sitemap found — 'In Sitemap' will show N/A")

                results.append(result)
                # Save partial results so they survive if user stops (refreshes/clicks away)
                st.session_state["crawl_results"] = results
                s = engine.stats
                stats_container.markdown(
                    f"**Discovered:** {s['discovered']} · "
                    f"**Processed:** {s['processed']} · "
                    f"**Queue:** {s['queue']} · "
                    f"**Duplicates skipped:** {s['duplicates_skipped']}"
                )
                current_url.caption(f"Crawling: {result.url}")
                progress_bar.progress(min(len(results) / max_pages, 1.0))
                df = _results_to_df(results)
                results_container.dataframe(df, use_container_width=True, hide_index=True)

            progress_bar.empty()
            current_url.empty()
            st.session_state["crawl_results"] = results
            st.success(f"Done! Crawled {len(results)} pages.")

            # Track usage
            try:
                from tracking.usage_tracker import log_usage_event
                log_usage_event(
                    event_type="page_crawl",
                    event_detail=f"{len(results)} pages crawled",
                )
            except Exception:
                pass

            # Save to Supabase if project is selected
            if results and st.session_state.get("crawler_project_id"):
                saved, failed = _save_crawl_results(results)
                if failed == 0:
                    st.success(f"Saved {saved} pages to project.")
                else:
                    st.warning(f"Saved {saved} pages, {failed} failed.")

            # Show export immediately
            if results:
                df = _results_to_df(results)
                domain = _get_domain_from_url(results[0].url)
                _show_results_with_export(df, "crawl", f"{domain}-crawl-results")
        finally:
            st.session_state["operation_in_progress"] = False

    # Show previous results if available
    elif "crawl_results" in st.session_state:
        results = st.session_state["crawl_results"]
        if results:
            df = _results_to_df(results)
            domain = _get_domain_from_url(results[0].url)
            _show_results_with_export(df, "crawl", f"{domain}-crawl-results")


def _show_check_url_list():
    url_text = st.text_area("Paste URLs (one per line)", height=200,
                            key="url_list_input")

    col_start, col_clear = st.columns([1, 5])
    with col_start:
        run = st.button("Check URLs", type="primary", key="btn_check_urls")
    with col_clear:
        if st.button("Clear Results", key="btn_clear_url_list"):
            st.session_state.pop("url_list_results", None)
            st.rerun()

    if run and url_text:
        urls = [_ensure_scheme(u.strip()) for u in url_text.strip().split("\n")
                if u.strip()]
        if not urls:
            st.warning("No valid URLs found.")
            return

        st.session_state["operation_in_progress"] = True
        try:
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.empty()
            results: list[CrawlResult] = []

            for i, result in enumerate(check_url_list(urls)):
                results.append(result)
                progress_bar.progress((i + 1) / len(urls))
                status_text.caption(f"Checking {i + 1}/{len(urls)}: {result.url}")
                df = _results_to_df(results)
                results_container.dataframe(df, use_container_width=True, hide_index=True)

            progress_bar.empty()
            status_text.empty()
            st.session_state["url_list_results"] = results
            st.success(f"Done! Checked {len(results)} URLs.")
        finally:
            st.session_state["operation_in_progress"] = False
        if results:
            df = _results_to_df(results)
            _show_results_with_export(df, "url_list", "url-check-results")

    elif "url_list_results" in st.session_state:
        results = st.session_state["url_list_results"]
        if results:
            df = _results_to_df(results)
            _show_results_with_export(df, "url_list", "url-check-results")


def _show_sitemap_check():
    domain_input = st.text_input("Domain or URL",
                                 placeholder="https://example.com or example.com",
                                 key="sitemap_domain_input")

    col_start, col_clear = st.columns([1, 5])
    with col_start:
        run = st.button("Check Sitemap", type="primary", key="btn_check_sitemap")
    with col_clear:
        if st.button("Clear Results", key="btn_clear_sitemap"):
            st.session_state.pop("sitemap_results", None)
            st.rerun()

    if run and domain_input:
        # Extract domain from URL or use as-is
        raw = domain_input.strip()
        try:
            parsed = urlparse(_ensure_scheme(raw))
            domain = parsed.hostname or raw
        except Exception:
            domain = raw

        status_text = st.empty()
        status_text.info(f"Fetching sitemap.xml for {domain}...")

        # Fetch sitemap entries
        entries = list(fetch_sitemap_from_domain(domain))

        if not entries:
            status_text.error(f"No URLs found in sitemap for {domain}")
            return

        status_text.success(f"Found {len(entries)} URLs in sitemap. Checking status...")

        # Always check HTTP status (like the original)
        stats_container = st.empty()
        progress_bar = st.progress(0)
        current_url = st.empty()
        results_container = st.empty()
        checked: list[SitemapEntry] = []

        for i, entry in enumerate(check_sitemap_urls(entries)):
            checked.append(entry)
            progress_bar.progress((i + 1) / len(entries))
            current_url.caption(f"Checking {i + 1}/{len(entries)}: {entry.url}")
            stats_container.markdown(
                f"**Discovered:** {len(entries)} · "
                f"**Processed:** {len(checked)} · "
                f"**Queue:** {len(entries) - len(checked)}"
            )
            df = _sitemap_to_df(checked)
            results_container.dataframe(df, use_container_width=True, hide_index=True)

        progress_bar.empty()
        current_url.empty()
        status_text.success(f"Done! Found {len(checked)} URLs in sitemap.")
        st.session_state["sitemap_results"] = checked
        if checked:
            domain = _get_domain_from_url(checked[0].url)
            df = _sitemap_to_df(checked)
            _show_results_with_export(df, "sitemap", f"{domain}-sitemap")

    elif "sitemap_results" in st.session_state:
        entries = st.session_state["sitemap_results"]
        if entries:
            domain = _get_domain_from_url(entries[0].url) if entries else "unknown"
            df = _sitemap_to_df(entries)
            _show_results_with_export(df, "sitemap", f"{domain}-sitemap")


def _sitemap_to_df(entries: list[SitemapEntry]) -> pd.DataFrame:
    rows = []
    for e in entries:
        rows.append({
            "URL": e.url,
            "Status": _status_badge(e.status_code, e.error),
            "Last Modified": e.lastmod or "—",
            "Change Freq": e.changefreq or "—",
            "Priority": e.priority or "—",
        })
    return pd.DataFrame(rows)


def _show_results_with_export(df: pd.DataFrame, key_prefix: str, filename: str = "results"):
    """Display results table with filter, CSV export and clipboard copy."""
    # Filter
    filter_text = st.text_input("Filter URLs", placeholder="Type to filter...",
                                key=f"{key_prefix}_filter")
    if filter_text:
        mask = df["URL"].str.contains(filter_text, case=False, na=False)
        df = df[mask]

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(df)} results")

    # Export
    col_csv, col_copy = st.columns([1, 1])
    csv_data = _df_to_csv(df)
    with col_csv:
        from datetime import date
        fname = f"{filename}-{date.today().isoformat()}.csv"
        st.download_button("Download CSV", data=csv_data, file_name=fname,
                           mime="text/csv", key=f"{key_prefix}_csv_dl")
    with col_copy:
        if st.button("Copy to clipboard", key=f"{key_prefix}_copy"):
            tsv = df.to_csv(sep="\t", index=False)
            st.code(tsv, language=None)
            st.caption("Select all and copy (Ctrl+A, Ctrl+C)")


# --- AI Analysis tab ---

def _score_badge(score: int | None) -> str:
    """Return score with colour emoji indicator."""
    if score is None:
        return "—"
    if score >= 75:
        return f"🟢 {score}"
    if score >= 50:
        return f"🟡 {score}"
    return f"🔴 {score}"


def _load_crawled_pages(token: str, project_id: str) -> list[dict]:
    """Load pages that have been crawled (last_crawled_at IS NOT NULL)."""
    from app import db_request
    try:
        return db_request("GET", "pages", token,
                          params={"select": "id,project_id,url,status_code,title,h1,meta_description,word_count,in_sitemap,canonical_url,depth",
                                  "project_id": f"eq.{project_id}",
                                  "status": "eq.active",
                                  "last_crawled_at": "not.is.null",
                                  "order": "url.asc"})
    except Exception:
        return []


def _load_existing_analyses(token: str, project_id: str) -> dict[str, dict]:
    """Load existing AI analyses keyed by page_id."""
    from app import db_request
    try:
        rows = db_request("GET", "crawl_ai_analysis", token,
                          params={"select": "page_id,seo_score,aeo_readiness_score,content_quality_score,issues,priority_action,action_plan,analysed_at",
                                  "project_id": f"eq.{project_id}"})
        return {r["page_id"]: r for r in rows}
    except Exception:
        return {}


def _load_arbeidspakke_dates(token: str, project_id: str) -> dict[str, str]:
    """Load most recent arbeidspakke date per page_id. Returns {page_id: 'dd.mm.yyyy'}."""
    from app import db_request
    try:
        rows = db_request("GET", "arbeidspakker", token,
                          params={"select": "page_id,generated_at",
                                  "project_id": f"eq.{project_id}",
                                  "order": "generated_at.desc"})
        # Keep only the most recent per page_id
        latest = {}
        for r in rows:
            pid = r.get("page_id")
            if pid and pid not in latest:
                raw = r.get("generated_at", "")
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    latest[pid] = dt.strftime("%d.%m.%Y")
                except (ValueError, AttributeError):
                    latest[pid] = raw[:10] if raw else "—"
        return latest
    except Exception:
        return {}


def _show_ai_analysis(project_ctx: dict | None) -> None:
    """AI Analysis tab content."""
    if not project_ctx:
        st.warning("Select a project to use AI Analysis.")
        return

    token = st.session_state.get("access_token")
    if not token:
        st.warning("Not authenticated.")
        return

    import os
    api_key = None
    try:
        api_key = st.secrets["PERPLEXITY_API_KEY"]
    except (KeyError, FileNotFoundError):
        api_key = os.getenv("PERPLEXITY_API_KEY")

    if not api_key:
        st.error("PERPLEXITY_API_KEY not configured.")
        return

    project_id = project_ctx["id"]
    supabase_url = ""
    anon_key = ""
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        anon_key = st.secrets["SUPABASE_ANON_KEY"]
    except (KeyError, FileNotFoundError):
        supabase_url = os.getenv("SUPABASE_URL", "")
        anon_key = os.getenv("SUPABASE_ANON_KEY", "")

    # Load data
    pages = _load_crawled_pages(token, project_id)
    if not pages:
        st.info("No crawled pages found for this project. Run a crawl first, then return here.")
        return

    analyses = _load_existing_analyses(token, project_id)
    arbeidspakke_dates = _load_arbeidspakke_dates(token, project_id)
    analysed_ids = set(analyses.keys())
    page_ids = set(p["id"] for p in pages)
    unanalysed = [p for p in pages if p["id"] not in analysed_ids]

    # Stats
    st.markdown(f"**Pages available for analysis:** {len(pages)} total crawled pages")
    col1, col2 = st.columns(2)
    col1.metric("Already analysed", len(analysed_ids & page_ids))
    col2.metric("Not yet analysed", len(unanalysed))

    # Action buttons
    col_btn1, col_btn2, col_spacer = st.columns([2, 2, 4])
    with col_btn1:
        run_new = st.button("Run AI Analysis on Unanalysed Pages", type="primary",
                            key="btn_ai_analyse_new", disabled=len(unanalysed) == 0)
    with col_btn2:
        run_all = st.button("Re-analyse All Pages", key="btn_ai_analyse_all")

    # Run analysis
    pages_to_analyse = None
    if run_new and unanalysed:
        pages_to_analyse = unanalysed
    elif run_all:
        pages_to_analyse = pages

    if pages_to_analyse:
        st.session_state["operation_in_progress"] = True
        try:
            total = len(pages_to_analyse)
            progress_bar = st.progress(0)
            status_text = st.empty()
            succeeded = 0
            failed = 0

            for i, page in enumerate(pages_to_analyse):
                status_text.text(f"Analysing {i + 1} of {total} pages: {page['url'][:60]}...")
                progress_bar.progress((i + 1) / total)

                result = analyse_page(page, api_key)
                if result:
                    ok = save_analysis(result, page["id"], project_id,
                                       supabase_url, anon_key, token)
                    if ok:
                        succeeded += 1
                    else:
                        failed += 1
                else:
                    failed += 1

                # Rate limit — 1s between requests
                if i < total - 1:
                    import time
                    time.sleep(1)

            progress_bar.empty()
            status_text.empty()

            if failed == 0:
                st.success(f"Done! Analysed {succeeded}/{total} pages.")
            else:
                st.warning(f"Done. {succeeded} succeeded, {failed} failed.")
        finally:
            st.session_state["operation_in_progress"] = False

        # Reload analyses after run
        analyses = _load_existing_analyses(token, project_id)

    # Display results
    if analyses:
        st.divider()

        # Summary metrics
        scores_seo = [a["seo_score"] for a in analyses.values() if a.get("seo_score") is not None]
        scores_aeo = [a["aeo_readiness_score"] for a in analyses.values() if a.get("aeo_readiness_score") is not None]
        scores_content = [a["content_quality_score"] for a in analyses.values() if a.get("content_quality_score") is not None]
        needs_attention = sum(1 for a in analyses.values()
                              if any(((a.get("seo_score") or 0) < 50,
                                      (a.get("aeo_readiness_score") or 0) < 50,
                                      (a.get("content_quality_score") or 0) < 50)))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Avg SEO Score", f"{sum(scores_seo) / len(scores_seo):.0f}" if scores_seo else "—")
        m2.metric("Avg AEO Readiness", f"{sum(scores_aeo) / len(scores_aeo):.0f}" if scores_aeo else "—")
        m3.metric("Avg Content Quality", f"{sum(scores_content) / len(scores_content):.0f}" if scores_content else "—")
        m4.metric("Needs Attention", needs_attention)

        st.divider()

        # Build page URL lookup
        page_url_lookup = {p["id"]: p["url"] for p in pages}

        # --- Build CSV data for exports ---
        _summary_rows = []
        _detail_rows = []
        for page_id, a in analyses.items():
            _url = page_url_lookup.get(page_id, "Unknown")
            _summary_rows.append({
                "URL": _url,
                "SEO Score": a.get("seo_score", ""),
                "AEO Readiness Score": a.get("aeo_readiness_score", ""),
                "Content Quality Score": a.get("content_quality_score", ""),
                "Priority Action": a.get("priority_action", ""),
                "Action Plan": a.get("action_plan", ""),
                "Analysed": (a.get("analysed_at") or "")[:10],
            })
            issues = a.get("issues", [])
            if isinstance(issues, str):
                try:
                    issues = json.loads(issues)
                except (json.JSONDecodeError, TypeError):
                    issues = []
            for issue in (issues or []):
                _detail_rows.append({
                    "URL": _url,
                    "SEO Score": a.get("seo_score", ""),
                    "AEO Score": a.get("aeo_readiness_score", ""),
                    "Content Score": a.get("content_quality_score", ""),
                    "Issue Type": issue.get("type", ""),
                    "Severity": issue.get("severity", ""),
                    "Description": issue.get("description", ""),
                })

        _summary_rows.sort(key=lambda x: x.get("SEO Score") or 999)
        _detail_rows.sort(key=lambda x: (x.get("SEO Score") or 999, x.get("Severity", "")))

        def _to_csv(rows: list[dict]) -> str:
            if not rows:
                return ""
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
            return buf.getvalue()

        _domain_slug = project_ctx.get("domain", "site").replace("https://", "").replace("http://", "").rstrip("/").replace("/", "_")
        _date_str = date.today().isoformat()

        dl1, dl2, _ = st.columns([1, 1, 3])
        dl1.download_button(
            "Export Summary CSV",
            data=_to_csv(_summary_rows),
            file_name=f"ai-analysis-summary-{_domain_slug}-{_date_str}.csv",
            mime="text/csv",
            key="btn_ai_summary_csv",
        )
        dl2.download_button(
            "Export Issues CSV",
            data=_to_csv(_detail_rows) if _detail_rows else "No issues found",
            file_name=f"ai-analysis-issues-{_domain_slug}-{_date_str}.csv",
            mime="text/csv",
            key="btn_ai_issues_csv",
        )

        # Results table
        st.subheader("Analysis Results")
        table_data = []
        for page_id, a in analyses.items():
            table_data.append({
                "URL": page_url_lookup.get(page_id, "Unknown"),
                "SEO Score": _score_badge(a.get("seo_score")),
                "AEO Score": _score_badge(a.get("aeo_readiness_score")),
                "Content Score": _score_badge(a.get("content_quality_score")),
                "Priority Action": a.get("priority_action", "—"),
                "Last Analysed": (a.get("analysed_at") or "")[:10],
                "Last Playbook": arbeidspakke_dates.get(page_id, "Never"),
            })

        # Sort by SEO score ascending (worst first)
        table_data.sort(key=lambda x: int(x["SEO Score"].split()[-1]) if x["SEO Score"] != "—" else 999)
        st.dataframe(table_data, use_container_width=True, hide_index=True)

        # Expandable details per page
        st.divider()
        st.subheader("Detailed Issues")
        for page_id, a in analyses.items():
            url = page_url_lookup.get(page_id, "Unknown")
            with st.expander(f"{url}"):
                col_s1, col_s2, col_s3 = st.columns(3)
                col_s1.markdown(f"**SEO:** {_score_badge(a.get('seo_score'))}")
                col_s2.markdown(f"**AEO:** {_score_badge(a.get('aeo_readiness_score'))}")
                col_s3.markdown(f"**Content:** {_score_badge(a.get('content_quality_score'))}")

                st.markdown(f"**Priority Action:** {a.get('priority_action', '—')}")
                st.markdown(f"**Action Plan:** {a.get('action_plan', '—')}")

                issues = a.get("issues", [])
                if isinstance(issues, str):
                    try:
                        issues = json.loads(issues)
                    except (json.JSONDecodeError, TypeError):
                        issues = []
                if issues:
                    st.markdown("**Issues:**")
                    for issue in issues:
                        severity = issue.get("severity", "").lower()
                        icon = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
                        st.markdown(f"- {icon} **{issue.get('type', '')}**: {issue.get('description', '')}")
