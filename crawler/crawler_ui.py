"""Streamlit UI for the web crawler and sitemap checker."""

from __future__ import annotations

import streamlit as st
import pandas as pd
import io
import csv
from urllib.parse import urlparse

from crawler.crawler_engine import CrawlerEngine, check_url_list, CrawlResult
from crawler.sitemap_parser import fetch_sitemap_from_domain, check_sitemap_urls, SitemapEntry


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


def show_crawler(project_ctx: dict | None = None):
    """Main entry point for the crawler UI."""
    st.title("Web Crawler")

    # Project context banner
    if project_ctx:
        st.info(f"Crawling as part of: **{project_ctx['name']}**")
        st.session_state["crawler_project_id"] = project_ctx["id"]
    else:
        st.warning("No project selected. Results won't be saved.")
        st.session_state["crawler_project_id"] = None

    tab_crawl, tab_sitemap = st.tabs(["Web Crawl", "Sitemap Check"])

    with tab_crawl:
        _show_web_crawl()

    with tab_sitemap:
        _show_sitemap_check()


def _show_web_crawl():
    mode = st.radio("Mode", ["Crawl from URL", "Check URL list"], horizontal=True,
                    key="crawl_mode")

    if mode == "Crawl from URL":
        _show_crawl_from_url()
    else:
        _show_check_url_list()


def _show_crawl_from_url():
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        start_url = st.text_input("Starting URL", placeholder="https://example.com",
                                  key="crawl_start_url")
    with col2:
        max_depth = st.number_input("Max depth", min_value=1, max_value=20, value=10,
                                    key="crawl_max_depth")
    with col3:
        max_pages = st.number_input("Max pages", min_value=1, max_value=2000, value=20,
                                    key="crawl_max_pages")

    skip_dupes = st.checkbox("Skip duplicates", value=True, key="crawl_skip_dupes")

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
        # Show export immediately
        if results:
            df = _results_to_df(results)
            domain = _get_domain_from_url(results[0].url)
            _show_results_with_export(df, "crawl", f"{domain}-crawl-results")

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
