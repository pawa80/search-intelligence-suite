from __future__ import annotations

"""
AEO Audit Agent - Smart Query Generator

Uses OpenAI GPT-4o-mini to generate realistic search queries based on page content.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests


@dataclass
class QueryGenerationResult:
    """Result of query generation."""
    queries: list[str]
    is_ai_generated: bool
    error: Optional[str] = None


def generate_queries_with_llm(
    title: str,
    first_paragraph: str,
    first_500_words: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 100,
    temperature: float = 0.7
) -> QueryGenerationResult:
    """
    Generate search queries using OpenAI GPT-4o-mini.

    Args:
        title: Page title
        first_paragraph: First paragraph of content
        first_500_words: First 500 words of content
        api_key: OpenAI API key
        model: Model to use (default: gpt-4o-mini)
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature

    Returns:
        QueryGenerationResult with queries and metadata
    """
    endpoint = "https://api.openai.com/v1/chat/completions"

    # Build context for the LLM
    content_context = f"""Title: {title}

First paragraph: {first_paragraph}

Content excerpt: {first_500_words[:1000]}"""

    prompt = """You are an SEO expert. Based on this content, generate exactly 3 search queries that a real person would type into Google or an AI assistant to find this information. Return ONLY the 3 queries, one per line, no numbering or explanation."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content_context}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
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
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error="Request timed out"
        )
    except requests.exceptions.HTTPError as e:
        error_msg = f"API error: {e.response.status_code}"
        if e.response.status_code == 401:
            error_msg = "Invalid API key"
        elif e.response.status_code == 429:
            error_msg = "Rate limit exceeded"
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error=error_msg
        )
    except requests.exceptions.RequestException as e:
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error=f"Request failed: {str(e)}"
        )

    # Parse response
    try:
        content = data["choices"][0]["message"]["content"].strip()
        # Split by newlines and clean up
        queries = [q.strip() for q in content.split("\n") if q.strip()]
        # Remove any numbering (1., 2., etc.) or bullet points
        cleaned_queries = []
        for q in queries:
            # Remove common prefixes like "1.", "1)", "-", "*", etc.
            cleaned = q.lstrip("0123456789.-)*• ").strip()
            if cleaned:
                cleaned_queries.append(cleaned)

        if len(cleaned_queries) >= 3:
            return QueryGenerationResult(
                queries=cleaned_queries[:3],
                is_ai_generated=True
            )
        else:
            return QueryGenerationResult(
                queries=[],
                is_ai_generated=False,
                error="LLM returned fewer than 3 queries"
            )

    except (KeyError, IndexError) as e:
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error=f"Failed to parse response: {str(e)}"
        )


def generate_queries_from_intents(
    title: str,
    first_paragraph: str,
    selected_intents: list[str],
    api_key: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 300,
    temperature: float = 0.7
) -> QueryGenerationResult:
    """
    Generate search queries based on user-selected intents.
    Generates 1-3 queries per intent depending on complexity.

    Args:
        title: Page title
        first_paragraph: First paragraph of content
        selected_intents: List of 3-6 user-confirmed intents
        api_key: OpenAI API key
        model: Model to use (default: gpt-4o-mini)
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature

    Returns:
        QueryGenerationResult with queries and metadata
    """
    if not api_key:
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error="OpenAI API key required"
        )

    endpoint = "https://api.openai.com/v1/chat/completions"

    # Format intents for prompt
    intents_text = "\n".join(f"- {intent}" for intent in selected_intents)
    current_year = datetime.now().year

    prompt = f"""Today's date is {datetime.now().strftime('%B %Y')}. Use {current_year} for any current year references.

Generate search queries based on these user intents.
Generate 1-3 queries per intent depending on the intent's complexity and search variations.
Each query should be a realistic phrase someone would type into an AI search engine.

Page context:
Title: {title}
First paragraph: {first_paragraph}

Selected intents:
{intents_text}

Return only the queries, one per line, no numbering or explanation."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
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
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error="Request timed out"
        )
    except requests.exceptions.HTTPError as e:
        error_msg = f"API error: {e.response.status_code}"
        if e.response.status_code == 401:
            error_msg = "Invalid API key"
        elif e.response.status_code == 429:
            error_msg = "Rate limit exceeded"
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error=error_msg
        )
    except requests.exceptions.RequestException as e:
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error=f"Request failed: {str(e)}"
        )

    # Parse response
    try:
        content = data["choices"][0]["message"]["content"].strip()
        # Split by newlines and clean up
        queries = [q.strip() for q in content.split("\n") if q.strip()]
        # Remove any numbering (1., 2., etc.) or bullet points
        cleaned_queries = []
        for q in queries:
            # Remove common prefixes like "1.", "1)", "-", "*", etc.
            cleaned = q.lstrip("0123456789.-)*• ").strip()
            if cleaned:
                cleaned_queries.append(cleaned)

        # Accept any number of queries >= number of intents
        min_expected = len(selected_intents)
        if len(cleaned_queries) >= min_expected:
            return QueryGenerationResult(
                queries=cleaned_queries,
                is_ai_generated=True
            )
        elif len(cleaned_queries) > 0:
            # Return what we got even if fewer than expected
            return QueryGenerationResult(
                queries=cleaned_queries,
                is_ai_generated=True
            )
        else:
            return QueryGenerationResult(
                queries=[],
                is_ai_generated=False,
                error="LLM returned no valid queries"
            )

    except (KeyError, IndexError) as e:
        return QueryGenerationResult(
            queries=[],
            is_ai_generated=False,
            error=f"Failed to parse response: {str(e)}"
        )


def get_fallback_queries(title: str, first_paragraph: str) -> list[str]:
    """
    Generate fallback queries using simple rules.
    Used when OpenAI API is unavailable.
    """
    import re

    # Extract topic from title
    topic = re.split(r'\s*[|\-–—:]{1,2}\s*', title)[0].strip() if title else ""

    # Remove common prefixes
    topic_lower = topic.lower()
    prefixes = [
        r"^my\s+(take|thoughts|view|opinion|guide)\s+(on|to)\s+",
        r"^our\s+(take|thoughts|view|guide)\s+(on|to)\s+",
        r"^the\s+(definitive|ultimate|complete|official|essential)\s+(guide\s+to|home\s+of)\s+",
        r"^(the\s+)?(official\s+)?(home|site|page)\s+(of|for)\s+(the\s+)?",
        r"^(understanding|exploring|introducing|announcing)\s+",
        r"^(what|why|how)\s+(is|are|to|does)\s+",
        r"^the\s+(best|top|ultimate)\s+",
        r"^(guide|introduction)\s+to\s+",
    ]

    for pattern in prefixes:
        match = re.match(pattern, topic_lower)
        if match:
            topic = topic[match.end():]
            break

    topic = re.sub(r"^(the|a|an)\s+", "", topic, flags=re.IGNORECASE).strip()
    topic_lower = topic.lower()

    if not topic_lower:
        return ["What is this about?", "How does this work?", "Best practices"]

    queries = [
        f"What is {topic_lower}",
        f"How does {topic_lower} work",
        f"{topic_lower} best practices"
    ]

    return queries
