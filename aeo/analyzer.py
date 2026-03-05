from __future__ import annotations

"""
AEO Audit Agent - Content Analyzer Module

Functions for extracting and analyzing web page content for AEO optimization.
"""

import re
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class AnalysisResult:
    """Container for page analysis results."""
    url: str
    title: str
    total_word_count: int
    first_500_words: str
    first_paragraph: str
    has_direct_answer: bool
    direct_answer_score: int  # 0-100 score
    direct_answer_reasons: list[str]
    extraction_success: bool
    headings: list[dict] = None  # List of {"level": "h1/h2/h3", "text": "..."}
    generated_queries: list[str] = None
    queries_ai_generated: bool = False
    full_content: str = ""
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.generated_queries is None:
            self.generated_queries = []
        if self.headings is None:
            self.headings = []


def fetch_page_content(url: str, timeout: int = 10) -> tuple[str, Optional[str]]:
    """
    Fetch HTML content from a URL.

    Returns:
        Tuple of (html_content, error_message)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AEOAuditBot/1.0)"
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text, None
    except requests.exceptions.Timeout:
        return "", "Request timed out. The page took too long to respond."
    except requests.exceptions.ConnectionError:
        return "", "Could not connect to the URL. Please check if it's valid."
    except requests.exceptions.HTTPError as e:
        return "", f"HTTP error: {e.response.status_code}"
    except requests.exceptions.RequestException as e:
        return "", f"Error fetching page: {str(e)}"


def extract_text_content(html: str) -> tuple[str, str, list[str], list[dict]]:
    """
    Extract readable text content from HTML.

    Returns:
        Tuple of (full_text, title, paragraphs, headings)
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, nav, footer, and other non-content elements
    for element in soup(["script", "style", "nav", "footer", "header",
                         "aside", "noscript", "iframe", "svg"]):
        element.decompose()

    # Get title
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)

    # Try to find main content area
    main_content = (
        soup.find("main") or
        soup.find("article") or
        soup.find(attrs={"role": "main"}) or
        soup.find("div", class_=re.compile(r"content|article|post", re.I)) or
        soup.body or
        soup
    )

    # Extract headings (H1, H2, H3)
    headings = []
    for heading in main_content.find_all(["h1", "h2", "h3"]):
        text = heading.get_text(strip=True)
        if text:
            headings.append({"level": heading.name, "text": text})

    # Extract paragraphs
    paragraphs = []
    for p in main_content.find_all(["p", "h1", "h2", "h3", "li"]):
        text = p.get_text(strip=True)
        if text and len(text) > 20:  # Filter out very short text
            paragraphs.append(text)

    # Get full text
    full_text = main_content.get_text(separator=" ", strip=True)
    # Clean up whitespace
    full_text = re.sub(r"\s+", " ", full_text)

    return full_text, title, paragraphs, headings


def count_words(text: str) -> int:
    """Count words in text."""
    words = text.split()
    return len(words)


def get_first_n_words(text: str, n: int = 500) -> str:
    """Extract first N words from text."""
    words = text.split()
    return " ".join(words[:n])


def check_direct_answer(first_paragraph: str) -> tuple[bool, int, list[str]]:
    """
    Check if the first paragraph appears to be a direct answer.

    Returns:
        Tuple of (is_direct_answer, score, reasons)
    """
    if not first_paragraph:
        return False, 0, ["No first paragraph found"]

    score = 0
    reasons = []

    # Check 1: Length is appropriate (not too short, not too long)
    word_count = count_words(first_paragraph)
    if 20 <= word_count <= 100:
        score += 25
        reasons.append(f"Good length ({word_count} words) - concise but informative")
    elif word_count < 20:
        reasons.append(f"Too short ({word_count} words) - may lack detail")
    else:
        reasons.append(f"Long first paragraph ({word_count} words) - consider being more concise")
        score += 10

    # Check 2: Starts with a definitive statement (not a question)
    first_paragraph_lower = first_paragraph.lower()
    if not first_paragraph.strip().endswith("?"):
        if any(first_paragraph_lower.startswith(word) for word in
               ["the ", "a ", "an ", "it ", "this ", "there "]):
            score += 20
            reasons.append("Starts with a definitive statement")
    else:
        reasons.append("First paragraph is a question, not an answer")

    # Check 3: Contains defining language
    defining_patterns = [
        r"\bis\b", r"\bare\b", r"\bmeans\b", r"\brefers to\b",
        r"\bdefined as\b", r"\bknown as\b", r"\bcalled\b"
    ]
    if any(re.search(pattern, first_paragraph_lower) for pattern in defining_patterns):
        score += 20
        reasons.append("Contains defining language (is, are, means, etc.)")

    # Check 4: Doesn't start with weak phrases
    weak_starts = ["in this article", "in this post", "welcome to",
                   "today we", "let's", "click here", "subscribe"]
    if not any(first_paragraph_lower.startswith(phrase) for phrase in weak_starts):
        score += 15
        reasons.append("Doesn't start with weak/promotional phrases")
    else:
        reasons.append("Starts with weak/promotional phrase - get to the answer faster")

    # Check 5: Contains substantive information (numbers, specific terms)
    if re.search(r"\d+", first_paragraph):
        score += 10
        reasons.append("Contains specific numbers/data")

    # Check 6: Not overly promotional
    promo_words = ["buy", "purchase", "discount", "sale", "offer", "deal", "subscribe"]
    promo_count = sum(1 for word in promo_words if word in first_paragraph_lower)
    if promo_count == 0:
        score += 10
        reasons.append("Not promotional - focused on information")
    else:
        reasons.append("Contains promotional language")

    is_direct_answer = score >= 50

    return is_direct_answer, min(score, 100), reasons


