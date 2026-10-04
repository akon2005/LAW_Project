"""
Similar Documents API route for VIDHIVEDA.
POST /api/similar — Find analogous cases via vector similarity.
"""
import time
from fastapi import APIRouter, HTTPException

from app.schemas.schemas import SimilarRequest, SimilarResponse, SourceDocument
from app.rag.pipeline import retrieve, get_embedding_model, get_collection

router = APIRouter()


@router.post("/similar", response_model=SimilarResponse)
async def find_similar(request: SimilarRequest):
    """
    Given a document ID, find semantically similar cases in the vector store.
    Uses the first chunk's embedding of the source document as the query vector.
    """
    start_time = time.time()

    try:
        collection = get_collection()

        # Retrieve the source document's embedding
        try:
            source_results = collection.get(
                ids=[request.doc_id],
                include=["embeddings", "metadatas", "documents"],
                limit=1,
            )
        except Exception:
            # Try filtering by doc_id in metadata
            source_results = collection.get(
                where={"doc_id": request.doc_id},
                include=["embeddings", "metadatas", "documents"],
                limit=1,
            )

        if (
            not source_results
            or not source_results.get("ids")
            or len(source_results["ids"]) == 0
        ):
            # Fall back: try using the document ID as a text query
            embedding_model = get_embedding_model()
            query_embedding = embedding_model.encode([request.doc_id]).tolist()[0]
        else:
            query_embedding = source_results["embeddings"][0]

        # Build filters
        chroma_where = None
        if request.filters:
            conditions = []
            if request.filters.get("document_type"):
                conditions.append({"legal_domain": request.filters["document_type"]})
            if request.filters.get("court"):
                conditions.append({"court": request.filters["court"]})
            if request.filters.get("year_from"):
                conditions.append({"year": {"$gte": int(request.filters["year_from"])}})
            if request.filters.get("year_to"):
                conditions.append({"year": {"$lte": int(request.filters["year_to"])}})
            if len(conditions) == 1:
                chroma_where = conditions[0]
            elif len(conditions) > 1:
                chroma_where = {"$and": conditions}

        # Search for similar, requesting more to exclude the source
        n_results = request.top_k + 5
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=chroma_where,
            include=["metadatas", "documents", "distances"],
        )

        source_doc = None
        similar_docs = []

        if results and results.get("ids") and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                chunk_id = results["ids"][0][i]
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                document = results["documents"][0][i] if results.get("documents") else ""
                distance = results["distances"][0][i] if results.get("distances") else 0.0
                similarity = max(0.0, min(1.0, 1.0 - distance))

                doc_id = metadata.get("doc_id", chunk_id)

                src = SourceDocument(
                    doc_id=doc_id,
                    case_id=doc_id,
                    title=metadata.get("case_name") or metadata.get("title") or chunk_id,
                    case_name=metadata.get("case_name") or metadata.get("title") or chunk_id,
                    document_type=metadata.get("legal_domain") or metadata.get("document_type") or "case_law",
                    court=metadata.get("court", ""),
                    year=metadata.get("year", 0),
                    relevance_score=round(similarity, 4),
                    similarity_score=round(similarity, 4),
                    snippet=document[:500] if document else "",
                    citation=metadata.get("citation", ""),
                )

                if doc_id == request.doc_id and source_doc is None:
                    source_doc = src
                else:
                    similar_docs.append(src)

            # Limit to top_k
            similar_docs = similar_docs[: request.top_k]

        elapsed = round(time.time() - start_time, 2)

        return SimilarResponse(
            source_doc=source_doc,
            similar_docs=similar_docs,
            processing_time_seconds=elapsed,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
