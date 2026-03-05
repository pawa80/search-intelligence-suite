"""URL normalisation and matching against the pages table."""
from __future__ import annotations

from urllib.parse import urlparse


def _clean_domain(domain: str) -> str:
    """Strip scheme and trailing slash from a domain string.
    Handles 'https://www.example.com/' → 'www.example.com'."""
    d = domain.strip()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.rstrip("/").lower()


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
    """Build dict of normalised URL → page_id from pages table rows.
    Also indexes without www. prefix for flexible matching."""
    lookup: dict[str, str] = {}
    for p in pages:
        url = p.get("url", "")
        page_id = p.get("id", "")
        if url and page_id:
            norm = normalise_url(url)
            lookup[norm] = page_id
            # Also add www/non-www variant for flexible matching
            parsed = urlparse(norm)
            netloc = parsed.netloc
            if netloc.startswith("www."):
                alt_netloc = netloc[4:]
            else:
                alt_netloc = f"www.{netloc}"
            alt_url = f"{parsed.scheme}://{alt_netloc}{parsed.path}"
            if parsed.query:
                alt_url += f"?{parsed.query}"
            if alt_url not in lookup:
                lookup[alt_url] = page_id
    return lookup


def match_url_to_page(url: str, lookup: dict[str, str], domain: str = "") -> str | None:
    """Match a URL to a page_id using the lookup. Returns page_id or None.

    For GA4 page paths (e.g. '/about/'), prepends the project domain.
    Tries with and without www. prefix to handle mismatches.
    """
    # If it's a full URL, normalise directly
    if url.startswith(("http://", "https://")):
        normalised = normalise_url(url)
        if normalised in lookup:
            return lookup[normalised]
        return None

    # It's a path (GA4 style) — prepend domain
    if not domain:
        return None

    clean = _clean_domain(domain)
    path = url if url.startswith("/") else f"/{url}"

    # Try the domain as-is
    full_url = f"https://{clean}{path}"
    normalised = normalise_url(full_url)
    if normalised in lookup:
        return lookup[normalised]

    # Try www/non-www variant
    if clean.startswith("www."):
        alt = clean[4:]
    else:
        alt = f"www.{clean}"
    alt_url = f"https://{alt}{path}"
    normalised = normalise_url(alt_url)
    if normalised in lookup:
        return lookup[normalised]

    return None
