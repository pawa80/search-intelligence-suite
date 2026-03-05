"""URL normalisation and matching against the pages table."""
from __future__ import annotations

from urllib.parse import urlparse


def normalise_url(url: str) -> str:
    """Normalise URL for matching: https, lowercase netloc, strip trailing slash."""
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    if scheme == "http":
        scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{netloc}{path}{query}"


def build_pages_lookup(pages: list[dict]) -> dict[str, str]:
    """Build dict of normalised URL → page_id from pages table rows."""
    lookup: dict[str, str] = {}
    for p in pages:
        url = p.get("url", "")
        page_id = p.get("id", "")
        if url and page_id:
            lookup[normalise_url(url)] = page_id
    return lookup


def match_url_to_page(url: str, lookup: dict[str, str], domain: str = "") -> str | None:
    """Match a URL to a page_id using the lookup. Returns page_id or None."""
    # If it's a full URL, normalise directly
    normalised = normalise_url(url)
    if normalised in lookup:
        return lookup[normalised]

    # If it's a path (GA4 style), prepend domain
    if domain and not url.startswith(("http://", "https://")):
        full_url = f"https://{domain}{url}"
        normalised = normalise_url(full_url)
        if normalised in lookup:
            return lookup[normalised]

    return None
