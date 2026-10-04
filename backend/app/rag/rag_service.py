"""
RAG generation (Steps 9-11).

Retrieval happens first and is reported independently: ``confidence`` is a
*retrieval* number (best dense similarity) and never a claim about the answer.
Generation runs second and is labelled with ``answer_origin`` so the UI can
separate "what the corpus contains" from "what a model wrote".

Grounding rules enforced here:
  * only retrieved chunks are placed in the prompt;
  * the system prompt forbids inventing cases, citations, statutes or dates;
  * every citation returned to the client is verified against the retrieved
    chunks before it is marked ``verified``;
  * when retrieval is weak, no answer is forced — the response is a
    ``low_confidence`` payload carrying the sources that were found.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from app.core.config import LLM_TIMEOUT_SECONDS
from app.rag.citation_service import _display_name, verify_citations

load_dotenv()

logger = logging.getLogger(__name__)

LOW_CONFIDENCE_MESSAGE = "Insufficient supporting precedent was found for this query."

SYSTEM_PROMPT = (
    "You are a legal research assistant.\n"
    "Use only the supplied source material.\n"
    "Do not invent cases, citations, statutes, dates, sections, or facts.\n"
    "If the retrieved sources do not contain sufficient information, say so.\n"
    "Every important legal claim must reference a supplied source (e.g. [SOURCE 1]).\n"
    "Do not issue a legal verdict.\n"
    "Do not make a final judicial decision.\n"
    "Do not present generated content as an official judgment."
)


class LLMUnavailable(RuntimeError):
    """Raised when a configured provider rejects the request."""


def get_llm_client() -> Tuple[Optional[Any], str, str]:
    """
    Resolve the configured LLM provider.

    Returns ``(client, model_name, provider)`` or ``(None, "", "")`` when no key
    is configured — in which case the pipeline stays retrieval-only instead of
    fabricating prose.
    """
    import os

    hf_token = os.getenv("HF_API_TOKEN", "") or os.getenv("HF_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    def usable(key: str) -> bool:
        return (
            bool(key)
            and not key.startswith("your-")
            and not key.startswith("<")
            and len(key) > 20
        )

    # Fall back to a token stored by `huggingface-cli login` so a locally
    # authenticated machine works without duplicating the token in .env.
    if not usable(hf_token):
        try:
            from huggingface_hub import get_token as _get_hf_token

            cached = _get_hf_token()
            if usable(cached):
                hf_token = cached
        except Exception:  # huggingface_hub missing or no cache
            pass

    provider = os.getenv("LLM_PROVIDER", "huggingface").strip().lower()

    if provider in {"huggingface", "hf"} and usable(hf_token):
        try:
            from openai import OpenAI

            return (
                OpenAI(
                    base_url=os.getenv(
                        "HF_BASE_URL", "https://router.huggingface.co/v1"
                    ),
                    api_key=hf_token,
                    timeout=LLM_TIMEOUT_SECONDS,
                ),
                os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct"),
                "huggingface",
            )
        except Exception as exc:
            logger.warning("[rag] HuggingFace client init failed: %s", exc)

    if provider == "openai" and usable(openai_key):
        try:
            from openai import OpenAI

            return (
                OpenAI(api_key=openai_key, timeout=LLM_TIMEOUT_SECONDS),
                os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "openai",
            )
        except Exception as exc:
            logger.warning("[rag] OpenAI client init failed: %s", exc)

    if provider == "anthropic" and usable(anthropic_key):
        try:
            from anthropic import Anthropic

            return (
                Anthropic(api_key=anthropic_key, timeout=LLM_TIMEOUT_SECONDS),
                os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                "anthropic",
            )
        except Exception as exc:
            logger.warning("[rag] Anthropic client init failed: %s", exc)

    return None, "", ""


class RAGService:
    # ── Context construction (Step 9) ──────────────────────────────────
    def build_context(self, retrieved: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks as numbered SOURCE blocks for the prompt."""
        blocks: List[str] = []
        for index, case in enumerate(retrieved, 1):
            parts = [f"SOURCE {index}"]
            parts.append(f"Case/Document: {_display_name(case)}")
            if case.get("court"):
                parts.append(f"Court: {case['court']}")
            if case.get("judgment_date") or case.get("year"):
                parts.append(
                    f"Year/Date: {case.get('judgment_date') or case.get('year')}"
                )
            parts.append(f"Source: {case.get('source') or 'not recorded upstream'}")
            if case.get("citation"):
                parts.append(f"Reported citation: {case['citation']}")
            parts.append(f"Source chunk: {case.get('chunk_id', '')}")
            parts.append(f"Relevant Text:\n{case.get('text', '')}")
            blocks.append("\n".join(parts))
        return "\n\n".join(blocks)

    # ── Generation (Step 9) ────────────────────────────────────────────
    def generate_response(
        self, query: str, retrieval_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        start = time.time()
        retrieved = retrieval_result.get("results", []) or []
        is_low_confidence = bool(retrieval_result.get("is_low_confidence", True))
        best_similarity = float(retrieval_result.get("best_similarity", 0.0) or 0.0)

        # Step 11 — weak or empty retrieval: do not force the LLM to answer.
        if not retrieved or is_low_confidence:
            return {
                "status": "low_confidence" if retrieved else "no_results",
                "answer": "",
                "confidence": round(max(0.0, best_similarity), 4),
                "confidence_basis": "dense_retrieval_similarity",
                "low_confidence_reason": retrieval_result.get("low_confidence_reason"),
                "sources": retrieved,
                "citations": [],
                "supporting_sources": [],
                "unverified_references": [],
                "message": LOW_CONFIDENCE_MESSAGE,
                "warning": LOW_CONFIDENCE_MESSAGE,
                "low_confidence": True,
                "answer_origin": "none",
                "generation_time": 0.0,
                "retrieval_time": retrieval_result.get("retrieval_time", 0.0),
            }

        context = self.build_context(retrieved)
        user_prompt = (
            f"Query: {query}\n\n"
            f"Retrieved source material:\n{context}\n\n"
            "Answer the query using only the sources above. Cite them as "
            "[SOURCE n]. If the sources do not support a point, say so."
        )

        answer = ""
        answer_origin = "none"
        provider = ""
        warning: Optional[str] = None

        client, model_name, provider = get_llm_client()
        if client is not None:
            try:
                answer = self._call_llm(client, model_name, provider, user_prompt)
                answer_origin = f"llm:{provider}"
            except Exception as exc:
                logger.error("[rag] LLM generation failed (%s): %s", provider, exc)
                warning = (
                    "The language model was unavailable, so no generated summary is "
                    "shown. The retrieved sources below are unaffected."
                )
                answer = ""
        else:
            warning = (
                "No LLM API key is configured (set HF_API_TOKEN, OPENAI_API_KEY or "
                "ANTHROPIC_API_KEY). Retrieval is live; no generated summary is shown."
            )

        # Retrieval-only fallback: metadata about the retrieved chunks, clearly
        # labelled as not model-generated so it is never mistaken for analysis.
        if not answer:
            answer = self._retrieval_summary(retrieved)
            answer_origin = "retrieval_template"

        # Step 10 — verify every citation against the retrieved chunks.
        citation_report = verify_citations(answer, retrieved, include_unreferenced=True)

        return {
            "status": "ok",
            "answer": answer,
            "confidence": round(max(0.0, best_similarity), 4),
            "confidence_basis": "dense_retrieval_similarity",
            "low_confidence_reason": None,
            "sources": retrieved,
            "citations": citation_report["citations"],
            "supporting_sources": citation_report["supporting_sources"],
            "unverified_references": citation_report["unverified_references"],
            "all_citations_verified": citation_report["all_citations_verified"],
            "message": None,
            "warning": warning,
            "low_confidence": False,
            "answer_origin": answer_origin,
            "generation_time": round(time.time() - start, 4),
            "retrieval_time": retrieval_result.get("retrieval_time", 0.0),
        }

    # ── Internals ──────────────────────────────────────────────────────
    def _call_llm(
        self, client: Any, model_name: str, provider: str, user_prompt: str
    ) -> str:
        if provider == "anthropic":
            response = client.messages.create(
                model=model_name,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.1,
                max_tokens=900,
            )
            return (response.content[0].text or "").strip()

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=900,
        )
        return (response.choices[0].message.content or "").strip()

    def _retrieval_summary(self, retrieved: List[Dict[str, Any]]) -> str:
        """
        Deterministic, non-generative summary of the retrieved chunks.

        Contains no legal analysis and no claims beyond what the corpus rows
        literally say, which is why it is safe to show without an LLM.
        """
        lines = [
            "**Retrieved source material** (no generated summary is available).",
            "",
        ]
        for index, case in enumerate(retrieved, 1):
            name = _display_name(case)
            details = [
                part
                for part in (
                    case.get("court"),
                    case.get("judgment_date") or case.get("year"),
                    f"source: {case['source']}" if case.get("source") else None,
                    f"chunk {case['chunk_id']}" if case.get("chunk_id") else None,
                    f"similarity {round(float(case.get('similarity_score') or 0), 3)}",
                )
                if part
            ]
            snippet = " ".join((case.get("text") or "").split())
            if len(snippet) > 420:
                snippet = snippet[:417] + "..."
            lines.append(f"[SOURCE {index}] {name} — {' · '.join(str(d) for d in details)}")
            lines.append(f"> {snippet}")
            lines.append("")
        return "\n".join(lines).strip()


rag_service = RAGService()
