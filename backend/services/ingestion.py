import uuid
import io
from sqlalchemy.orm import Session
from fastapi import UploadFile
from backend.models import Document, Chunk
from backend.services.embeddings import get_embeddings
from pypdf import PdfReader  # Requires 'pypdf' in requirements.txt

def smart_split_text(text: str, chunk_size: int = 500, overlap: int = 50):
    """
    Splits text by respecting sentence boundaries (periods, newlines) 
    rather than cutting words in half.
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        
        # If we are not at the end of text, try to find the last period or newline
        if end < text_len:
            # Look for the last period/newline within the last 20% of the chunk
            lookback = text[end-100:end]
            last_period = lookback.rfind('.')
            last_newline = lookback.rfind('\n')
            
            break_point = max(last_period, last_newline)
            
            if break_point != -1:
                # Adjust end to the found sentence break
                end = (end - 100) + break_point + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move forward, respecting overlap
        start = end - overlap
        
    return chunks

async def process_document(file: UploadFile, tenant_id: str, db: Session):
    # 1. Read Content based on File Type
    content = await file.read()
    filename = file.filename.lower()
    text_content = ""

    try:
        if filename.endswith(".pdf"):
            # PDF Parsing Logic
            pdf_stream = io.BytesIO(content)
            reader = PdfReader(pdf_stream)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
        else:
            # Fallback for TXT/MD
            text_content = content.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Parsing Error: {e}")
        # Try a safe fallback decode if PDF fails or if it's a text file
        text_content = content.decode("utf-8", errors="ignore")

    if not text_content.strip():
        # Avoid crashing, just return empty doc_id or raise explicit error
        raise Exception("File is empty or could not be parsed.")

    # 2. Create Document Record (Security: Linked to Tenant)
    doc_id = uuid.uuid4()
    doc_record = Document(
        id=doc_id,
        filename=file.filename,
        tenant_id=tenant_id 
    )
    db.add(doc_record)
    db.flush() 

    # 3. Smart Chunking
    text_chunks = smart_split_text(text_content)
    
    # 4. Generate Embeddings (Batch Process)
    vectors = get_embeddings(text_chunks)

    # 5. Save Chunks (Security: Linked to Tenant)
    db_chunks = []
    for i, text_segment in enumerate(text_chunks):
        db_chunks.append(Chunk(
            id=uuid.uuid4(),
            document_id=doc_id,
            tenant_id=tenant_id,  # STRICT TENANT ISOLATION
            content=text_segment,
            embedding=vectors[i], 
            metadata_={"source": file.filename, "chunk_index": i}
        ))

    db.add_all(db_chunks)
    db.commit()
    
    return str(doc_id)

def delete_tenant_data(tenant_id: str, db: Session):
    """
    Security: Only deletes data belonging to the specific tenant_id.
    """
    db.query(Document).filter(Document.tenant_id == tenant_id).delete()
    db.commit()