from __future__ import annotations

"""
AEO Audit Agent - Recommendations Engine

Uses Anthropic Claude Sonnet 4 to generate complete arbeidspakker (work packages)
with full page rewrites, FAQ replacements, JSON-LD schema, and SEO improvements.
Output language matches the page content language.
"""

import json
import os
from dataclasses import dataclass
from typing import Optional

from anthropic import Anthropic
from openai import OpenAI
import requests

try:
    import streamlit as st
    def _get_anthropic_key():
        return st.secrets.get("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY"))
except Exception:
    def _get_anthropic_key():
        return os.getenv("ANTHROPIC_API_KEY")

import intelligence_feed


# Note: Name is historical (originally o4-mini). Now used with gpt-4.1-mini.
O4_MINI_SYSTEM_PROMPT = """You generate a structural AEO audit report that identifies exactly what needs to change on a page for AI citation, without writing the replacement content.

OUTPUT LANGUAGE RULE (STRICT):
1. Detect the language of the page content being analysed.
2. Write your ENTIRE output in that same language — every heading, every paragraph, every bullet point.
3. English page = 100% English output. Norwegian page = 100% Norwegian output.
4. Do NOT mix languages under any circumstances.

CRITICAL RULE — NO FABRICATED DATA:
Do NOT invent, estimate, or fabricate any statistics, percentages, metrics, or numerical claims.
Only reference numbers that appear in the page content or in the suite data context block.
If no data is available, describe the issue qualitatively. Write "data not yet available" rather than inventing a figure.

OUTPUT STRUCTURE — follow this exact format:

**Key findings**
3-5 sentences diagnosing the single biggest AEO gap on this page, why it prevents AI citation, and what fixing it would achieve (qualitatively, no fabricated metrics).

## 1. AEO improvements (prioritised recommendations)
List 3-5 priority improvements. For each:
- What to change (specific element on the page)
- Why it matters for AI citation (reference AEO principles, not invented stats)
- Impact level: Critical / High / Medium
- Exact location on the page (which heading, which paragraph, which section)

## 2. Complete proposed page text
🔒 **Full page rewrites are available on the Premium tier.**
Instead, here is a structural blueprint:
- Opening paragraph: [Describe what the first 100 words should contain — direct answer, entity definition, key facts. Do NOT write the actual text.]
- For each H2 section: [State what the section should achieve, what entity it should define, what facts it should front-load. Do NOT write the replacement content.]
- Recommended word count target for the full page.

## 3. FAQ section
🔒 **Complete FAQ content with full answers is available on the Premium tier.**
Instead, here are the recommended FAQ questions this page should answer:
- List 4-5 questions that match search intent for the page topic.
- For each question: one sentence describing what the answer should cover (do NOT write the full answer).

## 4. Technical implementation
Provide complete, valid JSON-LD FAQ schema markup using the questions from Section 3.
For the answer text in the schema, write a single factual sentence per answer (max 30 words each) using ONLY information from the page content.

Also provide:
- Recommended H2 heading structure (full list of headings)
- Date markup recommendation
- Any technical HTML changes needed (semantic elements, schema types)

## 5. SEO improvements
- Exact meta title (max 60 chars)
- Exact meta description (max 155 chars)
- 3-5 internal linking recommendations with specific anchor text and target URL patterns
- Any hreflang or canonical fixes needed

## 6. Checklist
Numbered checklist of every change to implement. Each item is a specific, actionable instruction.

RULES:
1. NEVER write full replacement text for page sections. Describe what should be there, not the actual content.
2. NEVER invent statistics. If the page says "30% missing specifications harm visibility" you may reference that. If no number exists, do not create one.
3. The JSON-LD schema answers must be single sentences using ONLY facts from the page content.
4. Every recommendation must reference a specific location on the page (heading, paragraph number, section name).
5. The structural blueprint in Section 2 should be detailed enough that a copywriter knows exactly what to write — just don't write it for them.
6. If page type is provided, tailor advice accordingly (product page ≠ blog post ≠ landing page).
7. Reference GSC/GA data from the context block if available.
"""


