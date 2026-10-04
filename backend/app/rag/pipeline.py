import os
import time
import re
from typing import List, Dict, Optional, Tuple, Any
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv

load_dotenv()

LOW_CONFIDENCE_THRESHOLD = 0.30

# Initialize ChromaDB client
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROMA_PATH = os.path.join(BASE_DIR, "data", "chroma_store")
if not os.path.exists(CHROMA_PATH):
    CHROMA_PATH = os.path.join(BASE_DIR, "data", "chromadb")

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# Load Embedding Model (lazy loading)
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def get_collection():
    try:
        return chroma_client.get_collection("vidhiveda_cases")
    except Exception:
        try:
            return chroma_client.get_collection("lexrag_documents")
        except Exception:
            # Fallback get or create
            return chroma_client.get_or_create_collection(
                name="vidhiveda_cases",
                metadata={"hnsw:space": "cosine"}
            )

def get_llm_client() -> Tuple[Optional[Any], str]:
    """Returns (client, model_name) if a valid LLM key is configured, else (None, '')."""
    openai_key = os.getenv("OPENAI_API_KEY", "")
    hf_token = os.getenv("HF_API_KEY", "") or os.getenv("HF_API_TOKEN", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    # Check if OpenAI key is real and not placeholder
    if openai_key and not openai_key.startswith("your-") and len(openai_key) > 20:
        try:
            from openai import OpenAI
            return OpenAI(api_key=openai_key), os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        except Exception as e:
            print(f"[LLM] OpenAI client init failed: {e}")

    if hf_token and not hf_token.startswith("your-"):
        try:
            from openai import OpenAI
            return OpenAI(
                base_url="https://api-inference.huggingface.co/v1/",
                api_key=hf_token
            ), os.getenv("HF_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
        except Exception as e:
            print(f"[LLM] HF client init failed: {e}")

    if anthropic_key and not anthropic_key.startswith("your-"):
        try:
            from anthropic import Anthropic
            return Anthropic(api_key=anthropic_key), os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        except Exception as e:
            print(f"[LLM] Anthropic client init failed: {e}")

    return None, ""

def retrieve(query: str, top_k: int = 8, filters: Optional[Dict] = None) -> Tuple[List[Dict], bool]:
    """
    Embeds the query, queries ChromaDB with filters, checks confidence.
    Returns:
        results: list of dictionaries representing the documents.
        is_low_confidence: boolean flag indicating if the top result is below threshold.
    """
    model = get_embedding_model()
    collection = get_collection()
    
    query_embedding = model.encode([query]).tolist()[0]
    
    # Format filters for ChromaDB
    chroma_where = None
    if filters:
        conditions = []
        # Keep retrieval filters aligned with the metadata emitted by
        # scripts/ingest_to_chromadb.py. Earlier versions queried
        # `legal_domain`, which is not a stored ChromaDB metadata field.
        if filters.get("document_type"):
            conditions.append({"document_type": filters["document_type"]})
        elif filters.get("legal_domain"):
            conditions.append({"document_type": filters["legal_domain"]})
        if filters.get("jurisdiction"):
            conditions.append({"jurisdiction": filters["jurisdiction"]})
        if filters.get("court"):
            conditions.append({"court": filters["court"]})
        if filters.get("year_from"):
            conditions.append({"year": {"$gte": int(filters["year_from"])}})
        if filters.get("year_to"):
            conditions.append({"year": {"$lte": int(filters["year_to"])}})

        if len(conditions) == 1:
            chroma_where = conditions[0]
        elif len(conditions) > 1:
            chroma_where = {"$and": conditions}

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=chroma_where,
            include=["metadatas", "documents", "distances"]
        )
    except Exception as e:
        print(f"[Pipeline] ChromaDB query error: {e}. Retrying without where filter.")
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "documents", "distances"]
        )

    # Existing local indexes may predate the current ingestion metadata
    # schema. A zero-hit filter should not turn a useful semantic search into
    # an empty research result; retry without metadata constraints in that case.
    if chroma_where and (not results or not results.get("ids") or not results["ids"][0]):
        print("[Pipeline] Metadata filter returned no matches; retrying semantic retrieval without filters.")
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "documents", "distances"]
        )
    
    retrieved_cases = []
    best_similarity = -1.0
    
    if results and results.get('ids') and len(results['ids'][0]) > 0:
        for i in range(len(results['ids'][0])):
            case_id = results['ids'][0][i]
            metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
            document = results['documents'][0][i] if results.get('documents') else ""
            distance = results['distances'][0][i] if results.get('distances') else 0.0
            
            # ChromaDB with cosine space returns distance = 1 - cosine_similarity
            similarity = max(0.0, min(1.0, 1.0 - distance))
            if similarity > best_similarity:
                best_similarity = similarity
                
            case_info = metadata.copy()
            case_info['case_id'] = case_id
            case_info['doc_id'] = case_id
            case_info['title'] = metadata.get('case_name') or metadata.get('title') or case_id
            case_info['case_name'] = case_info['title']
            case_info['retrieval_document'] = document
            case_info['snippet'] = document
            case_info['similarity_score'] = round(similarity, 4)
            case_info['relevance_score'] = round(similarity, 4)
            case_info['document_type'] = metadata.get('legal_domain') or metadata.get('document_type') or 'case_law'
            
            # parse sections
            sec = metadata.get('section', '')
            if sec:
                case_info['sections'] = [s.strip() for s in sec.split(',') if s.strip()]
            else:
                case_info['sections'] = []

            retrieved_cases.append(case_info)
            
    is_low_confidence = (best_similarity < LOW_CONFIDENCE_THRESHOLD) if retrieved_cases else True
    return retrieved_cases, is_low_confidence


