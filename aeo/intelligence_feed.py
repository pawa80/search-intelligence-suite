from __future__ import annotations

"""
AEO Audit Agent - Intelligence Feed Module

Loads curated intelligence from newsletter analysis to make
recommendations trend-aware and non-generic.

Falls back gracefully if feed file is missing — agent works as before.
"""

import json
import os


FEED_PATH = os.path.join(os.path.dirname(__file__), "intelligence", "current_feed.json")
AEO_GUIDE_PATH = os.path.join(os.path.dirname(__file__), "intelligence", "aeo_guide.md")


def load_feed() -> dict | None:
    """Load the intelligence feed JSON. Returns None if missing or invalid."""
    try:
        with open(FEED_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def get_feed_metadata() -> dict:
    """Get feed version and date for display. Returns empty dict if no feed."""
    feed = load_feed()
    if not feed:
        return {}
    return {
        "version": feed.get("feed_version", "unknown"),
        "last_updated": feed.get("last_updated", "unknown"),
        "weeks_of_data": feed.get("weeks_of_data", 0),
    }


def get_current_feed() -> str:
    """Format the intelligence feed as a prompt-ready markdown string.

    Returns empty string if feed is missing, so the agent works exactly as before.
    """
    feed = load_feed()
    if not feed:
        return ""

    sections = []

    # Trend Alerts
    alerts = feed.get("trend_alerts", [])
    if alerts:
        sections.append("### Trend Alerts")
        for alert in alerts:
            confidence = alert.get("confidence", "medium").upper()
            sections.append(
                f"- **[{confidence}]** {alert['insight']}\n"
                f"  *Source: {alert.get('source', 'N/A')}*\n"
                f"  Implication: {alert.get('implication', '')}"
            )

    # Evolving Patterns
    patterns = feed.get("evolving_patterns", [])
    if patterns:
        sections.append("\n### Evolving Patterns")
        for p in patterns:
            sections.append(
                f"- **{p['pattern']}**\n"
                f"  First seen: {p.get('first_seen', 'N/A')} | "
                f"Latest: {p.get('latest_signal', 'N/A')}\n"
                f"  Impact on recommendations: {p.get('recommendation_impact', '')}"
            )

    # Counter-Signals (things NOT to recommend)
    counters = feed.get("counter_signals", [])
    if counters:
        sections.append("\n### Counter-Signals (DO NOT recommend these)")
        for c in counters:
            sections.append(
                f"- **Conventional wisdom:** {c['conventional_wisdom']}\n"
                f"  **Actual signal:** {c['actual_signal']}\n"
                f"  **Instead:** {c.get('action', '')}"
            )

    # Citation Patterns (from GEO Tracker data)
    citations = feed.get("citation_patterns", [])
    if citations:
        sections.append("\n### Citation Patterns (Evidence-Based)")
        for cp in citations:
            sections.append(
                f"- {cp['observation']}\n"
                f"  *Source: {cp.get('source', 'N/A')}* | "
                f"Quantified: {cp.get('quantified', 'N/A')}"
            )

    return "\n".join(sections)


def get_checklist_prompt() -> str:
    """Format intelligence items as an evaluatable checklist for the model.

    Each item becomes an explicit question the model must answer with a verdict.
    Returns empty string if feed is missing.
    """
    feed = load_feed()
    if not feed:
        return ""

    items = []
    item_num = 0

    for alert in feed.get("trend_alerts", []):
        item_num += 1
        confidence = alert.get("confidence", "medium").upper()
        items.append(
            f"INTELLIGENCE ITEM {item_num} [TREND ALERT — {confidence}]: "
            f"{alert['insight']}\n"
            f"  Implication: {alert.get('implication', '')}\n"
            f"  Source: {alert.get('source', 'N/A')}\n"
            f"  → Evaluate: Does this trend apply to the page being analyzed? "
            f"If YES, what specific change should be made?"
        )

    for p in feed.get("evolving_patterns", []):
        item_num += 1
        items.append(
            f"INTELLIGENCE ITEM {item_num} [EVOLVING PATTERN]: "
            f"{p['pattern']}\n"
            f"  Latest signal: {p.get('latest_signal', 'N/A')}\n"
            f"  Recommendation impact: {p.get('recommendation_impact', '')}\n"
            f"  → Evaluate: Does this pattern apply to the page? "
            f"If YES, what specific change should be made?"
        )

    for c in feed.get("counter_signals", []):
        item_num += 1
        items.append(
            f"INTELLIGENCE ITEM {item_num} [COUNTER-SIGNAL — DO NOT RECOMMEND]: "
            f"{c['conventional_wisdom']}\n"
            f"  Reality: {c['actual_signal']}\n"
            f"  Instead: {c.get('action', '')}\n"
            f"  → Evaluate: Were you about to recommend this conventional wisdom? "
            f"If so, STOP and recommend the alternative instead."
        )

    for cp in feed.get("citation_patterns", []):
        item_num += 1
        items.append(
            f"INTELLIGENCE ITEM {item_num} [CITATION PATTERN — EVIDENCE-BASED]: "
            f"{cp['observation']}\n"
            f"  Data: {cp.get('quantified', 'N/A')} ({cp.get('source', 'N/A')})\n"
            f"  → Evaluate: Does the page follow this citation pattern? "
            f"If NOT, what specific change would align it?"
        )

    return "\n\n".join(items)


def get_aeo_guide() -> str | None:
    """Load the AEO Guide from the synced markdown file.

    Returns None if the file doesn't exist, signalling the caller
    should fall back to the hardcoded AEO_GUIDE constant.
    """
    try:
        with open(AEO_GUIDE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
