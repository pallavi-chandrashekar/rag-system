import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import UploadFile
from backend.services.embeddings import get_embeddings

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

async def process_document(file: UploadFile, tenant_id: str, db: Session):
    # 1. Read
    content = await file.read()
    text_content = content.decode("utf-8")
    
    # 2. Chunk
    text_chunks = chunk_text(text_content)
    
    # 3. Embed
    embeddings = get_embeddings(text_chunks)
    
    # 4. Save
    for i, chunk in enumerate(text_chunks):
        embedding_vector = str(embeddings[i]) 
        
        query = text("""
            INSERT INTO chunks (id, tenant_id, content, embedding, metadata)
            VALUES (:id, :tenant_id, :content, :embedding, :metadata)
        """)
        
        db.execute(query, {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "content": chunk, 
            "embedding": embedding_vector,
            "metadata": "{}" 
        })
    
    db.commit()
    return "success"

def delete_tenant_data(tenant_id: str, db: Session):
    """Deletes all chunks associated with a specific tenant_id."""
    try:
        query = text("DELETE FROM chunks WHERE tenant_id = :tenant_id")
        db.execute(query, {"tenant_id": tenant_id})
        db.commit()
    except Exception as e:
        db.rollback()
        raise e