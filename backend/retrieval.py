"""
Hybrid retrieval (dense + BM25) with cross-encoder reranking and RBAC filtering.
"""
from typing import List, Dict, Any, Optional
import numpy as np

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchAny,
    Prefetch,
    FusionQuery,
    Fusion,
    SparseVector,
    Query,
    SearchRequest,
)
from fastembed import TextEmbedding, SparseTextEmbedding
from sentence_transformers import CrossEncoder

from config import (
    QDRANT_COLLECTION,
    DENSE_MODEL,
    SPARSE_MODEL,
    RERANK_MODEL,
    HYBRID_TOP_K,
    RERANK_TOP_N,
    ROLE_COLLECTIONS,
)

# Module-level singletons — initialised lazily
_dense_model: Optional[TextEmbedding] = None
_sparse_model: Optional[SparseTextEmbedding] = None
_reranker: Optional[CrossEncoder] = None


def _get_dense():
    global _dense_model
    if _dense_model is None:
        _dense_model = TextEmbedding(model_name=DENSE_MODEL)
    return _dense_model


def _get_sparse():
    global _sparse_model
    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL)
    return _sparse_model


def _get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def rbac_filter(role: str) -> Filter:
    allowed_collections = ROLE_COLLECTIONS.get(role, [])
    return Filter(
        must=[
            FieldCondition(
                key="collection",
                match=MatchAny(any=allowed_collections),
            )
        ]
    )


def hybrid_retrieve(
    client: QdrantClient,
    query: str,
    role: str,
    top_k: int = HYBRID_TOP_K,
) -> List[Dict[str, Any]]:
    dense_vec = list(_get_dense().embed([query]))[0].tolist()
    sparse_result = list(_get_sparse().embed([query]))[0]
    sparse_vec = SparseVector(
        indices=sparse_result.indices.tolist(),
        values=sparse_result.values.tolist(),
    )

    access_filter = rbac_filter(role)

    results = client.query_points(
        collection_name=QDRANT_COLLECTION,
        prefetch=[
            Prefetch(
                query=dense_vec,
                using="dense",
                limit=top_k,
                filter=access_filter,
            ),
            Prefetch(
                query=sparse_vec,
                using="sparse",
                limit=top_k,
                filter=access_filter,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )

    return [
        {
            "text": p.payload.get("text", ""),
            "source_document": p.payload.get("source_document", ""),
            "collection": p.payload.get("collection", ""),
            "section_title": p.payload.get("section_title", ""),
            "chunk_type": p.payload.get("chunk_type", "text"),
            "score": p.score,
        }
        for p in results.points
    ]


def rerank(query: str, candidates: List[Dict[str, Any]], top_n: int = RERANK_TOP_N) -> List[Dict[str, Any]]:
    if not candidates:
        return []
    reranker = _get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    for score, candidate in ranked:
        candidate["rerank_score"] = float(score)
    return [c for _, c in ranked[:top_n]]


def retrieve_and_rerank(
    client: QdrantClient,
    query: str,
    role: str,
) -> List[Dict[str, Any]]:
    candidates = hybrid_retrieve(client, query, role)
    return rerank(query, candidates)
