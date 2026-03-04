"""Streamlit UI for the web crawler and sitemap checker."""

import streamlit as st
import pandas as pd
import io
import csv
from urllib.parse import urlparse

from crawler.crawler_engine import CrawlerEngine, check_url_list, CrawlResult
from crawler.sitemap_parser import fetch_sitemap, check_sitemap_urls, SitemapEntry


def _status_color(code: int | None) -> str:
    if code is None:
        return "gray"
    if 200 <= code < 300:
        return "green"
    if 300 <= code < 400:
        return "orange"
    if 400 <= code < 500:
        return "red"
    return "darkred"


def _status_badge(code: int | None, error: str = "") -> str:
    if error:
        return f"ERR: {error}"
    if code is None:
        return "—"
    return str(code)


def _results_to_df(results: list[CrawlResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "URL": r.url,
            "Status": _status_badge(r.status_code, r.error),
            "Title": r.title,
            "Depth": r.depth,
            "Referrer": r.referrer,
            "Time (s)": r.response_time,
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


def show_crawler():
    """Main entry point for the crawler UI."""
    st.title("Web Crawler")

    tab_crawl, tab_sitemap = st.tabs(["Web Crawl", "Sitemap Check"])

    with tab_crawl:
        _show_web_crawl()

    with tab_sitemap:
        _show_sitemap_check()


def _show_web_crawl():
    # Input mode toggle
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
        max_depth = st.number_input("Max depth", min_value=1, max_value=5, value=2,
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

        stats_container = st.empty()
        current_url = st.empty()
        progress_bar = st.progress(0)
        results_container = st.empty()

        results: list[CrawlResult] = []
        for result in engine.crawl():
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

    # Show previous results if available
    if "crawl_results" in st.session_state and not run:
        results = st.session_state["crawl_results"]
        if results:
            df = _results_to_df(results)
            _show_results_with_export(df, "crawl")


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

    if "url_list_results" in st.session_state and not run:
        results = st.session_state["url_list_results"]
        if results:
            df = _results_to_df(results)
            _show_results_with_export(df, "url_list")


def _show_sitemap_check():
    col1, col2 = st.columns([3, 1])
    with col1:
        sitemap_url = st.text_input("Sitemap URL", placeholder="https://example.com/sitemap.xml",
                                    key="sitemap_url_input")
    with col2:
        check_status = st.checkbox("Check HTTP status", value=False,
                                   key="sitemap_check_status")

    col_start, col_clear = st.columns([1, 5])
    with col_start:
        run = st.button("Parse Sitemap", type="primary", key="btn_parse_sitemap")
    with col_clear:
        if st.button("Clear Results", key="btn_clear_sitemap"):
            st.session_state.pop("sitemap_results", None)
            st.rerun()

    if run and sitemap_url:
        url = _ensure_scheme(sitemap_url.strip())
        with st.spinner("Fetching sitemap..."):
            entries = list(fetch_sitemap(url))

        if not entries:
            st.warning("No URLs found in sitemap. Check the URL is correct.")
            return

        st.success(f"Found {len(entries)} URLs in sitemap.")

        if check_status:
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.empty()
            checked: list[SitemapEntry] = []

            for i, entry in enumerate(check_sitemap_urls(entries)):
                checked.append(entry)
                progress_bar.progress((i + 1) / len(entries))
                status_text.caption(f"Checking {i + 1}/{len(entries)}: {entry.url}")
                df = _sitemap_to_df(checked)
                results_container.dataframe(df, use_container_width=True, hide_index=True)

            progress_bar.empty()
            status_text.empty()
            st.session_state["sitemap_results"] = checked
        else:
            st.session_state["sitemap_results"] = entries

    if "sitemap_results" in st.session_state and not run:
        entries = st.session_state["sitemap_results"]
        if entries:
            df = _sitemap_to_df(entries)
            _show_results_with_export(df, "sitemap")


def _sitemap_to_df(entries: list[SitemapEntry]) -> pd.DataFrame:
    rows = []
    for e in entries:
        row = {
            "URL": e.url,
            "Last Modified": e.lastmod or "—",
            "Change Freq": e.changefreq or "—",
            "Priority": e.priority or "—",
        }
        if e.status_code is not None or e.error:
            row["Status"] = _status_badge(e.status_code, e.error)
        rows.append(row)
    return pd.DataFrame(rows)


def _show_results_with_export(df: pd.DataFrame, key_prefix: str):
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
        st.download_button("Download CSV", data=csv_data, file_name="crawler_results.csv",
                           mime="text/csv", key=f"{key_prefix}_csv_dl")
    with col_copy:
        # Streamlit doesn't have native clipboard, but we can use a text area trick
        if st.button("Copy to clipboard", key=f"{key_prefix}_copy"):
            # Use TSV for clipboard (easier to paste into sheets)
            tsv = df.to_csv(sep="\t", index=False)
            st.code(tsv, language=None)
            st.caption("Select all and copy the text above (Ctrl+A, Ctrl+C)")