AEO_GUIDE = """
# AEO OPTIMIZATION GUIDE

## CORE PRINCIPLES

### What is AEO?
Answer Engine Optimization (AEO) is the practice of structuring web content so AI-powered systems (ChatGPT, Perplexity, Google AI Overviews) can extract, trust, and cite your content in generated answers.

### How AI Selects Citations (The 6-Source Authority Set)
AI engines analyze ~20-50 candidate pages per query but only cite 5-7 in responses. Selection criteria:
1. **Semantic match** - Content directly answers the query intent
2. **Answer positioning** - Direct answer appears within first 100 words
3. **Trust signals** - Author credentials, publication date, domain authority
4. **Structural clarity** - Clean HTML, proper headings, schema markup
5. **Grounding efficiency** - Concise, quotable statements (not walls of text)

### The Grounding Budget (~2000 words)
AI has limited context per source. Your page competes for inclusion in this budget.
- **First 200 words = critical** (often all that's grounded)
- **Direct answer in paragraph 1** = high citation probability
- **Buried answer in paragraph 5** = low citation probability

## USER INTENT HIERARCHY

Priority order for optimization:
1. **Definitional** - "What is X?" → Provide clear definition in first sentence
2. **Procedural** - "How to X?" → Numbered steps, start with action verb
3. **Comparative** - "X vs Y" → Side-by-side breakdown, clear verdict
4. **Evaluative** - "Best X for Y" → Ranked list with reasoning
5. **Troubleshooting** - "X not working" → Problem/cause/solution format
6. **Factual** - "When/where/who X?" → Direct answer, then context

## CONTENT STRUCTURE RULES

### Semantic Triples
AI parses content as subject-predicate-object relationships.
- **Good:** "First-party data is information collected directly from customers."
- **Bad:** "When we talk about data collection, there are many approaches companies take..."

### Answer Positioning
- First paragraph must contain the direct answer
- Don't start with questions, history, or preamble
- Hook with value, not curiosity

### Optimal Paragraph Structure
1. **Lead:** Direct answer to likely query (1-2 sentences)
2. **Support:** Evidence, data, or explanation (2-3 sentences)
3. **Bridge:** Transition to next concept

## TECHNICAL REQUIREMENTS

### Schema Markup (Structured Data)
- FAQ schema for question-answer content
- HowTo schema for tutorials
- Article schema with author, datePublished, dateModified
- Organization schema for brand content

### HTML Structure
- One H1 containing primary keyword
- H2s for major sections (should match likely queries)
- H3s for sub-topics
- Lists for scannable information

## AUTHORITY SIGNALS

### E-E-A-T Implementation
- **Experience:** First-hand examples, case studies
- **Expertise:** Author credentials, methodology
- **Authoritativeness:** Citations to primary sources, data
- **Trust:** Contact info, about page, clear ownership

## COMMON AEO FAILURE PATTERNS

1. **Answer buried** - Direct answer appears after paragraph 3
2. **Passive voice** - "It is believed that..." vs "Research shows..."
3. **Missing definition** - Assumes reader knows terminology
4. **Wall of text** - No structure, hard to extract quotes
5. **Outdated content** - No date signals, stale information
6. **Thin content** - Under 500 words, lacks depth
"""


@dataclass
class RecommendationResult:
    """Result of recommendation generation."""
    recommendations: list[str]
    success: bool
    error: Optional[str] = None


