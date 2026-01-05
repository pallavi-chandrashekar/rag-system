from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.services.embeddings import get_embeddings
from backend.models import Chunk

def hybrid_search(db: Session, query: str, tenant_id: str, top_k=5):
    """
    Performs Hybrid Search (Vector + Keyword) weighted by RRF.
    """
    # 1. Generate Query Vector
    query_vector = get_embeddings([query])[0]
    
    # 2. Vector Search (Cosine Similarity)
    # Note: <-> is L2 distance, <=> is Cosine Distance in pgvector
    vector_results = db.execute(text("""
        SELECT id, content, 1 - (embedding <=> :vec) as score
        FROM chunks 
        WHERE tenant_id = :tenant_id
        ORDER BY embedding <=> :vec 
        LIMIT 50
    """), {"vec": str(query_vector), "tenant_id": tenant_id}).fetchall()

    # 3. Keyword Search (Full-Text)
    # Using plain SQL 'ilike' for simplicity in this demo, 
    # but strictly prefer 'tsvector' for production.
    keyword_results = db.execute(text("""
        SELECT id, content, 0 as score
        FROM chunks 
        WHERE tenant_id = :tenant_id AND content ILIKE :query
        LIMIT 50
    """), {"query": f"%{query}%", "tenant_id": tenant_id}).fetchall()

    # 4. RRF Fusion
    return _rrf_fusion(vector_results, keyword_results, k=60)[:top_k]

def _rrf_fusion(vector_results, keyword_results, k=60):
    """
    Reciprocal Rank Fusion algorithm.
    Score = 1 / (k + rank)
    """
    scores = {}
    
    # Process Vector Ranks
    for rank, row in enumerate(vector_results):
        doc_id = row.id
        if doc_id not in scores:
            scores[doc_id] = {"content": row.content, "score": 0}
        scores[doc_id]["score"] += 1 / (k + rank + 1)
        
    # Process Keyword Ranks
    for rank, row in enumerate(keyword_results):
        doc_id = row.id
        if doc_id not in scores:
            scores[doc_id] = {"content": row.content, "score": 0}
        scores[doc_id]["score"] += 1 / (k + rank + 1)
    
    # Sort by accumulated score
    sorted_docs = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
    return sorted_docs