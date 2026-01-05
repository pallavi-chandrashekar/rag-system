import io
import logging
from sqlalchemy.orm import Session
from backend.models import Document, Chunk
from backend.services.embeddings import get_embeddings
from pypdf import PdfReader
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def process_document_task(doc_id: str, file_content: bytes, db_session: Session):
    """
    Background task: Extracts text -> Chunks -> Embeds -> Saves to Postgres.
    """
    try:
        doc = db_session.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error(f"Document {doc_id} not found")
            return

        # 1. Update Status
        doc.status = "PROCESSING"
        db_session.commit()

        # 2. Extract Text (Simplified for PDF/HTML/TXT)
        text = ""
        if doc.filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(file_content))
            text = "\n".join([page.extract_text() for page in reader.pages])
        elif doc.filename.endswith(".html"):
            soup = BeautifulSoup(file_content, "html.parser")
            text = soup.get_text(separator=" ")
        else:
            text = file_content.decode("utf-8", errors="ignore")

        # 3. Smart Chunking (Level 2: Sliding Window)
        # In a real app, use 'unstructured' or 'langchain' for hierarchy-aware splitting
        chunks_text = _create_chunks(text, chunk_size=500, overlap=50)

        # 4. Batch Embedding (Cost efficiency)
        embeddings = get_embeddings(chunks_text)

        # 5. Save Chunks with Tenant Isolation (RLS enforcement)
        new_chunks = []
        for i, (chunk_text, vector) in enumerate(zip(chunks_text, embeddings)):
            new_chunks.append(
                Chunk(
                    document_id=doc.id,
                    tenant_id=doc.tenant_id,  # CRITICAL: Propagate tenant_id to chunks
                    content=chunk_text,
                    embedding=vector,
                    metadata_={"chunk_index": i, "source": doc.filename}
                )
            )
        
        db_session.add_all(new_chunks)
        doc.status = "COMPLETED"
        db_session.commit()
        logger.info(f"Successfully processed document {doc_id}")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        doc.status = "FAILED"
        db_session.commit()

def _create_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    tokens = text.split()
    chunks = []
    for i in range(0, len(tokens), chunk_size - overlap):
        chunk = " ".join(tokens[i : i + chunk_size])
        chunks.append(chunk)
    return chunks