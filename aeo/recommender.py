from __future__ import annotations

"""
AEO Audit Agent - Recommendations Engine

Uses OpenAI GPT-4o-mini to generate actionable recommendations for improving
a page's chances of being cited by AI search engines.
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

## OUTPUT FORMAT

When analyzing a page, provide:
1. **Summary:** 2-3 sentence AEO assessment
2. **Critical Issues:** Urgent problems affecting citation probability
3. **Action Plan:** Prioritized fixes with before/after examples
4. **Quick Wins:** Easy changes with immediate impact
"""


@dataclass
class RecommendationResult:
    """Result of recommendation generation."""
    recommendations: list[str]
    success: bool
    error: Optional[str] = None


def generate_recommendations(title, full_content, first_paragraph, direct_answer_score, citation_results, selected_intents, api_key, context_block=""):
    """Generate intelligence-first AEO recommendations with structured output.

    v0.8: Intelligence items are an explicit evaluation checklist — each one
    gets a verdict (APPLIES/NOT_APPLICABLE/RESPECTED). Recommendations must
    cite their intelligence source.
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

    # Truncate full_content to prevent token overflow (keep first 8000 chars)
    content_for_analysis = full_content[:8000] if full_content else ""

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

## INTELLIGENCE EVALUATION CHECKLIST ({feed_weeks} weeks of curated data, updated {feed_date})

You MUST evaluate EVERY intelligence item below against the page. For each item, determine:
- APPLIES: This intelligence is relevant and the page needs changes based on it
- NOT_APPLICABLE: This intelligence doesn't apply to this page (explain briefly why)
- RESPECTED: For counter-signals only — confirms you are NOT making this mistake

{intelligence_checklist}

CRITICAL RULES:
1. You MUST include ALL intelligence items in your "intelligence_applied" output array with a verdict for each.
2. Every action_plan item MUST have an "intelligence_source" field citing which intelligence item or AEO principle drives it.
3. If a counter-signal says "DO NOT recommend X", check your recommendations — if any recommend X, remove them and replace with the alternative.
4. PRESERVE the page's distinctive voice in all suggested rewrites. Do NOT flatten personality into corporate speak.
"""

    prompt = f"""You are an AEO (Answer Engine Optimization) expert. You have TWO sources of knowledge:
1. Foundational AEO methodology (timeless principles)
2. A live intelligence feed from {feed_weeks} weeks of curated AI search industry analysis (current trends)

Your recommendations MUST be driven by specific intelligence items, not generic best practices.

## AEO METHODOLOGY REFERENCE (Foundational)
{aeo_guide_content}
{intelligence_section}
{context_block}## PAGE BEING ANALYZED

**Title:** {title}

**Direct Answer Score:** {direct_answer_score}/100

**First Paragraph:**
{first_paragraph}

**User Intents Being Targeted:**
{chr(10).join(f'- {intent}' for intent in selected_intents) if selected_intents else 'None specified'}

**Citation Check Results:**
- Citation Rate: {citation_rate:.0f}%
- Cited Queries: {', '.join(cited_queries) if cited_queries else 'None'}
- Uncited Queries: {', '.join(uncited_queries) if uncited_queries else 'None'}
{competitor_section}

**Full Page Content:**
{content_for_analysis}

## YOUR TASK

1. First, evaluate EVERY intelligence item against this page (see checklist above).
2. Then, generate recommendations that are DRIVEN BY the intelligence evaluation.
3. Each recommendation must cite its intelligence source.

IMPORTANT: Each critical issue and action plan item MUST reference which specific user intent it affects.
Use format: 'For intent "[intent name]": [issue description]'

Respond ONLY with valid JSON in this exact format:
{{
    "summary": "2-3 sentence assessment referencing specific intelligence findings",
    "intelligence_applied": [
        {{
            "item": "Short name of the intelligence item",
            "type": "trend_alert|evolving_pattern|counter_signal|citation_pattern",
            "verdict": "APPLIES|NOT_APPLICABLE|RESPECTED",
            "impact": "How this intelligence item specifically affects this page (1-2 sentences)"
        }}
    ],
    "critical_issues": ["For intent '[specific intent]': issue description driven by intelligence finding"],
    "action_plan": [
        {{
            "priority": 1,
            "action": "Specific action to take",
            "reason": "Why this matters — referencing the intelligence source",
            "intelligence_source": "Name of the intelligence item or AEO principle driving this",
            "current_text": "Quote the problematic text from the page",
            "suggested_text": "Rewritten version that preserves the page's voice while improving AEO structure"
        }},
        {{
            "priority": 2,
            "action": "Second action",
            "reason": "Why this matters",
            "intelligence_source": "Intelligence item or principle",
            "current_text": "Current text",
            "suggested_text": "Improved text"
        }},
        {{
            "priority": 3,
            "action": "Third action",
            "reason": "Why this matters",
            "intelligence_source": "Intelligence item or principle",
            "current_text": "Current text if applicable",
            "suggested_text": "Improved text if applicable"
        }}
    ],
    "quick_wins": ["Easy change 1", "Easy change 2", "Easy change 3"]
}}

The intelligence_applied array MUST contain one entry for EVERY intelligence item in the checklist. Do not skip any.
Focus on the MOST impactful changes first. Be specific — quote actual text and provide concrete rewrites.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()

        # Clean up JSON if wrapped in markdown code blocks
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        return json.loads(result_text)

    except json.JSONDecodeError as e:
        return {
            "summary": "Unable to parse recommendations. Please try again.",
            "intelligence_applied": [],
            "critical_issues": [],
            "action_plan": [],
            "quick_wins": []
        }
    except Exception as e:
        return {
            "summary": f"Error generating recommendations: {str(e)}",
            "intelligence_applied": [],
            "critical_issues": [],
            "action_plan": [],
            "quick_wins": []
        }