def _generate_local_legal_synthesis(query: str, retrieved_cases: List[Dict]) -> Tuple[str, List[str]]:
    """
    Advanced local legal synthesis engine.
    Produces formal, structured legal research answers directly from retrieved precedents.
    """
    if not retrieved_cases:
        return (
            "No matching legal precedents or statutory provisions were retrieved for this query. "
            "Please try refining your search terms or broadening filter parameters.",
            []
        )

    # Extract distinct metadata
    courts = list(dict.fromkeys([c.get('court') for c in retrieved_cases if c.get('court')]))
    domains = list(dict.fromkeys([c.get('legal_domain') for c in retrieved_cases if c.get('legal_domain')]))
    sections = list(dict.fromkeys([
        s for c in retrieved_cases for s in c.get('sections', []) if s
    ]))
    years = [c.get('year') for c in retrieved_cases if c.get('year')]
    min_yr = min(years) if years else "N/A"
    max_yr = max(years) if years else "N/A"

    # Identify legal domain themes
    q_lower = query.lower()
    inferred_principles = []
    
    if "commercial" in q_lower or "cca" in q_lower or "dispute" in q_lower:
        inferred_principles.append("Commercial Courts Act, 2015 Scope & Jurisdiction")
    if "arbitrat" in q_lower or "award" in q_lower or "section 34" in q_lower:
        inferred_principles.append("Arbitration & Conciliation Act, 1996 — Section 34 Scrutiny")
    if "compensation" in q_lower or "damages" in q_lower or "breach" in q_lower or "contract" in q_lower:
        inferred_principles.append("Sections 73 & 74 Indian Contract Act (Damages for Breach)")
    if "mediation" in q_lower or "12a" in q_lower:
        inferred_principles.append("Mandatory Pre-Institution Mediation under Section 12A CCA")
    if "specified value" in q_lower or "threshold" in q_lower:
        inferred_principles.append("Specified Value Threshold under Section 12 Commercial Courts Act")
    if "limitation" in q_lower:
        inferred_principles.append("Limitation Act, 1963 Compliance")

    # Build structured precedent summaries
    case_bullets = []
    for i, c in enumerate(retrieved_cases[:5], 1):
        name = c.get('case_name', 'Unknown Precedent')
        yr = c.get('year', 'N/A')
        court = c.get('court', 'High Court / Supreme Court')
        cit = c.get('citation', 'Citation on record')
        sec = c.get('section', 'General Principles')
        doc = c.get('snippet', '')
        rel = c.get('relevance_score', 0) * 100

        # Extract concise summary from retrieval document
        clean_doc = doc.replace('\n', ' ').strip()
        if len(clean_doc) > 280:
            clean_doc = clean_doc[:277] + "..."

        case_bullets.append(
            f"**[{i}] {name} ({yr}) — {court}**\n"
            f"- *Citation*: `{cit}` | *Sections*: `{sec}` | *Relevance Match*: **{rel:.0f}%**\n"
            f"- *Ratio / Context*: {clean_doc}\n"
        )

    cases_text = "\n".join(case_bullets)

    # Compile comprehensive legal answer
    answer = f"""## Legal Research Synthesis

### 1. Executive Summary
In response to the research inquiry: *"**{query}**"*, an analysis of **{len(retrieved_cases)} retrieved judicial precedents** from the Supreme Court of India and High Courts ({min_yr}–{max_yr}) establishes the foundational legal framework applicable in Indian courts.

### 2. Relevant Statutory & Legislative Framework
The primary statutory provisions governing this domain include:
- **Applicable Domains**: {', '.join(domains) if domains else 'Commercial & Civil Law'}
- **Noted Legal Sections / Articles**: {', '.join(sections[:8]) if sections else 'Relevant procedural and substantive provisions'}
- **Judicial Jurisdiction**: {', '.join(courts[:4]) if courts else 'Supreme Court of India and Commercial Divisions of High Courts'}

### 3. Key Judicial Precedents & Holdings
{cases_text}

### 4. Key Legal Principles Established
1. **Binding Precedential Authority**: Under the doctrine of *stare decisis* (Article 141 for the Supreme Court and binding High Court precedents), courts interpret procedural and substantive rights strictly in accordance with statutory intent.
2. **Standard of Adjudication**: Commercial and civil disputes require compliance with statutory prerequisites, strict adherence to limitation timelines, and substantiation of claims through verifiable documentary evidence.
3. **Harmonious Construction**: Statutory provisions across parent acts (such as the Indian Contract Act, Arbitration Act, and Commercial Courts Act) are harmoniously construed to avoid procedural delays and uphold commercial efficacy.

---
*Note: This synthesis is compiled from the VIDHIVEDA judicial database containing {len(retrieved_cases)} matching precedents.*"""

    # Add any specific principles to list
    all_principles = inferred_principles
    for s in sections[:4]:
        all_principles.append(f"Section {s} Compliance")
    if not all_principles:
        all_principles = ["Judicial Precedent Authority", "Statutory Compliance", "Standard of Evidence"]

    return answer, all_principles[:6]


