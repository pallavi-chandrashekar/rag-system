import logging
import os
import shutil

from fastapi import FastAPI, Header, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

# Import database utilities
from backend.database import engine, get_db, Base
from backend.models import Document
from backend.api import routes  # Ensure this file exists!

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Enterprise RAG Platform")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include existing routes (Search/Ingest)
app.include_router(routes.router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# --- DOCUMENT MANAGEMENT ENDPOINTS ---

@app.get("/api/v1/documents")
async def list_documents(tenant_id: str = Header(...), db: Session = Depends(get_db)):
    """Fetch all documents for a specific tenant."""
    try:
        results = db.execute(
            text("SELECT id, filename, created_at FROM documents WHERE tenant_id = :tenant_id ORDER BY created_at DESC"),
            {"tenant_id": tenant_id}
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
        logger.error(f"List docs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str, tenant_id: str = Header(...), db: Session = Depends(get_db)):
    """Delete a document and all its chunks."""
    try:
        result = db.execute(
            text("DELETE FROM documents WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": doc_id, "tenant_id": tenant_id}
        )
        db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return {"status": "success", "message": "Document deleted"}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))