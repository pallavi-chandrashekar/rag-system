import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)  # The Security Boundary
    filename = Column(String, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, PROCESSED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)

class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    tenant_id = Column(String, nullable=False, index=True)  # Redundant but critical for RLS speed
    
    content = Column(Text, nullable=False)
    
    # The Hybrid Search Secret Sauce:
    # 1. Dense Vector (e.g., 1536 dims for OpenAI)
    embedding = Column(Vector(1536))
    
    # 2. Metadata for Filtering
    metadata_ = Column("metadata", JSONB)

    # Index for speed
    __table_args__ = (
        Index('ix_chunks_embedding', 'embedding', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}),
    )