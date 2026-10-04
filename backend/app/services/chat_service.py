import logging
import time
from typing import Any, Dict, List, Optional
from app.rag.rag_service import get_llm_client, SYSTEM_PROMPT, LOW_CONFIDENCE_MESSAGE
from app.rag.citation_service import verify_citations, _display_name
from app.rag.retrieval_service import retrieval_service

logger = logging.getLogger(__name__)

class ChatService:
    def build_context(self, retrieved: List[Dict[str, Any]]) -> str:
        blocks = []
        for index, case in enumerate(retrieved, 1):
            parts = [f"SOURCE {index}"]
            parts.append(f"Case/Document: {_display_name(case)}")
            if case.get("court"):
                parts.append(f"Court: {case['court']}")
            if case.get("judgment_date") or case.get("year"):
                parts.append(f"Year/Date: {case.get('judgment_date') or case.get('year')}")
            parts.append(f"Source chunk: {case.get('chunk_id', '')}")
            parts.append(f"Relevant Text:\n{case.get('text', '')}")
            blocks.append("\n".join(parts))
        return "\n\n".join(blocks)

    def generate_chat_response(self, query: str, history: List[Dict[str, str]], retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        retrieved = retrieval_result.get("results", []) or []
        is_low_confidence = bool(retrieval_result.get("is_low_confidence", True))
        best_similarity = float(retrieval_result.get("best_similarity", 0.0) or 0.0)

        if not retrieved or is_low_confidence:
            return {
                "answer": "I could not find sufficient supporting precedents or legal documents to answer your question with certainty.",
                "sources": retrieved,
                "citations": [],
                "low_confidence": True,
            }

        context = self.build_context(retrieved)
        
        # Build prompt messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add history
        for msg in history:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({"role": msg["role"], "content": msg["content"]})
                
        # Final user query with context
        user_prompt = (
            f"Query: {query}\n\n"
            f"Retrieved source material:\n{context}\n\n"
            "Answer the query using only the sources above. Cite them as "
            "[SOURCE n]. If the sources do not support a point, say so."
        )
        messages.append({"role": "user", "content": user_prompt})

        answer = ""
        provider = ""

        client, model_name, provider = get_llm_client()
        if client is not None:
            try:
                if provider == "anthropic":
                    response = client.messages.create(
                        model=model_name,
                        system=SYSTEM_PROMPT,
                        messages=[m for m in messages if m["role"] != "system"],
                        temperature=0.1,
                        max_tokens=1000,
                    )
                    answer = (response.content[0].text or "").strip()
                else:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=0.1,
                        max_tokens=1000,
                    )
                    answer = (response.choices[0].message.content or "").strip()
            except Exception as exc:
                logger.error("[chat] LLM generation failed: %s", exc)
                answer = "Sorry, I am currently unavailable to generate an answer."
        else:
            answer = "No LLM API key is configured. Here are the retrieved sources."

        # Verify citations
        citation_report = verify_citations(answer, retrieved, include_unreferenced=True)

        return {
            "answer": answer,
            "sources": retrieved,
            "citations": citation_report["citations"],
            "supporting_sources": citation_report["supporting_sources"],
            "low_confidence": False,
        }

chat_service = ChatService()