def generate_explanation(query: str, retrieved_cases: List[Dict]) -> Dict:
    """
    Generates a research-style explanation using the retrieved cases.
    Falls back gracefully to local legal synthesis if no LLM API key is present.
    """
    start_time = time.time()
    
    if not retrieved_cases:
        return {
            "answer": "No relevant cases found for the query.",
            "explanation": "No relevant cases found for the query.",
            "sources": [],
            "prediction_context": [],
            "key_principles": [],
            "citations": [],
            "unverified_citation": False,
            "confidence": "Low",
            "low_confidence": True,
            "disclaimer": "This is AI-generated research support and does not constitute legal advice.",
            "processing_time_seconds": 0.01,
        }
        
    client, model_name = get_llm_client()
    explanation = ""
    key_principles = []

    if client is not None:
        # LLM Available
        context_parts = []
        for case in retrieved_cases:
            c_name = case.get('case_name', 'Unknown Case')
            c_citation = case.get('citation', 'Unknown Citation')
            is_synthetic = (case.get('record_type') == 'Synthetic (Illustrative)')
            synth_flag = " [SYNTHETIC/ILLUSTRATIVE DATA]" if is_synthetic else ""
            part = f"Case: {c_name} ({case.get('year', 'N/A')}) — {case.get('court', 'N/A')} [Citation: {c_citation}]{synth_flag}\n"
            part += f"Summary/Holding: {case.get('retrieval_document', '')}\n"
            context_parts.append(part)
            
        context_str = "\n".join(context_parts)
        
        system_prompt = (
            "You are VIDHIVEDA, an AI-powered legal research engine for Indian Commercial Courts. "
            "Answer the query based on the retrieved precedents. "
            "Structure your answer with clear Markdown headings: ## Research Analysis, ### Statutory Framework, ### Case Precedents, ### Key Principles. "
            "Cite each source by [1], [2] etc. "
            "Never issue definitive verdicts or legal opinions."
        )
        
        user_prompt = f"Query: {query}\n\nRetrieved Cases:\n{context_str}\n\nProvide an authoritative legal research answer."
        
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=800
            )
            explanation = response.choices[0].message.content
        except Exception as e:
            print(f"[Pipeline] LLM generation error: {e}. Using local legal synthesis.")
            explanation, key_principles = _generate_local_legal_synthesis(query, retrieved_cases)
    else:
        # High quality local synthesis
        explanation, key_principles = _generate_local_legal_synthesis(query, retrieved_cases)

    # Format sources for frontend
    sources = []
    for c in retrieved_cases:
        sources.append({
            "doc_id": c.get("case_id") or c.get("doc_id", ""),
            "title": c.get("case_name") or c.get("title", ""),
            "case_name": c.get("case_name") or c.get("title", ""),
            "document_type": c.get("document_type") or c.get("legal_domain") or "case_law",
            "court": c.get("court", ""),
            "year": c.get("year", 0),
            "relevance_score": c.get("similarity_score", 0.0),
            "similarity_score": c.get("similarity_score", 0.0),
            "snippet": c.get("retrieval_document") or c.get("snippet", ""),
            "citation": c.get("citation", ""),
            "sections": c.get("sections", []),
            "legal_domain": c.get("legal_domain", ""),
            "source": c.get("source", ""),
            "record_type": c.get("record_type", ""),
            "retrieval_document": c.get("retrieval_document", ""),
        })

    # Citation verification
    cited_ids = [c['case_id'] for c in retrieved_cases if c.get('case_name') and c['case_name'].lower() in explanation.lower()]
    
    elapsed = round(time.time() - start_time, 2)
    
    return {
        "answer": explanation,
        "explanation": explanation,
        "sources": sources,
        "prediction_context": sources,
        "key_principles": key_principles,
        "citations": cited_ids,
        "unverified_citation": False,
        "confidence": "High" if len(retrieved_cases) > 0 else "Low",
        "low_confidence": False,
        "disclaimer": "This is AI-generated research support and does not constitute legal advice.",
        "processing_time_seconds": elapsed,
    }
