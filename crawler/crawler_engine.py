"""Web crawler engine — discovers URLs and extracts SEO data."""

import time
import json
import httpx
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dataclasses import dataclass, field

# Use OS certificate store on Windows (uv-managed Python lacks CA bundle)
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

USER_AGENT = "SearchIntelligenceSuite/1.0"
REQUEST_TIMEOUT = 10.0
CRAWL_DELAY = 0.5


@dataclass
class SEOData:
    meta_desc: str = ""
    og_desc: str = ""
    h1: str = ""
    h2: str = ""
    hero_alt: str = ""
    canonical: str = ""
    og_url: str = ""
    jsonld: str = ""


@dataclass
class CrawlResult:
    url: str
    status_code: int | None = None
    title: str = ""
    depth: int = 0
    referrer: str = ""
    response_time: float = 0.0
    error: str = ""
    in_sitemap: str = "N/A"
    seo: SEOData = field(default_factory=SEOData)
    links_found: list[str] = field(default_factory=list)


def extract_seo_data(soup: BeautifulSoup) -> SEOData:
    """Extract SEO metadata from parsed HTML."""
    seo = SEOData()

    # Meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        seo.meta_desc = meta["content"].strip()

    # OG description
    og = soup.find("meta", attrs={"property": "og:description"})
    if og and og.get("content"):
        seo.og_desc = og["content"].strip()

    # H1
    h1 = soup.find("h1")
    seo.h1 = h1.get_text(strip=True) if h1 else "Missing"

    # H2
    h2 = soup.find("h2")
    seo.h2 = h2.get_text(strip=True) if h2 else "Missing"

    # Hero image alt — first large image outside header
    header = soup.find("header")
    for img in soup.find_all("img"):
        if header and header.find(img.name):
            continue
        width = img.get("width", "")
        height = img.get("height", "")
        try:
            if width and int(width) < 100:
                continue
            if height and int(height) < 100:
                continue
        except ValueError:
            pass
        seo.hero_alt = img.get("alt", "")
        break

    # Canonical
    link_canon = soup.find("link", rel="canonical")
    if link_canon and link_canon.get("href"):
        seo.canonical = link_canon["href"].strip()

    # OG URL
    og_url = soup.find("meta", attrs={"property": "og:url"})
    if og_url and og_url.get("content"):
        seo.og_url = og_url["content"].strip()

    # JSON-LD
    jsonld_script = soup.find("script", type="application/ld+json")
    if jsonld_script and jsonld_script.string:
        raw = jsonld_script.string.strip()
        # Compact whitespace for display
        seo.jsonld = " ".join(raw.split())[:500]

    return seo


def normalise_url(url: str, scheme: str = "https", domain: str = "") -> str:
    """Normalise URL: strip fragment, ensure https, lowercase netloc."""
    parsed = urlparse(url)
    s = parsed.scheme or scheme
    # Force https
    if s == "http":
        s = "https"
    netloc = parsed.netloc.lower() or domain
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{s}://{netloc}{path}{query}"


def fetch_sitemap_urls(domain: str) -> set[str]:
    """Fetch sitemap.xml for a domain and return set of normalised URLs."""
    sitemap_urls: set[str] = set()
    import xml.etree.ElementTree as ET

    def _fetch_and_parse(url: str):
        try:
            r = httpx.get(url, headers={"User-Agent": USER_AGENT},
                          timeout=15.0, follow_redirects=True)
            if r.status_code != 200:
                return
            root = ET.fromstring(r.content)
        except Exception:
            return

        ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0].lstrip("{")

        # Check for sitemap index
        for sm in root.findall(f".//{{{ns}}}sitemap"):
            loc = sm.find(f"{{{ns}}}loc")
            if loc is None:
                loc = sm.find("loc")
            if loc is not None and loc.text:
                _fetch_and_parse(loc.text.strip())

        # Parse URL entries
        for url_elem in root.findall(f".//{{{ns}}}url"):
            loc = url_elem.find(f"{{{ns}}}loc")
            if loc is None:
                loc = url_elem.find("loc")
            if loc is not None and loc.text:
                sitemap_urls.add(normalise_url(loc.text.strip()))

        # Fallback without namespace
        if not sitemap_urls:
            for sm in root.findall(".//sitemap"):
                loc = sm.find("loc")
                if loc is not None and loc.text:
                    _fetch_and_parse(loc.text.strip())
            for url_elem in root.findall(".//url"):
                loc = url_elem.find("loc")
                if loc is not None and loc.text:
                    sitemap_urls.add(normalise_url(loc.text.strip()))

    _fetch_and_parse(f"https://{domain}/sitemap.xml")
    return sitemap_urls


