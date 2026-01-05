from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional

from backend.database import get_db
from backend.services.rag import hybrid_search, multi_query_search
from backend.services.chat import (
    rewrite_query, 
    generate_multi_queries, 
    decompose_query, 
    generate_hyde_answer
)
# UPDATED IMPORT: Added delete_tenant_data
from backend.services.ingestion import process_document, delete_tenant_data

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    tenant_id: str
    top_k: int = 5
    chat_history: List[Dict[str, str]] = []
    strategy: str = "simple" 

@router.post("/ingest")
async def ingest_file(
    tenant_id: str, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    try:
        doc_id = await process_document(file, tenant_id, db)
        return {"status": "success", "doc_id": doc_id}
    except Exception as e:
        print(f"Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query")
async def query_rag(request: QueryRequest, db: Session = Depends(get_db)):
    # 1. Base Contextual Rewrite
    standalone_query = request.query
    if request.chat_history:
        standalone_query = rewrite_query(request.query, request.chat_history)
    
    results = []
    generated_queries = [standalone_query]
    
    # 2. Apply Strategy
    if request.strategy == "multi_query":
        generated_queries = generate_multi_queries(standalone_query)
        results = multi_query_search(db, generated_queries, request.tenant_id, request.top_k)
        
    elif request.strategy == "decomposition":
        generated_queries = decompose_query(standalone_query)
        results = multi_query_search(db, generated_queries, request.tenant_id, request.top_k)
        
    elif request.strategy == "hyde":
        hyde_doc = generate_hyde_answer(standalone_query)
        generated_queries = [hyde_doc]
        results = hybrid_search(
            db, 
            query=hyde_doc, 
            tenant_id=request.tenant_id, 
            top_k=request.top_k, 
            search_type="vector"
        )
        
    else:
        results = hybrid_search(db, standalone_query, request.tenant_id, request.top_k)
    
    # 3. Return
    return {
        "original_query": request.query,
        "standalone_query": standalone_query,
        "strategy": request.strategy,
        "generated_queries": generated_queries,
        "results": results
    }

# NEW ENDPOINT
@router.delete("/reset/{tenant_id}")
async def reset_tenant(tenant_id: str, db: Session = Depends(get_db)):
    try:
        delete_tenant_data(tenant_id, db)
        return {"status": "success", "message": f"Data for tenant {tenant_id} deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))