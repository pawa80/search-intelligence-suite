"""Project Overview — landing page showing project status at a glance."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import streamlit as st


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, "")


def _refresh_jwt() -> str | None:
    try:
        from supabase import create_client
        sb = create_client(_get_secret("SUPABASE_URL"), _get_secret("SUPABASE_ANON_KEY"))
        response = sb.auth.refresh_session()
        if response and response.session:
            new_token = response.session.access_token
            st.session_state.access_token = new_token
            return new_token
    except Exception:
        pass
    return None


def _db_get(token: str, table: str, params: dict) -> list[dict]:
    url = f"{_get_secret('SUPABASE_URL')}/rest/v1/{table}"
    headers = {
        "apikey": _get_secret("SUPABASE_ANON_KEY"),
        "Authorization": f"Bearer {token}",
    }
    r = httpx.get(url, headers=headers, params=params, timeout=10.0)
    if r.status_code == 401:
        new_token = _refresh_jwt()
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = httpx.get(url, headers=headers, params=params, timeout=10.0)
    if r.status_code < 400:
        return r.json()
    return []


_ROLE_EMOJI = {
    "entity_anchor": "\U0001f7e3",
    "citation_target": "\U0001f7e2",
    "authority_builder": "\U0001f535",
    "conversion_endpoint": "\U0001f7e0",
    "cannibal_overlap": "\U0001f534",
}

_ROLE_LABEL = {
    "entity_anchor": "Brand Identity",
    "citation_target": "Citation Target",
    "authority_builder": "Authority Builder",
    "conversion_endpoint": "Conversion",
    "cannibal_overlap": "Competing Page",
}


def _load_overview_data(token: str, project_id: str) -> dict[str, Any]:
    """Load all overview data in parallel-ish queries, cached per project."""
    cache_key = f"_overview_data_{project_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    data: dict[str, Any] = {}

    # Pages count + last crawl
    pages = _db_get(token, "pages", {
        "select": "id,last_crawled_at",
        "project_id": f"eq.{project_id}",
        "status": "eq.active",
        "last_crawled_at": "not.is.null",
    })
    data["page_count"] = len(pages)
    data["page_ids"] = {p["id"] for p in pages}
    if pages:
        dates = [p.get("last_crawled_at", "") for p in pages if p.get("last_crawled_at")]
        data["last_crawl"] = max(dates)[:10] if dates else None
    else:
        data["last_crawl"] = None

    # Citation data — latest complete check date
    citation_rows = _db_get(token, "geo_check_results", {
        "select": "appears,position,check_date",
        "project_id": f"eq.{project_id}",
        "order": "check_date.desc",
    })
    if citation_rows:
        # Find latest check date
        latest_date = citation_rows[0].get("check_date", "")
        latest_rows = [r for r in citation_rows if r.get("check_date") == latest_date]
        cited = sum(1 for r in latest_rows if r.get("appears"))
        total = len(latest_rows)
        positions = [r["position"] for r in latest_rows if r.get("appears") and r.get("position")]
        avg_pos = round(sum(positions) / len(positions), 1) if positions else None
        data["citation_rate"] = cited
        data["citation_total"] = total
        data["citation_pct"] = round(cited / total * 100, 1) if total else 0
        data["citation_date"] = latest_date
        data["citation_avg_pos"] = avg_pos
    else:
        data["citation_rate"] = 0
        data["citation_total"] = 0
        data["citation_pct"] = 0
        data["citation_date"] = None
        data["citation_avg_pos"] = None

    # AI analysis count
    ai_rows = _db_get(token, "crawl_ai_analysis", {
        "select": "page_id",
        "project_id": f"eq.{project_id}",
    })
    data["ai_score_count"] = len(ai_rows)

    # GSC data count (unique pages)
    gsc_rows = _db_get(token, "gsc_data", {
        "select": "page_id",
        "project_id": f"eq.{project_id}",
    })
    data["gsc_count"] = len({r["page_id"] for r in gsc_rows if r.get("page_id")})

    # Playbook count (unique pages)
    ap_rows = _db_get(token, "arbeidspakker", {
        "select": "page_id",
        "project_id": f"eq.{project_id}",
    })
    data["playbook_count"] = len({r["page_id"] for r in ap_rows if r.get("page_id")})
    data["playbook_total"] = len(ap_rows)

    st.session_state[cache_key] = data
    return data


def _nav_button(label: str, target: str, key: str) -> None:
    """Button that navigates to a different tool via _tool_override."""
    if st.button(label, key=key):
        st.session_state["_tool_override"] = target
        st.rerun()


def _show_brand_audit_demo(project_id: str) -> None:
    """Static demo of the AI Brand Perception Audit feature."""

    # Inject scoped CSS for brand audit visual styling
    st.markdown("""<style>
