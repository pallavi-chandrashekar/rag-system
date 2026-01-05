from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict

from backend.database import get_db
from backend.services.rag import hybrid_search
from backend.services.chat import rewrite_query
from backend.services.ingestion import process_document

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    tenant_id: str
    top_k: int = 5
    chat_history: List[Dict[str, str]] = []

@router.post("/ingest")
async def ingest_file(
    tenant_id: str, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    try:
        if not process_document:
            raise HTTPException(status_code=500, detail="Ingestion service not found")
        doc_id = await process_document(file, tenant_id, db)
        return {"status": "success", "doc_id": doc_id}
    except Exception as e:
        print(f"Ingestion Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query")
async def query_rag(request: QueryRequest, db: Session = Depends(get_db)):
    # 1. Rewrite Query
    standalone_query = request.query
    if request.chat_history:
        standalone_query = rewrite_query(request.query, request.chat_history)
    
    # 2. Search
    results = hybrid_search(
        db, 
        query=standalone_query, 
        tenant_id=request.tenant_id, 
        top_k=request.top_k
    )
    
    # 3. RETURN DICTIONARY 
    return {
        "original_query": request.query,
        "standalone_query": standalone_query,
        "results": results
    }