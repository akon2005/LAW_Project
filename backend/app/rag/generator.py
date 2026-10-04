"""
RAG Generation service for LexRAG.
Uses an LLM (OpenAI or Anthropic) to generate citation-backed legal research answers.
This is a research assistant — never a decision-maker.
"""
from typing import List, Optional
from app.core.config import (
    LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY,
    OPENAI_MODEL, ANTHROPIC_MODEL,
)

# ── System Prompts ─────────────────────────────────────────────────────

RESEARCH_SYSTEM_PROMPT = """You are VIDHIVEDA, an AI-powered legal research assistant for Indian courts, developed for the Department of Justice, Ministry of Law & Justice (SIH1701).

CRITICAL RULES:
1. You are a RESEARCH ASSISTANT, NOT a decision-maker. Never issue verdicts, recommendations, or definitive legal opinions.
2. ALWAYS cite specific source documents by their title, year, and court when making any legal statement.
3. Use formal legal language appropriate for Indian courts.
4. If the retrieved documents don't contain sufficient information to answer, say so explicitly.
5. Do NOT hallucinate cases, statutes, or facts — only reference documents provided to you.
6. Structure your responses with clear headings and numbered citations.
7. End every response with the disclaimer: "This is AI-generated research support and does not constitute legal advice."
8. Be objective and balanced — present multiple perspectives when they exist in the sources."""

SUMMARY_SYSTEM_PROMPT = """You are VIDHIVEDA, an AI legal research assistant. Your task is to generate concise, accurate summaries of legal documents (case judgments, statutes, notifications).

RULES:
1. Extract the key facts, legal issues, holdings, and reasoning.
2. Identify applicable legal sections and principles.
3. Be objective and factual — do not add interpretation.
4. Structure the summary with: Background, Issues, Holdings, Reasoning, Key Sections.
5. Keep summaries to 200-400 words."""

TREND_SYSTEM_PROMPT = """You are VIDHIVEDA, an AI legal research assistant analyzing historical patterns in Indian court decisions.

CRITICAL RULES:
1. Present findings ONLY as historical data analysis, NEVER as predictions of future outcomes.
2. Frame all insights as "research input" — never suggest what a court should or will decide.
3. Cite specific cases and statistics from the provided data.
4. Include appropriate caveats about the limitations of trend analysis.
5. Be transparent about sample size and potential biases in the data."""


# ── Prompt Builders ────────────────────────────────────────────────────

def build_research_prompt(
    query: str,
    retrieved_docs: List[dict],
) -> str:
    """Build the RAG prompt with query + retrieved document chunks as context."""
    context = ""
    for i, doc in enumerate(retrieved_docs, 1):
        meta = doc.get("metadata", {})
        context += f"""
--- SOURCE {i} ---
Title: {meta.get('title', 'Unknown')}
Type: {meta.get('document_type', 'Unknown')}
Court: {meta.get('court', 'N/A')}
Jurisdiction: {meta.get('jurisdiction', 'N/A')}
Year: {meta.get('year', 'N/A')}
Sections: {meta.get('sections_str', 'N/A')}
Relevance: {doc.get('relevance_score', 0):.1%}

Content:
{doc.get('document', 'N/A')}
"""

    prompt = f"""## RESEARCH QUERY
{query}

## RETRIEVED SOURCES ({len(retrieved_docs)} documents)
{context}

## TASK
Based on the above retrieved source documents, provide a comprehensive research answer to the query. You must:

1. **Direct Answer**: Address the query directly using information from the sources.
2. **Legal Framework**: Identify relevant statutes, sections, and legal principles.
3. **Case Analysis**: Reference specific cases from the sources that are relevant.
4. **Key Principles**: Extract the key legal principles that emerge from the sources.
5. **Citations**: Number each source citation [1], [2], etc. corresponding to the source numbers above.

If the sources don't contain enough information to fully answer the query, clearly state what information is missing.

Conclude with: "This is AI-generated research support and does not constitute legal advice.\""""

    return prompt


