from fastapi import APIRouter, UploadFile, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any

# Imports from our project structure
from backend.database import get_db
from backend.models import Document
from backend.services.ingestion import process_document_task
from backend.services.rag import hybrid_search

router = APIRouter()

# --- Schemas (Pydantic Models) ---

class IngestResponse(BaseModel):
    status: str
    document_id: str
    message: str

class QueryRequest(BaseModel):
    query: str
    tenant_id: str
    top_k: int = 5

class SearchResult(BaseModel):
    id: str
    content: str
    score: float
    # We use 'Any' for metadata because it can be unstructured JSON
    metadata: Optional[Any] = None

class QueryResponse(BaseModel):
    results: List[SearchResult]


# --- Endpoints ---

@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile, 
    tenant_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Async Ingestion:
    1. Uploads file to memory (careful with large files).
    2. Creates a PENDING document record in DB.
    3. Offloads processing (Chunk -> Embed -> Save) to BackgroundTasks.
    """
    try:
        # 1. Create the database record immediately
        doc = Document(filename=file.filename, tenant_id=tenant_id, status="PENDING")
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # 2. Read file content
        # Note: In a real production app with >100MB files, 
        # stream this to S3/Disk instead of reading into RAM.
        file_content = await file.read()
        
        # 3. Offload the heavy work
        background_tasks.add_task(
            process_document_task, 
            doc_id=doc.id, 
            file_content=file_content, 
            db_session=db 
        )
        
        return {
            "status": "accepted", 
            "document_id": str(doc.id), 
            "message": "Ingestion started in background"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    """
    Hybrid Search Endpoint:
    Performs Vector Search + Keyword Search + RRF Fusion.
    Restricted by tenant_id (Row-Level Security).
    """
    try:
        results = hybrid_search(
            db=db, 
            query=request.query, 
            tenant_id=request.tenant_id, 
            top_k=request.top_k
        )
        
        # Format the output to match our Pydantic schema
        formatted_results = [
            SearchResult(
                id=str(r["id"]),  # Ensure UUIDs are strings
                content=r["content"],
                score=r["score"],
                metadata=r.get("metadata", {})
            )
            for r in results
        ]
        
        return {"results": formatted_results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))