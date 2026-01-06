import uuid
from sqlalchemy.orm import Session
from fastapi import UploadFile
from backend.models import Document, Chunk
from backend.services.embeddings import get_embeddings

# Simple text splitter
def split_text(text: str, chunk_size: int = 500, overlap: int = 50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

async def process_document(file: UploadFile, tenant_id: str, db: Session):
    # 1. Read Content
    content = await file.read()
    text_content = content.decode("utf-8", errors="ignore")
    
    # 2. Create Document Record
    doc_id = uuid.uuid4()
    doc_record = Document(
        id=doc_id,
        filename=file.filename,
        tenant_id=tenant_id
    )
    db.add(doc_record)
    db.flush() # Flush to get the ID ready for foreign keys

    # 3. Split Text
    text_chunks = split_text(text_content)
    
    # 4. Generate Embeddings (Batch processing is faster)
    # The get_embeddings function now guarantees a List[List[float]]
    vectors = get_embeddings(text_chunks)

    # 5. Save Chunks
    db_chunks = []
    for i, text in enumerate(text_chunks):
        db_chunks.append(Chunk(
            id=uuid.uuid4(),
            document_id=doc_id,
            tenant_id=tenant_id,
            content=text,
            embedding=vectors[i], # Passing List[float], NOT String
            metadata_={}          # Passing Dict, NOT String
        ))

    db.add_all(db_chunks)
    db.commit()
    
    return str(doc_id)

def delete_tenant_data(tenant_id: str, db: Session):
    """Utility to wipe data for a tenant (used by Reset endpoint)"""
    db.query(Document).filter(Document.tenant_id == tenant_id).delete()
    db.commit()