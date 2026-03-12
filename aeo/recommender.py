from __future__ import annotations

"""
AEO Audit Agent - Recommendations Engine

Uses OpenAI GPT-4o-mini to generate complete arbeidspakker (work packages)
with full page rewrites, FAQ replacements, JSON-LD schema, and SEO improvements.
Output language matches the page content language.
"""

import json
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
import requests

import intelligence_feed


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


def generate_recommendations(title, full_content, first_paragraph, direct_answer_score, citation_results, selected_intents, api_key, context_block=""):
    """Generate a complete arbeidspakke with full page rewrites matching the gold standard.

    v2.0: Outputs a complete 6-section arbeidspakke in the language of the page content.
    Full rewrites — no snippets, no suggestions. Paste-ready for CMS.
    """

    client = OpenAI(api_key=api_key)

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

    prompt = f"""You are an expert AEO (Answer Engine Optimization) consultant producing a complete arbeidspakke (work package) for a client.

## CRITICAL LANGUAGE RULE
Detect the language of the page content below. Write the ENTIRE arbeidspakke in THAT language. If the page is in Norwegian, write everything in Norwegian. If English, write in English. This applies to all sections, headings, analysis text, and rewrites. The only exception is technical markup (HTML tags, JSON-LD) which stays in English.

## AEO METHODOLOGY REFERENCE
{aeo_guide_content}
{intelligence_section}
{context_block}
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

**Full Page Content:**
{content_for_analysis}

## YOUR TASK — PRODUCE A COMPLETE ARBEIDSPAKKE

Write the arbeidspakke as clean markdown. Do NOT wrap it in code fences. Do NOT output JSON.

Start with a "Hovedfunn" / "Key findings" paragraph (2-4 sentences) that summarises the biggest gap between the page's potential and current performance. If GSC/GA data is available in the context above, reference the specific numbers (impressions, clicks, position, CTR, engagement time). If no suite data is available, say so once and proceed.

Then produce EXACTLY these 6 sections:

---

### Section 1: AEO priorities (summary)

Identify the top 3 AEO improvements. For each priority:
- State the priority and what to change
- Explain WHY it matters for AEO (1 sentence)
- Show a two-column comparison:
  - **Current:** Quote the actual text from the page
  - **Suggested:** Write the full replacement text

These 3 priorities MUST be incorporated into the full page rewrite in Section 2.

---

### Section 2: Complete rewritten page text

Write the ENTIRE body text for the page, from the first paragraph after H1 to just before the FAQ section. This is the full replacement text the client pastes into their CMS.

Rules:
- Mark all headings as [H1], [H2], [H3] etc.
- Include a subtitle line under [H1] (a short, compelling summary sentence)
- Start with a clear definition of the page's topic in the first sentence (semantic triple: "[Topic] is [definition]")
- Add a "Who uses [topic]?" section with a numbered list of industries/use cases
- Mark internal link opportunities as [link: /url-path] based on links found in the page content
- Write in the page's existing voice and tone — do NOT make it more corporate or generic
- Every paragraph must be substantive — no filler, no fluff
- Do NOT include the FAQ section here — that is Section 3

Add a note to the implementer explaining: this text replaces all existing body text from the first paragraph to just before the FAQ section. Images and visual content already on the page can be kept and placed where appropriate.

---

### Section 3: FAQ section — complete rewrite

Rewrite ALL FAQs on the page. Change the FAQ heading to be intent-based (e.g. "Vanlige spørsmål om [topic]" / "Frequently asked questions about [topic]") rather than brand-focused.

For EACH FAQ:
- Show the question (rewrite it to match user search intent, not brand language)
- Show the current answer (quote the actual text)
- Show the new answer (complete replacement, 3-6 sentences, comprehensive, entity-rich)

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
5. Do NOT add explanatory meta-commentary about what you're doing. Just produce the arbeidspakke.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16000,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()

        # GPT returns markdown directly — wrap in dict for compatibility with
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
