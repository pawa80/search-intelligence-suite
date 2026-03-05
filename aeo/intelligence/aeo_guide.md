# AEO OPTIMIZATION GUIDE FOR AI APIs
**Version:** 1.1 | **Last Updated:** 5 March 2026
**Purpose:** Machine-readable reference for AI systems providing AEO optimization advice on web pages.
**Source:** Synced from Notion page 2f49fa1ce4f5805dac3edce68f48be61. Run sync_aeo_guide.py to update.

---

## SECTION 1: CORE PRINCIPLES

### 1.1 What is AEO?
Answer Engine Optimization (AEO) is the practice of structuring web content so AI-powered systems (ChatGPT, Perplexity, Google AI Overviews, Claude, Gemini) can extract, trust, and cite your content in generated answers.

**Key Distinction:**
- SEO = Optimize for discovery (clicks to website)
- AEO = Optimize for citation (become the answer)

### 1.2 The Citation Selection Model
AI answer engines evaluate content on three criteria:
1. **Confidence** - Can the AI confidently extract a clear answer?
2. **Authority** - Does the source appear trustworthy?
3. **Structure** - Is the content machine-readable?

### 1.3 The Grounding Budget (VERIFIED)
Research confirms AI systems operate with fixed token budgets when generating answers:
- **Total budget:** ~2,000 words per query
- **Rank #1 source:** ~531 words (28% of budget)
- **Rank #5 source:** ~266 words (13% of budget)
- **Grounding plateaus:** at ~540 words per source

**Optimization implication:** If your answer is buried past word 2,000, the AI will not see it to cite it. Front-load answers.

---

## SECTION 2: USER INTENT HIERARCHY

### 2.1 Primary Optimization Target
When analyzing a page, prioritize **User Intent** over topics or keywords.
AI systems evaluate: "How confidently can this content resolve the user's underlying goal?"

### 2.2 Intent Categories (Priority Order)
1. **Definitions** - "What is X?"
2. **How-to/Process** - "How do I X?"
3. **Comparisons** - "X vs Y"
4. **Direct Facts** - Specific data points, prices, dates
5. **Explanations** - "Why does X happen?"
6. **Lists/Collections** - "Best X for Y"

### 2.3 Implementation Hierarchy
| Focus Area | AEO Execution Tactic |
|---|---|
| Primary Intent | Identify the 1-2 specific questions the page MUST resolve |
| Front-Loading | Place direct answer in first 50-100 words |
| Structure | Use Q&A formatting and semantic triples |
| Heading Logic | Phrase subheadings as actual user questions |

---

## SECTION 3: CONTENT STRUCTURE RULES

### 3.1 Semantic Triples (CRITICAL)
The atomic unit of meaning for AI is: **Subject -> Predicate -> Object**

**Examples:**
- "HubSpot -> is -> a marketing automation platform"
- "Claude -> was created by -> Anthropic"
- "AEO -> optimizes content for -> AI answer engines"

**Why this matters:** AI models process relationships between entities. Explicit triples are easier to extract and verify than narrative prose. HubSpot reported 642% increase in AI citations after restructuring content into semantic triples.

### 3.2 Answer Positioning Rules
| Rule | Implementation |
|---|---|
| First 50 words | Must contain a direct, complete answer to primary intent |
| First 100 words | Should contain supporting context |
| First 500 words | Should contain all critical information for citation |
| Beyond 500 words | Supporting detail only; may fall outside grounding budget |

### 3.3 Content Format Patterns

**For Definition Intents:**
```
[Term] is [definition in one clear sentence].
[2-3 sentences of supporting context]
```

**For How-To Intents:**
```
To [achieve goal], [action steps in sequence].
1. [First step]
2. [Second step]
3. [Third step]
```

**For Comparison Intents:**
```
[Option A] differs from [Option B] in [key dimension].
[Option A]: [characteristic]
[Option B]: [characteristic]
```

### 3.4 Structural Elements Checklist
- H2 headings phrased as questions matching user queries
- Direct answer immediately follows each question heading
- Short paragraphs (75-300 words per section)
- Tables for comparative data
- Lists only when itemization adds clarity
- Summary box at top for key takeaways

---

## SECTION 4: TECHNICAL REQUIREMENTS

### 4.1 Schema Markup (Required)
JSON-LD is the recommended format. Implement these schema types:

