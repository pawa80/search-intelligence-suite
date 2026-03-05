from __future__ import annotations

"""
AEO Audit Agent - User Intent Extractor

Extracts potential user intents from page content using GPT-4o-mini.
"""

from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class IntentExtractionResult:
    """Result of intent extraction."""
    intents: list[str]
    success: bool
    error: Optional[str] = None


def extract_intents(
    title: str,
    first_paragraph: str,
    first_500_words: str,
    headings: list[dict],
    api_key: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 300,
    temperature: float = 0.7
) -> IntentExtractionResult:
    """
    Extract potential user intents from page content using GPT-4o-mini.

    Args:
        title: Page title
        first_paragraph: First paragraph of content
        first_500_words: First 500 words of content
        headings: List of heading dicts with 'level' and 'text' keys
        api_key: OpenAI API key
        model: Model to use (default: gpt-4o-mini)
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature

    Returns:
        IntentExtractionResult with list of 10 intents
    """
    if not api_key:
        return IntentExtractionResult(
            intents=[],
            success=False,
            error="OpenAI API key required for intent extraction"
        )

    endpoint = "https://api.openai.com/v1/chat/completions"

    # Format headings for prompt
    headings_text = ""
    if headings:
        headings_list = [f"- {h.get('level', 'h2').upper()}: {h.get('text', '')}" for h in headings[:15]]
        headings_text = "\n".join(headings_list)
    else:
        headings_text = "(No headings found)"

    prompt = """This is agentic search (AEO) optimisation. Your job is to detect what the business intent and the user intent is on this page, and find the key phrases that:
a) the current content indicates
b) the business looks to be wanting

Review the entire text context, but put extra weight on title, first paragraph and first 200 words. Look for question-answer format patterns.

Output exactly 10 phrases to optimise for. These phrases represent user intents - what users would search for that this page should answer.

Return as a numbered list, one phrase per line, no explanations."""

    content_context = f"""Page Title: {title}

First Paragraph: {first_paragraph}

Content: {first_500_words}

Headings:
{headings_text}"""

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
        return IntentExtractionResult(
            intents=[],
            success=False,
            error="Request timed out"
        )
    except requests.exceptions.HTTPError as e:
        error_msg = f"API error: {e.response.status_code}"
        if e.response.status_code == 401:
            error_msg = "Invalid API key"
        elif e.response.status_code == 429:
            error_msg = "Rate limit exceeded"
        return IntentExtractionResult(
            intents=[],
            success=False,
            error=error_msg
        )
    except requests.exceptions.RequestException as e:
        return IntentExtractionResult(
            intents=[],
            success=False,
            error=f"Request failed: {str(e)}"
        )

    # Parse response
    try:
        content = data["choices"][0]["message"]["content"].strip()
        # Split by newlines and clean up
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        # Remove numbering and clean up each intent
        intents = []
        for line in lines:
            # Remove common prefixes like "1.", "1)", "-", "*", etc.
            cleaned = line.lstrip("0123456789.-)*• ").strip()
            if cleaned:
                intents.append(cleaned)

        if len(intents) >= 10:
            return IntentExtractionResult(
                intents=intents[:10],
                success=True
            )
        elif len(intents) >= 5:
            # Accept if we got at least 5 intents
            return IntentExtractionResult(
                intents=intents,
                success=True
            )
        else:
            return IntentExtractionResult(
                intents=[],
                success=False,
                error=f"LLM returned only {len(intents)} intents (expected 10)"
            )

    except (KeyError, IndexError) as e:
        return IntentExtractionResult(
            intents=[],
            success=False,
            error=f"Failed to parse response: {str(e)}"
        )
