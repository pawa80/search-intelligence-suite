"""Google Analytics 4 API client — gRPC with REST fallback."""
from __future__ import annotations

from typing import Any

import httpx
from google.oauth2.credentials import Credentials


def list_ga4_properties(creds: Credentials) -> list[dict[str, str]]:
    """List GA4 properties the user has access to.

    Tries gRPC client first, falls back to REST (Streamlit Cloud gRPC issues).
    """
    try:
        return _list_properties_grpc(creds)
    except Exception:
        return _list_properties_rest(creds)


def _list_properties_grpc(creds: Credentials) -> list[dict[str, str]]:
    """List properties via google-analytics-admin gRPC client."""
    from google.analytics.admin import AnalyticsAdminServiceClient

    client = AnalyticsAdminServiceClient(credentials=creds)
    results = []
    for account in client.list_account_summaries():
        for prop in account.property_summaries:
            results.append({
                "property_id": prop.property.split("/")[-1],
                "display_name": prop.display_name,
                "property_resource": prop.property,
            })
    return results


def _list_properties_rest(creds: Credentials) -> list[dict[str, str]]:
    """List properties via REST API (fallback)."""
    if not creds.valid:
        from google.auth.transport.requests import Request
        creds.refresh(Request())

    url = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"
    headers = {"Authorization": f"Bearer {creds.token}"}
    r = httpx.get(url, headers=headers, timeout=30.0)
    r.raise_for_status()
    data = r.json()

    results = []
    for account in data.get("accountSummaries", []):
        for prop in account.get("propertySummaries", []):
            prop_resource = prop.get("property", "")
            results.append({
                "property_id": prop_resource.split("/")[-1],
                "display_name": prop.get("displayName", ""),
                "property_resource": prop_resource,
            })
    return results


def fetch_ga4_data(
    creds: Credentials,
    property_id: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Fetch page-level GA4 data (sessions, engagement).

    Tries gRPC client first, falls back to REST.
    """
    try:
        return _fetch_data_grpc(creds, property_id, start_date, end_date)
    except Exception:
        return _fetch_data_rest(creds, property_id, start_date, end_date)


def _fetch_data_grpc(
    creds: Credentials,
    property_id: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Fetch data via google-analytics-data gRPC client."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        RunReportRequest,
    )

    client = BetaAnalyticsDataClient(credentials=creds)
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagedSessions"),
            Metric(name="engagementRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
        limit=10000,
    )
    response = client.run_report(request)
    return _parse_ga4_response(response.rows, is_grpc=True)


def _fetch_data_rest(
    creds: Credentials,
    property_id: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Fetch data via REST API (fallback)."""
    if not creds.valid:
        from google.auth.transport.requests import Request
        creds.refresh(Request())

    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }
    body = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "engagedSessions"},
            {"name": "engagementRate"},
            {"name": "averageSessionDuration"},
            {"name": "bounceRate"},
        ],
        "limit": 10000,
    }
    r = httpx.post(url, headers=headers, json=body, timeout=60.0)
    r.raise_for_status()
    data = r.json()
    return _parse_ga4_response(data.get("rows", []), is_grpc=False)


def _parse_ga4_response(rows: list, is_grpc: bool) -> list[dict[str, Any]]:
    """Parse GA4 response rows into standardised dicts."""
    results = []
    for row in rows:
        if is_grpc:
            page_path = row.dimension_values[0].value
            metrics = [m.value for m in row.metric_values]
        else:
            page_path = row["dimensionValues"][0]["value"]
            metrics = [m["value"] for m in row["metricValues"]]

        results.append({
            "page_path": page_path,
            "sessions": int(metrics[0]) if metrics[0] else 0,
            "engaged_sessions": int(metrics[1]) if metrics[1] else 0,
            "engagement_rate": round(float(metrics[2]), 4) if metrics[2] else 0,
            "avg_engagement_time": round(float(metrics[3]), 1) if metrics[3] else 0,
            "bounce_rate": round(float(metrics[4]), 4) if metrics[4] else 0,
        })
    return results
