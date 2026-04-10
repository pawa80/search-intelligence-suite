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


_SYSTEM_PROMPT = """You are an AEO (Answer Engine Optimization) intent analyst. Given a web page's metadata and content structure, generate 8-12 intent phrases that this page could be optimised to rank for in AI answer engines (ChatGPT, Perplexity, Google AI Overviews).

Each intent phrase should be:
- A natural language question or query a user might ask an AI engine
- Directly relevant to the page content and structure
- Varied in specificity (some broad, some specific)
- Grounded in the actual H2 headings and topics covered on the page
- Written in the same language as the page content

Put extra weight on the page title, H1, and H2 headings — these reveal the page's core topics. Use the meta description and content summary to understand the page's positioning and angle.

Return ONLY a JSON array of strings. No other text.
Example: ["what is customer data platform", "how to implement a CDP", "CDP vs DMP comparison"]"""


def suggest_intents(
    title: str,
    page_type: str = "",
    domain: str = "",
    domain_context: str = "",
    first_paragraph: str = "",
    h2_headings: list[str] | None = None,
    content_summary: str = "",
) -> list[str]:
    """Call Claude Haiku to generate 8-12 intent suggestions.

    v4.2: Now accepts H2 headings and content summary for deeper
    content-based intent generation (ported from standalone agent).
    """
    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("Intent suggestions: ANTHROPIC_API_KEY not configured")
        return []

    user_parts = [f"Page title: {title}"]
    if page_type:
        user_parts.append(f"Page type: {page_type}")
    if domain:
        user_parts.append(f"Domain: {domain}")
    if domain_context:
        user_parts.append(f"Domain context: {domain_context}")
    if first_paragraph:
        user_parts.append(f"Meta description: {first_paragraph[:500]}")
    if h2_headings:
        user_parts.append("H2 headings on this page:\n" + "\n".join(f"- {h}" for h in h2_headings[:20]))
    if content_summary:
        user_parts.append(f"Content summary:\n{content_summary[:1500]}")

    user_prompt = "\n".join(user_parts)

    _request_body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 500,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=_request_body,
            timeout=15.0,
        )
        if r.status_code == 529:
            st.warning("Our AI service is temporarily busy. Intent suggestions will be available shortly — please try again in a few minutes.")
            return []
        if r.status_code != 200:
            _err = f"Haiku API {r.status_code}: {r.text[:300]}"
            st.error(f"Intent suggestions failed — {_err}")
            return []
        data = r.json()

        # Extract text from response
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        if not text.strip():
            st.error("Intent suggestions: Haiku returned empty response")
            with st.expander("Debug: Haiku request/response"):
                st.code(user_prompt[:2000], language="text")
                st.json(data)
            return []

        # Clean markdown fences and preamble before parsing
        _clean = text.strip()
        if "```" in _clean:
            # Strip ```json ... ``` wrapping
            parts = _clean.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("["):
                    _clean = p
                    break
        # Strip any text before first [ and after last ]
        _start = _clean.find("[")
        _end = _clean.rfind("]")
        if _start != -1 and _end != -1 and _end > _start:
            _clean = _clean[_start:_end + 1]

        # Parse JSON array
        intents = json.loads(_clean)
        if isinstance(intents, list):
            return [str(i).strip() for i in intents if i]
        st.error(f"Intent suggestions: unexpected response format")
        with st.expander("Debug: Haiku response"):
            st.code(text[:500], language="text")
        return []

    except json.JSONDecodeError:
        st.error("Intent suggestions: failed to parse Haiku JSON response")
        with st.expander("Debug: raw Haiku response"):
            st.code(text[:1000] if text else "(empty)", language="text")
        return []
    except Exception as e:
        st.error(f"Intent suggestions error: {type(e).__name__}: {e}")
        with st.expander("Debug: request that failed"):
            st.code(user_prompt[:2000], language="text")
        return []
