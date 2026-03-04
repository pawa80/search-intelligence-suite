"""Web crawler engine — discovers URLs from a starting point."""

import time
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
class CrawlResult:
    url: str
    status_code: int | None = None
    title: str = ""
    depth: int = 0
    referrer: str = ""
    response_time: float = 0.0
    error: str = ""
    links_found: list[str] = field(default_factory=list)


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
        self.queue: list[tuple[str, int, str]] = [(self._normalise(start_url), 0, "")]
        self.results: list[CrawlResult] = []
        self.duplicates_skipped = 0
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

    def _normalise(self, url: str) -> str:
        """Normalise URL: strip fragment, ensure scheme, lowercase netloc."""
        parsed = urlparse(url)
        scheme = parsed.scheme or self.scheme
        netloc = parsed.netloc.lower() or self.domain
        path = parsed.path or "/"
        # Strip trailing slash for consistency (except root)
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{scheme}://{netloc}{path}{query}"

    def _is_internal(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc.lower() == self.domain

    def _is_crawlable(self, url: str) -> bool:
        """Skip non-page resources."""
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
                result.title = title_tag.get_text(strip=True) if title_tag else ""
                # Extract links
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    abs_url = urljoin(url, href)
                    normalised = self._normalise(abs_url)
                    if self._is_internal(normalised) and self._is_crawlable(normalised):
                        result.links_found.append(normalised)
        except httpx.TimeoutException:
            result.error = "Timeout"
        except httpx.ConnectError:
            result.error = "Connection failed"
        except Exception as e:
            result.error = str(e)[:100]
        return result

    def crawl(self):
        """Generator that yields CrawlResult for each page crawled."""
        while self.queue and len(self.results) < self.max_pages and not self._stop:
            url, depth, referrer = self.queue.pop(0)

            if self.skip_duplicates and url in self.visited:
                self.duplicates_skipped += 1
                continue

            self.visited.add(url)
            result = self._fetch(url)
            result.depth = depth
            result.referrer = referrer
            self.results.append(result)

            yield result

            # Queue discovered links
            if depth < self.max_depth:
                for link in result.links_found:
                    if link not in self.visited:
                        self.queue.append((link, depth + 1, url))

            time.sleep(CRAWL_DELAY)


def check_url_list(urls: list[str]):
    """Check status of a list of URLs (no crawling, just HEAD/GET)."""
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
                result.title = title_tag.get_text(strip=True) if title_tag else ""
        except httpx.TimeoutException:
            result.error = "Timeout"
        except httpx.ConnectError:
            result.error = "Connection failed"
        except Exception as e:
            result.error = str(e)[:100]
        yield result
        time.sleep(CRAWL_DELAY)
