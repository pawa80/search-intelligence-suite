"""Domain strategy generator — holistic AEO analysis via Claude Sonnet."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import httpx
import streamlit as st


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, "")


_SYSTEM_PROMPT = """You are an AEO (Answer Engine Optimization) domain strategist. You analyse websites holistically to create differentiated optimisation strategies.

Your job is NOT to optimise individual pages. Your job is to understand the SQUAD — what role each page plays in the domain's overall AEO strategy, where pages cannibalise each other, and where content gaps exist.

Think like a football manager picking a starting eleven: every player has a specific position. No two players should compete for the same role. The squad must cover all positions.

STRATEGIC PAGE ROLES (assign exactly one per page):
1. entity_anchor — Establishes brand/entity identity. Usually homepage + about. Focus: Organisation schema, sameAs, identity signals. Do NOT recommend FAQ or content-heavy changes.
2. citation_target — Designed to be cited by AI engines. Deep content, guides, how-tos. Focus: front-loaded answers, FAQ schema, comprehensive coverage of target queries.
3. authority_builder — Builds topical authority without expecting direct citations. Category pages, topic hubs, supporting content. Focus: internal linking, topic clustering, breadth.
4. conversion_endpoint — Where users take action. Product/service/contact pages. Focus: trust signals, comparison schema, clear value prop. FAQ schema HURTS these pages (per AEO research).
5. cannibal_overlap — Pages competing for the same queries. Strategy must decide: merge, differentiate, or archive one.
6. gap — Not an existing page. A topic that should have a page but doesn't.

CRITICAL RULE: The page_roles array MUST contain exactly one entry for EVERY page listed in the input. Do NOT skip any pages. Every page needs a strategic role, even if the role is obvious (e.g. homepage = entity_anchor). If you are unsure, assign authority_builder as the default. The user relies on every page having a role assigned.

OUTPUT FORMAT: Return ONLY valid JSON matching this exact structure (no markdown, no backticks, no preamble):
{
  "domain_summary": {
    "business_description": "...",
    "target_audience": "...",
    "primary_aeo_goal": "...",
    "competitive_context": "..."
  },
  "page_roles": [
    {
      "page_id": "...",
      "url": "...",
      "title": "...",
      "role": "entity_anchor|citation_target|authority_builder|conversion_endpoint|cannibal_overlap",
      "reasoning": "One sentence explaining why this role.",
      "priority_queries": ["query1", "query2"],
      "do_not_recommend": ["thing this page should NOT do because another page handles it"]
    }
  ],
  "cannibalisation": [
    {
      "page_ids": ["uuid1", "uuid2"],
      "urls": ["url1", "url2"],
      "shared_queries": ["query they compete for"],
      "recommendation": "How to resolve the conflict"
    }
  ],
  "gaps": [
    {
      "missing_topic": "...",
      "suggested_queries": ["query1", "query2"],
      "priority": "high|medium|low",
      "reasoning": "Why this content should exist"
    }
  ],
  "strategic_rules": [
    "Rule 1 that applies to all playbook generation for this domain",
    "Rule 2..."
  ],
  "strategy_narrative": "A 150-300 word qualitative writeup of the domain strategy in plain English. Write it as if briefing a marketing manager who needs to understand their site's AEO positioning at a glance. Group pages by role, explain why each group matters, mention specific high-value pages by name/URL, note any cannibalisation or gaps, and suggest next actions (e.g. generate playbooks for your top citation targets). Use plain language: say 'brand identity page' not 'entity_anchor', say 'citation target' not 'citation_target'. Include the count of pages per role."
}"""


def _build_user_prompt(project: dict, pages: list[dict], analyses: dict, playbook_counts: dict) -> str:
    """Build the user prompt from project data."""
    domain = project.get("domain", "unknown")
    domain_context = project.get("domain_context") or "No context provided"
    page_count = len(pages)

    page_blocks = []
    for p in pages:
        pe = p.get("page_elements") or {}
        if isinstance(pe, str):
            try:
                pe = json.loads(pe)
            except (json.JSONDecodeError, TypeError):
                pe = {}

        h2s = pe.get("h2_structure") or []
        h2_display = ", ".join(h2s[:8]) if h2s else "None"

        json_ld_types = []
        for item in (pe.get("json_ld") or []):
            if isinstance(item, dict) and "@type" in item:
                json_ld_types.append(item["@type"])
        jld_display = ", ".join(json_ld_types) if json_ld_types else "None"

        pid = p.get("id", "")
        analysis = analyses.get(pid, {})
        pb_count = playbook_counts.get(pid, 0)

        page_blocks.append(f"""---
