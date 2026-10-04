"""
ChromaDB-based vector store service for LexRAG.
Replaces the FAISS index with ChromaDB for persistent, metadata-filterable search.
"""
import chromadb
from typing import List, Optional, Dict
from app.core.config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME

# Module-level singleton
_client: Optional[chromadb.PersistentClient] = None
_collection = None


def get_client() -> chromadb.PersistentClient:
    """Get or create the ChromaDB persistent client."""
    global _client
    if _client is None:
        print(f"[VectorStore] Initializing ChromaDB at {CHROMA_PERSIST_DIR}")
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        print("[VectorStore] ChromaDB client ready.")
    return _client


def get_collection():
    """Get or create the main document collection."""
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        print(f"[VectorStore] Collection '{CHROMA_COLLECTION_NAME}' ready. "
              f"Documents: {_collection.count()}")
    return _collection


def is_collection_loaded() -> bool:
    """Check if the collection is loaded and has documents."""
    try:
        collection = get_collection()
        return collection.count() > 0
    except Exception:
        return False


def get_document_count() -> int:
    """Get the total number of document chunks in the collection."""
    try:
        return get_collection().count()
    except Exception:
        return 0


def add_documents(
    ids: List[str],
    embeddings: List[List[float]],
    documents: List[str],
    metadatas: List[Dict],
) -> None:
    """
    Add documents to the ChromaDB collection.

    Args:
        ids: Unique IDs for each chunk (e.g., 'doc_id__chunk_0')
        embeddings: Pre-computed embedding vectors
        documents: Text content of each chunk
        metadatas: Metadata dicts (doc_id, document_type, jurisdiction, court, year, etc.)
    """
    collection = get_collection()

    # ChromaDB has a batch limit; add in chunks of 500
    batch_size = 500
    for i in range(0, len(ids), batch_size):
        batch_end = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:batch_end],
            embeddings=embeddings[i:batch_end],
            documents=documents[i:batch_end],
            metadatas=metadatas[i:batch_end],
        )

    print(f"[VectorStore] Added {len(ids)} chunks. Total: {collection.count()}")


def search(
    query_embedding: List[float],
    top_k: int = 8,
    where: Optional[Dict] = None,
) -> List[Dict]:
    """
    Semantic similarity search with optional metadata filtering.

    Args:
        query_embedding: Query vector.
        top_k: Number of results to return.
        where: ChromaDB metadata filter dict (e.g., {"document_type": "case_law"}).

    Returns:
        List of dicts with 'doc_id', 'document', 'metadata', 'relevance_score'.
    """
    collection = get_collection()

    query_params = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        query_params["where"] = where

    try:
        results = collection.query(**query_params)
    except Exception as e:
        print(f"[VectorStore] Search error: {e}")
        return []

    # Parse results — ChromaDB returns lists of lists
    search_results = []
    if results and results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            # ChromaDB distance is cosine distance; convert to similarity
            distance = results["distances"][0][i] if results["distances"] else 0
            similarity = max(0, 1 - distance)  # cosine distance → similarity

            search_results.append({
                "chunk_id": chunk_id,
                "doc_id": results["metadatas"][0][i].get("doc_id", chunk_id),
                "document": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "relevance_score": round(similarity, 4),
            })

    return search_results


def get_similar(
    doc_id: str,
    top_k: int = 5,
    where: Optional[Dict] = None,
) -> List[Dict]:
    """
    Find documents similar to a given document.

    Args:
        doc_id: The source document ID.
        top_k: Number of similar results.
        where: Optional metadata filters.

    Returns:
        List of similar document dicts.
    """
    collection = get_collection()

    # Get the document's chunks
    try:
        doc_results = collection.get(
            where={"doc_id": doc_id},
            include=["embeddings"],
            limit=1,
        )
    except Exception:
        return []

    if not doc_results or not doc_results["embeddings"]:
        return []

    # Use the first chunk's embedding as the query
    query_embedding = doc_results["embeddings"][0]

    # Search for similar, excluding the source document
    results = search(query_embedding, top_k=top_k + 5, where=where)

    # Filter out chunks from the same document
    filtered = [r for r in results if r["doc_id"] != doc_id]
    return filtered[:top_k]


def delete_document(doc_id: str) -> int:
    """
    Delete all chunks belonging to a document.

    Returns:
        Number of chunks deleted.
    """
    collection = get_collection()
    try:
        # Get all chunk IDs for this document
        results = collection.get(
            where={"doc_id": doc_id},
            include=[],
        )
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
            return len(results["ids"])
    except Exception as e:
        print(f"[VectorStore] Delete error for {doc_id}: {e}")
    return 0


def reset_collection() -> None:
    """Delete and recreate the collection. USE WITH CAUTION."""
    global _collection
    client = get_client()
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
        print(f"[VectorStore] Collection '{CHROMA_COLLECTION_NAME}' deleted.")
    except Exception:
        pass
    _collection = None
    get_collection()  # recreate
    print(f"[VectorStore] Collection '{CHROMA_COLLECTION_NAME}' recreated.")


def build_where_filter(
    document_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    court: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    relevant_year: Optional[int] = None,
) -> Optional[Dict]:
    """
    Build a ChromaDB where-filter from search parameters.
    Returns None if no filters are specified.
    """
    conditions = []

    if document_type:
        conditions.append({"document_type": document_type})
    if jurisdiction:
        conditions.append({"jurisdiction": jurisdiction})
    if court:
        conditions.append({"court": court})
    if year_from:
        conditions.append({"year": {"$gte": year_from}})
    if year_to:
        conditions.append({"year": {"$lte": year_to}})
    
    if relevant_year is not None:
        conditions.append({"law_version_valid_from": {"$lte": relevant_year}})
        conditions.append({"law_version_valid_until": {"$gte": relevant_year}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}
