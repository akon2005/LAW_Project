"""
Embedding service (Step 4).

Loads the sentence-transformers model once per process, embeds in configurable
batches, normalizes vectors for cosine space, and caches query embeddings so a
repeated query never re-runs the model.

The model is chosen by ``EMBEDDING_MODEL`` in ``.env``; swapping it for
InLegalBERT or Legal-BERT requires no code change here. Note that changing the
model changes vector dimensions, so the collection must be re-ingested.
"""
from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from typing import List, Optional

from dotenv import load_dotenv

from app.core.config import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL_NAME

load_dotenv()

logger = logging.getLogger(__name__)

QUERY_CACHE_SIZE = int(os.getenv("EMBEDDING_QUERY_CACHE_SIZE", "256"))


class EmbeddingError(RuntimeError):
    """Raised when the embedding model cannot be loaded or applied."""


class EmbeddingService:
    def __init__(self, model_name: Optional[str] = None) -> None:
        self._model = None
        self._lock = threading.Lock()
        self.model_name = model_name or EMBEDDING_MODEL_NAME
        self.batch_size = EMBEDDING_BATCH_SIZE
        self._query_cache: "OrderedDict[str, List[float]]" = OrderedDict()

    # ── Model lifecycle ────────────────────────────────────────────────
    def _get_model(self):
        """Load the model exactly once (thread-safe)."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    # Check for remote provider
                    use_remote = os.getenv("REMOTE_EMBEDDING_PROVIDER")
                    if use_remote == "openai":
                        class RemoteOpenAIModel:
                            def __init__(self, model_name):
                                self.model_name = model_name
                                import openai
                                self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                            def encode(self, texts, **kwargs):
                                res = self.client.embeddings.create(input=texts, model=self.model_name)
                                class _ListProxy:
                                    def __init__(self, data): self.data = data
                                    def tolist(self): return self.data
                                return _ListProxy([d.embedding for d in res.data])
                            def get_sentence_embedding_dimension(self):
                                return 1536
                        logger.info("[embeddings] Using remote OpenAI embeddings")
                        self._model = RemoteOpenAIModel(os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
                        return self._model
                    
                    try:
                        from sentence_transformers import SentenceTransformer

                        logger.info("[embeddings] Loading model %s", self.model_name)
                        self._model = SentenceTransformer(self.model_name)
                    except ImportError as exc:
                        raise EmbeddingError(
                            "Local embeddings unavailable (sentence-transformers not installed). "
                            "Configure REMOTE_EMBEDDING_PROVIDER='openai' for production."
                        ) from exc
                    except Exception as exc:
                        raise EmbeddingError(
                            f"Could not load embedding model '{self.model_name}': {exc}"
                        ) from exc
        return self._model

    def is_ready(self) -> bool:
        """True when the model is already resident (no download triggered)."""
        return self._model is not None

    def warm_up(self) -> bool:
        """Try to load the model; returns False instead of raising."""
        try:
            self._get_model()
            return True
        except EmbeddingError as exc:
            logger.warning("[embeddings] warm-up failed: %s", exc)
            return False

    # ── Embedding ──────────────────────────────────────────────────────
    def generate_embeddings(
        self, texts: List[str], batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """Embed a list of documents in batches. Returns normalized vectors."""
        if not texts:
            return []
        model = self._get_model()
        try:
            embeddings = model.encode(
                texts,
                batch_size=batch_size or self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query, reusing a cached vector when possible."""
        key = (query or "").strip().lower()
        if key in self._query_cache:
            self._query_cache.move_to_end(key)
            return self._query_cache[key]

        model = self._get_model()
        try:
            vector = model.encode([query], normalize_embeddings=True)[0].tolist()
        except Exception as exc:
            raise EmbeddingError(f"Query embedding failed: {exc}") from exc

        if QUERY_CACHE_SIZE > 0:
            self._query_cache[key] = vector
            while len(self._query_cache) > QUERY_CACHE_SIZE:
                self._query_cache.popitem(last=False)
        return vector

    @property
    def dimension(self) -> Optional[int]:
        """Vector dimension, or None when the model has not been loaded yet."""
        model = self._get_model()
        return int(model.get_sentence_embedding_dimension())


embedding_service = EmbeddingService()
