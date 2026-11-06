"""
Two-scenario legal comparison (evidence-based, retrieval-grounded).

This module compares two competing accounts of the same legal dispute. It is
*argument analysis*, not a binary "A is right / B is wrong" classifier:

  1. one retrieval pass per scenario over the existing ChromaDB corpus;
  2. chunks are grouped by source document, so several chunks of one judgment
     are never counted as several independent precedents;
  3. each recovered precedent is placed next to the account it is topically
     closest to — that scenario is given the precedent as *supporting* evidence,
     the other scenario is shown the same precedent as *contrary* evidence;
  4. strengths / weaknesses / missing evidence are derived only from what was
     actually retrieved (or explicitly not retrieved);
  5. outcome prediction is reported only when a trained, evaluated classifier
     exists; otherwise it is marked unavailable with a reason.

Honesty rules:
  * topical alignment is a retrieval signal, never a legal conclusion;
  * no citation, court, date or provision is invented — every precedent carries
    the stored metadata of the row that produced it;
  * retrieval similarity is not a probability and is never rendered as one.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import (
    LOW_CONFIDENCE_THRESHOLD,
    MIN_EVIDENCE_SCORE,
    RETRIEVAL_TOP_K,
)
from app.ml.outcome_model import outcome_model_service
from app.rag.citation_service import build_citation
from app.rag.query_analyzer import legal_query_analyzer
from app.rag.reranker import content_tokens
from app.rag.retrieval_service import RetrievalError, retrieval_service

logger = logging.getLogger("vidhiveda.comparison")

DISCLAIMER = (
    "VIDHIVEDA compares two accounts using retrieved legal material. It does "
    "not decide which party is legally correct and does not replace judicial "
    "decision-making."
)

# Disposition phrases used only to *describe* what a retrieved passage contains.
# They are not used to decide which scenario is stronger.
_SUPPORT_PHRASES = ("allowed", "granted", "upheld", "affirmed", "decreed", "succeeded")
_CONTRARY_PHRASES = (
    "dismissed",
    "set aside",
    "reversed",
    "quashed",
    "acquitted",
    "rejected",
    "no merit",
    "unsustainable",
)

# One retrieved chunk is a weak signal of "supporting precedent"; require at
# least this share of the scenario's content words to call it aligned.
ALIGNMENT_MARGIN = 0.05


def _alignment(scenario_tokens: set, text: str) -> float:
    """Share of the scenario's content words that appear in ``text`` (0..1)."""
    if not scenario_tokens:
        return 0.0
    document = set(content_tokens((text or "")[:6000]))
    return len(scenario_tokens & document) / len(scenario_tokens)


def _disposition_signals(text: str) -> List[str]:
    """Disposition phrases literally present in the passage (informational)."""
    lowered = (text or "").lower()
    found: List[str] = []
    for phrase in _SUPPORT_PHRASES + _CONTRARY_PHRASES:
        if phrase in lowered and phrase not in found:
            found.append(phrase)
    return found


