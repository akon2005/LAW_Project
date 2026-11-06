"""
Intent classification for support questions.

A transparent rule-based classifier is used on purpose:

* it is auditable — every decision can name the pattern that fired;
* it needs no training data, no model download and no GPU;
* the support domain has a small, stable intent set, so a learned model would
  add a dependency and an unvalidated accuracy claim for no benefit.

The classifier never decides *what to say*; it only picks which retrieval and
tool path to prefer. Retrieved documentation still grounds the answer, so a
mis-classified message degrades into a broader document search rather than into
an invented answer.

If a future change needs a learned classifier, replace :func:`classify` behind
the same return shape and keep the rule classifier as the fallback.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Pattern, Tuple

# Ordered: the first matching rule wins, so specific intents come first.
# Each rule is (intent, [regex, ...]).
_RULES: List[Tuple[str, List[str]]] = [
    (
        "general_greeting",
        [
            r"^\s*(hi|hey|hello|yo|good (morning|afternoon|evening))\b",
            r"^\s*(thanks|thank you|cheers|ok|okay|cool)\s*[!.?]*$",
        ],
    ),
    (
        "feedback",
        [
            r"\b(that (helped|worked)|not helpful|didn'?t help|wrong answer|this is wrong|bad answer|good answer|feedback)\b",
        ],
    ),
    (
        "report_problem",
        [
            r"\breport(ing)?\b.{0,40}\b(bug|problem|issue|defect|error|missing feature)\b",
            r"\b(file|submit|raise)\b.{0,20}\b(bug|ticket|complaint)\b",
            r"\b(bug report|support ticket|contact support)\b",
        ],
    ),
    (
        "demo_request",
        [
            r"\b(demo|example|examples|showcase|show me how|walk me through|try this|sample prompt|gallery)\b",
        ],
    ),
    (
        "supported_feature_query",
        [
            r"\b(which|what|list|is there|are there|does it|can it|do you have)\b.*\b(features?|capabilit(?:y|ies)|implemented|available)\b",
            r"\bfeature status\b",
            # "is X supported?" about a capability, not "is this response
            # supported by a judgment?" — hence the capability noun list.
            r"\b(is|are)\b\s+(the\s+)?(voice|speech|microphone|theme|dark mode|light mode|offline|export|api|statute|statutes|prediction)\b.*\bsupported\b",
        ],
    ),
    (
        "rag_explanation",
        [
            r"\b(rag|retrieval[- ]augmented|retrieval augmented|embeddings?|vector (store|search|database)|chromadb|semantic search)\b",
        ],
    ),
    (
        "system_status",
        [
            r"\b(system status|system health|health check|is the (system|server|backend|api|service) (healthy|up|down|alive|running|reachable))\b",
            r"\b(is (it|everything) (healthy|up|working right now))\b",
            r"\bwhat('?s| is) the (current )?status\b",
        ],
    ),
    (
        "troubleshooting",
        [
            r"\b(not working|doesn'?t work|isn'?t working|broken|error|errored|failed|failing|fails|crash|stuck|frozen|hanging|spinning)\b",
            r"\b(not|isn'?t|won'?t)\s+(respond|responding|reply|replying|answer|answering|load|loading)\b",
            r"\b(unresponsive|no response|no reply)\b",
            r"\b(timeout|timed out|took too long)\b",
            r"\b(no results?|nothing (came|comes|appears)|empty results?|zero results?|returned nothing)\b",
            r"\b(unavailable|can'?t|cannot|can not|unable to|offline|refused|blocked)\b",
            r"\b(missing citations?|no citations?|unverified)\b",
            r"\b(rate limit|quota|429|422|503|500)\b",
            r"\b(no|without|missing)\s+(llm|api key|generated\s+(summary|answer)|summar(?:y|ies))\b",
            r"\b(microphone|voice|speech)\b.*\b(not|doesn'?t|fails?|error|blocked|denied)\b",
        ],
    ),
    (
        "website_navigation",
        [
            r"\b(where (is|are|do|can)|how do i (get|find|reach|open|go))\b",
            r"\b(tab|tabs|page|pages|menu|navbar|navigate|navigation|dashboard|sidebar|screen)\b",
            r"\b(settings?|theme|dark mode|light mode|appearance|palette)\b",
        ],
    ),
    (
        "legal_research_guidance",
        [
            r"\b(case law|case-law|judgments?|precedents?|citation|citations|legal (query|research|search|issue|question))\b",
            r"\b(search for (relevant )?(judgments?|cases?|precedents?)|find relevant|submit a (legal )?query)\b",
            r"\b(interpret|understand|read) (the )?(results?|retrieved|precedents?)\b",
        ],
    ),
    (
        "project_architecture",
        [
            r"\b(architecture|tech stack|backend|front end|frontend|fastapi|react|repo|repository|folder|directory|codebase|pipeline stages?)\b",
            r"\b(how is (it|the system|the project) (built|structured|designed))\b",
            r"\b(data ?set|corpus|chromadb|ingest|vector store|data source|where does the data)\b",
        ],
    ),
    (
        "how_to",
        [
            r"\bhow (do|does|can|could|should|to|would|will|is|are)\b",
            r"\b(steps?|guide|instructions?|walk ?through|tutorial)\b",
            r"\b(help me|show me)\b.*\b(use|using|set ?up|configure)\b",
        ],
    ),
    (
        "feature_explanation",
        [
            r"\bwhat (is|are|does)\b",
            r"\bexplain|describe|tell me about|why (is|does|can)\b",
        ],
    ),
]

_COMPILED: List[Tuple[str, List[Pattern[str]]]] = [
    (intent, [re.compile(pattern, re.IGNORECASE) for pattern in patterns])
    for intent, patterns in _RULES
]

INTENTS = [
    "website_navigation",
    "system_status",
    "feature_explanation",
    "how_to",
    "troubleshooting",
    "project_architecture",
    "rag_explanation",
    "demo_request",
    "legal_research_guidance",
    "supported_feature_query",
    "feedback",
    "report_problem",
    "general_greeting",
    "unknown",
]


def classify(message: str) -> Dict[str, Any]:
    """
    Classify a support message.

    Returns ``{intent, matched, rule}``. ``unknown`` means no rule fired; the
    service then answers from document retrieval and says so if nothing matches.
    """
    text = (message or "").strip()
    if not text:
        return {"intent": "unknown", "matched": [], "rule": "empty"}

    # A very short message is a greeting, not a question.
    if len(text.split()) <= 3 and re.match(r"^\s*(hi|hey|hello|yo|thanks|thank you)\b", text, re.IGNORECASE):
        return {"intent": "general_greeting", "matched": ["greeting"], "rule": "short_greeting"}

    for intent, patterns in _COMPILED:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return {"intent": intent, "matched": [match.group(0).strip()], "rule": pattern.pattern}

    return {"intent": "unknown", "matched": [], "rule": "no_rule_fired"}