class CrawlerEngine:
    def __init__(self, start_url: str, max_depth: int = 2, max_pages: int = 20,
                 skip_duplicates: bool = True):
        parsed = urlparse(start_url)
        self.domain = parsed.netloc.lower()
        self.scheme = parsed.scheme or "https"
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.skip_duplicates = skip_duplicates
        self.visited: set[str] = set()
        self.queue: list[tuple[str, int, str]] = [(normalise_url(start_url, self.scheme, self.domain), 0, "Start URL")]
        self.results: list[CrawlResult] = []
        self.duplicates_skipped = 0
        self.sitemap_urls: set[str] = set()
        self._stop = False

    def stop(self):
        self._stop = True

    @property
    def stats(self) -> dict:
        return {
            "discovered": len(self.visited) + len(self.queue),
            "processed": len(self.results),
            "queue": len(self.queue),
            "duplicates_skipped": self.duplicates_skipped,
        }

    def _is_internal(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc.lower() == self.domain

    def _is_crawlable(self, url: str) -> bool:
        skip_exts = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
                     ".css", ".js", ".ico", ".woff", ".woff2", ".ttf", ".eot",
                     ".mp3", ".mp4", ".avi", ".mov", ".zip", ".tar", ".gz"}
        path = urlparse(url).path.lower()
        return not any(path.endswith(ext) for ext in skip_exts)

    def _fetch(self, url: str) -> CrawlResult:
        result = CrawlResult(url=url)
        try:
            start = time.monotonic()
            r = httpx.get(url, headers={"User-Agent": USER_AGENT},
                          timeout=REQUEST_TIMEOUT, follow_redirects=True)
            result.response_time = round(time.monotonic() - start, 2)
            result.status_code = r.status_code

            if "text/html" in r.headers.get("content-type", ""):
                soup = BeautifulSoup(r.text, "html.parser")
                title_tag = soup.find("title")
                result.title = title_tag.get_text(strip=True) if title_tag else "No Title"

                # Extract SEO data
                result.seo = extract_seo_data(soup)

                # Extract internal links
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("#") or href.startswith("mailto:"):
                        continue
                    abs_url = urljoin(url, href)
                    norm = normalise_url(abs_url, self.scheme, self.domain)
                    if self._is_internal(norm) and self._is_crawlable(norm):
                        result.links_found.append(norm)
        except httpx.TimeoutException:
            result.error = "Timeout"
        except httpx.ConnectError:
            result.error = "Connection failed"
        except Exception as e:
            result.error = str(e)[:100]
        return result

    def crawl(self):
        """Generator that yields CrawlResult for each page crawled.
        First yields a special 'sitemap fetching' phase, then crawls pages."""
        # Fetch sitemap first (like the original)
        self.sitemap_urls = fetch_sitemap_urls(self.domain)

        while self.queue and len(self.results) < self.max_pages and not self._stop:
            url, depth, referrer = self.queue.pop(0)

            if self.skip_duplicates and url in self.visited:
                self.duplicates_skipped += 1
                continue

            self.visited.add(url)
            result = self._fetch(url)
            result.depth = depth
            result.referrer = referrer

            # Cross-reference with sitemap
            norm_url = normalise_url(url, self.scheme, self.domain)
            result.in_sitemap = "Yes" if norm_url in self.sitemap_urls else "No"

            self.results.append(result)
            yield result

            # Queue discovered links
            if depth < self.max_depth:
                for link in result.links_found:
                    if link not in self.visited:
                        self.queue.append((link, depth + 1, url))

            time.sleep(CRAWL_DELAY)


def check_url_list(urls: list[str]):
    """Check status and extract SEO data for a list of URLs."""
    for url in urls:
        result = CrawlResult(url=url)
        try:
            start = time.monotonic()
            r = httpx.get(url, headers={"User-Agent": USER_AGENT},
                          timeout=REQUEST_TIMEOUT, follow_redirects=True)
            result.response_time = round(time.monotonic() - start, 2)
            result.status_code = r.status_code
            if "text/html" in r.headers.get("content-type", ""):
                soup = BeautifulSoup(r.text, "html.parser")
                title_tag = soup.find("title")
                result.title = title_tag.get_text(strip=True) if title_tag else "No Title"
                result.seo = extract_seo_data(soup)
        except httpx.TimeoutException:
            result.error = "Timeout"
        except httpx.ConnectError:
            result.error = "Connection failed"
        except Exception as e:
            result.error = str(e)[:100]
        yield result
        time.sleep(CRAWL_DELAY)
