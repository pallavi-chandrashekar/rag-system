from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header, Body
from sqlalchemy.orm import Session
from sqlalchemy import text  # Required for raw SQL queries
from pydantic import BaseModel
from typing import List, Dict

from backend.database import get_db
from backend.services.rag import hybrid_search, multi_query_search
from backend.services.chat import (
    rewrite_query, generate_multi_queries, decompose_query, generate_hyde_answer
)
from backend.services.ingestion import process_document, delete_tenant_data

router = APIRouter()

class SearchPayload(BaseModel):
    text: str
    tenant_id: str
    search_type: str = "hybrid"
    top_k: int = 5
    chat_history: List[Dict[str, str]] = []

# --- 1. INGEST ---
@router.post("/api/v1/ingest")
async def ingest_file(
    file: UploadFile = File(...), 
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    try:
        doc_id = await process_document(file, x_tenant_id, db)
        return {"status": "success", "doc_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. SEARCH ---
@router.post("/api/v1/search")
async def search_rag(payload: SearchPayload, db: Session = Depends(get_db)):
    query_text = payload.text
    strategy = payload.search_type
    
    standalone_query = query_text
    if payload.chat_history:
        standalone_query = rewrite_query(query_text, payload.chat_history)
    
    results = []
    generated_queries = [standalone_query]
    
    if strategy == "multi_query":
        generated_queries = generate_multi_queries(standalone_query)
        results = multi_query_search(db, generated_queries, payload.tenant_id, payload.top_k)
    elif strategy == "decomposition":
        generated_queries = decompose_query(standalone_query)
        results = multi_query_search(db, generated_queries, payload.tenant_id, payload.top_k)
    elif strategy == "hyde":
        hyde_doc = generate_hyde_answer(standalone_query)
        generated_queries = [hyde_doc]
        results = hybrid_search(db, hyde_doc, payload.tenant_id, payload.top_k, search_type="vector")
    else:
        results = hybrid_search(db, standalone_query, payload.tenant_id, payload.top_k)
    
    return {
        "original_query": query_text,
        "generated_queries": generated_queries,
        "results": results
    }

# --- 3. LIST DOCUMENTS (Moved Here) ---
@router.get("/api/v1/documents")
async def list_documents(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    try:
        results = db.execute(
            text("SELECT id, filename, created_at FROM documents WHERE tenant_id = :tenant_id ORDER BY created_at DESC"),
            {"tenant_id": x_tenant_id}
        ).fetchall()
        
        return {
            "documents": [
                {
                    "id": str(row.id), 
                    "filename": row.filename, 
                    "created_at": str(row.created_at).split(" ")[0]
                } 
                for row in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. DELETE DOCUMENT (Moved Here) ---
@router.delete("/api/v1/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    try:
        # Cascade delete is handled by database foreign keys usually, 
        # but let's be safe and delete chunks if needed or rely on ON DELETE CASCADE
        result = db.execute(
            text("DELETE FROM documents WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": doc_id, "tenant_id": x_tenant_id}
        )
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))