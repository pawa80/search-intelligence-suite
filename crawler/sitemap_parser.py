"""Sitemap XML parser — fetch and parse sitemaps, check status of each URL."""

import time
import httpx
import xml.etree.ElementTree as ET
from dataclasses import dataclass

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

USER_AGENT = "SearchIntelligenceSuite/1.0"
REQUEST_TIMEOUT = 15.0


@dataclass
class SitemapEntry:
    url: str
    lastmod: str = ""
    changefreq: str = ""
    priority: str = ""
    status_code: int | None = None
    error: str = ""


def _fetch_xml(url: str) -> bytes | None:
    """Fetch XML content from a URL."""
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT},
                      timeout=REQUEST_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def _parse_sitemap_xml(content: bytes) -> tuple[list[SitemapEntry], list[str]]:
    """Parse sitemap XML. Returns (entries, nested_sitemap_urls)."""
    entries = []
    nested = []

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return entries, nested

    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0].lstrip("{")

    def _find(parent, tag):
        elem = parent.find(f"{{{ns}}}{tag}")
        if elem is None:
            elem = parent.find(tag)
        return elem

    def _findall(parent, tag):
        elems = parent.findall(f".//{{{ns}}}{tag}")
        if not elems:
            elems = parent.findall(f".//{tag}")
        return elems

    # Check if this is a sitemap index
    for sitemap in _findall(root, "sitemap"):
        loc = _find(sitemap, "loc")
        if loc is not None and loc.text:
            nested.append(loc.text.strip())

    # Parse URL entries
    for url_elem in _findall(root, "url"):
        loc = _find(url_elem, "loc")
        if loc is None or not loc.text:
            continue
        entry = SitemapEntry(url=loc.text.strip())
        lastmod = _find(url_elem, "lastmod")
        if lastmod is not None and lastmod.text:
            entry.lastmod = lastmod.text.strip()
        changefreq = _find(url_elem, "changefreq")
        if changefreq is not None and changefreq.text:
            entry.changefreq = changefreq.text.strip()
        priority = _find(url_elem, "priority")
        if priority is not None and priority.text:
            entry.priority = priority.text.strip()
        entries.append(entry)

    return entries, nested


def fetch_sitemap(sitemap_url: str):
    """Fetch and parse a sitemap, following nested sitemap index files.
    Yields SitemapEntry objects as they are discovered."""
    to_fetch = [sitemap_url]
    fetched = set()

    while to_fetch:
        url = to_fetch.pop(0)
        if url in fetched:
            continue
        fetched.add(url)

        content = _fetch_xml(url)
        if content is None:
            continue

        entries, nested = _parse_sitemap_xml(content)
        to_fetch.extend(n for n in nested if n not in fetched)

        yield from entries


def fetch_sitemap_from_domain(domain: str):
    """Auto-detect sitemap from domain. Tries /sitemap.xml.
    Yields SitemapEntry objects."""
    url = f"https://{domain}/sitemap.xml"
    yield from fetch_sitemap(url)


def check_sitemap_urls(entries: list[SitemapEntry]):
    """Check HTTP status for each sitemap entry. Yields updated entries."""
    for entry in entries:
        try:
            r = httpx.get(entry.url, headers={"User-Agent": USER_AGENT},
                          timeout=REQUEST_TIMEOUT, follow_redirects=True)
            entry.status_code = r.status_code
        except httpx.TimeoutException:
            entry.error = "Timeout"
        except Exception as e:
            entry.error = str(e)[:80]
        yield entry
        time.sleep(0.3)
