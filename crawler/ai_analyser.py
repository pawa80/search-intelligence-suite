"""AI analysis of crawled pages — SEO, AEO readiness, content quality."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import streamlit as st


PERPLEXITY_BASE = "https://api.perplexity.ai"
MODEL = "sonar"

SYSTEM_PROMPT = """You are an SEO and AEO (Answer Engine Optimisation) analyst.
You receive crawled page data and return a structured JSON assessment.
Respond ONLY with valid JSON. No explanation, no markdown, no backticks."""

USER_PROMPT_TEMPLATE = """Analyse this crawled page and return a JSON assessment.

URL: {url}
HTTP Status: {status_code}
Title: {title}
H1: {h1}
H2 headings: {h2}
Meta description: {meta_description}
Word count: {word_count}
In sitemap: {in_sitemap}
Canonical URL: {canonical_url}
Has JSON-LD schema: {json_ld}
Depth from root: {depth}

Return this exact JSON structure:
{{
  "seo_score": <integer 0-100>,
  "aeo_readiness_score": <integer 0-100>,
  "content_quality_score": <integer 0-100>,
  "issues": [
    {{"type": "<issue_type>", "severity": "<high|medium|low>", "description": "<one sentence>"}}
  ],
  "priority_action": "<single most important fix in one sentence>",
  "action_plan": "<2-3 sentence summary of what to fix and why>"
}}

Scoring guide:
- seo_score: technical SEO health (status codes, title/H1 quality, canonical, sitemap, meta)
- aeo_readiness_score: how well structured for AI answer engines (FAQ schema, H2 structure, word count, definitions)
- content_quality_score: content signals (word count, H1/H2 presence, meta description quality)"""


def analyse_page(page: dict[str, Any], api_key: str) -> dict[str, Any] | None:
    """Run AI analysis on a single crawled page. Returns parsed JSON or None."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        url=page.get("url", ""),
        status_code=page.get("status_code", ""),
        title=page.get("title", ""),
        h1=page.get("h1", ""),
        h2=page.get("h2", ""),
        meta_description=page.get("meta_description", ""),
        word_count=page.get("word_count", ""),
        in_sitemap=page.get("in_sitemap", ""),
        canonical_url=page.get("canonical_url", ""),
        json_ld=page.get("json_ld", ""),
        depth=page.get("depth", ""),
    )

    try:
        response = httpx.post(
            f"{PERPLEXITY_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        # Strip any accidental backticks or markdown
        clean = raw.strip().strip("```json").strip("```").strip()
        return json.loads(clean)
    except Exception as e:
        import streamlit as st
        st.warning(f"AI analysis failed for {page.get('url', '?')}: {e}")
        return None


def save_analysis(
    result: dict[str, Any],
    page_id: str,
    project_id: str,
    supabase_url: str,
    anon_key: str,
    jwt: str,
) -> bool:
    """UPSERT a single analysis result to crawl_ai_analysis."""
    body = {
        "page_id": page_id,
        "project_id": project_id,
        "seo_score": result.get("seo_score"),
        "aeo_readiness_score": result.get("aeo_readiness_score"),
        "content_quality_score": result.get("content_quality_score"),
        "issues": json.dumps(result.get("issues", [])),
        "priority_action": result.get("priority_action", ""),
        "action_plan": result.get("action_plan", ""),
        "ai_model": MODEL,
        "analysed_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=merge-duplicates",
        }
        upsert_params = {"on_conflict": "page_id"}
        r = httpx.post(
            f"{supabase_url}/rest/v1/crawl_ai_analysis",
            headers=headers, json=body, params=upsert_params, timeout=10.0,
        )
        if r.status_code == 401:
            try:
                from supabase import create_client
                sb = create_client(supabase_url, anon_key)
                resp = sb.auth.refresh_session()
                if resp and resp.session:
                    new_token = resp.session.access_token
                    st.session_state.access_token = new_token
                    headers["Authorization"] = f"Bearer {new_token}"
                    r = httpx.post(
                        f"{supabase_url}/rest/v1/crawl_ai_analysis",
                        headers=headers, json=body, params=upsert_params, timeout=10.0,
                    )
            except Exception:
                pass
        return r.status_code < 400
    except Exception:
        return False