| Content Type | Schema | Purpose |
|---|---|---|
| Q&A pairs | FAQPage | Highest citation rate for AI answers |
| Tutorials | HowTo | Step extraction for process queries |
| Articles | Article + Author | Authority and attribution signals |
| Products | Product + Review | Comparison and shopping queries |
| Business info | Organization + LocalBusiness | Entity recognition |

**FAQPage Example:**
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "[Exact user question]",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "[Direct answer in 1-3 sentences]"
    }
  }]
}
```

### 4.2 HTML Structure Requirements
- One H1 per page (the primary topic)
- Logical H2/H3/H4 hierarchy (never skip levels)
- Use `<article>`, `<section>`, `<aside>` semantic tags
- Wrap lists in proper `<ul>` or `<ol>` tags
- Keep critical content in HTML (not hidden in JavaScript)

### 4.3 Technical Baseline
- Core Web Vitals passing (LCP <2.5s, FID <100ms, CLS <0.1)
- Mobile responsive
- Clean, descriptive URLs
- XML sitemap submitted
- No critical content behind login/paywall

---

## SECTION 5: AUTHORITY SIGNALS

### 5.1 E-E-A-T for AEO
| Signal | Implementation |
|---|---|
| Experience | Include first-hand examples, case studies, screenshots |
| Expertise | Author credentials, certifications, professional context |
| Authority | Citations to reputable sources, data backing claims |
| Trust | Clear attribution, no anonymous content, contact information |

### 5.2 Citation-Building Tactics
- Include original data or research AI cannot find elsewhere
- Quote industry experts (with proper attribution)
- Reference authoritative sources (government, academic, industry bodies)
- Maintain consistency across all brand properties (website, social, directories)

### 5.3 Brand Authority for AEO
AI pulls citations from across the web. Optimize:
- Wikipedia/Wikidata presence if eligible
- Industry publication mentions
- Review site profiles (complete and consistent)
- Social media authority signals
- Press mentions and PR coverage

---

## SECTION 6: ANALYSIS FRAMEWORK

### 6.1 Page Audit Checklist
When analyzing a page for AEO optimization, evaluate:

**Intent Alignment (Weight: 40%)**
- Primary intent clearly identifiable?
- Answer to primary intent in first 100 words?
- Heading questions match likely user queries?

**Structure Quality (Weight: 30%)**
- Semantic triples present for key claims?
- Clear Q&A formatting?
- Logical heading hierarchy?
- Content scannable (short paragraphs, lists where appropriate)?

**Technical Implementation (Weight: 20%)**
- Relevant schema markup present?
- Schema validates without errors?
- Semantic HTML used correctly?

**Authority Signals (Weight: 10%)**
- Author/source clearly attributed?
- Claims backed by evidence?
- External citations to reputable sources?

### 6.2 Common Failure Patterns
| Problem | Solution |
|---|---|
| Answer buried below fold | Move direct answer to first paragraph |
| Narrative prose without structure | Restructure as semantic triples |
| Headings describe topics, not questions | Rephrase as user questions |
| No schema markup | Add FAQPage or relevant schema |
| Long paragraphs (500+ words) | Break into 75-300 word sections |
| Vague statements without specifics | Add concrete data, examples, numbers |

### 6.3 Priority Recommendation Order
When providing optimization advice, prioritize fixes in this order:
1. Add/move direct answer to first 50 words
2. Restructure key claims as semantic triples
3. Convert topic headings to question headings
4. Add FAQPage schema markup
5. Improve authority signals (citations, attribution)
6. Technical cleanup (HTML structure, performance)

---

## SECTION 7: OUTPUT TEMPLATES

### 7.1 Recommendation Format
When providing AEO advice, structure recommendations as:
```
**Issue:** [Specific problem identified]
**Impact:** [Why this hurts AEO visibility]
**Fix:** [Concrete action to take]
**Example Before:** [Current problematic content]
**Example After:** [Optimized version]
```

### 7.2 Direct Answer Template
When suggesting a front-loaded answer:
```
[Entity/Topic] is/does [clear definition/answer]. [Supporting detail in one sentence]. [Third sentence connecting to user's likely goal].
```

### 7.3 Semantic Triple Conversion
When converting narrative to semantic triples:

**Before (Narrative):**
"Our platform helps businesses manage their marketing workflows through automation."

**After (Triple):**
"[Platform Name] is a marketing automation platform. [Platform Name] automates marketing workflows. [Platform Name] serves businesses of all sizes."

---

## SECTION 8: METRICS & VALIDATION

### 8.1 AEO Success Indicators
- Citation frequency in AI answers
- Appearance in Google AI Overviews
- Featured snippet capture rate
- Share of voice in AI responses for target queries

### 8.2 Pre-Publication Checklist
- Direct answer score: First sentence answers primary intent?
- Structure score: Semantic triples for all key claims?
- Schema score: Relevant markup validates?
- Query alignment: Content matches likely user questions?

---

## SECTION 9: REFERENCE DATA

### 9.1 Key Statistics
- AI Overviews appear in 13-16% of Google searches (Jan 2026)
- 80% of consumers rely on zero-click results
- 40% of AI Overview citations rank beyond position 10 in traditional search
- Pages with FAQPage schema are 3.2x more likely to appear in AI Overviews
- AI-referred sessions increased 527% between Jan-May 2025

### 9.2 Platform Differences
| Platform | Optimization Priority |
|---|---|
| Google AI Overviews | E-E-A-T signals, freshness, mobile optimization |
| ChatGPT | Neutral tone, external citations, authoritative positioning |
| Perplexity | Conversational style, practical examples, real-time data |
| Claude | Structured content, clear reasoning, attribution |

### 9.3 Confidence Levels
This guide is based on:
- **High confidence (90%+):** Grounding budget research, schema implementation, structural best practices
- **Medium confidence (75-85%):** Intent hierarchy, authority signals
- **Evolving:** Platform-specific differences, long-term algorithm changes

---

## SECTION 10: API USAGE INSTRUCTIONS

### 10.1 When Analyzing a Page
1. Extract visible text content
2. Identify primary user intent(s) the page attempts to serve
3. Locate where (word position) the answer appears
4. Assess semantic triple presence for key claims
5. Check for schema markup presence
6. Generate prioritized recommendations

### 10.2 Output Requirements
- Be specific and actionable
- Include before/after examples
- Prioritize recommendations by impact
- Flag critical issues first (missing answers, buried content)
- Limit recommendations to 3-5 most impactful changes

### 10.3 Scope Boundaries
This guide covers content optimization only. Do not provide advice on:
- Paid advertising
- Social media strategy (except as authority signal)
- Link building tactics
- General SEO beyond AEO relevance

---

## SECTION 11: ADVANCED CITATION ACQUISITION

This section covers three research-backed tactics that determine citation rate but are not covered in Sections 1–10: content freshness mechanics, the "best of" listicle strategy, and cross-platform brand consistency.

### 11.1 Content Freshness as a Citation Signal (VERIFIED)

AI answer engines weight recency as a measurable trust signal, not just a quality proxy.

**Quantified benchmarks (2025–2026 research):**

| Metric | Data Point | Source |
|---|---|---|
| Content age of cited pages | 95% of ChatGPT citations from content published within last 10 months | Large-scale 129k domain analysis |
| Update recency of top-cited pages | 76.4% updated within last 30 days | Multiple 2025 studies |
| Timestamp visibility effect | Pages with visible "last updated" label receive ~1.8× more citations | 2025 AEO studies |
| Freshness weight in AEO scoring | ~10–15% of overall citation scoring model | AEO scoring frameworks |
| Improvement from systematic refresh | 3–6× improvement in citation rate once freshness is addressed | 2026 market reports |

**Implementation rules:**

| Tactic | Implementation |
|---|---|
| Technical timestamps | Add `datePublished` and `dateModified` in JSON-LD (ISO 8601 format) |
| On-page temporal markers | Include "Updated [Month Year]" in first 200 words |
| URL and title signals | Include current year in title tags, meta descriptions, URL slugs for evergreen content |
| Update cadence | Refresh highest-value pages at minimum monthly; even minor substantive updates register |
| Avoid cosmetic edits | Changing "2024" to "2025" without content changes does not trigger freshness signals |

**Optimization implication:** Freshness gates eligibility before other signals are evaluated on time-sensitive topics. A perfectly structured page with stale timestamps may be disqualified before grounding budget is allocated.

### 11.2 The "Best Of" Listicle Strategy

**Research basis:** Ahrefs analysis of 26,283 source URLs across ~750 "best X" prompts in ChatGPT.

**Core finding:** AI systems prefer to extract from a single comprehensive source rather than aggregate from multiple pages. This creates a structural citation advantage for "best of" style content.

**Key data points:**
- 44% of all ChatGPT citations come from "best of" / "top tools" / comparison list content
- 35% of cited listicles come from low-authority domains — domain strength is less important than structure and recency
- 79% of cited "best X" posts had been updated within the prior 90 days
- Tables within listicles increase citation likelihood 2.5× vs. unstructured list content

**The self-inclusion mechanic:** AI systems evaluate whether a source is structured, fresh, comprehensive, and crawlable — not whether it is editorially neutral. A brand that publishes a "Best [Category] Tools in 2026" article and includes itself is competing for citation on the same structural criteria as third-party reviews. This has been documented as a consistent pattern in Ahrefs' research (Asana, Zapier, and others).

**Implementation rules:**

| Requirement | Specification |
|---|---|
| Format | Listicle with numbered or structured entries |
| Update frequency | Minimum quarterly; monthly preferred |
| Table inclusion | Add comparison table — required for 2.5× citation multiplier |
| Self-inclusion | Position honestly; typically position 2–4 performs better than position 1 (appears less promotional to AI scoring) |
| Indexation | Ensure Bing indexes the page (ChatGPT uses Bing as primary crawl source) |
| Scope | Create minimum 3 "best X for Y" articles per core category |

**Confidence level:** High (85%) on content type dominance. Medium (70%) on self-inclusion citation mechanics — documented but not yet replicated across controlled studies.

### 11.3 Cross-Platform Brand Consistency

**Core finding:** Only ~11% of domains are cited by both ChatGPT and Perplexity. The overlap correlates with consistent, verifiable brand presence across multiple authoritative external sources — not with any single platform optimization.

**Why this matters:** AI systems verify entity claims by cross-referencing multiple sources. Inconsistent brand descriptions, founding dates, or product descriptions across platforms create entity confidence failures that suppress citation.

**High-priority citation platforms (ChatGPT + Perplexity overlap):**

| Platform | Citation Role |
|---|---|
| Wikipedia / Wikidata | ~29.7% of ChatGPT's top 1,000 citations; highest-weight entity validation source |
| Reddit | High citation rate for conversational and comparison queries |
| LinkedIn (company page) | Entity verification for B2B brands |
| G2 / Capterra / Trustpilot | Category citation sources for software and services |
| Industry directories and bodies | Domain-specific authority signals |
| Press/PR coverage | External attribution that validates brand claims |

**Implementation rules:**
- Audit brand name, description, founding date, product category, and target market across all platforms for consistency
- Prioritize Wikipedia/Wikidata presence if eligible — this single source has disproportionate impact
- Ensure consistent naming conventions (no variation between "Acme Corp", "Acme Corporation", "ACME")
- Treat each platform as a citation source, not a traffic source — the goal is entity corroboration, not clicks

**Confidence level:** Medium-high (80%) on cross-platform consistency as a citation driver. The 11% overlap figure is well-documented; causal mechanism between consistency and citation rate is directionally supported but not isolated in controlled research.

### 11.4 Multimodal Content Signals (Emerging — Lower Confidence)

**Note:** This area is evolving rapidly. Treat as directional guidance, not established best practice.

AI Overviews and answer engines are increasingly pulling from non-text content. Pages where visual and media signals reinforce text claims receive higher confidence scores than text-only pages.

**Current signal set:**
- **Image alt text**: Descriptive, contextual alt text is now an AEO signal, not only an accessibility requirement. Alt text should include entity names and semantic relationships consistent with the page's primary intent
- **Video transcripts**: Published transcripts and captions allow AI systems to extract claims from video content. A page with a video but no transcript is partially opaque to AI extraction
- **Image captions**: Treated as supporting claims for the adjacent text content
- **Schema for media**: `VideoObject` schema with `transcript` property and `ImageObject` schema increase extractability

**Confidence level:** Medium (65–70%). Direction is clear; specific citation rate impact of multimodal signals is not yet quantified in published research. Prioritize after Sections 11.1–11.3.

---

**Sources:** Ahrefs (2025), multiple large-scale AEO citation analyses (2025–2026), Perplexity-aggregated research. Statistics in Section 11 carry medium-high confidence. The 11.4 multimodal section is flagged as emerging. All data subject to same evolution caveat as Section 9.
