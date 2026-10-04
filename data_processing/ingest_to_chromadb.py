"""
ChromaDB Ingestion Script for LexRAG.
Chunks legal documents, embeds them, and stores in ChromaDB.
"""
import json
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DATASET_DIR, CHUNK_SIZE, CHUNK_OVERLAP
from app.rag.embeddings import encode_batch_to_list
from app.db.vectorstore import add_documents, reset_collection, get_document_count


import re

def strip_verdict_sentences(text: str) -> str:
    """
    Strips any sentence containing verdict-revealing keywords to prevent label leakage.
    """
    if not text:
        return ""
    
    # Split text into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    verdict_keywords = {
        "held", "convicted", "acquitted", "sentenced", "ruled", 
        "conviction", "acquittal", "dismissed", "allowed", "decreed", 
        "judgment", "verdict", "ruling", "sentencing", "guilty", "innocent",
        "the court ruled", "finds the accused", "found guilty"
    }
    
    filtered_sentences = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        has_verdict = False
        for kw in verdict_keywords:
            # Word boundary check for keywords to avoid false positives
            pattern = r'\b' + re.escape(kw) + r'\b' if ' ' not in kw else re.escape(kw)
            if re.search(pattern, sentence_lower):
                has_verdict = True
                break
        if not has_verdict:
            filtered_sentences.append(sentence)
            
    return " ".join(filtered_sentences)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks for embedding.
    Uses sentence-aware splitting to avoid breaking mid-sentence.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    sentences = text.replace('\n', ' ').split('. ')
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = current_chunk + (". " if current_chunk else "") + sentence
        if len(candidate) > chunk_size and current_chunk:
            chunks.append(current_chunk + ".")
            # Overlap: keep last portion
            words = current_chunk.split()
            overlap_words = int(len(words) * (overlap / chunk_size))
            current_chunk = " ".join(words[-overlap_words:]) + ". " + sentence if overlap_words > 0 else sentence
        else:
            current_chunk = candidate

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


def load_dataset(file_path: Path, document_type: str) -> List[Dict]:
    """Load a dataset file and normalize to common format."""
    if not file_path.exists():
        print(f"  [Skip] {file_path.name} not found")
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    normalized = []
    for i, doc in enumerate(docs):
        normalized.append({
            "doc_id": doc.get("doc_id", doc.get("case_id", f"unknown_{i}")),
            "title": doc.get("title", doc.get("case_name", "Untitled")),
            "document_type": document_type,
            "jurisdiction": doc.get("jurisdiction", "India"),
            "court": doc.get("court", ""),
            "year": doc.get("year", 0),
            "full_text": doc.get("full_text", doc.get("facts", "")),
            "sections": doc.get("sections", []),
            "outcome": doc.get("outcome", ""),
            "reasoning": doc.get("reasoning_excerpt", ""),
            # Include temporal fields if they exist in dataset JSON
            "law_version_valid_from": doc.get("law_version_valid_from"),
            "law_version_valid_until": doc.get("law_version_valid_until"),
        })

    return normalized


def main():
    print("=" * 60)
    print("  LexRAG — ChromaDB Ingestion")
    print("=" * 60)

    # Reset the collection for fresh ingestion
    reset_collection()

    # Load all datasets
    all_docs = []
    for filename, doc_type in [
        ("cases.json", "case_law"),
        ("statutes.json", "statute"),
        ("notifications.json", "notification"),
        ("regulations.json", "regulation"),
    ]:
        docs = load_dataset(DATASET_DIR / filename, doc_type)
        all_docs.extend(docs)
        if docs:
            print(f"[Dataset] Loaded {len(docs)} {doc_type} documents from {filename}")

    if not all_docs:
        print("ERROR: No documents found to ingest.")
        sys.exit(1)

    print(f"\n[Ingest] Processing {len(all_docs)} documents...")
    print(f"[Ingest] Chunk size: {CHUNK_SIZE}, Overlap: {CHUNK_OVERLAP}")

    # Chunk all documents
    all_ids = []
    all_texts = []
    all_metadatas = []

    for doc in all_docs:
        # Prevent label leakage: do NOT include reasoning excerpt. Strip verdict sentences from full_text
        clean_content = strip_verdict_sentences(doc["full_text"])
        chunks = chunk_text(clean_content)

        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{doc['doc_id']}__chunk_{chunk_idx}"
            all_ids.append(chunk_id)
            all_texts.append(chunk)
            all_metadatas.append({
                "doc_id": str(doc["doc_id"]),
                "title": str(doc["title"]),
                "document_type": str(doc["document_type"]),
                "jurisdiction": str(doc["jurisdiction"]),
                "court": str(doc.get("court") or ""),
                "year": int(doc["year"] or 0),
                "sections_str": str(", ".join(doc.get("sections") or [])),
                "outcome": str(doc.get("outcome") or ""),
                "chunk_index": int(chunk_idx),
                "total_chunks": int(len(chunks)),
                "law_version_valid_from": int(doc.get("law_version_valid_from") or doc["year"] or 0),
                "law_version_valid_until": int(doc.get("law_version_valid_until") or 9999),
            })

    print(f"[Ingest] Generated {len(all_ids)} chunks from {len(all_docs)} documents")
    print(f"[Ingest] Average chunks per document: {len(all_ids) / len(all_docs):.1f}")

    # Embed all chunks
    print("[Ingest] Encoding chunks with Sentence-Transformer...")
    all_embeddings = encode_batch_to_list(all_texts, batch_size=16)
    print(f"[Ingest] Generated {len(all_embeddings)} embeddings")

    # Store in ChromaDB
    print("[Ingest] Storing in ChromaDB...")
    add_documents(
        ids=all_ids,
        embeddings=all_embeddings,
        documents=all_texts,
        metadatas=all_metadatas,
    )

    total = get_document_count()
    print(f"\n[SUCCESS] Ingestion complete!")
    print(f"   Documents: {len(all_docs)}")
    print(f"   Chunks: {total}")
    print(f"   Chunk size: {CHUNK_SIZE} chars (overlap: {CHUNK_OVERLAP})")


if __name__ == "__main__":
    main()