def build_summary_prompt(doc: dict) -> str:
    """Build a prompt for document summarization."""
    return f"""## DOCUMENT TO SUMMARIZE

**Title**: {doc.get('title', 'Unknown')}
**Type**: {doc.get('document_type', 'Unknown')}
**Court**: {doc.get('court', 'N/A')}
**Year**: {doc.get('year', 'N/A')}
**Sections**: {', '.join(doc.get('sections', []))}

**Full Text**:
{doc.get('full_text', '')}

## TASK
Generate a structured summary covering:
1. **Background**: Brief context and facts
2. **Legal Issues**: Key legal questions addressed
3. **Holdings/Provisions**: Main decisions or statutory provisions
4. **Reasoning**: Court's reasoning or legislative intent
5. **Key Sections**: Applicable legal sections
6. **Key Principles**: Important legal principles established

Keep the summary between 200-400 words. Be factual and objective."""


def build_trend_prompt(
    topic: str,
    retrieved_docs: List[dict],
) -> str:
    """Build a prompt for trend analysis."""
    context = ""
    for i, doc in enumerate(retrieved_docs, 1):
        meta = doc.get("metadata", {})
        context += f"""
--- DATA POINT {i} ---
Title: {meta.get('title', 'Unknown')}
Year: {meta.get('year', 'N/A')}
Court: {meta.get('court', 'N/A')}
Outcome: {meta.get('outcome', 'N/A')}
Sections: {meta.get('sections_str', 'N/A')}
Content Excerpt: {doc.get('document', '')[:500]}
"""

    return f"""## TREND ANALYSIS REQUEST
Topic: {topic}

## HISTORICAL DATA ({len(retrieved_docs)} relevant documents)
{context}

## TASK
Analyze the historical patterns and trends in the provided data regarding "{topic}". You must:

1. **Pattern Identification**: Identify any patterns in how courts have approached this topic.
2. **Statistical Summary**: Summarize the data (outcome distribution, timeline, courts involved).
3. **Evolving Interpretation**: Note how legal interpretation has evolved over time, if applicable.
4. **Jurisdictional Variations**: Highlight any differences across jurisdictions or courts.

CRITICAL: Frame ALL findings as historical analysis. Do NOT predict future outcomes or suggest what a court should decide. Include appropriate caveats about limitations.

End with: "This trend analysis is provided as research input only and does not predict or recommend any judicial outcome.\""""


# ── Generation Functions ───────────────────────────────────────────────

async def generate_research_answer(
    query: str,
    retrieved_docs: List[dict],
) -> dict:
    """Generate a citation-backed research answer using RAG."""
    prompt = build_research_prompt(query, retrieved_docs)
    return await _generate(RESEARCH_SYSTEM_PROMPT, prompt, retrieved_docs)


async def generate_summary(doc: dict) -> dict:
    """Generate an AI summary of a legal document."""
    prompt = build_summary_prompt(doc)
    result = await _generate(SUMMARY_SYSTEM_PROMPT, prompt, [])

    # Extract key points from summary
    key_points = _extract_key_points(result.get("answer", ""))
    cited_sections = doc.get("sections", [])

    return {
        "doc_id": doc.get("doc_id", ""),
        "title": doc.get("title", ""),
        "summary": result.get("answer", ""),
        "key_points": key_points,
        "cited_sections": cited_sections,
    }


async def generate_trend_analysis(
    topic: str,
    retrieved_docs: List[dict],
) -> dict:
    """Generate trend/predictive insights from historical data."""
    prompt = build_trend_prompt(topic, retrieved_docs)
    return await _generate(TREND_SYSTEM_PROMPT, prompt, retrieved_docs)


async def _generate(
    system_prompt: str,
    user_prompt: str,
    retrieved_docs: List[dict],
) -> dict:
    """Route to the configured LLM provider."""
    if LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        result = await _generate_openai(system_prompt, user_prompt)
    elif LLM_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        result = await _generate_anthropic(system_prompt, user_prompt)
    else:
        result = _generate_template(user_prompt, retrieved_docs)
    return result