def generate_queries_rule_based(title: str, first_paragraph: str) -> list[str]:
    """
    Generate 3 realistic search queries using rule-based approach.

    This is the fallback when OpenAI API is unavailable.

    Returns:
        List of 3 query strings
    """
    queries = []

    # Clean up title - remove site name suffixes like "| Site Name" or "- Site Name"
    clean_title = re.split(r'\s*[|\-–—]\s*', title)[0].strip()

    if not clean_title and not first_paragraph:
        return ["What is this topic?", "How does this work?", "Why is this important?"]

    # Query 1: Direct "what is" question from title
    # Extract key topic from title
    title_lower = clean_title.lower()

    # Remove common prefixes
    for prefix in ["how to ", "guide to ", "the complete ", "the ultimate ",
                   "a guide to ", "understanding ", "learn about "]:
        if title_lower.startswith(prefix):
            title_lower = title_lower[len(prefix):]
            break

    if title_lower:
        # Create a "what is" query
        queries.append(f"What is {title_lower}?")

    # Query 2: "How" question - either from title or inferred
    if "how to" in title.lower():
        queries.append(clean_title + "?")
    elif first_paragraph:
        # Extract a likely topic and create a how question
        words = first_paragraph.split()[:10]
        topic_hint = " ".join(words[:5])
        # Look for action verbs or nouns
        if any(word in first_paragraph.lower() for word in
               ["process", "method", "step", "way", "approach"]):
            queries.append(f"How does {title_lower} work?")
        else:
            queries.append(f"How to use {title_lower}?")
    else:
        queries.append(f"How does {title_lower} work?")

    # Query 3: "Why" or comparison question
    if first_paragraph:
        # Check for benefit/importance language
        if any(word in first_paragraph.lower() for word in
               ["important", "benefit", "advantage", "help", "improve"]):
            queries.append(f"Why is {title_lower} important?")
        elif any(word in first_paragraph.lower() for word in
                 ["best", "top", "compare", "vs", "versus", "difference"]):
            queries.append(f"What is the best {title_lower}?")
        else:
            queries.append(f"Why use {title_lower}?")
    else:
        queries.append(f"Why is {title_lower} important?")

    # Ensure we have exactly 3 queries
    while len(queries) < 3:
        queries.append(f"What are the benefits of {title_lower}?")

    return queries[:3]


def smart_generate_queries(
    title: str,
    first_paragraph: str,
    first_500_words: str,
    openai_api_key: Optional[str] = None
) -> tuple[list[str], bool]:
    """
    Generate queries using LLM if available, otherwise fall back to rules.

    Args:
        title: Page title
        first_paragraph: First paragraph of content
        first_500_words: First 500 words of content
        openai_api_key: Optional OpenAI API key

    Returns:
        Tuple of (queries, is_ai_generated)
    """
    if openai_api_key:
        try:
            from query_generator import generate_queries_with_llm

            result = generate_queries_with_llm(
                title=title,
                first_paragraph=first_paragraph,
                first_500_words=first_500_words,
                api_key=openai_api_key
            )

            if result.is_ai_generated and len(result.queries) >= 3:
                return result.queries[:3], True

        except Exception:
            pass  # Fall through to rule-based

    # Fallback to rule-based
    queries = generate_queries_rule_based(title, first_paragraph)
    return queries, False


def analyze_url(url: str, openai_api_key: Optional[str] = None) -> AnalysisResult:
    """
    Main analysis function - fetches and analyzes a URL.

    Returns:
        AnalysisResult with all analysis data
    """
    # Ensure URL has scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Fetch content
    html, error = fetch_page_content(url)

    if error:
        return AnalysisResult(
            url=url,
            title="",
            total_word_count=0,
            first_500_words="",
            first_paragraph="",
            has_direct_answer=False,
            direct_answer_score=0,
            direct_answer_reasons=[],
            extraction_success=False,
            headings=[],
            error_message=error
        )

    # Extract text
    full_text, title, paragraphs, headings = extract_text_content(html)

    # Get metrics
    total_words = count_words(full_text)
    first_500 = get_first_n_words(full_text, 500)
    first_paragraph = paragraphs[0] if paragraphs else ""

    # Note: Direct answer scoring removed - now calculated after intent selection
    # via intent_scorer.py for intent-specific relevance scoring

    # Generate search queries (LLM if available, otherwise rule-based)
    queries, ai_generated = smart_generate_queries(
        title=title,
        first_paragraph=first_paragraph,
        first_500_words=first_500,
        openai_api_key=openai_api_key
    )

    return AnalysisResult(
        url=url,
        title=title,
        total_word_count=total_words,
        first_500_words=first_500,
        first_paragraph=first_paragraph,
        has_direct_answer=False,  # Deprecated - use intent_scorer instead
        direct_answer_score=0,    # Deprecated - use intent_scorer instead
        direct_answer_reasons=[], # Deprecated - use intent_scorer instead
        extraction_success=True,
        headings=headings,
        generated_queries=queries,
        queries_ai_generated=ai_generated,
        full_content=full_text
    )