/* Brand audit section styling */
div[data-testid="stExpander"].brand-audit-strategy details {
    border-left: 4px solid #a78bfa !important;
}
div[data-testid="stExpander"].brand-audit-inv1 details {
    border-left: 4px solid #2dd4a0 !important;
}
div[data-testid="stExpander"].brand-audit-inv2 details {
    border-left: 4px solid #5b9cf6 !important;
}
div[data-testid="stExpander"].brand-audit-inv3 details {
    border-left: 4px solid #f0a500 !important;
}
div[data-testid="stExpander"].brand-audit-inv4 details {
    border-left: 4px solid #f06070 !important;
}
</style>""", unsafe_allow_html=True)

    st.markdown(
        '<h3 style="margin-bottom: 0;">'
        '<span style="color: var(--accent, #f0a500);">Brand Context</span> Auditor</h3>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Opus strategises. Sonnet executes with web search. You see both layers."
    )

    st.markdown(
        '<span style="background: var(--accent, #f0a500); color: #000; padding: 2px 8px; '
        'border-radius: 3px; font-size: 12px; font-weight: 600;">SAMPLE AUDIT \u2014 wagamama</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    with st.expander("\U0001f7e3 Strategy Layer (Opus-tier reasoning)", expanded=False):
        st.markdown("""**AI Brand Audit Investigation Plan: wagamama**

---

**1. Core Brand Identity & Cuisine Perception**
How do AI systems characterize wagamama's culinary identity \u2014 and do they accurately reflect the pan-Asian (primarily Japanese-inspired) positioning, or do they flatten it into a generic "Asian restaurant" category?

**2. Competitive Positioning Against Fast-Casual Asian Rivals**
Where do AI systems place wagamama in the competitive landscape \u2014 alongside premium chains like Yo! Sushi and Itsu, or fast-food adjacents like Pret? This reveals whether AI is reinforcing or undermining wagamama's mid-premium positioning.

**3. Menu Accuracy & Signature Dish Recognition**
Wagamama has a distinctive menu with long-standing signature dishes (katsu curry, ramen, gyoza). Do AI systems confidently and correctly describe these, or introduce errors that could mislead prospective diners?

**4. Brand Authority & Sustainability Narrative**
Wagamama has invested publicly in sustainability credentials (plant-based menu expansion, carbon reduction pledges). Does AI reflect this as part of the brand story, or is it absent \u2014 effectively erasing a key brand differentiator?

**5. Reputation Signals Around Price, Value & Experience**
As wagamama has expanded and raised prices post-pandemic, sentiment around value-for-money has become contested. Does AI echo this tension or does it present an uncritically positive (or negative) brand picture?

---

