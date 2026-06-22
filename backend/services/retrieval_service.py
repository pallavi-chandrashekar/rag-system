"""Tenant-scoped retrieval service.

Implements grounded, multi-tenant retrieval over the pgvector store. Two
strategies are exposed:

* ``retrieve_vector``  -- pure semantic (cosine) similarity search.
* ``retrieve_hybrid``  -- weighted fusion of vector similarity and lexical
  keyword overlap:  ``combined = w_vec * vector + w_kw * keyword``.

Every query is *strictly* scoped to a single ``tenant_id`` at the SQL layer so
one tenant can never read another tenant's chunks. Results are normalised into
citation ``Source`` dictionaries the API can return verbatim.
"""

import re
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.embeddings import get_embeddings

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Extremely common words contribute no retrieval signal.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "with", "as", "by", "at", "it", "this", "that", "what",
    "how", "do", "does", "i", "you", "we", "my", "our", "your",
}


def _tokenize(value: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(value.lower()) if t not in _STOPWORDS]


def compute_keyword_score(query: str, content: str) -> float:
    """Lexical overlap between a query and a chunk, normalised to ``[0, 1]``.

    Defined as the fraction of (meaningful) query terms that appear in the
    chunk. Pure function -- deterministic and DB-free so it is unit testable.
    """
    query_terms = set(_tokenize(query))
    if not query_terms:
        return 0.0
    content_terms = set(_tokenize(content))
    matched = query_terms & content_terms
    return len(matched) / len(query_terms)


class RetrievalService:
    """Encapsulates retrieval strategy + tenant isolation."""

    def __init__(self, settings=settings):
        self.settings = settings

    # -- Vector ------------------------------------------------------------
    def retrieve_vector(
        self, db: Session, query: str, tenant_id: str, top_k: int = None
    ) -> List[Dict]:
        """Semantic search scoped to ``tenant_id``. Returns raw candidates."""
        top_k = top_k or self.settings.RAG_TOP_K
        query_vector = get_embeddings([query])[0]
        vector_str = str(query_vector)

        rows = db.execute(
            text(
                """
                SELECT id, document_id, content, metadata,
                       1 - (embedding <=> :vec) AS vector_score
                FROM chunks
                WHERE tenant_id = :tenant_id
                  AND (1 - (embedding <=> :vec)) > :floor
                ORDER BY embedding <=> :vec
                LIMIT :limit
                """
            ),
            {
                "vec": vector_str,
                "tenant_id": tenant_id,
                "floor": self.settings.RAG_VECTOR_FLOOR,
                "limit": top_k * 10,
            },
        ).fetchall()

        return [
            {
                "id": str(r.id),
                "document_id": str(r.document_id),
                "content": r.content,
                "metadata": r.metadata or {},
                "vector_score": float(r.vector_score),
                "keyword_score": 0.0,
            }
            for r in rows
        ]

    # -- Keyword candidates ------------------------------------------------
    def _retrieve_keyword_candidates(
        self, db: Session, query: str, tenant_id: str, limit: int
    ) -> List[Dict]:
        """Postgres full-text candidates so keyword-only hits surface too."""
        words = _tokenize(query)
        if not words:
            return []
        ts_query = " | ".join(words)
        rows = db.execute(
            text(
                """
                SELECT id, document_id, content, metadata
                FROM chunks
                WHERE tenant_id = :tenant_id
                  AND to_tsvector('english', content) @@ to_tsquery('english', :q)
                LIMIT :limit
                """
            ),
            {"tenant_id": tenant_id, "q": ts_query, "limit": limit},
        ).fetchall()
        return [
            {
                "id": str(r.id),
                "document_id": str(r.document_id),
                "content": r.content,
                "metadata": r.metadata or {},
                "vector_score": 0.0,
                "keyword_score": 0.0,
            }
            for r in rows
        ]

    # -- Hybrid ------------------------------------------------------------
    def retrieve_hybrid(
        self, db: Session, query: str, tenant_id: str, top_k: int = None
    ) -> List[Dict]:
        """Weighted fusion of vector + keyword retrieval, tenant-scoped."""
        top_k = top_k or self.settings.RAG_TOP_K

        candidates: Dict[str, Dict] = {}
        for c in self.retrieve_vector(db, query, tenant_id, top_k):
            candidates[c["id"]] = c

        for c in self._retrieve_keyword_candidates(
            db, query, tenant_id, top_k * 10
        ):
            candidates.setdefault(c["id"], c)

        return self._fuse(query, list(candidates.values()))[:top_k]

    def _fuse(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """Apply weighted scoring + ranking to a candidate set."""
        w_vec = self.settings.RAG_VECTOR_WEIGHT
        w_kw = self.settings.RAG_KEYWORD_WEIGHT
        for c in candidates:
            c["keyword_score"] = compute_keyword_score(query, c["content"])
            c["combined_score"] = round(
                w_vec * c["vector_score"] + w_kw * c["keyword_score"], 6
            )
        return sorted(candidates, key=lambda c: c["combined_score"], reverse=True)

    def retrieve(
        self, db: Session, query: str, tenant_id: str, top_k: int = None
    ) -> List[Dict]:
        """Strategy entry point honouring the hybrid feature flag."""
        if self.settings.RAG_ENABLE_HYBRID_RETRIEVAL:
            return self.retrieve_hybrid(db, query, tenant_id, top_k)
        ranked = self._fuse(query, self.retrieve_vector(db, query, tenant_id, top_k))
        return ranked[: (top_k or self.settings.RAG_TOP_K)]

    # -- Confidence + citations -------------------------------------------
    @staticmethod
    def confidence(results: List[Dict]) -> float:
        """Answer confidence proxy = best combined score in the result set."""
        if not results:
            return 0.0
        return round(max(r.get("combined_score", 0.0) for r in results), 4)

    def format_sources(
        self, results: List[Dict], tenant_id: str, filenames: Dict[str, str]
    ) -> List[Dict]:
        """Convert raw candidates into citation ``Source`` dictionaries."""
        sources = []
        for r in results:
            meta = r.get("metadata") or {}
            sources.append(
                {
                    "document_id": r["document_id"],
                    "filename": filenames.get(
                        r["document_id"], meta.get("source", "unknown")
                    ),
                    "chunk_id": r["id"],
                    "chunk_index": int(meta.get("chunk_index", 0)),
                    "tenant_id": tenant_id,
                    "text_snippet": (r["content"][:300] + "…")
                    if len(r["content"]) > 300
                    else r["content"],
                    "retrieval_score": r.get("combined_score", 0.0),
                    "keyword_score": round(r.get("keyword_score", 0.0), 4),
                    "vector_score": round(r.get("vector_score", 0.0), 4),
                    "combined_score": r.get("combined_score", 0.0),
                }
            )
        return sources

    def lookup_filenames(
        self, db: Session, document_ids: List[str]
    ) -> Dict[str, str]:
        """Resolve document_id -> filename for citation display."""
        if not document_ids:
            return {}
        rows = db.execute(
            text("SELECT id, filename FROM documents WHERE id = ANY(:ids)"),
            {"ids": document_ids},
        ).fetchall()
        return {str(r.id): r.filename for r in rows}


retrieval_service = RetrievalService()
