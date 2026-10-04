"""
Embedding service using Sentence-Transformers for LexRAG.
Converts legal documents and queries into dense vector representations.
"""
import numpy as np
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from app.core.config import EMBEDDING_MODEL_NAME, EMBEDDING_DIMENSION

# Module-level singleton
_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (singleton)."""
    global _model
    if _model is None:
        print(f"[Embeddings] Loading model: {EMBEDDING_MODEL_NAME}")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(f"[Embeddings] Model loaded. Dimension: {EMBEDDING_DIMENSION}")
    return _model


def encode_query(query: str) -> List[float]:
    """
    Encode a search query into an embedding vector.
    Returns a plain list for ChromaDB compatibility.
    """
    model = get_model()
    embedding = model.encode(query, normalize_embeddings=True)
    return embedding.astype("float32").tolist()


def encode_document(text: str, doc_type: str = "", sections: List[str] = None) -> List[float]:
    """
    Encode a legal document (or chunk) into an embedding vector.
    Optionally prepends document type and section info for richer representation.
    """
    model = get_model()
    # Build enriched text
    parts = []
    if doc_type:
        parts.append(f"[{doc_type.upper()}]")
    if sections:
        section_text = ", ".join([f"Section {s}" for s in sections])
        parts.append(f"Sections: {section_text}")
    parts.append(text)
    combined_text = " ".join(parts)

    embedding = model.encode(combined_text, normalize_embeddings=True)
    return embedding.astype("float32").tolist()


def encode_batch(texts: List[str], batch_size: int = 32) -> np.ndarray:
    """
    Batch-encode a list of texts into embedding vectors.
    Returns numpy array for bulk operations.
    """
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return embeddings.astype("float32")


def encode_batch_to_list(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Batch-encode texts and return as list of lists (ChromaDB compatible).
    """
    embeddings = encode_batch(texts, batch_size)
    return embeddings.tolist()
