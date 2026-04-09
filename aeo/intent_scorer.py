"""Local intent relevance scoring — no AI call, pure text matching."""
from __future__ import annotations

import re


def _tokenize(text: str) -> set[str]:
    """Lowercase tokenize, strip punctuation, remove stopwords."""
    _STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "and", "but", "or",
        "not", "no", "nor", "so", "yet", "both", "either", "neither", "this",
        "that", "these", "those", "it", "its", "what", "which", "who", "whom",
        "how", "when", "where", "why", "if", "then", "than", "very", "just",
        "about", "up", "out", "off", "over", "under", "again", "further",
        "om", "og", "i", "er", "en", "et", "det", "de", "som", "med", "på",
        "til", "av", "for", "fra", "har", "hva", "kan", "vil", "skal",
        "var", "ved", "den", "seg", "ikke", "men", "eller", "etter",
    }
    words = set(re.findall(r"[a-zA-ZæøåÆØÅäöÄÖüÜ]{2,}", text.lower()))
    return words - _STOPWORDS


def score_intent_relevance(
    selected_intents: list[str],
    title: str = "",
    h1: str = "",
    meta_description: str = "",
    h2_headings: list[str] | None = None,
) -> dict:
    """Score how well selected intents match the page content.

    Returns:
        {
            "total_score": 0-100,
            "keyword_overlap": 0-40,    # intent words found in page metadata
            "coverage": 0-35,           # how many H2 topics are covered by intents
            "specificity": 0-25,        # longer, more specific intents score higher
            "breakdown": [{"intent": str, "matched_elements": list[str], "word_count": int}]
        }
    """
    if not selected_intents:
        return {"total_score": 0, "keyword_overlap": 0, "coverage": 0, "specificity": 0, "breakdown": []}

    h2s = h2_headings or []

    # Build page token sets
    title_tokens = _tokenize(title)
    h1_tokens = _tokenize(h1)
    meta_tokens = _tokenize(meta_description)
    h2_tokens_list = [_tokenize(h) for h in h2s]
    all_page_tokens = title_tokens | h1_tokens | meta_tokens
    for ht in h2_tokens_list:
        all_page_tokens |= ht

    # --- Keyword overlap (0-40) ---
    # What % of intent words appear somewhere in the page metadata
    total_intent_words = 0
    total_matched_words = 0
    breakdown = []

    for intent in selected_intents:
        intent_tokens = _tokenize(intent)
        if not intent_tokens:
            breakdown.append({"intent": intent, "matched_elements": [], "word_count": len(intent.split())})
            continue

        total_intent_words += len(intent_tokens)
        matched = intent_tokens & all_page_tokens
        total_matched_words += len(matched)

        # Track which elements matched
        matched_elements = []
        if intent_tokens & title_tokens:
            matched_elements.append("title")
        if intent_tokens & h1_tokens:
            matched_elements.append("H1")
        if intent_tokens & meta_tokens:
            matched_elements.append("meta")
        for j, ht in enumerate(h2_tokens_list):
            if intent_tokens & ht:
                matched_elements.append(f"H2:{h2s[j][:30]}")
                break  # one H2 match is enough

        breakdown.append({
            "intent": intent,
            "matched_elements": matched_elements,
            "word_count": len(intent.split()),
        })

    keyword_ratio = total_matched_words / total_intent_words if total_intent_words > 0 else 0
    keyword_overlap = round(keyword_ratio * 40)

    # --- Coverage (0-35) ---
    # What % of H2 topics have at least one intent that matches them
    if h2s:
        covered_h2s = 0
        for ht in h2_tokens_list:
            if not ht:
                continue
            for intent in selected_intents:
                intent_tokens = _tokenize(intent)
                if intent_tokens & ht:
                    covered_h2s += 1
                    break
        coverage_ratio = covered_h2s / len(h2_tokens_list)
        coverage = round(coverage_ratio * 35)
    else:
        # No H2s available — give partial credit based on keyword overlap
        coverage = round(keyword_ratio * 15)

    # --- Specificity (0-25) ---
    # Longer intent phrases are more specific and useful
    avg_word_count = sum(len(i.split()) for i in selected_intents) / len(selected_intents)
    # 1-2 words = generic, 3-4 = good, 5+ = very specific
    if avg_word_count >= 5:
        specificity = 25
    elif avg_word_count >= 4:
        specificity = 20
    elif avg_word_count >= 3:
        specificity = 15
    elif avg_word_count >= 2:
        specificity = 8
    else:
        specificity = 3

    total_score = min(keyword_overlap + coverage + specificity, 100)

    return {
        "total_score": total_score,
        "keyword_overlap": keyword_overlap,
        "coverage": coverage,
        "specificity": specificity,
        "breakdown": breakdown,
    }
