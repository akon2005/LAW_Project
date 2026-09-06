"""
Trends API route for VIDHIVEDA.
POST /api/trends — Fetch historical legal trend analysis.
"""
import time
from fastapi import APIRouter, HTTPException

from app.models.schemas import TrendRequest, TrendResponse, SourceDocument
from app.services.pipeline import retrieve

router = APIRouter()


@router.post("/trends", response_model=TrendResponse)
async def analyze_trends(request: TrendRequest):
    """
    Analyze historical patterns in legal decisions for a given topic.
    Uses RAG to retrieve relevant cases and generates a trend analysis.
    """
    start_time = time.time()

    try:
        # Retrieve relevant cases for the topic
        retrieved_cases, is_low_confidence = retrieve(
            query=request.topic,
            top_k=request.top_k,
            filters=request.filters if request.filters else None,
        )

        if not retrieved_cases:
            elapsed = round(time.time() - start_time, 2)
            return TrendResponse(
                topic=request.topic,
                analysis="No relevant historical data found for this topic. Try broadening the search.",
                sources=[],
                key_principles=[],
                processing_time_seconds=elapsed,
            )

        # Build sources
        sources = []
        for case in retrieved_cases:
            sources.append(
                SourceDocument(
                    doc_id=case.get("case_id") or case.get("doc_id", ""),
                    title=case.get("case_name") or case.get("title", ""),
                    case_name=case.get("case_name") or case.get("title", ""),
                    document_type=case.get("document_type") or case.get("legal_domain") or "case_law",
                    court=case.get("court", ""),
                    year=case.get("year", 0),
                    relevance_score=case.get("similarity_score", 0.0),
                    similarity_score=case.get("similarity_score", 0.0),
                    snippet=case.get("retrieval_document", "")[:500],
                    citation=case.get("citation", ""),
                )
            )

        # Generate trend analysis using local synthesis (no LLM dependency)
        analysis = _generate_trend_analysis(request.topic, retrieved_cases)

        # Extract key principles
        key_principles = _extract_trend_principles(request.topic, retrieved_cases)

        elapsed = round(time.time() - start_time, 2)

        return TrendResponse(
            topic=request.topic,
            analysis=analysis,
            sources=sources,
            key_principles=key_principles,
            processing_time_seconds=elapsed,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _generate_trend_analysis(topic: str, cases: list) -> str:
    """Generate a structured trend analysis from retrieved cases."""
    if not cases:
        return "No data available for trend analysis."

    # Extract metadata
    courts = list(dict.fromkeys(c.get("court") for c in cases if c.get("court")))
    years = [c.get("year") for c in cases if c.get("year")]
    domains = list(dict.fromkeys(c.get("legal_domain") for c in cases if c.get("legal_domain")))

    min_year = min(years) if years else "N/A"
    max_year = max(years) if years else "N/A"

    # Build year distribution
    year_counts = {}
    for y in years:
        year_counts[y] = year_counts.get(y, 0) + 1

    year_dist = "\n".join(f"  - {y}: {count} case(s)" for y, count in sorted(year_counts.items()))

    # Build case summaries
    case_summaries = []
    for i, c in enumerate(cases[:10], 1):
        name = c.get("case_name", "Unknown")
        yr = c.get("year", "N/A")
        court = c.get("court", "N/A")
        snippet = c.get("retrieval_document", "")[:200]
        case_summaries.append(f"**[{i}] {name} ({yr})** — {court}\n> {snippet}")

    cases_text = "\n\n".join(case_summaries)

    analysis = f"""## Historical Trend Analysis: {topic}

### Dataset Overview
- **Total relevant precedents**: {len(cases)}
- **Time range**: {min_year} – {max_year}
- **Courts involved**: {', '.join(courts[:6]) if courts else 'Multiple jurisdictions'}
- **Legal domains**: {', '.join(domains[:4]) if domains else 'Various'}

### Year-wise Distribution
{year_dist}

### Key Precedents
{cases_text}

### Observations
1. The analysis covers **{len(cases)} judicial decisions** spanning from {min_year} to {max_year}.
2. Cases were heard across **{len(courts)} court(s)**, indicating {"broad jurisdictional interest" if len(courts) > 3 else "concentrated judicial attention"} in this area.
3. The legal domain primarily falls under **{', '.join(domains[:3]) if domains else 'general legal principles'}**.

---
*This trend analysis is compiled from the VIDHIVEDA judicial database. It is provided as historical research input and does not predict or recommend any judicial outcome.*"""

    return analysis


def _extract_trend_principles(topic: str, cases: list) -> list:
    """Extract key principles relevant to the trend topic."""
    principles = []
    q_lower = topic.lower()

    principle_keywords = {
        "arbitration": "Arbitration & Conciliation Act, 1996",
        "contract": "Indian Contract Act, 1872",
        "commercial": "Commercial Courts Act, 2015",
        "mediation": "Pre-Institution Mediation",
        "compensation": "Compensation & Damages Framework",
        "damages": "Compensation & Damages Framework",
        "limitation": "Limitation Act, 1963",
        "jurisdiction": "Jurisdictional Determination",
        "constitutional": "Constitutional Law Principles",
        "fundamental right": "Fundamental Rights Analysis",
        "criminal": "Criminal Procedure Code",
        "family": "Family Law Principles",
        "property": "Property Law Framework",
        "intellectual property": "IP Law Framework",
        "tax": "Tax Law Analysis",
    }

    for keyword, principle in principle_keywords.items():
        if keyword in q_lower:
            principles.append(principle)

    # Add general principles
    principles.extend([
        "Judicial Precedent Analysis",
        "Statutory Compliance",
    ])

    return list(dict.fromkeys(principles))[:6]