def _dedupe_by_document(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Collapse chunks into documents.

    Several chunks of one judgment must not read as several precedents. The
    highest-scoring chunk represents the document; ``matched_chunks`` records
    how many chunks of it were retrieved.
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for record in records:
        key = record.get("document_id") or record.get("chunk_id") or record.get("source") or ""
        score = float(record.get("similarity_score") or 0.0)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = {**record, "matched_chunks": 1}
        else:
            existing["matched_chunks"] += 1
            if score > float(existing.get("similarity_score") or 0.0):
                existing.update({**record, "matched_chunks": existing["matched_chunks"]})
    return sorted(
        grouped.values(), key=lambda item: float(item.get("similarity_score") or 0.0), reverse=True
    )


def _to_precedent(record: Dict[str, Any], alignment: float) -> Dict[str, Any]:
    """A precedent record that preserves the stored source metadata."""
    return {
        "case_name": record.get("case_name") or "",
        "court": record.get("court") or "",
        "year": record.get("year") or "",
        "judgment_date": record.get("judgment_date") or "",
        "citation": record.get("citation") or "",
        "source": record.get("source") or "",
        "source_url": record.get("source_url") or "",
        "chunk_id": record.get("chunk_id") or "",
        "document_id": record.get("document_id") or "",
        "sections": record.get("sections") or [],
        "articles": record.get("articles") or [],
        "similarity_score": round(float(record.get("similarity_score") or 0.0), 4),
        "alignment": round(alignment, 4),
        "matched_chunks": int(record.get("matched_chunks") or 1),
        "disposition_signals": _disposition_signals(record.get("text") or ""),
        "excerpt": " ".join((record.get("text") or "").split())[:600],
        "verified": True,
    }


def _scenario_query(scenario: Dict[str, Any], legal_issue: str, case_facts: str, provisions: List[str]) -> str:
    parts = [legal_issue]
    if case_facts:
        parts.append(case_facts)
    if provisions:
        parts.append("Legal sections: " + "; ".join(provisions))
    parts.append(scenario.get("position") or "")
    return "\n".join(part for part in parts if part)


class ComparisonService:
    def compare(self, request: Dict[str, Any]) -> Dict[str, Any]:
        legal_issue = (request.get("legal_issue") or "").strip()
        case_facts = (request.get("case_facts") or "").strip()
        provisions = [p for p in (request.get("provisions") or []) if str(p).strip()]
        scenario_a = request.get("scenario_a") or {}
        scenario_b = request.get("scenario_b") or {}
        has_scenario_b = bool((scenario_b.get("position") or "").strip())
        top_k = int(request.get("top_k") or RETRIEVAL_TOP_K)
        filters = request.get("filters") or None

        analysis = legal_query_analyzer.analyze(" ".join([legal_issue, case_facts]))
        sections = provisions or [
            record["normalized_text"] for record in analysis.get("legal_sections", [])
        ]

        results: Dict[str, Dict[str, Any]] = {}
        retrieval_errors: List[str] = []

        query_a = _scenario_query(scenario_a, legal_issue, case_facts, provisions)
        try:
            results["scenario_a"] = retrieval_service.retrieve(
                query=query_a,
                top_k=top_k,
                filters=filters,
                sections=sections or None,
            )
        except RetrievalError as exc:
            logger.error("[comparison] Retrieval failed for scenario_a: %s", exc)
            retrieval_errors.append(str(exc))
            results["scenario_a"] = {
                "results": [],
                "best_similarity": 0.0,
                "is_low_confidence": True,
                "low_confidence_reason": str(exc),
                "candidate_count": 0,
            }

        if has_scenario_b:
            query_b = _scenario_query(scenario_b, legal_issue, case_facts, provisions)
            try:
                results["scenario_b"] = retrieval_service.retrieve(
                    query=query_b,
                    top_k=top_k,
                    filters=filters,
                    sections=sections or None,
                )
            except RetrievalError as exc:
                logger.error("[comparison] Retrieval failed for scenario_b: %s", exc)
                retrieval_errors.append(str(exc))
                results["scenario_b"] = {
                    "results": [],
                    "best_similarity": 0.0,
                    "is_low_confidence": True,
                    "low_confidence_reason": str(exc),
                    "candidate_count": 0,
                }
        else:
            results["scenario_b"] = {
                "results": [],
                "best_similarity": 0.0,
                "is_low_confidence": False,
                "low_confidence_reason": None,
                "candidate_count": 0,
            }

        if retrieval_errors and not any(r.get("results") for r in results.values()):
            raise RetrievalError("; ".join(retrieval_errors))

        # ── Group chunks into documents, per scenario ──────────────────
        docs_a = _dedupe_by_document(results["scenario_a"].get("results", []))
        docs_b = _dedupe_by_document(results["scenario_b"].get("results", [])) if has_scenario_b else []

        tokens_a = set(content_tokens(scenario_a.get("position") or ""))
        tokens_b = set(content_tokens(scenario_b.get("position") or "")) if has_scenario_b else set()

        # Best chunks keyed by document, plus which scenario(s) retrieved them.
        merged: Dict[str, Dict[str, Any]] = {}
        pair_list = [(docs_a, "a")]
        if has_scenario_b:
            pair_list.append((docs_b, "b"))
        for source, side in pair_list:
            for record in source:
                key = record.get("document_id") or record.get("chunk_id") or ""
                entry = merged.setdefault(key, {"record": record, "sides": set()})
                entry["sides"].add(side)
                if float(record.get("similarity_score") or 0.0) > float(
                    entry["record"].get("similarity_score") or 0.0
                ):
                    entry["record"] = record

        scored: List[Dict[str, Any]] = []
        for entry in merged.values():
            record = entry["record"]
            text = record.get("text") or ""
            align_a = _alignment(tokens_a, text)
            align_b = _alignment(tokens_b, text) if has_scenario_b else 0.0
            precedent = _to_precedent(record, max(align_a, align_b))
            if has_scenario_b:
                precedent["aligns_with"] = self._aligns_with(align_a, align_b, entry["sides"])
            else:
                precedent["aligns_with"] = "a" if align_a > ALIGNMENT_MARGIN else "neutral"
            precedent["retrieved_for"] = sorted(entry["sides"])
            scored.append(precedent)

        scenario_a_view = self._scenario_view(
            scenario_a, scored, tokens_a, tokens_b, provisions, side="a", legal_issue=legal_issue
        )
        scenario_b_view = self._scenario_view(
            scenario_b, scored, tokens_b, tokens_a, provisions, side="b", legal_issue=legal_issue
        ) if has_scenario_b else None

        evidence_quality = self._evidence_quality(results, scenario_a_view, scenario_b_view, provisions)
        outcome = self._outcome_estimate(results, scenario_a_view, scenario_b_view, evidence_quality)

        citations: List[Dict[str, Any]] = []
        seen = set()
        for precedent in scored:
            record = merged.get(precedent["document_id"] or precedent["chunk_id"], {}).get("record")
            if not record:
                continue
            citation = build_citation(record, verified=True, reference="retrieved")
            if citation["chunk_id"] not in seen:
                seen.add(citation["chunk_id"])
                citations.append(citation)

        limitations = self._limitations(request, scenario_a_view, scenario_b_view, evidence_quality, outcome, scored)
        comparative_analysis = self._comparative_analysis(
            legal_issue=legal_issue,
            case_facts=case_facts,
            scenario_a=scenario_a_view,
            scenario_b=scenario_b_view,
            scored=scored,
            outcome=outcome,
            evidence_quality=evidence_quality,
        )

        return {
            "status": "ok",
            "mode": "comparison" if has_scenario_b else "single_scenario",
            "legal_issue": legal_issue,
            "case_summary": self._case_summary(scenario_a, scenario_b, case_facts),
            "legal_issues": analysis.get("legal_issues", []),
            "applicable_law": self._applicable_law(provisions, analysis, scored),
            "scenario_a": scenario_a_view,
            "scenario_b": scenario_b_view,
            "comparative_analysis": comparative_analysis,
            "evidence_comparison": self._evidence_comparison(scored),
            "evidence_quality": evidence_quality,
            "outcome_prediction": outcome,
            "citations": citations,
            "precedents": scored,
            "retrieval": {
                "query_analysis": analysis,
                "scenario_a": {
                    "best_similarity": round(float(results["scenario_a"].get("best_similarity") or 0.0), 4),
                    "low_confidence": bool(results["scenario_a"].get("is_low_confidence", True)),
                    "precedent_count": len(docs_a),
                },
                "scenario_b": {
                    "best_similarity": round(float(results["scenario_b"].get("best_similarity") or 0.0), 4),
                    "low_confidence": bool(results["scenario_b"].get("is_low_confidence", True)),
                    "precedent_count": len(docs_b),
                },
            },
            "limitations": limitations,
            "disclaimer": DISCLAIMER,
        }

    # ── Internals ──────────────────────────────────────────────────────
    @staticmethod
    def _aligns_with(align_a: float, align_b: float, sides: set) -> str:
        """
        Which account a precedent is topically closer to.

        Requires a real margin, otherwise the passage is reported as neutral —
        a coin-flip must not be presented as support for either side.
        """
        if align_a <= 0.0 and align_b <= 0.0:
            return "neutral"
        if align_a - align_b > ALIGNMENT_MARGIN:
            return "a"
        if align_b - align_a > ALIGNMENT_MARGIN:
            return "b"
        return "neutral" if sides else "neutral"

    def _scenario_view(
        self,
        scenario: Dict[str, Any],
        scored: List[Dict[str, Any]],
        own_tokens: set,
        other_tokens: set,
        provisions: List[str],
        side: str,
        legal_issue: str,
    ) -> Dict[str, Any]:
        # Recompute alignment relative to this scenario for clarity.
        supporting: List[Dict[str, Any]] = []
        contrary: List[Dict[str, Any]] = []
        for precedent in scored:
            alignment_own = _alignment(own_tokens, precedent["excerpt"])
            alignment_other = _alignment(other_tokens, precedent["excerpt"])
            evidence_text = f"{precedent['excerpt']} {' '.join(precedent['sections'])}"
            alignment_own = max(alignment_own, _alignment(own_tokens, evidence_text))
            alignment_other = max(alignment_other, _alignment(other_tokens, evidence_text))
            similarity = float(precedent.get("similarity_score") or 0.0)
            retrieved_for_own = side in precedent.get("retrieved_for", [])
            if similarity < MIN_EVIDENCE_SCORE:
                continue
            if alignment_own - alignment_other > ALIGNMENT_MARGIN:
                supporting.append({**precedent, "alignment": round(alignment_own, 4)})
            elif alignment_other - alignment_own > ALIGNMENT_MARGIN:
                if not retrieved_for_own or alignment_other > alignment_own:
                    contrary.append({**precedent, "alignment": round(alignment_other, 4)})

        supporting.sort(key=lambda p: p["similarity_score"], reverse=True)
        contrary.sort(key=lambda p: p["similarity_score"], reverse=True)

        top = float(max((p["similarity_score"] for p in supporting), default=0.0))

        provision_evidence = self._provision_presence(provisions, scored)

        strengths: List[str] = []
        weaknesses: List[str] = []
        missing: List[str] = []

        if supporting:
            strengths.append(
                f"{len(supporting)} retrieved judgment(s) are topically aligned with this account "
                f"(closest similarity {top:.2f})."
            )
        else:
            weaknesses.append(
                "No retrieved judgment aligned with this account above the evidence threshold."
            )

        found_provisions = [p["label"] for p in provision_evidence if p["found"]]
        missing_provisions = [p["label"] for p in provision_evidence if not p["found"]]
        if found_provisions:
            strengths.append(
                "Requested provision(s) appearing in the retrieved material: "
                + ", ".join(found_provisions)
                + "."
            )
        if missing_provisions:
            weaknesses.append(
                "Requested provision(s) not located in the retrieved material: "
                + ", ".join(missing_provisions)
                + "."
            )
            missing.extend(
                f"Evidence citing {label} was not retrieved." for label in missing_provisions
            )

        if contrary:
            weaknesses.append(
                f"{len(contrary)} retrieved judgment(s) are topically closer to the opposing "
                "account and could distinguish or weaken this position."
            )
        if top and top < LOW_CONFIDENCE_THRESHOLD:
            weaknesses.append(
                f"The strongest aligned similarity ({top:.2f}) is below the "
                f"{LOW_CONFIDENCE_THRESHOLD:.2f} evidence threshold."
            )

        if not scenario.get("position"):
            missing.append("This scenario was submitted without a supporting statement.")

        return {
            "label": scenario.get("label") or ("Scenario A" if side == "a" else "Scenario B"),
            "position": scenario.get("position") or "",
            "supporting_precedents": supporting[:5],
            "contrary_precedents": contrary[:5],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "missing_evidence": missing,
            "supporting_count": len(supporting),
            "contrary_count": len(contrary),
            "best_alignment_similarity": round(top, 4),
            "provisions": provision_evidence,
            "legal_issue": legal_issue,
        }

    @staticmethod
    def _provision_presence(provisions: List[str], scored: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not provisions:
            return []
        haystack = " ".join(
            f"{' '.join(p.get('sections') or [])} {' '.join(p.get('articles') or [])} {p.get('excerpt') or ''}"
            for p in scored
        ).lower()
        presence: List[Dict[str, Any]] = []
        for provision in provisions:
            label = str(provision).strip()
            if not label:
                continue
            token = label.split()[-1].lower()
            presence.append({"label": label, "found": token in haystack})
        return presence

    @staticmethod
    def _applicable_law(
        provisions: List[str], analysis: Dict[str, Any], scored: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        law: List[Dict[str, Any]] = []
        seen = set()

        def add(label: str, statute: Optional[str], section: str, origin: str, chunk_id: str = "") -> None:
            if not label or label in seen:
                return
            seen.add(label)
            law.append(
                {"label": label, "statute": statute, "section": section, "origin": origin, "chunk_id": chunk_id}
            )

        for record in analysis.get("legal_sections", []):
            add(record["normalized_text"], record.get("statute"), record.get("section"), "query")
        for provision in provisions:
            add(str(provision), None, str(provision), "requested")
        for precedent in scored:
            for section in precedent.get("sections") or []:
                label = section if str(section).lower().startswith("section") else f"Section {section}"
                add(label, None, str(section), "retrieved_evidence", precedent.get("chunk_id") or "")
            for article in precedent.get("articles") or []:
                label = article if str(article).lower().startswith("article") else f"Article {article}"
                add(label, "Constitution", str(article), "retrieved_evidence", precedent.get("chunk_id") or "")
        return law

    @staticmethod
    def _case_summary(
        scenario_a: Dict[str, Any], scenario_b: Optional[Dict[str, Any]], case_facts: str
    ) -> str:
        parts: List[str] = []
        if case_facts:
            parts.append(f"Shared case facts: {case_facts}")
        parts.append(
            f"Party A ({(scenario_a.get('label') or 'Scenario A')}) states: "
            f"{scenario_a.get('position') or 'no statement supplied'}"
        )
        if scenario_b and scenario_b.get("position"):
            parts.append(
                f"Party B ({(scenario_b.get('label') or 'Scenario B')}) states: "
                f"{scenario_b.get('position') or 'no statement supplied'}"
            )
        return "\n".join(parts)

    @staticmethod
    def _evidence_comparison(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
        both: List[Dict[str, Any]] = []
        only_a: List[Dict[str, Any]] = []
        only_b: List[Dict[str, Any]] = []
        for precedent in scored:
            entry = {
                "chunk_id": precedent["chunk_id"],
                "case_name": precedent["case_name"],
                "court": precedent["court"],
                "year": precedent["year"],
                "aligns_with": precedent["aligns_with"],
                "similarity_score": precedent["similarity_score"],
                "matched_chunks": precedent["matched_chunks"],
            }
            sides = precedent.get("retrieved_for") or []
            if len(sides) == 2:
                both.append(entry)
            elif sides == ["a"]:
                only_a.append(entry)
            elif sides == ["b"]:
                only_b.append(entry)
            else:
                both.append(entry)
        return {
            "retrieved_for_both": both,
            "retrieved_for_scenario_a_only": only_a,
            "retrieved_for_scenario_b_only": only_b,
            "note": (
                "Chunks are grouped by source document, so one judgment is counted once "
                "however many of its chunks matched."
            ),
        }

    @staticmethod
    def _evidence_quality(
        results: Dict[str, Dict[str, Any]],
        scenario_a: Dict[str, Any],
        scenario_b: Optional[Dict[str, Any]],
        provisions: List[str],
    ) -> Dict[str, Any]:
        has_b = scenario_b is not None and bool(scenario_b.get("position"))
        sim_a = float(results["scenario_a"].get("best_similarity") or 0.0)
        sim_b = float(results["scenario_b"].get("best_similarity") or 0.0) if has_b else 0.0
        best = max(sim_a, sim_b)
        reasons: List[str] = []
        if best < MIN_EVIDENCE_SCORE:
            status = "INSUFFICIENT_EVIDENCE"
            reasons.append(
                f"The best retrieved similarity ({best:.3f}) is below the evidence threshold "
                f"({MIN_EVIDENCE_SCORE:.2f})."
            )
        elif has_b and (scenario_a["supporting_count"] == 0 or scenario_b["supporting_count"] == 0):
            status = "LIMITED_EVIDENCE"
            reasons.append("Only one of the two accounts has aligned retrieved precedent.")
        elif not has_b and scenario_a["supporting_count"] == 0:
            status = "LIMITED_EVIDENCE"
            reasons.append("No retrieved precedent aligned with this account above the evidence threshold.")
        elif best < LOW_CONFIDENCE_THRESHOLD:
            status = "LIMITED_EVIDENCE"
            reasons.append(
                f"The best retrieved similarity ({best:.3f}) is marginal; rely on the sources directly."
            )
        else:
            status = "SUFFICIENT_EVIDENCE_FOR_ANALYSIS"
            reasons.append(
                "Both accounts have aligned retrieved precedent above the evidence threshold."
                if has_b
                else "Aligned retrieved precedent is above the evidence threshold."
            )

        if provisions:
            found = [p for p in scenario_a.get("provisions", []) if p.get("found")]
            if not found:
                reasons.append("No requested provision was located in the retrieved material.")
        return {
            "status": status,
            "best_similarity": round(best, 4),
            "reasons": reasons,
            "precedent_count": len(results["scenario_a"].get("results", []))
            + (len(results["scenario_b"].get("results", [])) if has_b else 0),
        }

    @staticmethod
    def _outcome_estimate(
        results: Dict[str, Dict[str, Any]],
        scenario_a: Dict[str, Any],
        scenario_b: Optional[Dict[str, Any]],
        evidence_quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        model = outcome_model_service.status()
        base = {
            "available": False,
            "target": None,
            "predicted_class": None,
            "calibrated_probability": None,
            "model_version": model.get("version"),
            "status": "PREDICTION_NOT_AVAILABLE",
            "per_scenario": {},
            "limitations": [
                "Retrieval similarity is not a probability and is never reported as one.",
            ],
        }
        if evidence_quality["status"] == "INSUFFICIENT_EVIDENCE":
            base["status"] = "INSUFFICIENT_EVIDENCE"
            base["reason"] = "Insufficient retrieved evidence to support any outcome estimate."
            return base
        if not model.get("available"):
            base["reason"] = model.get("reason")
            base["limitations"].append(
                "No trained, evaluated outcome classifier is available, so no historical "
                "disposition is estimated."
            )
            return base

        # A trained model exists: estimate each account's disposition separately.
        # The classifier consumes pre-judgment facts only; it is never fed the
        # opposing party's account or the retrieved verdict text.
        base["available"] = True
        base["status"] = "EXPERIMENTAL_PREDICTION"
        base["target"] = "historical_disposition_class"
        base["model_version"] = model.get("version")
        base["calibration"] = model.get("calibration")
        base["experimental"] = True

        # The recorded held-out metrics travel with the estimate so the UI can
        # show why this capability is labelled experimental instead of
        # presenting a class probability as a settled result.
        metrics = model.get("metrics") or {}
        if metrics:
            base["model_metrics"] = {
                "accuracy": metrics.get("accuracy"),
                "macro_f1": metrics.get("macro_f1"),
                "val_macro_f1": metrics.get("val_macro_f1"),
                "test_size": metrics.get("test_size"),
                "n_train": model.get("n_train"),
                "test_class_distribution": metrics.get("class_distribution_test"),
            }
        base["validation"] = (
            "Held-out metrics come from a small, temporally split dataset. The classifier "
            "is experimental, not validated, and its output is not a verdict."
        )

        candidates = [("scenario_a", scenario_a)]
        if scenario_b and scenario_b.get("position"):
            candidates.append(("scenario_b", scenario_b))

        for key, scenario in candidates:
            text = scenario.get("position") or ""
            if not text.strip():
                continue
            try:
                prediction = outcome_model_service.predict_from_texts([text])
            except Exception as exc:  # a prediction must never break the comparison
                logger.warning("[comparison] Prediction failed for %s: %s", key, exc)
                continue
            base["per_scenario"][key] = prediction
        base["limitations"].append(
            "A model estimate of a historical disposition is not a judicial determination."
        )
        return base

    @staticmethod
    def _comparative_analysis(
        legal_issue: str,
        case_facts: str,
        scenario_a: Dict[str, Any],
        scenario_b: Optional[Dict[str, Any]],
        scored: List[Dict[str, Any]],
        outcome: Dict[str, Any],
        evidence_quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Synthesize a structured comparative legal argument analysis."""
        has_b = scenario_b is not None and bool(scenario_b.get("position"))
        a_label = scenario_a.get("label") or "Party A"
        b_label = (scenario_b.get("label") or "Party B") if has_b else None

        a_sup = scenario_a.get("supporting_count", 0)
        a_con = scenario_a.get("contrary_count", 0)

        findings: List[str] = []
        if has_b:
            b_sup = scenario_b.get("supporting_count", 0)
            b_con = scenario_b.get("contrary_count", 0)
            findings.append(
                f"{a_label}: {a_sup} aligned supporting precedent(s) located; {a_con} contrary authority(ies) identified."
            )
            findings.append(
                f"{b_label}: {b_sup} aligned supporting precedent(s) located; {b_con} contrary authority(ies) identified."
            )
            if a_sup > b_sup:
                findings.append(
                    f"Precedent balance: {a_label}'s position currently finds more direct factual/statutory support in indexed case law."
                )
            elif b_sup > a_sup:
                findings.append(
                    f"Precedent balance: {b_label}'s position currently finds more direct factual/statutory support in indexed case law."
                )
            else:
                findings.append(
                    "Precedent balance: Both parties have balanced topical precedent alignment in the indexed corpus."
                )
        else:
            findings.append(
                f"{a_label}: {a_sup} supporting precedent(s) and {a_con} contrary authority(ies) found in indexed corpus."
            )

        outcome_insights: List[str] = []
        if outcome.get("available") and outcome.get("per_scenario"):
            per_sc = outcome["per_scenario"]
            if "scenario_a" in per_sc:
                pred_a = per_sc["scenario_a"]
                outcome_insights.append(
                    f"{a_label}: Historical tendency toward '{pred_a.get('label')}' "
                    f"({round(pred_a.get('confidence', 0) * 100, 1)}% calibrated probability)."
                )
            if has_b and "scenario_b" in per_sc:
                pred_b = per_sc["scenario_b"]
                outcome_insights.append(
                    f"{b_label}: Historical tendency toward '{pred_b.get('label')}' "
                    f"({round(pred_b.get('confidence', 0) * 100, 1)}% calibrated probability)."
                )
        else:
            outcome_insights.append(
                outcome.get("reason")
                or "Supervised outcome prediction is unavailable; legal research should rely on the precedent citations directly."
            )

        summary_bits = [
            f"Analysis of legal issue: '{legal_issue}'.",
            f"Evidence evaluation status: {evidence_quality.get('status', 'ANALYSIS_COMPLETE')}.",
        ]
        if case_facts:
            summary_bits.append(f"Context established from shared facts: {case_facts[:200]}...")

        return {
            "executive_summary": " ".join(summary_bits),
            "key_findings": findings,
            "outcome_insights": outcome_insights,
            "evidence_status": evidence_quality.get("status"),
            "disclaimer": (
                "This comparative legal analysis provides decision-support and research input. "
                "It does not substitute for judicial deliberation or counsel opinions."
            ),
        }

    @staticmethod
    def _limitations(
        request: Dict[str, Any],
        scenario_a: Dict[str, Any],
        scenario_b: Optional[Dict[str, Any]],
        evidence_quality: Dict[str, Any],
        outcome: Dict[str, Any],
        scored: List[Dict[str, Any]],
    ) -> List[str]:
        limitations = [
            "Both scenario statements are treated as allegations, not established facts.",
            "Topical alignment with a retrieved judgment is not a legal conclusion about either party.",
        ]
        if not request.get("case_facts"):
            limitations.append(
                "No shared case facts were supplied; the comparison rests on the two positions alone."
            )
        if not request.get("provisions"):
            limitations.append(
                "No statutory provisions were supplied, so no provision-specific verification was performed."
            )
        if evidence_quality["status"] == "INSUFFICIENT_EVIDENCE":
            limitations.append(
                "Retrieved evidence is insufficient to distinguish between the competing positions."
            )
        if outcome.get("reason") and not outcome.get("available"):
            limitations.append(outcome["reason"])

        scenarios_to_check = [scenario_a]
        if scenario_b and scenario_b.get("position"):
            scenarios_to_check.append(scenario_b)
        for scenario in scenarios_to_check:
            if scenario.get("supporting_count", 0) == 0:
                limitations.append(
                    f"{scenario.get('label', 'Scenario')} has no aligned retrieved precedent; its position is unverified in this corpus."
                )
        if not scored:
            limitations.append("No precedent was retrieved for either account.")
        return limitations


comparison_service = ComparisonService()
