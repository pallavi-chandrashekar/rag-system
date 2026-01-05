from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.services.embeddings import get_embeddings 

def hybrid_search(db: Session, query: str, tenant_id: str, top_k=5):
    """
    Performs Hybrid Search (Vector + Keyword) weighted by RRF.
    """
    # 1. Generate Query Vector
    query_vector = get_embeddings([query])[0]
    vector_str = str(query_vector)
    
    # 2. Vector Search (Cosine Similarity)
    # THRESHOLD SET TO 0.2 (The sweet spot)
    vector_query = text("""
        SELECT id, content, 1 - (embedding <=> :vec) as score
        FROM chunks 
        WHERE tenant_id = :tenant_id 
          AND (1 - (embedding <=> :vec)) > 0.2
        ORDER BY embedding <=> :vec 
        LIMIT 50
    """)
    
    vector_results = db.execute(
        vector_query, 
        {"vec": vector_str, "tenant_id": tenant_id}
    ).fetchall()

    # 3. Keyword Search (Full-Text)
    keyword_query = text("""
        SELECT id, content, 0 as score
        FROM chunks 
        WHERE tenant_id = :tenant_id AND content ILIKE :query
        LIMIT 50
    """)
    
    keyword_results = db.execute(
        keyword_query, 
        {"query": f"%{query}%", "tenant_id": tenant_id}
    ).fetchall()

    # 4. RRF Fusion
    return _rrf_fusion(vector_results, keyword_results, k=60)[:top_k]

def _rrf_fusion(vector_results, keyword_results, k=60):
    scores = {}
    for rank, row in enumerate(vector_results):
        doc_id = row.id
        if doc_id not in scores:
            scores[doc_id] = {"id": doc_id, "content": row.content, "score": 0} 
        scores[doc_id]["score"] += 1 / (k + rank + 1)
        
    for rank, row in enumerate(keyword_results):
        doc_id = row.id
        if doc_id not in scores:
            scores[doc_id] = {"id": doc_id, "content": row.content, "score": 0}
        scores[doc_id]["score"] += 1 / (k + rank + 1)
    
    return sorted(scores.values(), key=lambda x: x["score"], reverse=True)