async def _generate_openai(system_prompt: str, user_prompt: str) -> dict:
    """Generate using OpenAI API."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        answer = response.choices[0].message.content
        key_principles = _extract_key_principles(answer)

        return {
            "answer": answer,
            "key_principles": key_principles,
        }
    except Exception as e:
        print(f"[Generator] OpenAI error: {e}")
        return {"answer": f"LLM generation error: {str(e)}", "key_principles": []}


async def _generate_anthropic(system_prompt: str, user_prompt: str) -> dict:
    """Generate using Anthropic Claude API."""
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=ANTHROPIC_MODEL,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        answer = response.content[0].text
        key_principles = _extract_key_principles(answer)

        return {
            "answer": answer,
            "key_principles": key_principles,
        }
    except Exception as e:
        print(f"[Generator] Anthropic error: {e}")
        return {"answer": f"LLM generation error: {str(e)}", "key_principles": []}


def _generate_template(user_prompt: str, retrieved_docs: List[dict]) -> dict:
    """Template-based fallback when no LLM API is configured."""
    sources_summary = []
    for i, doc in enumerate(retrieved_docs[:5], 1):
        meta = doc.get("metadata", {})
        title = meta.get("title", "Unknown Document")
        year = meta.get("year", "N/A")
        court = meta.get("court", "N/A")
        doc_type = meta.get("document_type", "document")
        relevance = doc.get("relevance_score", 0)
        snippet = doc.get("document", "")[:300]

        sources_summary.append(
            f"**[{i}] {title} ({year})** — {court} | {doc_type} | "
            f"Relevance: {relevance:.0%}\n> {snippet}..."
        )

    answer = f"""## Research Results

Based on the retrieved legal documents, here are the most relevant sources for your query:

### Relevant Sources

{chr(10).join(sources_summary)}

### Note
This is a template-based response. For AI-generated analysis with detailed legal reasoning, configure an LLM API key (OpenAI or Anthropic) in your `.env` file.

*⚠️ This is AI-generated research support and does not constitute legal advice.*"""

    return {
        "answer": answer,
        "key_principles": ["Configure LLM API for full analysis"],
    }


def _extract_key_principles(text: str) -> List[str]:
    """Extract key legal principles from generated text."""
    principles = []
    keywords = {
        "burden of proof": "Burden of proof allocation",
        "beyond reasonable doubt": "Criminal standard: beyond reasonable doubt",
        "preponderance of evidence": "Civil standard: preponderance of evidence",
        "natural justice": "Principles of natural justice",
        "audi alteram partem": "Right to be heard (audi alteram partem)",
        "res judicata": "Res judicata — matter already judged",
        "stare decisis": "Stare decisis — precedent binding",
        "ratio decidendi": "Ratio decidendi — reason for decision",
        "obiter dictum": "Obiter dictum — incidental remarks",
        "ultra vires": "Ultra vires — beyond authority",
        "due process": "Due process requirements",
        "fundamental right": "Fundamental rights consideration",
        "limitation period": "Limitation period applicability",
        "commercial dispute": "Commercial dispute classification",
        "specified value": "Specified value threshold",
        "arbitration": "Arbitration clause/proceedings",
    }
    text_lower = text.lower()
    for keyword, principle in keywords.items():
        if keyword in text_lower:
            principles.append(principle)
    return principles[:8]


def _extract_key_points(text: str) -> List[str]:
    """Extract key bullet points from a summary."""
    import re
    points = []
    # Look for numbered or bulleted items
    patterns = [
        r'\d+\.\s+\*\*(.+?)\*\*',  # 1. **Point**
        r'[-•]\s+(.+?)(?:\n|$)',     # - Point or • Point
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        points.extend(matches)
    # Deduplicate and limit
    return list(dict.fromkeys(points))[:10]