Page ID: {pid}
URL: {p.get('url', '')}
Title: {p.get('title') or 'Untitled'}
Page type: {p.get('page_type') or 'Not classified'}
Meta description: {p.get('meta_description') or 'None'}
H2 structure: {h2_display}
JSON-LD types: {jld_display}
SEO score: {analysis.get('seo_score', 'Not analysed')}
AEO readiness: {analysis.get('aeo_readiness_score', 'Not analysed')}
Has playbooks: {'yes (' + str(pb_count) + ')' if pb_count else 'no'}
---""")

    return f"""Analyse this domain holistically and assign strategic roles.

Domain: {domain}
Project context: {domain_context}

Pages ({page_count} total):
{"".join(page_blocks)}

Based on ALL of these pages together, assign each page a strategic role, identify cannibalisation, identify content gaps, and define the strategic rules that should govern all playbook generation for this domain."""


def generate_domain_strategy(project: dict, pages: list[dict], analyses: dict, playbook_counts: dict) -> dict | None:
    """Generate a holistic domain strategy via Claude Sonnet.
    Returns the parsed strategy dict, or a fallback dict with raw_text on parse failure."""
    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY not configured.")
        return None

    user_prompt = _build_user_prompt(project, pages, analyses, playbook_counts)

    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=120.0,
        )
        if r.status_code == 529:
            st.warning("Our AI service is temporarily busy. Your existing strategy is safe. Please try again in 5 minutes.")
            return None
        if r.status_code >= 400:
            st.error(f"Strategy generation API error: {r.status_code} — {r.text[:200]}")
            return None
        data = r.json()

        # Extract text
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        # Parse JSON — strip markdown fences if present
        _clean = text.strip()
        if "```" in _clean:
            parts = _clean.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("{"):
                    _clean = p
                    break
        _start = _clean.find("{")
        _end = _clean.rfind("}")
        if _start != -1 and _end != -1 and _end > _start:
            _clean = _clean[_start:_end + 1]

        try:
            strategy = json.loads(_clean)

            # Validate: warn if Sonnet skipped pages
            _input_ids = {str(p.get("id", "")) for p in pages}
            _output_ids = {r.get("page_id") for r in strategy.get("page_roles", [])}
            _missing = _input_ids - _output_ids
            if _missing:
                st.warning(f"Strategy covers {len(_output_ids)}/{len(_input_ids)} pages. "
                           f"{len(_missing)} pages have no role assigned — regenerate for full coverage.")

            return strategy
        except json.JSONDecodeError:
            # Fallback: store raw text
            return {"raw_text": text[:8000], "parse_error": True}

    except Exception as e:
        st.error(f"Strategy generation failed: {e}")
        return None


def save_domain_strategy(token: str, project_id: str, strategy: dict) -> bool:
    """Save strategy to projects.domain_strategy via PATCH.

    Safety: validates strategy has non-empty page_roles before saving.
    Backs up current strategy to domain_strategy_previous first.
    """
    # Validate — never overwrite with empty/broken strategy
    if not strategy or strategy.get("parse_error"):
        st.error("Strategy validation failed — not saving. Existing strategy preserved.")
        return False
    if not strategy.get("page_roles"):
        st.error("Strategy has no page_roles — not saving. Existing strategy preserved.")
        return False

    base_url = _get_secret("SUPABASE_URL")
    anon_key = _get_secret("SUPABASE_ANON_KEY")

    # Backup current strategy to domain_strategy_previous
    try:
        _headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {token}",
        }
        _r = httpx.get(f"{base_url}/rest/v1/projects",
                       headers=_headers,
                       params={"select": "domain_strategy", "id": f"eq.{project_id}"},
                       timeout=10.0)
        if _r.status_code < 400:
            _rows = _r.json()
            if _rows and _rows[0].get("domain_strategy"):
                _backup_headers = {**_headers, "Content-Type": "application/json", "Prefer": "return=minimal"}
                httpx.patch(f"{base_url}/rest/v1/projects",
                            headers=_backup_headers,
                            params={"id": f"eq.{project_id}"},
                            json={"domain_strategy_previous": _rows[0]["domain_strategy"]},
                            timeout=10.0)
    except Exception:
        pass  # Backup is best-effort — don't block save

    url = f"{base_url}/rest/v1/projects"
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    now = datetime.now(timezone.utc).isoformat()
    r = httpx.patch(
        url,
        headers=headers,
        params={"id": f"eq.{project_id}"},
        json={
            "domain_strategy": json.dumps(strategy),
            "domain_strategy_generated_at": now,
        },
        timeout=10.0,
    )
    if r.status_code == 401:
        # Refresh and retry
        try:
            from supabase import create_client
            sb = create_client(_get_secret("SUPABASE_URL"), _get_secret("SUPABASE_ANON_KEY"))
            stored_access = st.session_state.get("access_token")
            stored_refresh = st.session_state.get("refresh_token")
            if stored_access and stored_refresh:
                sb.auth.set_session(stored_access, stored_refresh)
            resp = sb.auth.refresh_session()
            if resp and resp.session:
                new_token = resp.session.access_token
                st.session_state.access_token = new_token
                headers["Authorization"] = f"Bearer {new_token}"
                r = httpx.patch(url, headers=headers,
                                params={"id": f"eq.{project_id}"},
                                json={"domain_strategy": json.dumps(strategy),
                                      "domain_strategy_generated_at": now},
                                timeout=10.0)
        except Exception:
            pass
    return r.status_code < 400


def build_strategy_context_for_page(domain_strategy: dict, page_id: str) -> str:
    """Build the strategy context block to inject into a playbook prompt for a specific page."""
    if not domain_strategy or domain_strategy.get("parse_error"):
        return ""

    page_roles = domain_strategy.get("page_roles", [])
    page_role = None
    for role in page_roles:
        if role.get("page_id") == str(page_id):
            page_role = role
            break

    if not page_role:
        return ""

    summary = domain_strategy.get("domain_summary", {})
    rules = domain_strategy.get("strategic_rules", [])

    lines = [
        "## DOMAIN STRATEGY CONTEXT (applies to all recommendations)",
        f"Domain: {summary.get('business_description', '')}",
        f"Target audience: {summary.get('target_audience', '')}",
        f"Primary AEO goal: {summary.get('primary_aeo_goal', '')}",
        "",
        f"THIS PAGE'S STRATEGIC ROLE: {page_role['role'].upper().replace('_', ' ')}",
        f"Reasoning: {page_role.get('reasoning', '')}",
    ]

    pq = page_role.get("priority_queries", [])
    if pq:
        lines.append(f"Priority queries for this page: {', '.join(pq)}")

    dnr = page_role.get("do_not_recommend", [])
    if dnr:
        lines.append(f"DO NOT recommend for this page: {', '.join(dnr)}")

    if rules:
        lines.append("")
        lines.append("STRATEGIC RULES FOR THIS DOMAIN:")
        for rule in rules:
            lines.append(f"- {rule}")

    lines.extend([
        "",
        f"IMPORTANT: Your recommendations for this page must be DIFFERENTIATED from other pages on this domain.",
        f"This page's role is {page_role['role']}. Other pages handle other roles.",
        "Do not recommend entity establishment content for a citation target page.",
        "Do not recommend FAQ schema for a conversion endpoint page.",
        "Every playbook must be unique to this page's strategic position in the domain.",
    ])

    return "\n".join(lines)
