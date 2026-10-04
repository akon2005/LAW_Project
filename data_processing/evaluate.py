"""
RAG Evaluation Script for LexRAG.
Tests retrieval quality: precision, relevance scoring, citation accuracy.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DATASET_DIR
from app.rag.embeddings import encode_query
from app.db.vectorstore import search, get_document_count


# Sample test queries with expected relevant document IDs
TEST_QUERIES = [
    {
        "query": "What defines a commercial dispute under the Commercial Courts Act 2015?",
        "expected_doc_ids": ["STATUTE_CCA_2015_001"],
        "expected_type": "statute",
    },
    {
        "query": "How are Commercial Courts constituted at the district level?",
        "expected_doc_ids": ["STATUTE_CCA_2015_002"],
        "expected_type": "statute",
    },
    {
        "query": "What is the specified value threshold for commercial disputes?",
        "expected_doc_ids": ["STATUTE_CCA_2015_005", "NOTIF_2018_001"],
        "expected_type": None,
    },
    {
        "query": "Grounds for setting aside arbitral award",
        "expected_doc_ids": ["STATUTE_ARB_1996_002"],
        "expected_type": "statute",
    },
    {
        "query": "Pre-institution mediation requirements in commercial cases",
        "expected_doc_ids": ["NOTIF_2018_002"],
        "expected_type": "notification",
    },
]


def evaluate_retrieval():
    """Evaluate retrieval quality on test queries."""
    print("=" * 60)
    print("  LexRAG — RAG Evaluation")
    print("=" * 60)

    total_docs = get_document_count()
    print(f"[Eval] Collection size: {total_docs} chunks\n")

    if total_docs == 0:
        print("ERROR: Collection is empty. Run ingest_to_chromadb.py first.")
        sys.exit(1)

    total_hits = 0
    total_expected = 0
    total_mrr = 0.0

    for i, test in enumerate(TEST_QUERIES, 1):
        query = test["query"]
        expected_ids = set(test["expected_doc_ids"])
        expected_type = test.get("expected_type")

        print(f"--- Query {i}: {query}")

        # Encode and search
        q_emb = encode_query(query)
        results = search(query_embedding=q_emb, top_k=5)

        # Extract unique doc_ids from results
        retrieved_ids = []
        seen = set()
        for r in results:
            doc_id = r["doc_id"]
            if doc_id not in seen:
                retrieved_ids.append(doc_id)
                seen.add(doc_id)

        # Calculate metrics
        hits = len(expected_ids.intersection(set(retrieved_ids)))
        total_hits += hits
        total_expected += len(expected_ids)

        # MRR (Mean Reciprocal Rank)
        rr = 0.0
        for rank, doc_id in enumerate(retrieved_ids, 1):
            if doc_id in expected_ids:
                rr = 1.0 / rank
                break
        total_mrr += rr

        # Report
        precision = hits / len(expected_ids) if expected_ids else 0
        status = "✅" if hits > 0 else "❌"

        print(f"  {status} Hit@5: {hits}/{len(expected_ids)} | MRR: {rr:.3f}")
        print(f"  Expected: {expected_ids}")
        print(f"  Retrieved: {retrieved_ids[:5]}")

        if results:
            top_score = results[0]["relevance_score"]
            top_type = results[0]["metadata"].get("document_type", "?")
            print(f"  Top result: {results[0]['doc_id']} (score: {top_score:.3f}, type: {top_type})")
        print()

    # Summary
    n = len(TEST_QUERIES)
    recall = total_hits / total_expected if total_expected > 0 else 0
    mean_mrr = total_mrr / n if n > 0 else 0

    print("=" * 60)
    print(f"  RESULTS: {n} queries evaluated")
    print(f"  Recall@5:     {recall:.1%} ({total_hits}/{total_expected})")
    print(f"  Mean MRR:     {mean_mrr:.3f}")
    print("=" * 60)


if __name__ == "__main__":
    evaluate_retrieval()
