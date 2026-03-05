from __future__ import annotations

"""
AEO Audit Agent - Perplexity Citation Checker

Checks if a target URL appears in Perplexity AI citations for given queries.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

import requests


@dataclass
class CitationResult:
    """Result of a single citation check."""
    query: str
    cited: bool
    citation_snippet: str
    sources_found: list[str]
    error: str = None


def normalize_url(url: str) -> str:
    """
    Normalize URL for comparison by extracting domain and path.

    Removes protocol, www prefix, and trailing slashes.
    """
    parsed = urlparse(url.lower())
    domain = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{domain}{path}"


def check_citation(
    query: str,
    target_url: str,
    api_key: str,
    model: str = "sonar"
) -> CitationResult:
    """
    Check if target URL is cited by Perplexity for a given query.

    Args:
        query: The search query to send to Perplexity
        target_url: The URL we're checking for in citations
        api_key: Perplexity API key
        model: Perplexity model to use (default: sonar)

    Returns:
        CitationResult with citation status and details
    """
    endpoint = "https://api.perplexity.ai/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": query
            }
        ]
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.Timeout:
        return CitationResult(
            query=query,
            cited=False,
            citation_snippet="",
            sources_found=[],
            error="Request timed out"
        )
    except requests.exceptions.HTTPError as e:
        error_msg = f"API error: {e.response.status_code}"
        if e.response.status_code == 401:
            error_msg = "Invalid API key"
        elif e.response.status_code == 429:
            error_msg = "Rate limit exceeded"
        return CitationResult(
            query=query,
            cited=False,
            citation_snippet="",
            sources_found=[],
            error=error_msg
        )
    except requests.exceptions.RequestException as e:
        return CitationResult(
            query=query,
            cited=False,
            citation_snippet="",
            sources_found=[],
            error=f"Request failed: {str(e)}"
        )

    # Extract citations from response
    citations = data.get("citations", [])
    sources_found = citations if isinstance(citations, list) else []

    # Get the response content
    content = ""
    if data.get("choices") and len(data["choices"]) > 0:
        content = data["choices"][0].get("message", {}).get("content", "")

    # Check if target URL is in citations
    target_normalized = normalize_url(target_url)
    cited = False
    citation_snippet = ""

    for source in sources_found:
        source_normalized = normalize_url(source)
        # Check if the target domain/path appears in any citation
        if target_normalized in source_normalized or source_normalized in target_normalized:
            cited = True
            # Try to extract relevant snippet from content
            citation_snippet = content[:300] + "..." if len(content) > 300 else content
            break

    return CitationResult(
        query=query,
        cited=cited,
        citation_snippet=citation_snippet,
        sources_found=sources_found
    )


def check_all_queries(
    queries: list[str],
    target_url: str,
    api_key: str,
    model: str = "sonar"
) -> list[CitationResult]:
    """
    Check citations for multiple queries.

    Args:
        queries: List of search queries
        target_url: The URL we're checking for
        api_key: Perplexity API key
        model: Perplexity model to use

    Returns:
        List of CitationResult objects
    """
    results = []
    for query in queries:
        result = check_citation(query, target_url, api_key, model)
        results.append(result)
    return results


def get_citation_summary(results: list[CitationResult]) -> dict:
    """
    Summarize citation check results.

    Returns:
        Dict with summary statistics
    """
    total = len(results)
    cited_count = sum(1 for r in results if r.cited)
    error_count = sum(1 for r in results if r.error)

    return {
        "total_queries": total,
        "cited_count": cited_count,
        "not_cited_count": total - cited_count - error_count,
        "error_count": error_count,
        "citation_rate": (cited_count / total * 100) if total > 0 else 0,
        "all_sources": list(set(
            source
            for r in results
            for source in r.sources_found
        ))
    }