**Priority angle:** Start with #3 \u2014 menu accuracy errors are the most operationally damaging misrepresentations and the easiest to verify against ground truth.""")

    with st.expander("\U0001f7e2 Investigation 1: Brand Overview & Customer Sentiment", expanded=False):
        st.markdown("""**Brand Overview**

Wagamama is a London-based restaurant chain specialising in Japanese ramen bars and offering a variety of Asian food. Their first restaurant opened in 1992 in Bloomsbury, founded by Alan Yau. The brand has gone global with franchised restaurants in 22 countries across Europe and the Middle East, plus 8 company-owned locations in the US.

---

**Brand Positioning & Marketing**

In June 2025, Wagamama launched its "biggest campaign" in its 33-year history \u2014 a new brand platform called 'Food is Life', built around the belief that food plays a vital role in connection, comfort, creativity, and culture. The casual dining chain is also working towards a 200-site UK target, supported by brand strength, pricing power, and digital engagement.

---

**Retail Expansion**

Wagamama is capitalising on the foodservice-to-retail shift by launching full meal solutions into grocery, expanding its reach and revenue streams. However, by going into retail, the brand exposes itself to fresh challenges \u2014 including competing with established FMCG brands and conceding some control over its image.

---

**Customer Sentiment (Key Gaps & Issues)**

Consumer reviews are notably mixed. On Trustpilot (wagamama.co.uk), the brand scores just **2.3 out of 5** from 328 reviews. Recurring complaints include pricing, portion sizes, and inconsistent quality. A significant critique centres on vegan options being "significantly decreased," which is seen as a broken promise given Wagamama's earlier 50% vegan pledge.

Some longer-term customers feel the brand "used to be good" but is now "overpriced."

**Notable gap:** The brand's public-facing marketing emphasises wellness, nourishment, and inclusivity, but customer reviews frequently flag allergy handling, accessibility failures, and inconsistent food quality.""")
        st.markdown(
            '<div style="background: rgba(240, 96, 112, 0.15); border-left: 3px solid #f06070; '
            'padding: 0.6rem 1rem; border-radius: 4px; margin-top: 0.5rem;">'
            '<strong style="color: #f06070;">\u26a0 Sentiment Risk:</strong> '
            'Trustpilot 2.3/5 from 328 reviews despite 100+ locations. '
            'Marketing narrative diverges significantly from customer experience.</div>',
            unsafe_allow_html=True,
        )

    with st.expander("\U0001f535 Investigation 2: Cuisine Type & Food Offering", expanded=False):
        st.markdown("""**What the brand serves:**

Wagamama is a London-based restaurant chain that specialises in Japanese ramen bars and offers a variety of Asian food, selling dishes including bao buns, curries, donburi, teppanyaki grill noodles, ramen, and pho.

**Cuisine identity:**

While Japanese cuisine forms the backbone of their menu, Wagamama incorporates flavours from other Asian regions, making their dishes diverse. The menu also includes pad thai \u2014 a Thai-inspired addition \u2014 alongside more traditional Japanese items.

**Brand positioning:**

Wagamama positions itself as "a staple of modern Asian cuisine," with an Asian-inspired menu "created to soothe, nourish, sustain and inspire." The brand also aligns itself with the Japanese philosophy of *kaizen* (continuous improvement).

**Notable gap/inaccuracy:** There is a consistent tension in how wagamama is classified \u2014 sources oscillate between calling it a "Japanese restaurant" and an "Asian-fusion" chain. Wagamama's own US site describes "popular Asian + Japanese dishes" and "Asian-fusion cuisine." This ambiguity could dilute the brand's perceived authenticity with purists of either Japanese or broader Asian cuisine.""")
        st.markdown(
            '<div style="background: rgba(91, 156, 246, 0.15); border-left: 3px solid #5b9cf6; '
            'padding: 0.6rem 1rem; border-radius: 4px; margin-top: 0.5rem;">'
            '<strong style="color: #5b9cf6;">\U0001f4a1 Identity Gap:</strong> '
            'AI oscillates between "Japanese" and "Asian-fusion" \u2014 brand identity is ambiguous across platforms.</div>',
            unsafe_allow_html=True,
        )

    with st.expander("\U0001f7e0 Investigation 3: Competitive Framing", expanded=False):
        st.markdown("""**How wagamama is categorised vs. Itsu & Pret**

wagamama is broadly described as "the UK's leading pan-Asian casual restaurant chain" \u2014 placing it firmly in **casual dining**, not fast food. However, its competitive set is blurring. wagamama's top competitors are identified as Nando's, Itsu, and ASK Italian, grouping it with both fast-casual and full-service brands. Companies like Pret, wagamama, Itsu, and Yo Sushi are collectively cited as "championing food" in the same breath \u2014 suggesting consumer and trade perception increasingly bundles them together.

**The Itsu distinction is sharp:** Itsu focuses on grab-and-go food \u2014 you pick up your meal and eat on the move \u2014 making it ideal for busy people who want lighter meals and quick options. wagamama, by contrast, positions itself as "a warm, welcoming, inclusive place to eat \u2014 both casual and cosy."

**Retail crossover is narrowing the gap:** Restaurant brands like Leon, Itsu, and wagamama are capitalising on retail by launching full meal solutions into grocery. wagamama's new products \u2014 pastes, sauces and meal kits \u2014 launched initially in Waitrose.

**Notable gap/inaccuracy:** wagamama is occasionally labelled "fast food" in external sources (e.g., travel guides), which conflicts with its own positioning. The brand promotes fast service and a casual dining vibe \u2014 but the dine-in, communal bench format is meaningfully different from Pret or Itsu's grab-and-go model, a distinction not always reflected in how third parties categorise it.""")
        st.markdown(
            '<div style="background: rgba(240, 165, 0, 0.15); border-left: 3px solid #f0a500; '
            'padding: 0.6rem 1rem; border-radius: 4px; margin-top: 0.5rem;">'
            '<strong style="color: #f0a500;">\U0001f3af Positioning Risk:</strong> '
            'AI occasionally categorises wagamama as "fast food" \u2014 conflating dine-in casual dining with grab-and-go.</div>',
            unsafe_allow_html=True,
        )

    with st.expander("\U0001f534 Investigation 4: Mid-Premium Positioning", expanded=False):
        st.markdown("""**Verdict: AI is broadly reinforcing wagamama's mid-premium positioning \u2014 but with some notable nuances and risks.**

**What AI & Search Results Say About the Brand**

Wagamama is described as "the only UK pan-Asian brand concept of scale and one of the UK's market-leading premium casual dining brands" \u2014 language consistent with a mid-premium identity. Customer NPS scores of +42 (December 2024) rank it among the UK's top two casual dining brands by BrandVue.

AI-generated product analysis sites consistently place wagamama in the mid-premium band. Core menu items are described as "positioned in the mid-price band for mains," often featured in loyalty promotions via the "Soul Club" rewards scheme. The brand is characterised by "contemporary design, youthful appeal, and fusion of healthy and indulgent dining options," with franchise investment requirements "reflecting its international brand strength and polished casual positioning."

**A Key Positioning Risk: Supermarket Expansion**

Wagamama has launched a range of ready meals and sauces into multiple supermarkets \u2014 a move that could dilute its mid-premium restaurant identity in AI narratives. Industry analysts note that restaurant brands can "hold their own and often compete fiercely, even at a premium price point," but caution the retail sector is not easy to crack.

**Notable Gaps in AI Perception**

AI sources are largely silent on wagamama's **experiential and cultural storytelling** \u2014 the communal dining philosophy and Japanese-inspired design language that underpin its premium-over-fast-casual positioning. This matters because "AI can repeat outdated or incorrect information just as easily as positive mentions," and if negative framing or misinformation goes unnoticed, "it can quietly damage brand trust at scale."

**Summary:** AI systems are currently reinforcing wagamama's mid-premium label through pricing language and NPS data, but the growing supermarket presence introduces narrative drift risk that warrants monitoring across AI platforms.""")
        st.markdown(
            '<div style="background: rgba(45, 212, 160, 0.15); border-left: 3px solid #2dd4a0; '
            'padding: 0.6rem 1rem; border-radius: 4px; margin-top: 0.5rem;">'
            '<strong style="color: #2dd4a0;">\u2705 Verdict:</strong> '
            'Mid-premium positioning is <strong>currently reinforced</strong> by AI \u2014 but supermarket expansion creates narrative drift risk.</div>',
            unsafe_allow_html=True,
        )

    # Cost metrics — styled container
    st.write("")
    st.markdown(
        '<div style="background: var(--surface2, #21252e); border: 1px solid var(--border, #2a2f3a); '
        'border-radius: 6px; padding: 0.5rem 1rem 0.2rem;">'
        '<p style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; '
        'color: var(--text-muted, #7a8099); margin-bottom: 0.3rem;">Inference Economics</p></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Strategy (Opus)", "4,988 tokens", delta="$0.07", delta_color="off")
    c2.metric("Execution (Sonnet)", "143,055 tokens", delta="$0.43", delta_color="off")
    c3.metric("Total Cost", "$0.50")
    c4.metric("Strategy Share", "15%")

    st.markdown(
        '<p style="text-align: center; color: var(--text-muted, #7a8099); font-size: 13px; margin-top: 0.5rem;">'
        'Coming to Aevilab Q2 2026 \u2014 enter your domain, get a full brand perception audit in under 2 minutes.</p>',
        unsafe_allow_html=True,
    )


def show_overview(
    project_ctx: dict[str, Any] | None,
    token: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """Main entry point for the Project Overview page."""
    st.title("Project Overview")

    if not project_ctx:
        st.info("Select or create a project to get started.")
        return

    project_id = project_ctx["id"]
    domain = project_ctx.get("domain", "")
    st.caption(f"**{project_ctx['name']}** · {domain}")

    # Load all overview data
    data = _load_overview_data(token, project_id)

    # === Section 1: YOUR DOMAIN STRATEGY ===
    st.subheader("Your Domain Strategy")

    # Parse domain strategy once for reuse
    _ds_raw = project_ctx.get("domain_strategy") or {}
    if isinstance(_ds_raw, str):
        try:
            _ds = json.loads(_ds_raw)
        except (json.JSONDecodeError, TypeError):
            _ds = {}
    else:
        _ds = _ds_raw
    page_roles = _ds.get("page_roles", []) if _ds and not _ds.get("parse_error") else []

    col_user, col_ai = st.columns(2)

    # Left: Domain Strategy — Your Input
    with col_user:
        st.markdown("**Domain Strategy — Your Input**")
        domain_context = project_ctx.get("domain_context") or st.session_state.get("domain_context", "")
        if domain_context:
            lines = domain_context.strip().split("\n")
            if len(lines) > 3:
                preview = "\n".join(lines[:3])
                with st.expander(f"{preview}\n\n...CLICK TO EXPAND", expanded=False):
                    st.markdown(domain_context)
            else:
                st.markdown(domain_context)
        else:
            st.caption("Add your domain context in Project Settings to improve playbook quality.")
        _nav_button("Edit Your Strategy Manifest", "Settings", f"ov_edit_strategy_{project_id}")

    # Right: AI Derived Domain Strategy
    with col_ai:
        st.markdown("**AI Derived Domain Strategy**")

        if page_roles:
            # Show narrative if available, otherwise generate summary from roles
            narrative = _ds.get("strategy_narrative", "")
            if narrative:
                st.markdown(narrative)
            else:
                # Fallback: auto-generate a basic summary from page_roles
                _role_groups: dict[str, list[str]] = {}
                for pr in page_roles:
                    role_raw = pr.get("role", "authority_builder")
                    label = _ROLE_LABEL.get(role_raw, role_raw.replace("_", " ").title())
                    url = pr.get("url", "")
                    try:
                        path = urlparse(url).path.strip("/")
                        url_short = f"/{path}" if path else "/ (Homepage)"
                    except Exception:
                        url_short = url[:40]
                    _role_groups.setdefault(label, []).append(url_short)

                _parts = []
                for role_label, urls in _role_groups.items():
                    emoji = next((e for r, e in _ROLE_EMOJI.items() if _ROLE_LABEL.get(r) == role_label), "\U0001f3af")
                    _parts.append(f"{emoji} **{len(urls)} {role_label}** pages")
                st.markdown(" · ".join(_parts))

            # Collapsible detailed page roles table
            with st.expander("View detailed page roles", expanded=False):
                for pr in page_roles:
                    role_raw = pr.get("role", "")
                    emoji = _ROLE_EMOJI.get(role_raw, "\U0001f3af")
                    label = _ROLE_LABEL.get(role_raw, role_raw.replace("_", " ").title())
                    url = pr.get("url", "")
                    try:
                        path = urlparse(url).path.strip("/")
                        url_short = f"/{path}" if path else "/ (Homepage)"
                    except Exception:
                        url_short = url[:40]
                    st.markdown(f"{emoji} **{label}** · `{url_short}`")

            # Stale strategy check
            strategy_page_ids = {pr.get("page_id") for pr in page_roles}
            current_page_ids = data.get("page_ids", set())
            if current_page_ids - strategy_page_ids:
                st.caption("Note: run new crawl + regenerate strategy to include new pages")

            # Strategy date + regenerate link
            _gen_at = project_ctx.get("domain_strategy_generated_at")
            if _gen_at:
                _gen_date = str(_gen_at)[:10]
                st.caption(f"Strategy generated on {_gen_date}. Regenerate on the **Crawl** page.")
            else:
                st.caption("Regenerate on the **Crawl** page.")
        else:
            st.caption("No domain strategy yet. Generate one on the **Crawl** page to get differentiated playbooks.")
            _nav_button("Generate Strategy", "Crawl", f"ov_goto_crawl_strategy_{project_id}")

    st.divider()

    # === Section 2: CITATION RATE ===
    st.subheader("Citation Rate")
    if data["citation_date"]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Citation Rate", f"{data['citation_rate']}/{data['citation_total']} ({data['citation_pct']}%)")
        c2.metric("Last Check", data["citation_date"])
        c3.metric("Avg Position", data["citation_avg_pos"] if data["citation_avg_pos"] else "\u2014")
    else:
        st.caption("No citation checks yet. Run your first check in Rank Tracker.")
    _nav_button("Rank Tracker", "Rank Tracker", f"ov_goto_rank_{project_id}")

    st.divider()

    # === Section 3: CRAWL SUMMARY ===
    st.subheader("Crawl Summary")
    if data["page_count"] > 0:
        st.markdown(f"**{data['page_count']}** pages crawled · Last crawl: **{data['last_crawl']}**")
    else:
        st.caption("No pages crawled yet. Start your first crawl.")
    _nav_button("Crawl", "Crawl", f"ov_goto_crawl_{project_id}")

    st.divider()

    # === Section 4: YOUR MATRIX ===
    st.subheader("Your Matrix")
    st.caption("Your page matrix tracks optimisation progress across all crawled pages.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pages in Matrix", data["page_count"])
    m2.metric("With AI Scores", data["ai_score_count"])
    m3.metric("With GSC Data", data["gsc_count"])
    m4.metric("With Playbook", data["playbook_count"])
    _nav_button("Your Matrix", "Matrix", f"ov_goto_matrix_{project_id}")

    st.divider()

    # === BRAND PERCEPTION AUDIT (demo) ===
    _show_brand_audit_demo(project_id)

    st.divider()

    # === Section 5: USER INPUT REQUIRED (placeholder) ===
    if data["playbook_total"] > 0:
        st.markdown(
            f"""<div style="background: var(--surface2, #21252e); border-left: 3px solid var(--stone, #8B8B8B); padding: 1rem; border-radius: 4px; opacity: 0.6;">
<strong>\U0001f4cb Coming soon: Playbook Implementation Tracker</strong><br>
You have {data['playbook_total']} active playbooks. This section will show which playbooks have been implemented by your team, track the dates changes were applied, and connect those changes to the outcome measurements below. When your team confirms a playbook has been applied, Aevilab starts monitoring for results.
</div>""",
            unsafe_allow_html=True,
        )
        st.write("")

    # === Section 6: CHANGES DETECTED (placeholder) ===
    st.markdown(
        """<div style="background: var(--surface2, #21252e); border-left: 3px solid var(--stone, #8B8B8B); padding: 1rem; border-radius: 4px; opacity: 0.6;">
<strong>\U0001f50d Coming soon: Intelligent Change Detection</strong><br>
After your next crawl, Aevilab will automatically detect content changes on your pages \u2014 new headings, updated schema, modified content \u2014 and show you what changed and when. Combined with citation and traffic tracking, this creates a direct feedback loop: change \u2192 detect \u2192 measure \u2192 learn. This is how Aevilab gets smarter with every crawl.
</div>""",
        unsafe_allow_html=True,
    )
