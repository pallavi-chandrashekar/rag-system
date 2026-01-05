from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
from backend.services.embeddings import get_embeddings 

def hybrid_search(db: Session, query: str, tenant_id: str, top_k=5, search_type="hybrid"):
    """
    Performs Hybrid Search (Vector + Keyword) weighted by RRF.
    search_type: 'hybrid' (Vector + Keyword) or 'vector' (Vector only, good for HyDE)
    """
    # 1. Generate Query Vector
    query_vector = get_embeddings([query])[0]
    vector_str = str(query_vector)
    
    # 2. Vector Search (Cosine Similarity)
    # FIX: Increased threshold from 0.2 to 0.35
    # 0.2 was too permissive (letting in "chocolate cake"). 
    # 0.35 is robust enough to block noise while keeping semantic matches (Scenario 1).
    vector_query = text("""
        SELECT id, content, 1 - (embedding <=> :vec) as score
        FROM chunks 
        WHERE tenant_id = :tenant_id 
          AND (1 - (embedding <=> :vec)) > 0.35
        ORDER BY embedding <=> :vec 
        LIMIT 50
    """)
    
    vector_results = db.execute(
        vector_query, 
        {"vec": vector_str, "tenant_id": tenant_id}
    ).fetchall()
    
    keyword_results = []
    if search_type == "hybrid":
        # 3. Robust Keyword Search (Postgres Full-Text Search)
        # We split the query into words and use ' | ' (OR) logic.
        words = [w for w in query.split() if w.strip()]
        
        if words:
            # Join words with OR operator for Postgres tsquery
            ts_query_str = " | ".join(words)
            
            keyword_query = text("""
                SELECT id, content, 
                       ts_rank_cd(to_tsvector('english', content), to_tsquery('english', :q)) as score
                FROM chunks 
                WHERE tenant_id = :tenant_id 
                  AND to_tsvector('english', content) @@ to_tsquery('english', :q)
                ORDER BY score DESC
                LIMIT 50
            """)
            
            keyword_results = db.execute(
                keyword_query, 
                {"q": ts_query_str, "tenant_id": tenant_id}
            ).fetchall()

    # 4. RRF Fusion (Returns a List[Dict])
    return _rrf_fusion(vector_results, keyword_results, k=60)[:top_k]

def multi_query_search(db: Session, queries: List[str], tenant_id: str, top_k=5):
    """
    Runs hybrid search for multiple queries and de-duplicates/fuses results.
    """
    all_results = []
    
    for q in queries:
        # Fetch slightly more results per sub-query to ensure diversity
        results = hybrid_search(db, q, tenant_id, top_k=top_k * 2)
        all_results.extend(results)
    
    # Simple Deduplication
    unique_docs = {}
    for res in all_results:
        # 'res' is a Dictionary here, NOT a SQLAlchemy Row.
        doc_id = res['id'] 
        
        if doc_id not in unique_docs:
            unique_docs[doc_id] = res
        else:
            # If document found by multiple queries, boost its score
            current_score = unique_docs[doc_id]['score']
            new_score = res['score']
            unique_docs[doc_id]['score'] = max(current_score, new_score) + 0.05

    # Sort by final score
    sorted_results = sorted(unique_docs.values(), key=lambda x: x['score'], reverse=True)
    return sorted_results[:top_k]

def _rrf_fusion(vector_results, keyword_results, k=60):
    scores = {}
    
    # Helper to process result rows
    def process_results(results):
        for rank, row in enumerate(results):
            doc_id = row.id
            if doc_id not in scores:
                scores[doc_id] = {"id": doc_id, "content": row.content, "score": 0} 
            scores[doc_id]["score"] += 1 / (k + rank + 1)
            
    process_results(vector_results)
    process_results(keyword_results)
    
    return sorted(scores.values(), key=lambda x: x["score"], reverse=True)