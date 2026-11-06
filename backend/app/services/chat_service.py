import logging
import time
from typing import Any, Dict, List, Optional
from app.rag.rag_service import get_llm_client, SYSTEM_PROMPT, LOW_CONFIDENCE_MESSAGE
from app.rag.citation_service import verify_citations, _display_name
from app.rag.retrieval_service import retrieval_service
from app.rag.query_analyzer import legal_query_analyzer

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        self.rewrite_prompt = (
            "You are a legal research assistant. Your task is to rewrite the user's latest query "
            "so that it is fully self-contained and suitable for semantic document retrieval, "
            "based on the conversation history.\n"
            "If the latest query refers to previous concepts (e.g. 'summarize that case', 'what about property law?'), "
            "incorporate the relevant entities from the history into the new query.\n"
            "If the query is already self-contained, just return it as is.\n"
            "DO NOT answer the query. Return ONLY the rewritten query text."
        )

    def rewrite_query(self, query: str, history: List[Dict[str, str]]) -> str:
        """Use the LLM to rewrite the query based on conversation history for better retrieval."""
        if not history:
            return query

        client, model_name, provider = get_llm_client()
        if not client:
            return query

        messages = [{"role": "system", "content": self.rewrite_prompt}]
        for msg in history[-4:]: # Only use the last few turns for context
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": f"Rewrite this query for standalone search: {query}"})

        try:
            if provider == "anthropic":
                response = client.messages.create(
                    model=model_name,
                    system=self.rewrite_prompt,
                    messages=[m for m in messages if m["role"] != "system"],
                    temperature=0.0,
                    max_tokens=100,
                )
                rewritten = (response.content[0].text or "").strip()
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=100,
                )
                rewritten = (response.choices[0].message.content or "").strip()

            # Remove any prefix the LLM might add like "Rewritten query: "
            if ":" in rewritten and len(rewritten.split(":")[0]) < 20:
                rewritten = rewritten.split(":", 1)[1].strip()

            # Remove quotes
            rewritten = rewritten.strip("'\"")

            logger.info("[chat] Rewrote query '%s' -> '%s'", query, rewritten)
            return rewritten if rewritten else query
        except Exception as exc:
            logger.error("[chat] Query rewrite failed: %s", exc)
            return query

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

    def generate_chat_response(self, original_query: str, history: List[Dict[str, str]], retrieval_result: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        retrieved = retrieval_result.get("results", []) or []
        is_low_confidence = bool(retrieval_result.get("is_low_confidence", True))

        # We will answer normally if there's no retrieved documents but it's a general question
        # To determine this, we check the query analysis task
        task = analysis.get("task", "precedent_retrieval")

        if (not retrieved or is_low_confidence) and task == "precedent_retrieval":
            return {
                "answer": "I could not find sufficient supporting precedents or legal documents to answer your question with certainty.",
                "sources": retrieved,
                "citations": [],
                "low_confidence": True,
            }

        context = self.build_context(retrieved)

        # Build dynamic system prompt based on task
        task_prompts = {
            "summarization": "You are a legal summarizer. Summarize the provided judgments clearly, highlighting the facts, legal issues, and final decision.",
            "provision_lookup": "You are a legal expert. Explain the requested legal provisions using simple language, relying strictly on the retrieved text.",
            "outcome_prediction": "You are a legal analyst. Analyze the provided cases to assess the likely outcome of the scenario, but explicitly state that you cannot guarantee judicial outcomes.",
            "precedent_retrieval": SYSTEM_PROMPT
        }

        system_msg = task_prompts.get(task, SYSTEM_PROMPT)

        # Build prompt messages
        messages = [{"role": "system", "content": system_msg}]

        # Add history
        for msg in history[-10:]:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Final user query with context
        if retrieved:
            user_prompt = (
                f"Query: {original_query}\n\n"
                f"Retrieved source material:\n{context}\n\n"
                f"Answer the query using only the sources above. Cite them as [SOURCE n]."
            )
        else:
            user_prompt = original_query

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

        # Verify citations only if there are sources
        citation_report = {"citations": [], "supporting_sources": []}
        if retrieved:
            citation_report = verify_citations(answer, retrieved, include_unreferenced=True)

        return {
            "answer": answer,
            "sources": retrieved,
            "citations": citation_report["citations"],
            "supporting_sources": citation_report["supporting_sources"],
            "low_confidence": False,
        }

chat_service = ChatService()