def generate_recommendations(title, full_content, first_paragraph, direct_answer_score, citation_results, selected_intents, api_key, context_block="", page_type=None, domain_context=None, model_tier="expensive"):
    """Generate a complete arbeidspakke with full page rewrites matching the gold standard.

    v2.5: Model toggle — Claude Sonnet 4 (expensive, ~$0.11/gen) or OpenAI gpt-4.1-mini (cheap, ~$0.02/gen).
    Outputs a complete 6-section arbeidspakke in the language of the page content.
    Full rewrites — no snippets, no suggestions. Paste-ready for CMS.
    """

    _empty_result = {
        "summary": "",
        "intelligence_applied": [],
        "critical_issues": [],
        "action_plan": [],
        "quick_wins": []
    }

    if model_tier == "expensive":
        anthropic_key = _get_anthropic_key()
        if not anthropic_key:
            _empty_result["summary"] = "ANTHROPIC_API_KEY not configured. Add it to .env or Streamlit Cloud secrets."
            return _empty_result
    else:
        openai_key = api_key or os.getenv("OPENAI_API_KEY")
        if not openai_key:
            _empty_result["summary"] = "OPENAI_API_KEY not configured. Add it to .env or Streamlit Cloud secrets."
            return _empty_result

    from urllib.parse import urlparse

    # Format citation results for prompt
    cited_queries = [r['query'] for r in citation_results if r.get('cited')]
    uncited_queries = [r['query'] for r in citation_results if not r.get('cited')]
    citation_rate = len(cited_queries) / len(citation_results) * 100 if citation_results else 0

    # Build top-5 competitor domains from sources_found
    domain_query_counts = {}
    for r in citation_results:
        for source_url in r.get('sources_found', []):
            try:
                domain = urlparse(source_url).netloc.lower().replace('www.', '')
            except Exception:
                continue
            if domain:
                if domain not in domain_query_counts:
                    domain_query_counts[domain] = set()
                domain_query_counts[domain].add(r['query'])
    top_competitors = sorted(domain_query_counts.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    total_queries = len(citation_results)
    competitor_lines = []
    for domain, queries in top_competitors:
        competitor_lines.append(f"- {domain} (cited in {len(queries)}/{total_queries} queries)")
    competitor_section = ""
    if competitor_lines:
        competitor_section = "\n**Top Competing Sources (by domain):**\n" + "\n".join(competitor_lines)

    # Truncate full_content to prevent token overflow (keep first 12000 chars for better rewrites)
    content_for_analysis = full_content[:12000] if full_content else ""

    # Load AEO Guide: prefer Notion-synced file, fall back to hardcoded constant
    aeo_guide_content = intelligence_feed.get_aeo_guide() or AEO_GUIDE

    # Load intelligence checklist (returns empty string if missing — graceful fallback)
    intelligence_checklist = intelligence_feed.get_checklist_prompt()
    feed_meta = intelligence_feed.get_feed_metadata()
    feed_weeks = feed_meta.get("weeks_of_data", 0)
    feed_date = feed_meta.get("last_updated", "unknown")

    # Build the intelligence evaluation section
    intelligence_section = ""
    if intelligence_checklist:
        intelligence_section = f"""

## INTELLIGENCE FEED ({feed_weeks} weeks of curated data, updated {feed_date})

Use these intelligence items to inform your recommendations. Prioritise items marked as trend_alert or counter_signal.

{intelligence_checklist}

CRITICAL RULES:
1. If a counter-signal says "DO NOT recommend X", do NOT include X in your output.
2. PRESERVE the page's distinctive voice in all rewrites. Do NOT flatten personality into corporate speak.
"""

    # Build page type context
    if page_type:
        page_type_section = f"""
## PAGE TYPE CONTEXT
The page being optimised is a **{page_type}**. Adapt ALL recommendations to this page type:

- **Forside (Homepage):** Focus on entity definition, brand positioning, navigation structure, and trust signals. Do NOT recommend FAQ sections unless the brand specifically uses FAQ on homepage. Prioritise semantic triples that define the brand entity. H2 structure should reflect core value propositions and service categories, not questions.
- **Produktside (Product/Service page):** Focus on product-specific FAQ, feature-benefit structure, comparison signals, and purchase intent optimisation. JSON-LD should use Product or Service schema in addition to FAQ.
- **Blogginnlegg (Blog post):** Focus on topical authority, question-based H2s for featured snippets, comprehensive answer structure, internal linking to related posts and service pages. FAQ schema is appropriate here.
- **Landingsside (Landing page):** Focus on conversion-oriented structure, single clear CTA, benefit-driven headings, social proof signals. Minimal FAQ — only if it supports conversion.
- **FAQ-side (FAQ page):** Full FAQ optimisation — comprehensive Q&A pairs, FAQ schema, question clustering by topic, internal links from answers to relevant service/product pages.
- **Om oss (About page):** Focus on entity definition, team/founder bios as semantic triples, trust signals (awards, certifications, years in business), organisational schema markup.
- **Kategoriside (Category/listing page):** Focus on category definition, subcategory structure, breadcrumb optimisation, aggregated product/service signals, ItemList schema.
- **Kontaktside (Contact page):** Focus on LocalBusiness schema, NAP consistency, service area definition, minimal content optimisation — mainly technical.
"""
    else:
        page_type_section = """
## PAGE TYPE CONTEXT
No page type specified. Analyse the content and infer the page type. State your inference in the opening paragraph.
"""

    # Build domain context section (only if provided)
    domain_context_section = ""
    if domain_context and domain_context.strip():
        domain_context_section = f"""
## DOMAIN CONTEXT
The following is universal context about this domain/brand. Use this information to ground all recommendations, rewrites, and FAQs in the brand's actual identity, services, and positioning. This context applies to EVERY page on this domain.

{domain_context.strip()}
"""

    # --- Build system prompt (methodology + task instructions) ---
    system_prompt = f"""CRITICAL — OUTPUT LANGUAGE:
Detect the language of the PAGE CONTENT provided in the user message. Write the ENTIRE work package in that same language.

- If the page content is in English, write everything in English (including section headers, analysis, rewrites, FAQ, checklist — everything).
- If the page content is in Norwegian, write everything in Norwegian.
- If the page content is in another language, write everything in that language.

The section structure (Section 1, Section 2, etc.) stays the same regardless of language, but ALL text within each section must be in the detected language.
Do NOT default to Norwegian. Do NOT mix languages. The page content language is the ONLY signal that determines your output language.

---

You are an expert AEO (Answer Engine Optimization) consultant producing a complete work package for a client.
{page_type_section}
{domain_context_section}
## AEO METHODOLOGY REFERENCE
{aeo_guide_content}
{intelligence_section}

## YOUR TASK — PRODUCE A COMPLETE WORK PACKAGE

Write the work package as clean markdown. Do NOT wrap it in code fences. Do NOT output JSON.

Start with a **Key findings** paragraph (2-4 sentences) that summarises the biggest gap between the page's potential and current performance. If GSC/GA data is available in the context, reference the specific numbers (impressions, clicks, position, CTR, engagement time). If no suite data is available, say so once and proceed.

Then produce EXACTLY these 6 sections:

---

### Section 1: AEO priorities (summary)

Identify the top 3 AEO improvements. For each priority, use this structure:

#### Priority [number]: [what to change]
[Why it matters for AEO — 1 sentence]

**Current:**
> [quote the actual text from the page]

**Suggested:**
> [full replacement text]

These 3 priorities MUST be incorporated into the full page rewrite in Section 2.

---

### Section 2: Complete rewritten page text

Write the ENTIRE body text for the page, from the first paragraph after H1 to just before the FAQ section. This is the full replacement text the client pastes into their CMS.

Rules:
- Use standard markdown heading syntax for all headings: `#` for H1, `##` for H2, `###` for H3 etc. Do NOT use bracketed labels like [H1] or [H2].
- Include a subtitle line under the H1 heading (a short, compelling summary sentence)
- Start with a clear definition of the page's topic in the first sentence (semantic triple: "[Topic] is [definition]")
- Add a "Who uses [topic]?" section with a numbered list of industries/use cases
- Mark internal link opportunities as [link: /url-path] based on links found in the page content
- Write in the page's existing voice and tone — do NOT make it more corporate or generic
- Every paragraph must be substantive — no filler, no fluff
- Do NOT include the FAQ section here — that is Section 3

Add a note to the implementer explaining: this text replaces all existing body text from the first paragraph to just before the FAQ section. Images and visual content already on the page can be kept and placed where appropriate.

---

### Section 3: FAQ section — complete rewrite

Rewrite ALL FAQs on the page. Change the FAQ heading to be intent-based (e.g. "Frequently asked questions about [topic]") rather than brand-focused.

For EACH FAQ, use this exact markdown structure:

#### Q: [rewritten question matching user search intent]

**Current answer:**
> [quote the actual text from the page, or "Not present on page" if missing]

**New answer:**
[complete replacement, 3-6 sentences, comprehensive, entity-rich]

---

The `####`, blockquote for current answer, and horizontal rule between FAQs are mandatory formatting.

The new answers must:
- Answer the question directly in the first sentence
- Include specific details, numbers, and examples from the page content
- Be written to match the voice of the page
- Be self-contained (a reader should understand the answer without reading the rest of the page)

If the page has no FAQ section, create 5 intent-based FAQs with full answers based on the page content and common search queries for the topic.

---

### Section 4: Technical implementation

#### 4a. FAQ Schema Markup (JSON-LD)
Generate a complete, valid JSON-LD FAQPage schema containing ALL the new FAQ questions and answers from Section 3. Output it as a ready-to-paste `<script type="application/ld+json">` block. This goes in the page's `<head>` tag alongside any existing schema — do NOT replace existing Organization or other schema.

#### 4b. Heading structure (H2 tags)
List all the H2 sections from the rewritten page text (Section 2), numbered, confirming the heading hierarchy.

#### 4c. Publication date and author
Recommend adding a visible "Last updated: [date]" line under the H1. Explain why this matters for AI trust signals.

---

### Section 5: SEO improvements

#### 5a. Meta title and meta description
- Show the current meta title
- Write a new meta title (under 60 characters, includes primary keyword early)
- Write a new meta description (under 155 characters, includes a value proposition and call to action)

#### 5b. Internal linking
List additional internal links that should be added to the page, grouped by category (e.g. industry pages, solution pages). Explain where in the text each link fits naturally. Reference any links you already marked with [link:] in Section 2.

#### 5c. Link audit
Note any links on the page that point to wrong-language versions (e.g. /en/ links on a /no/ page) and flag them for fixing.

---

### Section 6: Implementation checklist

Create a checklist with checkbox markdown (`- [ ]`) grouped by category:
- Content (body text replacement, FAQ replacement, FAQ heading change)
- Technical (FAQ schema markup, H2 tags, publication date)
- SEO (meta title, meta description, internal links, link audit fixes)

---

## OUTPUT QUALITY RULES

1. FULL REWRITES ONLY. Every section must contain COMPLETE replacement text. No "consider adding...", no "you could improve...", no snippets. The client must be able to paste every piece of text directly into their CMS.
2. PRESERVE THE PAGE'S VOICE. Read the tone of the existing content and match it. If it's conversational, stay conversational. If it's formal, stay formal.
3. BE SPECIFIC. Reference actual content from the page. Quote real text. Use real URLs found in the content for internal links.
4. The JSON-LD in Section 4 must be syntactically valid and contain the EXACT question/answer text from Section 3.
5. Do NOT add explanatory meta-commentary about what you're doing. Just produce the work package.
6. REMEMBER: Write in the SAME LANGUAGE as the page content. English page = English output. Norwegian page = Norwegian output."""

    # --- Build user message (page-specific data) ---
    user_message = f"""{context_block}
## PAGE BEING ANALYZED

**Title:** {title}

**Direct Answer Score:** {direct_answer_score}/100

**First Paragraph:**
{first_paragraph}

**Page intent / what this page should achieve:**
{chr(10).join(f'- {intent}' for intent in selected_intents) if selected_intents else 'Not specified'}

**Citation Check Results:**
- Citation Rate: {citation_rate:.0f}%
- Cited Queries: {', '.join(cited_queries) if cited_queries else 'None'}
- Uncited Queries: {', '.join(uncited_queries) if uncited_queries else 'None'}
{competitor_section}

REMINDER: The page content below determines the output language. Detect its language and write your entire response in that language.

**Full Page Content:**
{content_for_analysis}"""

    try:
        if model_tier == "cheap":
            # o4-mini path
            oai_client = OpenAI(api_key=openai_key)

            # Build o4-mini system prompt with page type + domain context injected
            o4_system = O4_MINI_SYSTEM_PROMPT
            if page_type:
                o4_system += f"\nPAGE TYPE: This page is a **{page_type}**. Tailor all recommendations and rewrites to this page type.\n"
            if domain_context and domain_context.strip():
                o4_system += f"\nDOMAIN CONTEXT:\n{domain_context.strip()}\n"
            if intelligence_section:
                o4_system += f"\n{intelligence_section}\n"

            response = oai_client.chat.completions.create(
                model="gpt-4.1-mini-2025-04-14",
                messages=[
                    {"role": "system", "content": o4_system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=16000,
            )
            result_text = response.choices[0].message.content.strip()

            # Track usage
            try:
                from tracking.usage_tracker import log_usage_event
                _usage = response.usage
                _in = _usage.prompt_tokens if _usage else 0
                _out = _usage.completion_tokens if _usage else 0
                # gpt-4.1-mini pricing: $0.40/M input, $1.60/M output
                _cost = (_in * 0.4 + _out * 1.6) / 1_000_000
                log_usage_event(
                    event_type="arbeidspakke_generation",
                    api_provider="openai",
                    model="gpt-4.1-mini-2025-04-14",
                    input_tokens=_in,
                    output_tokens=_out,
                    estimated_cost_usd=_cost,
                    event_detail="model_tier=cheap",
                )
            except Exception:
                pass

        else:
            # Sonnet path (existing)
            client = Anthropic(api_key=anthropic_key)

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=16000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            result_text = message.content[0].text.strip()

            # Track usage
            try:
                from tracking.usage_tracker import log_usage_event
                _in = message.usage.input_tokens
                _out = message.usage.output_tokens
                _cost = (_in * 3 + _out * 15) / 1_000_000
                log_usage_event(
                    event_type="arbeidspakke_generation",
                    api_provider="anthropic",
                    model="claude-sonnet-4-20250514",
                    input_tokens=_in,
                    output_tokens=_out,
                    estimated_cost_usd=_cost,
                    event_detail="model_tier=expensive",
                )
            except Exception:
                pass

        # Both models return markdown directly — wrap in dict for compatibility with
        # _format_arbeidspakke() which reads recs.get('summary')
        return {
            "summary": result_text,
            "intelligence_applied": [],
            "critical_issues": [],
            "action_plan": [],
            "quick_wins": []
        }

    except Exception as e:
        return {
            "summary": f"Error generating arbeidspakke: {str(e)}",
            "intelligence_applied": [],
            "critical_issues": [],
            "action_plan": [],
            "quick_wins": []
        }
