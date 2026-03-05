"""Google Search Console API client."""
from __future__ import annotations

from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def list_gsc_properties(creds: Credentials) -> list[dict[str, str]]:
    """List all GSC properties (sites) the user has access to."""
    service = build("searchconsole", "v1", credentials=creds)
    result = service.sites().list().execute()
    sites = result.get("siteEntry", [])
    return [
        {"url": s["siteUrl"], "permission": s.get("permissionLevel", "")}
        for s in sites
    ]


def fetch_gsc_data(
    creds: Credentials,
    site_url: str,
    start_date: str,
    end_date: str,
    row_limit: int = 5000,
) -> list[dict[str, Any]]:
    """Fetch page-level GSC data (clicks, impressions, CTR, position).

    Args:
        site_url: The GSC property URL (e.g. "sc-domain:example.com" or "https://example.com/")
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        row_limit: Max rows (default 5000)

    Returns:
        List of dicts with keys: url, clicks, impressions, ctr, position
    """
    service = build("searchconsole", "v1", credentials=creds)
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["page"],
        "rowLimit": row_limit,
    }
    response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = response.get("rows", [])

    results = []
    for row in rows:
        results.append({
            "url": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": round(row.get("ctr", 0), 4),
            "position": round(row.get("position", 0), 1),
        })
    return results
