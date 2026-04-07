"""AI intent suggestion helper — generates intent phrases via Claude Haiku."""
from __future__ import annotations

import json
import os

import httpx
import streamlit as st


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, "")


_SYSTEM_PROMPT = """You are an AEO (Answer Engine Optimization) intent analyst. Given a web page's title, first paragraph, page type, and domain context, generate 8-12 intent phrases that this page could be optimised to rank for in AI answer engines (ChatGPT, Perplexity, Google AI Overviews).

Each intent phrase should be:
- A natural language question or query a user might ask an AI engine
- Directly relevant to the page content
- Varied in specificity (some broad, some specific)
- Written in the same language as the page content

Return ONLY a JSON array of strings. No other text.
Example: ["what is customer data platform", "how to implement a CDP", "CDP vs DMP comparison"]"""


def suggest_intents(
    title: str,
    page_type: str = "",
    domain: str = "",
    domain_context: str = "",
    first_paragraph: str = "",
) -> list[str]:
    """Call Claude Haiku to generate 8-12 intent suggestions. Returns list of strings."""
    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        return []

    user_parts = [f"Page title: {title}"]
    if page_type:
        user_parts.append(f"Page type: {page_type}")
    if domain:
        user_parts.append(f"Domain: {domain}")
    if domain_context:
        user_parts.append(f"Domain context: {domain_context}")
    if first_paragraph:
        user_parts.append(f"First paragraph: {first_paragraph[:500]}")

    user_prompt = "\n".join(user_parts)

    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 500,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=10.0,
        )
        r.raise_for_status()
        data = r.json()

        # Extract text from response
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        # Parse JSON array
        intents = json.loads(text.strip())
        if isinstance(intents, list):
            return [str(i).strip() for i in intents if i]
        return []

    except Exception:
        return []
